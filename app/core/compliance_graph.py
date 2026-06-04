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

from app.core.registration_checklist import CHECKLIST, STAGES, get_checklist_item, get_basis_split
from app.core.qms_framework import get_document_by_id, DOSSIERS

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


# 法规名规范化：把 73 项对照表里的变体/合写/占位写法，归一到规范法规名。
# - 变体（同一法规被写成 §三 / 第五部分 等）→ 合并到主节点
# - 占位符（"对应性能测试标准""对应适应症专项指导原则"）→ 映射为 None，不建节点
# - 合写（"A / B"）→ 在 canonical_regs() 里拆开
REG_CANONICAL = {
    "人工智能医疗器械注册审查指导原则§三": "人工智能医疗器械注册审查指导原则（2022第8号）",
    "人工智能医疗器械注册审查指导原则第五部分": "人工智能医疗器械注册审查指导原则（2022第8号）",
    "人工智能医疗器械注册审查指导原则（2022第8号）第五部分": "人工智能医疗器械注册审查指导原则（2022第8号）",
    "对应性能测试标准": None,
    "对应适应症专项指导原则": None,
}


def canonical_regs(name: str) -> list[str]:
    """把一个 basis 里的法规名规范化为 0~N 个干净法规名（拆合写、并变体、剔占位）。"""
    out = []
    for part in re.split(r"\s*/\s*", name or ""):   # 拆 "A / B" 合写
        part = part.strip()
        if not part:
            continue
        if part in REG_CANONICAL:
            mapped = REG_CANONICAL[part]
            if mapped:
                out.append(mapped)
            # mapped is None → 占位符，丢弃
        else:
            out.append(part)
    return out


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
        # 文档节点。有 doc_id 时用 qms_framework 的正式文档名（如"质量手册"），
        # 这样节点名准确且可被搜索；output（对照表里的交付物描述）存为别名。
        dnode = doc_node_id(doc_id, seq)
        if not G.has_node(dnode):
            name = output
            alias = output
            if doc_id:
                fw = get_document_by_id(doc_id)
                if fw and fw.get("name"):
                    name = fw["name"]
            G.add_node(dnode, type="Document", name=name, alias=alias, doc_id=doc_id,
                       generatable=bool(doc_id), sub=sub)
        # 阶段 --PRODUCES--> 文档
        if not G.has_edge(stage, dnode, key="PRODUCES"):
            G.add_edge(stage, dnode, key="PRODUCES", rel="PRODUCES", seq=seq, activity=activity)
        # 文档 --BELONGS_TO--> 阶段（反向便捷）
        if not G.has_edge(dnode, stage, key="BELONGS_TO"):
            G.add_edge(dnode, stage, key="BELONGS_TO", rel="BELONGS_TO")
        # 法规要求节点：若该条目有"多法规拆分"，为每部法规建独立要求（各配自己的条款）；
        # 否则按整条 (basis, clause) 建一条要求。每条要求只 CITES 它自己那一部法规文件。
        split = get_basis_split(seq) if not extra else None
        if split:
            pairs = [(p["regulation"], p["clause"]) for p in split]
        else:
            pairs = [(basis, clause)]

        for reg_raw, req_clause in pairs:
            # 规范化法规名（并变体、拆合写、剔占位）。占位符 → 无干净法规，跳过该 pair。
            clean = canonical_regs(reg_raw)
            if not clean:
                continue
            for reg_name in clean:
                rnode = req_node_id(reg_name, req_clause)
                if not G.has_node(rnode):
                    G.add_node(rnode, type="Requirement", basis=reg_name, clause=req_clause, summary=note)
                # 文档 --SATISFIES--> 要求
                G.add_edge(dnode, rnode, key=f"SAT-{seq}-{int(extra)}-{reg_node_id(reg_name)}",
                           rel="SATISFIES", seq=seq, extra=extra)
                # 要求 --CITES--> 它自己那一部法规文件
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

    # 4) 从法规原文抽取的审查要求（审核员视角倒推：法规 → 要求 → 文档）
    _add_extracted_requirements(G)

    # 5) 档案归档层：文档 --归入--> 档案（DHF/DMR/DHR/技术文档/NMPA）
    _add_dossiers(G)

    return G


