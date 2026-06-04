from fastapi import APIRouter, HTTPException

from app.core.compliance_graph import (
    stats, by_stage, by_document, by_requirement, search_requirements,
    neighbors_subgraph, related_requirements, path_between,
    full_graph, node_detail, overview_subgraph,
)
from app.core.registration_checklist import get_checklist, STAGES

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/overview")
async def overview():
    """图谱总览：阶段列表 + 规模统计。"""
    return {"stages": STAGES, "stats": stats()}


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


# ── 真图能力 ──────────────────────────────────────────────────────────────

@router.get("/graph")
async def graph_full():
    """整张图（节点+边），供前端力导向可视化。"""
    return full_graph()


@router.get("/overview-graph")
async def graph_overview():
    """轻量概览图：只含枢纽节点（阶段/法规/档案），供默认快速渲染。"""
    return overview_subgraph()


@router.get("/node/{node_id}")
async def node(node_id: str):
    """单节点详情 + 直接邻居。"""
    res = node_detail(node_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return res


@router.get("/subgraph/{node_id}")
async def subgraph(node_id: str, hops: int = 1):
    """以某节点为中心的邻居子图（供可视化）。hops 默认 1。"""
    res = neighbors_subgraph(node_id, hops=max(1, min(hops, 3)))
    if not res:
        raise HTTPException(status_code=404, detail=f"节点 {node_id} 不存在")
    return res


@router.get("/related/{req_id}")
async def related(req_id: str):
    """多跳：与某法规要求经由共同文档关联的其它法规要求。"""
    res = related_requirements(req_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"法规要求 {req_id} 不存在")
    return res


@router.get("/path")
async def path(src: str, dst: str):
    """两节点间最短关联路径，解释"X 如何关联到 Y"。"""
    res = path_between(src, dst)
    if not res:
        raise HTTPException(status_code=404, detail="节点不存在")
    return res
