import logging
from pathlib import Path
from datetime import datetime, timezone

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
import anthropic

from app.core.config import settings
from app.ingestion.loader import load_document
from app.ingestion.chunker import chunk_pages
from app.models.schemas import SourceChunk, QueryResponse, DocumentInfo

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的医疗器械行业质量管理体系（QMS）专家，熟悉中国及国际医疗器械法规体系。

你的职责：
- 根据检索到的法规文件、标准和指导原则准确回答问题
- 回答时引用具体的条款、章节或文件名称
- 对于法规要求，区分强制要求（"应"/"must"）和建议事项（"宜"/"should"）
- 如果检索内容不足以完整回答，明确说明并建议查阅原始文件

回答格式：
1. 直接回答核心问题
2. 引用相关法规依据（文件名+条款）
3. 如有实际操作建议，单独列出

注意：你的回答基于所提供的文件内容，如有最新法规更新，请以官方发布为准。"""


class RAGEngine:
    def __init__(self):
        logger.info("Initializing embedding model: %s", settings.embedding_model)
        self.embedder = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
        self.chroma = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.claude = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("RAGEngine ready")

    def _get_collection(self, name: str):
        return self.chroma.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_document(
        self,
        file_path: Path,
        doc_name: str,
        doc_id: str,
        collection_name: str | None = None,
    ) -> int:
        collection_name = collection_name or settings.default_collection
        collection = self._get_collection(collection_name)

        pages = load_document(file_path)
        chunks = chunk_pages(pages)

        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.encode(texts, normalize_embeddings=True).tolist()

        ids = [f"{doc_id}::chunk::{c['chunk_index']}" for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "file_type": file_path.suffix.lstrip("."),
                "page": c["page"],
                "chunk_index": c["chunk_index"],
                "collection": collection_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for c in chunks
        ]

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

        logger.info("Ingested %d chunks from %s into %s", len(chunks), doc_name, collection_name)
        return len(chunks)

    def delete_document(self, doc_id: str, collection_name: str | None = None) -> int:
        collection_name = collection_name or settings.default_collection
        collection = self._get_collection(collection_name)
        results = collection.get(where={"doc_id": doc_id})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    def list_documents(self, collection_name: str | None = None) -> list[DocumentInfo]:
        collection_name = collection_name or settings.default_collection
        try:
            collection = self._get_collection(collection_name)
        except Exception:
            return []

        results = collection.get(include=["metadatas"])
        if not results["ids"]:
            return []

        docs: dict[str, DocumentInfo] = {}
        for meta in results["metadatas"]:
            doc_id = meta["doc_id"]
            if doc_id not in docs:
                docs[doc_id] = DocumentInfo(
                    doc_id=doc_id,
                    name=meta["doc_name"],
                    file_type=meta.get("file_type", "unknown"),
                    chunk_count=1,
                    collection=meta.get("collection", collection_name),
                    created_at=meta.get("created_at", ""),
                )
            else:
                docs[doc_id].chunk_count += 1
        return list(docs.values())

    def query(self, question: str, top_k: int | None = None, collection_name: str | None = None) -> QueryResponse:
        top_k = top_k or settings.top_k
        collection_name = collection_name or settings.default_collection

        q_embedding = self.embedder.encode([question], normalize_embeddings=True).tolist()

        collection = self._get_collection(collection_name)
        results = collection.query(
            query_embeddings=q_embedding,
            n_results=min(top_k, collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        sources: list[SourceChunk] = []
        context_parts: list[str] = []

        if results["ids"] and results["ids"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                score = 1 - dist  # cosine distance → similarity
                sources.append(SourceChunk(
                    doc_name=meta["doc_name"],
                    page=meta.get("page"),
                    chunk_index=meta["chunk_index"],
                    content=doc,
                    score=round(score, 4),
                ))
                context_parts.append(
                    f"【来源：{meta['doc_name']} 第{meta.get('page', '?')}页】\n{doc}"
                )

        context = "\n\n---\n\n".join(context_parts) if context_parts else "（未找到相关文件内容）"
        user_message = f"参考以下文件内容：\n\n{context}\n\n问题：{question}"

        response = self.claude.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        answer = response.content[0].text

        return QueryResponse(answer=answer, sources=sources, question=question)

    def health(self) -> dict:
        total_chunks = 0
        total_docs = 0
        try:
            collections = self.chroma.list_collections()
            for col in collections:
                c = self.chroma.get_collection(col.name)
                count = c.count()
                total_chunks += count
                metas = c.get(include=["metadatas"])["metadatas"]
                doc_ids = {m["doc_id"] for m in metas}
                total_docs += len(doc_ids)
        except Exception:
            pass
        return {
            "status": "ok",
            "vector_store": "chromadb",
            "total_chunks": total_chunks,
            "total_documents": total_docs,
        }


# Module-level singleton, lazy-initialized
_engine: RAGEngine | None = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine
