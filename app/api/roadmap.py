from fastapi import APIRouter, HTTPException

from app.core.roadmap import get_roadmap, get_task_by_id

router = APIRouter(prefix="/api/roadmap", tags=["roadmap"])


@router.get("")
async def roadmap():
    """返回完整实施路线图（8 阶段 + 任务卡片，含对应文件解析）。"""
    return get_roadmap()


@router.get("/{task_id}")
async def roadmap_task(task_id: str):
    """返回单个任务详情，含对应文件（doc_ids 解析后可直接走 /api/generate/stream 生成）。"""
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return task
