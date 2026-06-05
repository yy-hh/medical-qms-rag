from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from urllib.parse import quote

from app.core import doc_store
from app.core.docx_export import markdown_to_docx
from app.api.company import load_profile

router = APIRouter(prefix="/api/docs", tags=["docs"])


class SaveDocRequest(BaseModel):
    doc_id: Optional[str] = None
    doc_name: str
    content: str


@router.post("/save")
async def save(req: SaveDocRequest):
    """生成完成后存档（同一文档+同一产品视为重新生成，覆盖更新）。"""
    if not (req.content or "").strip():
        raise HTTPException(status_code=400, detail="内容为空")
    profile = load_profile()
    rid = doc_store.save_doc(
        doc_id=req.doc_id, doc_name=req.doc_name, content=req.content,
        product_name=profile.get("product_name", ""),
        company_name=profile.get("company_name", ""),
    )
    return {"id": rid, "ok": True}


@router.get("")
async def list_all():
    """已生成文档列表（不含正文）。"""
    return {"docs": doc_store.list_docs()}


@router.get("/{rid}")
async def detail(rid: str):
    d = doc_store.get_doc(rid)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return d


@router.get("/{rid}/download")
async def download(rid: str):
    """下载存档文档为 .docx。"""
    d = doc_store.get_doc(rid)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        data = markdown_to_docx(d["content"], title=d["doc_name"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{e}")
    filename = f"{d['doc_name']}.docx"
    disposition = f"attachment; filename=\"document.docx\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
    )


@router.delete("/{rid}")
async def remove(rid: str):
    if not doc_store.delete_doc(rid):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"ok": True}
