"""合规知识图谱：用 networkx 真图引擎建模「法规 × 文档 × 阶段」。

这是一张带类型的多重有向图（MultiDiGraph）：

节点类型（node attr: type）
  Stage        注册阶段（S1~S6）          属性: no, name, en, color, goal
  Document     文档/证据                  属性: name, doc_id, generatable, sub
  Requirement  法规要求（具体条款）       属性: basis, clause, summary
  Regulation   法规/标准文件（去掉条款）  属性: name        ← 比扁平表多出的一层，支撑多跳

边类型（edge attr: rel）
  Stage      --PRODUCES-->   Document      在该阶段产出该文档（attr: seq, activity）
  Document   --SATISFIES-->  Requirement   该文档满足该法规要求（attr: seq, extra）
  Requirement--CITES-->      Regulation    该要求出自某法规文件
  Document   --BELONGS_TO--> Stage         （反向便捷边，便于按文档查阶段）

种子数据来自 registration_checklist.CHECKLIST（73 项）；模型扩充的额外
「文档→法规要求」关系放在 EXTRA_LINKS。真图能力（多跳/路径/子图）建立在此图上。
"""
import re

import networkx as nx

from app.core.registration_checklist import CHECKLIST, STAGES, get_checklist_item

# 模型扩充的额外「文档满足法规要求」关系（审核后填入）。每条：
#   {"seq": 对应 checklist 序号, "basis": 法规名, "clause": 条款, "requirement": 要求简述}
EXTRA_LINKS: list[dict] = []


def _hash(s: str) -> str:
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return f"{h:08x}"


def req_node_id(basis: str, clause: str) -> str:
    return f"REQ-{_hash(basis + '|' + clause)}"


def reg_node_id(name: str) -> str:
    return f"REG-{_hash(name)}"


def doc_node_id(doc_id, seq: int) -> str:
    return f"DOC-{doc_id}" if doc_id else f"DOC-item-{seq}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _split_regulations(basis: str) -> list[str]:
    """一个 basis 字段可能写了多部法规（用 ；/ 分隔），拆成单独的法规名。"""
    parts = re.split(r"[；;]\s*", basis or "")
    return [p.strip() for p in parts if p.strip()]


def build_graph() -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    stages_by_key = {s["key"]: s for s in STAGES}

    # 1) 阶段节点
    for s in STAGES:
        G.add_node(s["key"], type="Stage", no=s["no"], name=s["name"],
                   en=s["en"], color=s["color"], goal=s["goal"])

    def add_links(seq, stage, sub, activity, output, doc_id, basis, clause, note, extra=False):
        # 文档节点
        dnode = doc_node_id(doc_id, seq)
        if not G.has_node(dnode):
            G.add_node(dnode, type="Document", name=output, doc_id=doc_id,
                       generatable=bool(doc_id), sub=sub)
        # 阶段 --PRODUCES--> 文档
        if not G.has_edge(stage, dnode, key="PRODUCES"):
            G.add_edge(stage, dnode, key="PRODUCES", rel="PRODUCES", seq=seq, activity=activity)
        # 文档 --BELONGS_TO--> 阶段（反向便捷）
        if not G.has_edge(dnode, stage, key="BELONGS_TO"):
            G.add_edge(dnode, stage, key="BELONGS_TO", rel="BELONGS_TO")
        # 法规要求节点
        rnode = req_node_id(basis, clause)
        if not G.has_node(rnode):
            G.add_node(rnode, type="Requirement", basis=basis, clause=clause, summary=note)
        # 文档 --SATISFIES--> 要求
        G.add_edge(dnode, rnode, key=f"SAT-{seq}-{int(extra)}", rel="SATISFIES",
                   seq=seq, extra=extra)
        # 要求 --CITES--> 法规文件（拆多部）
        for reg_name in _split_regulations(basis):
            gnode = reg_node_id(reg_name)
            if not G.has_node(gnode):
                G.add_node(gnode, type="Regulation", name=reg_name)
            if not G.has_edge(rnode, gnode, key="CITES"):
                G.add_edge(rnode, gnode, key="CITES", rel="CITES")

    # 2) 种子：73 项
    for it in CHECKLIST:
        add_links(it["seq"], it["stage"], it["sub"], it["activity"], it["output"],
                  it.get("doc_id"), it["basis"], it["clause"], it.get("note", ""))

    # 3) 模型扩充的额外关系
    for ex in EXTRA_LINKS:
        base = get_checklist_item(ex["seq"])
        if not base:
            continue
        add_links(ex["seq"], base["stage"], base["sub"], base["activity"], base["output"],
                  base.get("doc_id"), ex["basis"], ex["clause"], ex.get("requirement", ""),
                  extra=True)

    return G


