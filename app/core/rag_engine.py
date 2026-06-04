import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock

import jieba
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


class BM25Index:
    def __init__(self, collection: str, db: sqlite3.Connection):
        self.collection = collection
        self.db = db
        self._lock = Lock()
        self._chunks: list[dict] = []
        self._bm25: BM25Okapi | None = None
        self._load()

    def _load(self):
        rows = self.db.execute(
            "SELECT doc_id, doc_name, file_type, page, chunk_index, text, created_at "
            "FROM chunks WHERE collection=?",
            (self.collection,),
        ).fetchall()
        self._chunks = [
            {"doc_id": r[0], "doc_name": r[1], "file_type": r[2],
             "page": r[3], "chunk_index": r[4], "text": r[5], "created_at": r[6]}
            for r in rows
        ]
        self._rebuild()

    def _rebuild(self):
        self._bm25 = BM25Okapi([_tokenize(c["text"]) for c in self._chunks]) if self._chunks else None

    def add(self, new_chunks: list[dict]):
        with self._lock:
            self._chunks.extend(new_chunks)
            self._rebuild()

    def remove_doc(self, doc_id: str):
        with self._lock:
            self._chunks = [c for c in self._chunks if c["doc_id"] != doc_id]
            self._rebuild()

    def search(self, query: str, top_k: int) -> list[tuple[dict, float]]:
        if not self._bm25 or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        top = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:min(top_k, len(self._chunks))]
        return [(self._chunks[i], float(s)) for i, s in top if s > 0]

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
        # timeout 防止 Poe 端慢/挂起时 executor 线程被无限阻塞；max_retries 避免静默重试拖长首字节
        self.llm = OpenAI(
            api_key=api_key,
            base_url=settings.api_base_url,
            timeout=120.0,
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
        collection_name = collection_name or settings.default_collection
        rows = self.db.execute(
            "SELECT doc_id, doc_name, file_type, collection, created_at, COUNT(*) FROM chunks WHERE collection=? GROUP BY doc_id",
            (collection_name,),
        ).fetchall()
        return [DocumentInfo(doc_id=r[0], name=r[1], file_type=r[2], collection=r[3], created_at=r[4], chunk_count=r[5]) for r in rows]

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(self, question: str, top_k: int, collection_name: str | None = None) -> list[SourceChunk]:
        collection_name = collection_name or settings.default_collection
        index = self._get_index(collection_name)
        hits = index.search(question, top_k)
        return [
            SourceChunk(doc_name=c["doc_name"], page=c.get("page"),
                        chunk_index=c["chunk_index"], content=c["text"], score=round(s, 4))
            for c, s in hits
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
        return {"status": "ok", "vector_store": "bm25+sqlite", "total_chunks": total_chunks, "total_documents": total_docs}


_engine: RAGEngine | None = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine
