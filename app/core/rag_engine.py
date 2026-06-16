import logging
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock

import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from openai import OpenAI

from app.core.config import settings
from app.ingestion.loader import load_document
from app.ingestion.chunker import chunk_pages
from app.models.schemas import SourceChunk, QueryResponse, DocumentInfo

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "qms.db"
MEDICAL_DICT_PATH = BASE_DIR / "data" / "medical_dict.txt"

SYSTEM_PROMPT = """你是一位专业的医疗器械行业质量管理体系（QMS）专家，熟悉中国及国际医疗器械法规体系。

你的职责：
- 根据检索到的法规文件、标准和指导原则准确回答问题
- 回答时明确引用文件名称和具体条款编号
- 区分强制要求（"应"/"shall"）和建议性要求（"宜"/"should"）
- 若检索内容不足以完整回答，明确说明并建议查阅原始文件

回答格式（使用 Markdown）：
1. **直接回答**核心问题（1-3句）
2. **法规依据**：引用具体条款（文件名 + 条款号）
3. **实操建议**（如有）：分点列出

注意：回答基于已上传的文件内容，如涉及最新法规变化，请以官方发布为准。"""


def _tokenize(text: str) -> list[str]:
    return [t for t in jieba.cut(text) if t.strip()]


# 匹配「第十四条 / 第14条 / 第二十一条」等法条编号，用于精确召回法规原文。
_ARTICLE_RE = re.compile(r"第[一二三四五六七八九十百零〇0-9]+条")


def _article_refs(text: str) -> set[str]:
    return set(_ARTICLE_RE.findall(text))


def _is_toc_noise(text: str) -> bool:
    # 抓取时混入的"相关指导原则列表"目录页：密集罗列标题、几乎无句子。
    # 这类 chunk 因高频出现"指导原则/审查"在三路检索里虚高，挤掉条例原文，属纯噪声。
    # 阈值经全库验证：titles>=4 且句号<=2 命中 31/1737，零误杀实质内容（含第十四条的均保留）。
    titles = text.count("指导原则") + text.count("审查原则")
    return titles >= 4 and text.count("。") <= 2


# ── 向量 embedding（中文语义召回路）─────────────────────────────────────────
# 走远程 Xinference（OpenAI 兼容 /v1/embeddings）。不在本地加载模型，
# 故无需 GPU / 模型下载；编码是网络调用，按 batch 分批发送。
_embed_client = None
_EMBED_BATCH = 64


def _get_embed_client():
    global _embed_client
    if _embed_client is None:
        import httpx
        logger.info("Embedding via remote: %s (model=%s)",
                    settings.embedding_base_url, settings.embedding_model)
        _embed_client = OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
            max_retries=2,
        )
    return _embed_client


def _embed(texts: list[str]) -> np.ndarray:
    """编码为 L2 归一化的 float32 矩阵 [N, dim]，归一化后内积即余弦相似度。
    bge 服务不保证返回归一化向量，这里统一做 L2 归一化。"""
    client = _get_embed_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        resp = client.embeddings.create(
            model=settings.embedding_model,
            input=texts[i:i + _EMBED_BATCH],
        )
        out.extend(d.embedding for d in resp.data)
    arr = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


