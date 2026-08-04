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
    # embedding 后端：local=本地 sentence-transformers（默认，无外部依赖）；
    # remote=远程 OpenAI 兼容服务（旧方案，需 embedding_base_url 在线）。
    embedding_mode: str = "local"
    embedding_hf_name: str = "BAAI/bge-large-zh-v1.5"   # 本地模式 HF 仓库名（1024维）
    embedding_device: str = "auto"                      # auto|cpu|cuda
    hf_endpoint: str = ""                               # 可选 HF 镜像，加速首次下载
    # remote 模式复用（local 模式不使用）
    embedding_base_url: str = "http://192.168.201.55:5529/v1"
    embedding_model: str = "bge-large-zh-v1.5"
    embedding_dim: int = 1024
    embedding_api_key: str = "not-needed"
    rrf_k: int = 60
    # 加权 RRF + 按查询自适应向量权重：
    # - 查询不含法条号（如"第二三类…需要哪些材料"）：措辞与原文不同，向量是唯一可靠信号
    #   （单路常命中 rank1-2），给高权重 rrf_w_vector 顶上来，避免被 BM25/关键词弱信号稀释。
    # - 查询含法条号（如"第十四条"）：关键词精确路有 +12 法条加权应主导，向量降到
    #   rrf_w_vector_article，否则会用语义相似的别的法条把精确命中挤下去。
    rrf_w_vector: float = 4.0
    rrf_w_vector_article: float = 2.0
    rrf_w_bm25: float = 1.0
    rrf_w_keyword: float = 1.0

    # 验证码发送机器人（企业官方机器人，对全员可用，绕开 bot-availability 限制）
    # 留空则回退到 lark-cli 的 bot→user 双重发送。
    notify_app_id: str = ""
    notify_app_secret: str = ""
    lark_domain: str = "https://open.feishu.cn"   # Lark 国际版用 https://open.larksuite.com

    # Server
    host: str = "0.0.0.0"
    port: int = 8003

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
