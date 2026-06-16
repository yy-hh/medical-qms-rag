from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # LLM API — supports "anthropic" or "openai_compatible"
    api_mode: str = "openai_compatible"
    api_key: str = ""
    api_base_url: str = "https://api.poe.com/v1"
    claude_model: str = "claude-opus-4-6"

    # Legacy: kept for backward compat
    anthropic_api_key: str = ""

    # Storage (SQLite lives next to this dir)
    chroma_persist_dir: str = str(BASE_DIR / "vector_store")
    default_collection: str = "medical_qms"

    # RAG
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5

    # Hybrid retrieval: BM25 + 向量语义召回，RRF 融合
    # 向量走远程 Xinference（OpenAI 兼容 /v1/embeddings），不在本地加载模型。
    enable_vector: bool = True
    embedding_base_url: str = "http://192.168.201.55:5529/v1"
    embedding_model: str = "bge-large-zh-v1.5"
    embedding_dim: int = 1024
    embedding_api_key: str = "not-needed"
    rrf_k: int = 60

    # Server
    host: str = "0.0.0.0"
    port: int = 8003

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