class BM25Index:
    def __init__(self, collection: str, db: sqlite3.Connection):
        self.collection = collection
        self.db = db
        self._lock = Lock()
        self._chunks: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self._load()

    def _load(self):
        # 只加载 is_active=1 的 chunk。噪声（目录页/论坛页脚等）已在 DB 标记 is_active=0，
        # 不删行（可逆）、不入索引。清洗规则见 scripts/clean_noise.py。
        rows = self.db.execute(
            "SELECT id, doc_id, doc_name, file_type, page, chunk_index, text, created_at, embedding "
            "FROM chunks WHERE collection=? AND is_active=1",
            (self.collection,),
        ).fetchall()
        self._chunks = [
            {"id": r[0], "doc_id": r[1], "doc_name": r[2], "file_type": r[3],
             "page": r[4], "chunk_index": r[5], "text": r[6], "created_at": r[7]}
            for r in rows
        ]
        # 向量矩阵：行号与 self._chunks 对齐；DB 里为 NULL 的（存量/新增）当场编码并回写。
        self._emb: np.ndarray | None = None
        if settings.enable_vector and self._chunks:
            blobs = [r[8] for r in rows]
            self._build_emb(blobs)
        self._rebuild()

    def _build_emb(self, blobs: list):
        missing_idx = [i for i, b in enumerate(blobs) if b is None]
        if missing_idx:
            logger.info("Collection '%s': encoding %d chunks (no cached vector)...",
                        self.collection, len(missing_idx))
            vecs = _embed([self._chunks[i]["text"] for i in missing_idx])
            updates = []
            for k, i in enumerate(missing_idx):
                blobs[i] = vecs[k].tobytes()
                updates.append((blobs[i], self._chunks[i]["id"]))
            self.db.executemany("UPDATE chunks SET embedding=? WHERE id=?", updates)
            self.db.commit()
            logger.info("Collection '%s': encoded & persisted %d vectors", self.collection, len(missing_idx))
        self._emb = np.stack([np.frombuffer(b, dtype=np.float32) for b in blobs])

    def _rebuild(self):
        self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in self._chunks]) if self._chunks else None

    def add(self, new_chunks: list[dict]):
        with self._lock:
            # 上传时也过滤目录页噪声：不入索引、不浪费编码调用，并把 DB 行标记 is_active=0
            # （与 _load 的 WHERE is_active=1 一致，重启后仍被排除）。
            dropped = [c for c in new_chunks if _is_toc_noise(c["text"])]
            if dropped:
                new_chunks = [c for c in new_chunks if not _is_toc_noise(c["text"])]
                self.db.executemany(
                    "UPDATE chunks SET is_active=0 WHERE id=?",
                    [(f"{c['doc_id']}::chunk::{c['chunk_index']}",) for c in dropped],
                )
                self.db.commit()
                logger.info("Collection '%s': skipped %d 目录页 noise chunk(s) on add", self.collection, len(dropped))
            # 新 chunk 现场编码并写 DB；id 由 doc_id+chunk_index 重建（与 ingest 主键一致）。
            if settings.enable_vector and new_chunks:
                vecs = _embed([c["text"] for c in new_chunks])
                updates = []
                for c, v in zip(new_chunks, vecs):
                    cid = f"{c['doc_id']}::chunk::{c['chunk_index']}"
                    c["id"] = cid
                    updates.append((v.tobytes(), cid))
                self.db.executemany("UPDATE chunks SET embedding=? WHERE id=?", updates)
                self.db.commit()
                new_emb = np.stack([v for v in vecs])
                self._emb = new_emb if self._emb is None else np.vstack([self._emb, new_emb])
            self._chunks.extend(new_chunks)
            self._rebuild()

    def remove_doc(self, doc_id: str):
        with self._lock:
            keep = [i for i, c in enumerate(self._chunks) if c["doc_id"] != doc_id]
            self._chunks = [self._chunks[i] for i in keep]
            if self._emb is not None:
                self._emb = self._emb[keep] if keep else None
            self._rebuild()

    def search(self, query: str, top_k: int) -> list[tuple[dict, float]]:
        if not self._bm25 or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        top = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:min(top_k, len(self._chunks))]
        return [(self._chunks[i], float(s)) for i, s in top if s > 0]

    def keyword_search(self, query: str, top_k: int) -> list[tuple[dict, float]]:
        """精确匹配一路：词项命中 text/doc_name（doc_name 权重更高），
        并对含查询所提法条编号的 chunk 强加权。补 BM25 在高频词稀释下漏召回法规原文的短板。"""
        if not self._chunks:
            return []
        terms = {t for t in _tokenize(query) if len(t) > 1}
        q_articles = _article_refs(query)
        if not terms and not q_articles:
            return []
        scored = []
        for i, c in enumerate(self._chunks):
            text = c["text"]
            name = c["doc_name"]
            s = sum(text.count(t) for t in terms) + 3.0 * sum(t in name for t in terms)
            if q_articles:
                s += 12.0 * len(q_articles & _article_refs(text))
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self._chunks[i], float(s)) for i, s in scored[:min(top_k, len(self._chunks))]]

    def vector_search(self, query: str, top_k: int) -> list[tuple[dict, float]]:
        """语义召回路：query 编码后与归一化向量矩阵做内积（=余弦），取 top_k。
        与 BM25/关键词的词频信号正交，能召回措辞不同但语义相关的法规原文。"""
        if self._emb is None or not self._chunks:
            return []
        qv = _embed([query])[0]
        sims = self._emb @ qv
        n = min(top_k, len(self._chunks))
        top = np.argpartition(-sims, n - 1)[:n]
        top = top[np.argsort(-sims[top])]
        return [(self._chunks[i], float(sims[i])) for i in top]

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def doc_ids(self) -> set[str]:
        return {c["doc_id"] for c in self._chunks}


class RAGEngine:
    def __init__(self):
        if MEDICAL_DICT_PATH.exists():
            jieba.load_userdict(str(MEDICAL_DICT_PATH))
            logger.info("Loaded medical jieba dictionary")

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init_db()
        self._indices: dict[str, BM25Index] = {}
        self._db_lock = Lock()

        for (col,) in self.db.execute("SELECT DISTINCT collection FROM chunks").fetchall():
            self._indices[col] = BM25Index(col, self.db)
            logger.info("  Collection '%s': %d chunks", col, self._indices[col].count)

        api_key = settings.api_key or settings.anthropic_api_key
        # 用细粒度 httpx.Timeout：流式下若 Poe 端两次数据块之间卡住超过 read 超时即报错，
        # 让阻塞的 executor 线程能退出、归还线程池（否则大请求卡死会耗尽线程池拖垮整个服务）。
        import httpx
        self.llm = OpenAI(
            api_key=api_key,
            base_url=settings.api_base_url,
            timeout=httpx.Timeout(connect=15.0, read=90.0, write=30.0, pool=15.0),
            max_retries=1,
        )
        logger.info("RAGEngine ready (model=%s)", settings.claude_model)

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                collection TEXT NOT NULL,
                page INTEGER,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_doc ON chunks(doc_id);
            CREATE INDEX IF NOT EXISTS idx_col ON chunks(collection);
        """)
        # 向量列（幂等）：存 float32 向量的 bytes，NULL 表示尚未编码。
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(chunks)").fetchall()}
        if "embedding" not in cols:
            self.db.execute("ALTER TABLE chunks ADD COLUMN embedding BLOB")
        # is_active（幂等）：0=噪声不入索引（目录页/论坛页脚），默认 1。清洗脚本 scripts/clean_noise.py。
        if "is_active" not in cols:
            self.db.execute("ALTER TABLE chunks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        self.db.commit()

    def _get_index(self, collection: str) -> BM25Index:
        if collection not in self._indices:
            self._indices[collection] = BM25Index(collection, self.db)
        return self._indices[collection]

    # ── Ingestion ────────────────────────────────────────────────────────────

    def ingest_document(self, file_path: Path, doc_name: str, doc_id: str, collection_name: str | None = None) -> int:
        collection_name = collection_name or settings.default_collection
        pages = load_document(file_path)
        raw_chunks = chunk_pages(pages)
        now = datetime.now(timezone.utc).isoformat()
        file_type = file_path.suffix.lstrip(".")

        rows, index_chunks = [], []
        for c in raw_chunks:
            cid = f"{doc_id}::chunk::{c['chunk_index']}"
            rows.append((cid, doc_id, doc_name, file_type, collection_name, c["page"], c["chunk_index"], c["text"], now))
            index_chunks.append({"doc_id": doc_id, "doc_name": doc_name, "file_type": file_type,
                                  "page": c["page"], "chunk_index": c["chunk_index"], "text": c["text"], "created_at": now})

        with self._db_lock:
            self.db.executemany(
                "INSERT OR REPLACE INTO chunks (id,doc_id,doc_name,file_type,collection,page,chunk_index,text,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
            self.db.commit()
        self._get_index(collection_name).add(index_chunks)
        logger.info("Ingested %d chunks from '%s' into '%s'", len(rows), doc_name, collection_name)
        return len(rows)

    def delete_document(self, doc_id: str, collection_name: str | None = None) -> int:
        collection_name = collection_name or settings.default_collection
        with self._db_lock:
            cur = self.db.execute("DELETE FROM chunks WHERE doc_id=? AND collection=?", (doc_id, collection_name))
            self.db.commit()
        if collection_name in self._indices:
            self._indices[collection_name].remove_doc(doc_id)
        return cur.rowcount

    def list_documents(self, collection_name: str | None = None) -> list[DocumentInfo]:
        # 不指定 collection 时返回全部知识库文档（文档分布在 regulations/standards/
        # guidance-* 等多个 collection，没有名为 default_collection 的集合）。
        if collection_name:
            rows = self.db.execute(
                "SELECT doc_id, doc_name, file_type, collection, created_at, COUNT(*) FROM chunks WHERE collection=? GROUP BY doc_id",
                (collection_name,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT doc_id, doc_name, file_type, collection, created_at, COUNT(*) FROM chunks GROUP BY doc_id ORDER BY collection",
            ).fetchall()
        return [DocumentInfo(doc_id=r[0], name=r[1], file_type=r[2], collection=r[3], created_at=r[4], chunk_count=r[5]) for r in rows]

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def _collections_for(self, collection_name: str | None) -> list[str]:
        if collection_name:
            return [collection_name]
        return [r[0] for r in self.db.execute(
            "SELECT DISTINCT collection FROM chunks").fetchall()]

    def retrieve(self, question: str, top_k: int, collection_name: str | None = None) -> list[SourceChunk]:
        # 混合检索三路：BM25（词频）+ 向量（语义，正交信号）+ 关键词精确（法条号兜底），RRF 融合。
        # 跨库各取候选后，把每路分别拍平成【全局】列表再排名做 RRF——而非每库内部 rank。
        # 全局 rank 下，多路都靠前的 chunk（强相关法规原文）才会胜出，
        # 不会因「每库都贡献一个本地第一名」而被挤到同分并列、把真正相关的稀释掉。
        # 候选池要足够深：向量命中的强相关 chunk 可能在某库 BM25 路里排名靠后，
        # 池太小会在融合前就被截断。每路每库取较深候选，再做全局 RRF。
        pool = max(top_k * 8, 60)
        bm25_all: list[tuple[dict, float]] = []
        vec_all: list[tuple[dict, float]] = []
        kw_all: list[tuple[dict, float]] = []
        for col in self._collections_for(collection_name):
            idx = self._get_index(col)
            bm25_all.extend(idx.search(question, pool))
            kw_all.extend(idx.keyword_search(question, pool))
            if settings.enable_vector:
                vec_all.extend(idx.vector_search(question, pool))

        scores: dict[str, float] = {}
        chunks: dict[str, dict] = {}
        # 加权 RRF + 自适应向量权重：查询含法条号时让关键词精确路主导（向量降权），
        # 否则措辞失配只能靠向量语义顶（向量高权）。详见 config 注释。
        w_vector = (settings.rrf_w_vector_article if _article_refs(question)
                    else settings.rrf_w_vector)
        for hits, weight in ((bm25_all, settings.rrf_w_bm25),
                             (vec_all, w_vector),
                             (kw_all, settings.rrf_w_keyword)):
            hits.sort(key=lambda x: x[1], reverse=True)
            for rank, (c, _s) in enumerate(hits):
                key = f"{c['doc_id']}#{c['chunk_index']}"
                scores[key] = scores.get(key, 0.0) + weight / (settings.rrf_k + rank)
                chunks[key] = c

        fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            SourceChunk(doc_name=(c := chunks[k])["doc_name"], page=c.get("page"),
                        chunk_index=c["chunk_index"], content=c["text"], score=round(s, 4))
            for k, s in fused
        ]

    def build_context(self, sources: list[SourceChunk]) -> str:
        if not sources:
            return "（未找到相关文件内容，请先上传相关法规文件）"
        return "\n\n---\n\n".join(
            f"【来源：{s.doc_name}  第{s.page or '?'}页】\n{s.content}"
            for s in sources
        )

    # ── LLM Generation ───────────────────────────────────────────────────────

    def _extra_body(self) -> dict | None:
        # 注意：不要给 Poe 的 OpenAI 兼容端点传 thinking 参数——
        # 实测带 thinking 会让流式请求 ~30s 后报 "Connection error"，
        # 而 Poe 的 opus-4 本身就会输出 reasoning_content（已被忽略）。
        return None

    def _messages(self, question: str, context: str, history: list[dict] | None) -> list[dict]:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-6:]:  # last 3 Q&A turns
            msgs.append({"role": turn["role"], "content": turn["content"]})
        msgs.append({"role": "user", "content": f"参考以下文件内容：\n\n{context}\n\n当前问题：{question}"})
        return msgs

    def generate_stream(self, question: str, context: str, history: list[dict] | None = None):
        """Yield plain text deltas (filters out thinking tokens)."""
        stream = self.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=self._messages(question, context, history),
            stream=True,
            extra_body=self._extra_body(),
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                yield delta.content

    def query(self, question: str, top_k: int | None = None, collection_name: str | None = None,
              history: list[dict] | None = None) -> QueryResponse:
        sources = self.retrieve(question, top_k or settings.top_k, collection_name)
        context = self.build_context(sources)
        response = self.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=self._messages(question, context, history),
            extra_body=self._extra_body(),
        )
        return QueryResponse(answer=response.choices[0].message.content, sources=sources, question=question)

    # ── Health ────────────────────────────────────────────────────────────────

    def health(self) -> dict:
        total_chunks = self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        total_docs = self.db.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks").fetchone()[0]
        store = "bm25+vector+sqlite" if settings.enable_vector else "bm25+sqlite"
        return {"status": "ok", "vector_store": store, "total_chunks": total_chunks, "total_documents": total_docs}


_engine: RAGEngine | None = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine
