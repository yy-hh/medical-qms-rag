from pydantic import BaseModel, Field
from typing import Optional


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    collection: Optional[str] = None
    history: Optional[list[Message]] = None


class StreamQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    collection: Optional[str] = None
    history: Optional[list[Message]] = None


class SourceChunk(BaseModel):
    doc_name: str
    page: Optional[int] = None
    chunk_index: int
    content: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    question: str


class DocumentInfo(BaseModel):
    doc_id: str
    name: str
    file_type: str
    chunk_count: int
    collection: str
    created_at: str


class IngestResponse(BaseModel):
    doc_id: str
    name: str
    chunk_count: int
    collection: str
    message: str


class DeleteResponse(BaseModel):
    doc_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    vector_store: str
    total_chunks: int
    total_documents: int