# 进程内缓存
_G = None


def graph() -> nx.MultiDiGraph:
    global _G
    if _G is None:
        _G = build_graph()
    return _G


# ── 基础查询（与旧接口兼容，界面不破）──────────────────────────────────────

def by_stage(stage_key: str) -> dict:
    G = graph()
    if stage_key not in G:
        return {"stage": stage_key, "documents": [], "requirements": [], "count": 0}
    docs, reqs, count = {}, {}, 0
    for _, dnode, k, d in G.out_edges(stage_key, keys=True, data=True):
        if d.get("rel") != "PRODUCES":
            continue
        count += 1
        dn = G.nodes[dnode]
        entry = docs.setdefault(dnode, {"name": dn["name"], "doc_id": dn.get("doc_id"), "reqs": []})
        for _, rnode, ed in G.out_edges(dnode, data=True):
            if ed.get("rel") == "SATISFIES":
                rn = G.nodes[rnode]
                entry["reqs"].append({"basis": rn["basis"], "clause": rn["clause"]})
                reqs[rnode] = {"basis": rn["basis"], "clause": rn["clause"]}
    return {"stage": stage_key, "documents": list(docs.values()),
            "requirements": list(reqs.values()), "count": count}


def by_document(key_or_doc_id: str) -> dict:
    G = graph()
    dnode = key_or_doc_id if key_or_doc_id in G else f"DOC-{key_or_doc_id}"
    if dnode not in G or G.nodes[dnode].get("type") != "Document":
        return {}
    dn = G.nodes[dnode]
    stages, reqs = set(), []
    for _, tgt, d in G.out_edges(dnode, data=True):
        if d.get("rel") == "BELONGS_TO":
            stages.add(tgt)
        elif d.get("rel") == "SATISFIES":
            rn = G.nodes[tgt]
            reqs.append({"basis": rn["basis"], "clause": rn["clause"], "note": rn.get("summary", "")})
    return {"doc_key": dnode, "doc_name": dn["name"], "doc_id": dn.get("doc_id"),
            "stages": sorted(stages), "requirements": reqs}


def by_requirement(req_id: str) -> dict:
    G = graph()
    if req_id not in G or G.nodes[req_id].get("type") != "Requirement":
        return {}
    rn = G.nodes[req_id]
    satisfied = []
    for dnode, _, d in G.in_edges(req_id, data=True):
        if d.get("rel") != "SATISFIES":
            continue
        dn = G.nodes[dnode]
        # 找该文档所属阶段
        for _, st, ed in G.out_edges(dnode, data=True):
            if ed.get("rel") == "BELONGS_TO":
                satisfied.append({"doc_name": dn["name"], "doc_id": dn.get("doc_id"),
                                  "stage": st, "activity": ""})
    return {"req_id": req_id, "basis": rn["basis"], "clause": rn["clause"],
            "satisfied_by": satisfied}


def search_requirements(keyword: str) -> list[dict]:
    G = graph()
    kw = _norm(keyword)
    out = []
    for n, attr in G.nodes(data=True):
        if attr.get("type") != "Requirement":
            continue
        if kw and kw not in _norm(attr["basis"]) and kw not in _norm(attr["clause"]):
            continue
        docs = []
        for dnode, _, d in G.in_edges(n, data=True):
            if d.get("rel") != "SATISFIES":
                continue
            dn = G.nodes[dnode]
            stage = next((st for _, st, ed in G.out_edges(dnode, data=True)
                          if ed.get("rel") == "BELONGS_TO"), None)
            docs.append({"doc_name": dn["name"], "doc_id": dn.get("doc_id"), "stage": stage})
        out.append({"req_id": n, "basis": attr["basis"], "clause": attr["clause"], "docs": docs})
    return out


# ── 真图能力：多跳 / 路径 / 邻居子图 ───────────────────────────────────────

def neighbors_subgraph(node_id: str, hops: int = 1) -> dict:
    """以某节点为中心、半径 hops 的邻居子图（无向意义上的可达），返回节点+边，供可视化。"""
    G = graph()
    if node_id not in G:
        return {}
    und = G.to_undirected(as_view=True)
    nodes = set(nx.ego_graph(und, node_id, radius=hops).nodes())
    sub = G.subgraph(nodes)
    return _serialize(sub, center=node_id)


def related_requirements(req_id: str, hops: int = 2) -> dict:
    """多跳：与某法规要求"相关"的其它要求 —— 经由"共同文档"或"同一法规文件"连过去。
    回答："满足这条要求的文档，还满足了哪些其它法规要求"。"""
    G = graph()
    if req_id not in G or G.nodes[req_id].get("type") != "Requirement":
        return {}
    # 1 跳：satisfies 该要求的文档
    docs = [d for d, _, e in G.in_edges(req_id, data=True) if e.get("rel") == "SATISFIES"]
    related = {}
    for dnode in docs:
        for _, rnode, e in G.out_edges(dnode, data=True):
            if e.get("rel") == "SATISFIES" and rnode != req_id:
                rn = G.nodes[rnode]
                related.setdefault(rnode, {"req_id": rnode, "basis": rn["basis"],
                                           "clause": rn["clause"], "via_docs": []})
                related[rnode]["via_docs"].append(G.nodes[dnode]["name"])
    rn = G.nodes[req_id]
    return {"req_id": req_id, "basis": rn["basis"], "clause": rn["clause"],
            "related": list(related.values())}


def path_between(src: str, dst: str) -> dict:
    """两节点间最短路径（在无向视图上），用于解释"X 如何关联到 Y"。"""
    G = graph()
    if src not in G or dst not in G:
        return {}
    und = G.to_undirected(as_view=True)
    try:
        path = nx.shortest_path(und, src, dst)
    except nx.NetworkXNoPath:
        return {"path": []}
    steps = []
    for n in path:
        a = G.nodes[n]
        t = a.get("type")
        if t == "Requirement":
            label = a.get("clause") or a.get("basis") or n
        else:
            label = a.get("name") or n
        steps.append({"id": n, "type": t, "label": label})
    return {"path": steps, "hops": len(path) - 1}


def _serialize(sub, center=None) -> dict:
    nodes = []
    for n, a in sub.nodes(data=True):
        nodes.append({"id": n, "type": a.get("type"),
                      "label": a.get("name") or a.get("basis") or a.get("clause") or n,
                      "clause": a.get("clause"), "doc_id": a.get("doc_id"),
                      "color": a.get("color"), "center": n == center})
    edges = []
    seen = set()
    for u, v, d in sub.edges(data=True):
        rel = d.get("rel")
        sig = (u, v, rel)
        if sig in seen:
            continue
        seen.add(sig)
        edges.append({"source": u, "target": v, "rel": rel})
    return {"nodes": nodes, "edges": edges}


def stats() -> dict:
    G = graph()
    types = {}
    for _, a in G.nodes(data=True):
        types[a.get("type")] = types.get(a.get("type"), 0) + 1
    rels = {}
    for _, _, d in G.edges(data=True):
        rels[d.get("rel")] = rels.get(d.get("rel"), 0) + 1
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "node_types": types,
        "edge_types": rels,
        # 兼容旧界面字段
        "requirements": types.get("Requirement", 0),
        "documents": types.get("Document", 0),
        "generatable_docs": sum(1 for _, a in G.nodes(data=True)
                                if a.get("type") == "Document" and a.get("generatable")),
    }
