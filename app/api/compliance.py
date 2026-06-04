from fastapi import APIRouter, HTTPException

from app.core.compliance_graph import (
    graph, stats, by_stage, by_document, by_requirement, search_requirements,
)
from app.core.registration_checklist import get_checklist

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/overview")
async def overview():
    """图谱总览：阶段列表 + 规模统计。"""
    g = graph()
    return {"stages": g["stages"], "stats": stats()}


@router.get("/checklist")
async def checklist():
    """完整 73 项全流程对照表（按阶段分组）。"""
    return get_checklist()


@router.get("/stage/{stage_key}")
async def stage_view(stage_key: str):
    """维度·阶段：某阶段要产出哪些文档、覆盖哪些法规要求。"""
    res = by_stage(stage_key)
    if not res.get("count"):
        raise HTTPException(status_code=404, detail=f"阶段 {stage_key} 无数据")
    return res


@router.get("/document/{key}")
async def document_view(key: str):
    """维度·文档：某文档满足哪些法规要求、属于哪些阶段。key 可为 doc_id 或 item-<seq>。"""
    res = by_document(key)
    if not res:
        raise HTTPException(status_code=404, detail=f"文档 {key} 无数据")
    return res


@router.get("/requirement/{req_id}")
async def requirement_view(req_id: str):
    """维度·法规：某法规要求由哪些文档在哪些阶段满足。"""
    res = by_requirement(req_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"法规要求 {req_id} 不存在")
    return res


@router.get("/search")
async def search(q: str):
    """按法规名/条款关键词检索法规要求及其关联文档。"""
    if not q.strip():
        return {"results": []}
    return {"results": search_requirements(q)}
