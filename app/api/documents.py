import uuid
import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import JSONResponse, FileResponse, Response

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.models.schemas import IngestResponse, DeleteResponse, DocumentInfo
from app.api.deps import get_shared_account

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
ALLOWED_TYPES = {".pdf", ".docx", ".txt", ".md"}


def _find_raw_file(doc_id: str) -> Path | None:
    """按 doc_id 前缀在 data/documents/ 找原始文件（命名为 {doc_id}_{原名}）。"""
    if not doc_id or "/" in doc_id or "\\" in doc_id or ".." in doc_id:
        return None
    matches = sorted(UPLOAD_DIR.glob(f"{doc_id}_*"))
    return matches[0] if matches else None


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form(default=None),
    _account: str = Depends(get_shared_account),
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
async def list_documents(collection: str | None = None,
                         _account: str = Depends(get_shared_account)):
    engine = get_engine()
    return engine.list_documents(collection)


@router.get("/{doc_id}/raw")
async def read_document(doc_id: str, _account: str = Depends(get_shared_account)):
    """在线阅读原始文件。PDF 内联返回（浏览器内置 viewer 渲染）；
    TXT/MD 返回纯文本；DOCX 抽取文本后返回（浏览器无法直接渲染 docx）。"""
    path = _find_raw_file(doc_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="原始文件不存在（可能是早期导入未保留原文件）")

    suffix = path.suffix.lower()
    # 原名 = 去掉 "{doc_id}_" 前缀
    orig_name = path.name[len(doc_id) + 1:] if path.name.startswith(doc_id + "_") else path.name

    if suffix == ".pdf":
        disposition = f"inline; filename=\"doc.pdf\"; filename*=UTF-8''{quote(orig_name)}"
        return FileResponse(
            str(path), media_type="application/pdf",
            headers={"Content-Disposition": disposition},
        )

    if suffix in (".txt", ".md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="gbk", errors="replace")
        return JSONResponse({"type": "text", "name": orig_name, "content": text})

    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(str(path))
            text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DOCX 解析失败：{e}")
        return JSONResponse({"type": "text", "name": orig_name, "content": text})

    raise HTTPException(status_code=415, detail=f"不支持在线阅读的类型：{suffix}")


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str, collection: str | None = None,
                          _account: str = Depends(get_shared_account)):
    engine = get_engine()
    deleted = engine.delete_document(doc_id, collection)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")

    # Remove physical file if present
    for f in UPLOAD_DIR.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)

    return DeleteResponse(doc_id=doc_id, message=f"已删除 {deleted} 个文本块")