def _add_dossiers(G: nx.MultiDiGraph):
    """据 qms_framework.DOSSIERS 的 compiles 字段，连 文档 --ARCHIVED_IN--> 档案。"""
    for d in DOSSIERS:
        dossier_node = d["id"]   # 如 DOSSIER-DHF
        if not G.has_node(dossier_node):
            G.add_node(dossier_node, type="Dossier", name=d["name"],
                       en=d.get("en", ""), desc=d.get("desc", ""))
        for did in d.get("compiles", []):
            dnode = f"DOC-{did}"
            if not G.has_node(dnode):
                fw = get_document_by_id(did)
                if not fw:
                    continue
                G.add_node(dnode, type="Document", name=fw["name"], alias=fw["name"],
                           doc_id=did, generatable=True, sub="")
            if not G.has_edge(dnode, dossier_node, key="ARCHIVED_IN"):
                G.add_edge(dnode, dossier_node, key="ARCHIVED_IN", rel="ARCHIVED_IN")


def _add_extracted_requirements(G: nx.MultiDiGraph):
    """加载 extracted_requirements.json，为每条抽取的审查要求建节点：
    Requirement(标题+章节) --CITES--> Regulation(法规)；并 SATISFIES 到关联文档。
    这是图谱里"法规包含哪些要求、每条要求由哪些文档体现"的主体数据。"""
    import os, json
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "extracted_requirements.json")
    if not os.path.exists(path):
        return
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        return

    for entry in data:
        reg_name = entry.get("regulation")
        if not reg_name:
            continue
        gnode = reg_node_id(reg_name)
        if not G.has_node(gnode):
            G.add_node(gnode, type="Regulation", name=reg_name)
        for req in entry.get("requirements", []):
            clause = req.get("clause") or ""
            title = req.get("title") or ""
            detail = req.get("detail") or ""
            # 要求节点 id 用 法规+章节+标题 保证唯一
            rnode = "REQX-" + _hash(reg_name + "|" + clause + "|" + title)
            if not G.has_node(rnode):
                G.add_node(rnode, type="Requirement", basis=reg_name,
                           clause=(clause + ("：" + title if title else "")) or title,
                           title=title, detail=detail, summary=detail, extracted=True)
            # 要求 --CITES--> 法规
            if not G.has_edge(rnode, gnode, key="CITES"):
                G.add_edge(rnode, gnode, key="CITES", rel="CITES")
            # 文档 --SATISFIES--> 要求
            for did in (req.get("doc_ids") or []):
                dnode = f"DOC-{did}"
                if not G.has_node(dnode):
                    fw = get_document_by_id(did)
                    if not fw:
                        continue
                    G.add_node(dnode, type="Document", name=fw["name"], alias=fw["name"],
                               doc_id=did, generatable=True, sub="")
                G.add_edge(dnode, rnode, key=f"SATX-{rnode}", rel="SATISFIES", extracted=True)


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
        t = a.get("type")
        if t == "Requirement":
            # 法规要求节点显示「条款」，区别于法规文件节点显示的「法规名」
            label = a.get("clause") or a.get("basis") or n
        else:
            label = a.get("name") or a.get("basis") or a.get("clause") or n
        nodes.append({"id": n, "type": t, "label": label,
                      "alias": a.get("alias"), "clause": a.get("clause"),
                      "basis": a.get("basis"), "doc_id": a.get("doc_id"),
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


def full_graph() -> dict:
    """整张图序列化，供前端力导向可视化。"""
    return _serialize(graph())


def node_detail(node_id: str) -> dict:
    """单节点详情 + 直接邻居（点击节点时展示）。"""
    G = graph()
    if node_id not in G:
        return {}
    a = dict(G.nodes[node_id])
    a["id"] = node_id
    neighbors = []
    for _, v, d in G.out_edges(node_id, data=True):
        nb = G.nodes[v]
        neighbors.append({"id": v, "type": nb.get("type"), "rel": d.get("rel"),
                          "label": nb.get("name") or nb.get("clause") or nb.get("basis") or v,
                          "dir": "out"})
    for u, _, d in G.in_edges(node_id, data=True):
        nb = G.nodes[u]
        neighbors.append({"id": u, "type": nb.get("type"), "rel": d.get("rel"),
                          "label": nb.get("name") or nb.get("clause") or nb.get("basis") or u,
                          "dir": "in"})
    return {"node": a, "neighbors": neighbors}


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
