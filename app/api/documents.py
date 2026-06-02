import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.models.schemas import IngestResponse, DeleteResponse, DocumentInfo

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
ALLOWED_TYPES = {".pdf", ".docx", ".txt", ".md"}


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form(default=None),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}，支持 PDF/DOCX/TXT/MD")

    doc_id = str(uuid.uuid4())[:8]
    safe_name = file.filename.replace(" ", "_")
    save_path = UPLOAD_DIR / f"{doc_id}_{safe_name}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    collection_name = collection or settings.default_collection
    engine = get_engine()
    try:
        chunk_count = engine.ingest_document(save_path, file.filename, doc_id, collection_name)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")

    return IngestResponse(
        doc_id=doc_id,
        name=file.filename,
        chunk_count=chunk_count,
        collection=collection_name,
        message=f"成功导入 {chunk_count} 个文本块",
    )


@router.get("", response_model=list[DocumentInfo])
async def list_documents(collection: str | None = None):
    engine = get_engine()
    return engine.list_documents(collection)


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str, collection: str | None = None):
    engine = get_engine()
    deleted = engine.delete_document(doc_id, collection)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")

    # Remove physical file if present
    for f in UPLOAD_DIR.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)

    return DeleteResponse(doc_id=doc_id, message=f"已删除 {deleted} 个文本块")
