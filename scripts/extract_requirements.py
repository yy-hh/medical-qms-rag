"""从法规原文抽取「审查要求」，构建「法规 → 要求 → 文档」关联（审核员视角倒推）。

对每部法规：
  1. 从知识库按 doc_name 取全文 chunk
  2. 让模型抽取该法规包含的审查要求清单，每条带：章节、要求标题、要求内容，
     以及"应由哪些文档体现"（从给定的可生成文档清单里选 doc_id）
  3. 输出 JSON，审核后固化进 compliance_graph

用法：
    python scripts/extract_requirements.py "临床评价技术指导原则"     # 单部，按 doc_name 关键词
    python scripts/extract_requirements.py --list                      # 列出知识库所有法规
结果写 /tmp/req_extract_<安全名>.json
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.core.qms_framework import get_all_documents

DOC_CATALOG = [{"doc_id": d["id"], "name": d["name"]} for d in get_all_documents()]

SYS = """你是医疗器械注册技术审评专家。任务：阅读一部法规/指导原则的原文，
站在审评员角度，抽取该法规对企业提出的「审查要求」清单。
每条要求要可核查、具体；并从给定的【可生成文档清单】中判断该要求应由哪些文档体现。
只依据原文，不要编造原文没有的要求；文档只能从清单里选 doc_id，选不到就留空数组。"""


def fetch_full_text(engine, name_kw: str, max_chars: int = 40000):
    rows = engine.db.execute(
        "SELECT doc_name, chunk_index, text FROM chunks WHERE doc_name LIKE ? ORDER BY doc_name, chunk_index",
        (f"%{name_kw}%",),
    ).fetchall()
    if not rows:
        return None, ""
    doc_name = rows[0][0]
    text = "\n".join(r[2] for r in rows)
    return doc_name, text[:max_chars]


def extract(engine, reg_display: str, full_text: str):
    catalog = "\n".join(f"- {d['doc_id']}: {d['name']}" for d in DOC_CATALOG)
    prompt = f"""法规名称：{reg_display}

## 可生成文档清单（doc_id: 名称）
{catalog}

## 法规原文（节选）
{full_text}

## 任务
抽取该法规包含的审查要求清单。严格输出 JSON 数组，不要多余文字、不要 markdown 代码块：
[
  {{
    "clause": "章节/条款定位（如 第三章第二节 或 三、（一），原文没有编号就简述位置）",
    "title": "要求简短标题（10~20字）",
    "detail": "要求的具体内容（一句话说清要企业做到什么）",
    "doc_ids": ["该要求应由哪些文档体现，从清单选 doc_id，可多个或为空"]
  }}
]
要求条目控制在 8~25 条，覆盖该法规主要审查点。"""
    stream = engine.llm.chat.completions.create(
        model=settings.claude_model, max_tokens=8192, stream=True,
        messages=[{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
    )
    content = ""
    for ch in stream:
        if ch.choices and getattr(ch.choices[0].delta, "content", None):
            content += ch.choices[0].delta.content
    m = re.search(r"\[.*\]", content, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        objs = re.findall(r"\{[^{}]*\}", m.group(0), re.S)
        out = []
        for o in objs:
            try:
                out.append(json.loads(o))
            except Exception:
                pass
        return out


# 批量抽取的核心法规：(知识库doc_name关键词, 规范法规名——作为图谱里的 Regulation 节点名)
BATCH_REGS = [
    ("人工智能医疗器械注册审查指导原则_2022年第8号", "人工智能医疗器械注册审查指导原则（2022第8号）"),
    ("人工智能医用软件产品分类界定指导原则", "人工智能医用软件产品分类界定指导原则（2021）"),
    ("人工智能辅助检测医疗器械软件临床评价", "人工智能辅助检测医疗器械（软件）临床评价注册审查指导原则（2023第38号）"),
    ("肺结节CT图像辅助检测软件", "肺结节CT图像辅助检测软件注册审查指导原则（2022第21号）"),
    ("糖尿病视网膜病变眼底图像", "糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则（2022第23号）"),
    ("乳腺X射线图像辅助检测软件", "乳腺X射线图像辅助检测软件注册审查指导原则（2022第22号）"),
    ("医疗器械软件注册审查指导原则", "医疗器械软件注册审查指导原则（2022修订）"),
    ("医疗器械网络安全注册审查指导原则", "医疗器械网络安全注册审查指导原则（2022修订）"),
    ("医疗器械可用性工程注册审查指导原则_2024", "医疗器械可用性工程注册审查指导原则（2024）"),
    ("医疗器械临床评价技术指导原则", "医疗器械临床评价技术指导原则（2021）"),
    ("真实世界数据用于医疗器械临床评价", "医疗器械真实世界数据用于临床评价技术指导原则（试行）（2021）"),
    ("医疗器械生产质量管理规范附录独立软件", "医疗器械生产质量管理规范附录·独立软件"),
    ("医疗器械生产质量管理规范独立软件现场检查", "医疗器械生产质量管理规范独立软件现场检查指导原则（2021）"),
    ("医疗器械产品技术要求编写指导原则", "医疗器械产品技术要求编写指导原则（2022修订）"),
    ("医用软件通用名称命名指导原则", "医用软件通用名称命名指导原则（2021）"),
    ("移动医疗器械注册审查指导原则", "移动医疗器械注册审查指导原则（2025修订）"),
]


def run_one(engine, kw, canonical):
    doc_name, text = fetch_full_text(engine, kw)
    if not doc_name:
        print(f"[未找到] {kw}", flush=True)
        return None
    print(f"\n=== {canonical} ←原文 {doc_name} ({len(text)}字) ===", flush=True)
    reqs = extract(engine, canonical, text)
    print(f"  抽取 {len(reqs)} 条", flush=True)
    for r in reqs:
        docs = "、".join(r.get("doc_ids", [])) or "（无）"
        print(f"    [{r.get('clause','?')[:24]}] {r.get('title','')} → {docs}", flush=True)
    return {"regulation": canonical, "source_doc": doc_name, "requirements": reqs}


def main():
    engine = get_engine()
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        rows = engine.db.execute("SELECT DISTINCT doc_name FROM chunks ORDER BY doc_name").fetchall()
        for (n,) in rows:
            print(n)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        allres = []
        for kw, canon in BATCH_REGS:
            r = run_one(engine, kw, canon)
            if r:
                allres.append(r)
        with open("/tmp/req_extract_batch.json", "w", encoding="utf-8") as f:
            json.dump(allres, f, ensure_ascii=False, indent=2)
        total = sum(len(r["requirements"]) for r in allres)
        print(f"\n=== 批量完成：{len(allres)} 部法规，共 {total} 条要求 → /tmp/req_extract_batch.json ===", flush=True)
        return
    kw = sys.argv[1] if len(sys.argv) > 1 else "临床评价技术指导原则"
    r = run_one(engine, kw, kw)
    safe = re.sub(r"[^\w]", "_", kw)[:30]
    with open(f"/tmp/req_extract_{safe}.json", "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 /tmp/req_extract_{safe}.json", flush=True)


if __name__ == "__main__":
    main()
