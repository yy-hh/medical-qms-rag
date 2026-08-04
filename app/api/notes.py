from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.core import note_store
from app.api.deps import get_current_account

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteRequest(BaseModel):
    id: Optional[str] = None
    title: str = ""
    content: str = ""
    tags: list[str] = []


@router.post("")
async def upsert(req: NoteRequest, account_id: str = Depends(get_current_account)):
    """新建或更新笔记（id 为空=新建）。"""
    title = (req.title or "").strip()
    content = (req.content or "").strip()
    if not title and not content:
        raise HTTPException(status_code=400, detail="标题和正文不能都为空")
    if not title:
        title = content.splitlines()[0][:50]
    tags = ",".join(t.strip() for t in req.tags if t and t.strip())
    rid = note_store.save_note(account_id, note_id=req.id, title=title,
                               content=req.content or "", tags=tags)
    return {"id": rid, "ok": True}


@router.get("")
async def list_all(q: str | None = None, tag: str | None = None,
                   account_id: str = Depends(get_current_account)):
    """笔记列表 + 全部标签。q 关键词搜索，tag 标签筛选。"""
    notes = note_store.list_notes(account_id, q=q, tag=tag)
    return {"notes": notes, "tags": note_store.all_tags(account_id)}


@router.get("/{rid}")
async def detail(rid: str, account_id: str = Depends(get_current_account)):
    d = note_store.get_note(rid, account_id)
    if not d:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return d


@router.delete("/{rid}")
async def remove(rid: str, account_id: str = Depends(get_current_account)):
    if not note_store.delete_note(rid, account_id):
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"ok": True}
