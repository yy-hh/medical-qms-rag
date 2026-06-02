from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "vector_store")
    default_collection: str = "medical_qms"

    # RAG
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5

    # Server
    host: str = "0.0.0.0"
    port: int = 8003

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
