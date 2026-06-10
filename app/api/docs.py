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
async def list_all(product: str | None = None, all: bool = False):
    """已生成文档列表（不含正文）。默认只返回【当前选中产品】的文档（按产品隔离）；
    传 all=true 返回全部、或 product=<名称> 指定产品。每份按 checklist 子类推断档案。"""
    from app.core.qms_framework import DOSSIERS
    from app.core.registration_checklist import CHECKLIST, infer_dossiers, PLANNING_DOSSIER
    from app.api.company import current_product_name

    dossiers_meta = [{"key": ds["id"], "name": ds["name"]} for ds in DOSSIERS]
    dossiers_meta.append(PLANNING_DOSSIER)   # 第6个档案：注册策划资料
    name2meta = {m["key"]: m for m in dossiers_meta}

    # 把存档文档匹配回 checklist：优先 doc_id，其次 output 首段名
    by_docid = {i["doc_id"]: i for i in CHECKLIST if i.get("doc_id")}
    by_name = {}
    for i in CHECKLIST:
        nm = i["output"].split("；")[0].split("&")[0].strip()
        by_name.setdefault(nm, i)

    if all:
        docs = doc_store.list_docs()
    else:
        docs = doc_store.list_docs(product_name=(product if product is not None else current_product_name()))
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
