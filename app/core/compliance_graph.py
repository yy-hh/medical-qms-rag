"""合规知识图谱：把「法规要求 × 文档/证据 × 注册阶段」三个维度关联起来。

核心三元关系：一条关联 = "在某【阶段】，用某【文档/证据】，满足某【法规要求】"。

数据以 registration_checklist.CHECKLIST（73 项全流程对照表）为种子派生：
  - 每条 checklist item 天然就是一个 (stage, 文档output, 法规basis+clause) 三元组
  - 法规要求(Requirement) 由 (basis, clause) 去重派生为独立实体，分配稳定 req_id
  - 文档(Document) 优先关联 qms_framework 中可生成的模板(doc_id)，否则以 output 名称作为"清单文档"

提供三个方向的互查：
  - by_requirement: 这条法规要求 → 哪些文档在哪些阶段满足
  - by_document:    这份文档 → 满足哪些法规要求、属于哪些阶段
  - by_stage:       这个阶段 → 要产出哪些文档、覆盖哪些法规要求

模型扩充的「一份文档满足多条法规要求」的额外关联存在 EXTRA_LINKS 中，与种子关联合并。
"""
import re

from app.core.registration_checklist import CHECKLIST, STAGES, get_checklist_item

# 模型扩充的额外关联（审核后填入）。每条：
#   {"seq": 对应 checklist 序号, "basis": 法规名, "clause": 条款, "requirement": 要求简述}
# 表示该 checklist 条目对应的文档，除自带的 basis/clause 外，还满足这条法规要求。
EXTRA_LINKS: list[dict] = []


def _req_id(basis: str, clause: str) -> str:
    """由 (法规名, 条款) 生成稳定的 requirement id。"""
    key = f"{basis}|{clause}"
    h = 0
    for ch in key:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return f"REQ-{h:08x}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def build_graph() -> dict:
    """构建合规图谱：requirements / documents / stages / links。"""
    stages_by_key = {s["key"]: s for s in STAGES}

    requirements: dict[str, dict] = {}
    documents: dict[str, dict] = {}
    links: list[dict] = []

    def ensure_req(basis: str, clause: str, summary: str = "") -> str:
        rid = _req_id(basis, clause)
        if rid not in requirements:
            requirements[rid] = {
                "req_id": rid,
                "basis": basis,
                "clause": clause,
                "summary": summary,
                "doc_seqs": [],     # 哪些 checklist 条目（文档）满足它
            }
        return rid

    def ensure_doc(seq: int, name: str, doc_id, stage: str) -> str:
        # 文档 key：有 doc_id 用 doc_id，否则用 seq（清单文档，暂无模板）
        key = doc_id if doc_id else f"item-{seq}"
        if key not in documents:
            documents[key] = {
                "key": key,
                "name": name,
                "doc_id": doc_id,            # 可生成模板的 id（可为 None）
                "generatable": bool(doc_id),
                "seqs": [],                  # 关联的 checklist 序号
                "stages": set(),
                "req_ids": set(),
            }
        documents[key]["seqs"].append(seq)
        documents[key]["stages"].add(stage)
        return key

    for item in CHECKLIST:
        seq = item["seq"]
        stage = item["stage"]
        # 法规要求实体（种子：每条的 basis+clause）
        rid = ensure_req(item["basis"], item["clause"], item.get("note", ""))
        # 文档实体
        dkey = ensure_doc(seq, item["output"], item.get("doc_id"), stage)
        # 关联
        documents[dkey]["req_ids"].add(rid)
        requirements[rid]["doc_seqs"].append(seq)
        links.append({
            "seq": seq,
            "stage": stage,
            "stage_name": stages_by_key.get(stage, {}).get("name", stage),
            "doc_key": dkey,
            "doc_name": item["output"],
            "doc_id": item.get("doc_id"),
            "req_id": rid,
            "basis": item["basis"],
            "clause": item["clause"],
            "activity": item["activity"],
            "sub": item["sub"],
            "note": item.get("note", ""),
        })

    # 合并模型扩充的额外关联
    for ex in EXTRA_LINKS:
        base = get_checklist_item(ex["seq"])
        if not base:
            continue
        rid = ensure_req(ex["basis"], ex["clause"], ex.get("requirement", ""))
        dkey = ex.get("doc_id") or f"item-{ex['seq']}"
        if dkey in documents:
            documents[dkey]["req_ids"].add(rid)
            requirements[rid]["doc_seqs"].append(ex["seq"])
        links.append({
            "seq": ex["seq"], "stage": base["stage"],
            "stage_name": stages_by_key.get(base["stage"], {}).get("name", base["stage"]),
            "doc_key": dkey, "doc_name": base["output"], "doc_id": base.get("doc_id"),
            "req_id": rid, "basis": ex["basis"], "clause": ex["clause"],
            "activity": base["activity"], "sub": base["sub"],
            "note": ex.get("requirement", ""), "extra": True,
        })

    # set → list 便于 JSON 序列化
    for d in documents.values():
        d["stages"] = sorted(d["stages"])
        d["req_ids"] = sorted(d["req_ids"])

    return {"requirements": requirements, "documents": documents, "links": links,
            "stages": STAGES}


# 进程内缓存（数据是静态的）
_GRAPH = None


def graph() -> dict:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


# ── 三维互查 ──────────────────────────────────────────────────────────────

def by_stage(stage_key: str) -> dict:
    """某阶段 → 该阶段的文档与法规覆盖。"""
    g = graph()
    items = [l for l in g["links"] if l["stage"] == stage_key]
    docs = {}
    reqs = {}
    for l in items:
        docs.setdefault(l["doc_key"], {"name": l["doc_name"], "doc_id": l["doc_id"], "reqs": []})
        docs[l["doc_key"]]["reqs"].append({"basis": l["basis"], "clause": l["clause"]})
        reqs[l["req_id"]] = {"basis": l["basis"], "clause": l["clause"]}
    return {"stage": stage_key, "documents": list(docs.values()),
            "requirements": list(reqs.values()), "count": len(items)}


def by_document(key_or_doc_id: str) -> dict:
    """某文档 → 满足哪些法规要求、属于哪些阶段。"""
    g = graph()
    items = [l for l in g["links"]
             if l["doc_key"] == key_or_doc_id or l["doc_id"] == key_or_doc_id]
    if not items:
        return {}
    return {
        "doc_key": items[0]["doc_key"],
        "doc_name": items[0]["doc_name"],
        "doc_id": items[0]["doc_id"],
        "stages": sorted({l["stage"] for l in items}),
        "requirements": [{"basis": l["basis"], "clause": l["clause"], "note": l["note"]}
                         for l in items],
    }


def by_requirement(req_id: str) -> dict:
    """某法规要求 → 哪些文档在哪些阶段满足它。"""
    g = graph()
    req = g["requirements"].get(req_id)
    if not req:
        return {}
    items = [l for l in g["links"] if l["req_id"] == req_id]
    return {
        "req_id": req_id,
        "basis": req["basis"],
        "clause": req["clause"],
        "satisfied_by": [{"doc_name": l["doc_name"], "doc_id": l["doc_id"],
                          "stage": l["stage"], "activity": l["activity"]}
                         for l in items],
    }


def search_requirements(keyword: str) -> list[dict]:
    """按法规名/条款关键词搜法规要求（供问答与界面检索）。"""
    g = graph()
    kw = _norm(keyword)
    out = []
    for rid, r in g["requirements"].items():
        if kw in _norm(r["basis"]) or kw in _norm(r["clause"]):
            items = [l for l in g["links"] if l["req_id"] == rid]
            out.append({
                "req_id": rid, "basis": r["basis"], "clause": r["clause"],
                "docs": [{"doc_name": l["doc_name"], "doc_id": l["doc_id"], "stage": l["stage"]}
                         for l in items],
            })
    return out


def stats() -> dict:
    g = graph()
    return {
        "requirements": len(g["requirements"]),
        "documents": len(g["documents"]),
        "links": len(g["links"]),
        "generatable_docs": sum(1 for d in g["documents"].values() if d["generatable"]),
    }
