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
    """已生成文档列表（不含正文）。每份按其 checklist 子类推断归入的档案
    （DHF/DMR/DHR/技术文档/NMPA），覆盖按 seq 生成、无预置 doc_id 的文档。"""
    from app.core.qms_framework import DOSSIERS
    from app.core.registration_checklist import CHECKLIST, infer_dossiers

    dossiers_meta = [{"key": ds["id"], "name": ds["name"]} for ds in DOSSIERS]
    name2meta = {ds["id"]: {"key": ds["id"], "name": ds["name"]} for ds in DOSSIERS}

    # 把存档文档匹配回 checklist：优先 doc_id，其次 output 首段名
    by_docid = {i["doc_id"]: i for i in CHECKLIST if i.get("doc_id")}
    by_name = {}
    for i in CHECKLIST:
        nm = i["output"].split("；")[0].split("&")[0].strip()
        by_name.setdefault(nm, i)

    docs = doc_store.list_docs()
    for d in docs:
        item = by_docid.get(d.get("doc_id")) or by_name.get(d.get("doc_name"))
        dossier_ids = infer_dossiers(item) if item else []
        d["dossiers"] = [name2meta[k] for k in dossier_ids if k in name2meta]
    return {"docs": docs, "dossiers": dossiers_meta}


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
