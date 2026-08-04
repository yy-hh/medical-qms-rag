from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from urllib.parse import quote

from app.core import doc_store
from app.core.docx_export import markdown_to_docx
from app.api.company import load_profile
from app.api.deps import get_current_account

router = APIRouter(prefix="/api/docs", tags=["docs"])


class SaveDocRequest(BaseModel):
    doc_id: Optional[str] = None
    doc_name: str
    content: str


import re as _re

# 外部导入的 QMS 体系文档（doc_id 形如 "QMS-P07 风险管理控制程序"）按编号前缀归档。
# 依据每类文档的实质内容映射到对应 dossier；未列出的程序/制度/记录默认归 QMS 程序文件体系(DMR·DHR)。
_QMS_PREFIX_MAP = [
    (r"QMS-QM", ["DOSSIER-DMR", "DOSSIER-DHR"]),                              # 质量手册
    (r"QMS-P07|QMS-P30", ["DOSSIER-DHF", "DOSSIER-TF", "DOSSIER-NMPA"]),      # 风险管理
    (r"QMS-P09", ["DOSSIER-DHF", "DOSSIER-DMR"]),                             # 设计开发
    (r"QMS-P26|QMS-P27|QMS-P28", ["DOSSIER-DHF", "DOSSIER-DMR"]),             # 软件可追溯/配置/生命周期
    (r"QMS-P29", ["DOSSIER-DHF", "DOSSIER-TF", "DOSSIER-NMPA"]),              # 网络安全
    (r"QMS-R04|QMS-R14", ["DOSSIER-DHF", "DOSSIER-DMR"]),                     # 软件缺陷/问题
    (r"QMS-R12", ["DOSSIER-DHR", "DOSSIER-DMR", "DOSSIER-NMPA"]),             # 变更控制
    (r"QMS-P18|QMS-P19", ["DOSSIER-NMPA"]),                                   # 不良事件/召回
]


def _qms_prefix_dossiers(doc_id: str) -> list[str]:
    if "QMS-" not in doc_id.upper():
        return []
    for pat, ds in _QMS_PREFIX_MAP:
        if _re.search(pat, doc_id, _re.I):
            return ds
    return ["DOSSIER-DMR", "DOSSIER-DHR"]   # 其余程序文件/管理制度/记录表单 → QMS 程序文件体系


@router.post("/save")
async def save(req: SaveDocRequest, account_id: str = Depends(get_current_account)):
    """生成完成后存档（同一账号+文档+产品视为重新生成，覆盖更新）。"""
    if not (req.content or "").strip():
        raise HTTPException(status_code=400, detail="内容为空")
    profile = load_profile(account_id)
    rid = doc_store.save_doc(
        account_id=account_id,
        doc_id=req.doc_id, doc_name=req.doc_name, content=req.content,
        product_name=profile.get("product_name", ""),
        company_name=profile.get("company_name", ""),
    )
    return {"id": rid, "ok": True}


@router.get("")
async def list_all(product: str | None = None, all: bool = False,
                   account_id: str = Depends(get_current_account)):
    """已生成文档列表（不含正文）。默认只返回【当前选中产品】的文档（按账号+产品隔离）；
    传 all=true 返回该账号全部、或 product=<名称> 指定产品。每份按 checklist 子类推断档案。"""
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
        docs = doc_store.list_docs(account_id)
    else:
        pname = product if product is not None else current_product_name(account_id)
        docs = doc_store.list_docs(account_id, product_name=pname)
    for d in docs:
        item = by_docid.get(d.get("doc_id")) or by_name.get(d.get("doc_name"))
        dossier_ids = infer_dossiers(item) if item else []
        # 外部导入的 QMS 文档 doc_id 形如 "QMS-P07..."（唯一），无法精确命中 checklist，
        # 按编号前缀映射到对应档案，使其在文件管理页正确分类而非全落"未归档"。
        if not dossier_ids:
            dossier_ids = _qms_prefix_dossiers(d.get("doc_id") or "")
        d["dossiers"] = [name2meta[k] for k in dossier_ids if k in name2meta]
    return {"docs": docs, "dossiers": dossiers_meta}


@router.get("/{rid}")
async def detail(rid: str, account_id: str = Depends(get_current_account)):
    d = doc_store.get_doc(rid, account_id)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return d


@router.get("/{rid}/download")
async def download(rid: str, account_id: str = Depends(get_current_account)):
    """下载存档文档为 .docx。"""
    d = doc_store.get_doc(rid, account_id)
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


from pathlib import Path as _Path

_ORIG_DIR = _Path(__file__).resolve().parent.parent.parent / "data" / "qms_originals"


@router.get("/{rid}/has-original")
async def has_original(rid: str, account_id: str = Depends(get_current_account)):
    """该文档是否有可下载的原始 Word 文件（导入的 QMS 文档才有）。"""
    d = doc_store.get_doc(rid, account_id)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"has_original": (_ORIG_DIR / f"{rid}.docx").exists()}


@router.get("/{rid}/original")
async def download_original(rid: str, account_id: str = Depends(get_current_account)):
    """下载原始 Word 文件（保留完整格式/表格）。仅导入的 QMS 文档有。"""
    d = doc_store.get_doc(rid, account_id)
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    path = _ORIG_DIR / f"{rid}.docx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="该文档无原始文件")
    filename = f"{d['doc_name']}.docx"
    disposition = f"attachment; filename=\"original.docx\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=path.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
    )


@router.delete("/{rid}")
async def remove(rid: str, account_id: str = Depends(get_current_account)):
    if not doc_store.delete_doc(rid, account_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    # 一并清理原始文件
    p = _ORIG_DIR / f"{rid}.docx"
    p.unlink(missing_ok=True)
    return {"ok": True}
