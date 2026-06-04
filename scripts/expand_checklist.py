"""用模型扩充注册全流程对照表：以现有 73 项为骨架，逐阶段补充可能遗漏的文档条目。

用法：
    python scripts/expand_checklist.py S2          # 只扩充研发阶段
    python scripts/expand_checklist.py all         # 扩充全部 6 阶段
输出写到 /tmp/checklist_expanded_<stage>.json，供审核后合并回 registration_checklist.py。
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.core.registration_checklist import STAGES, CHECKLIST

SYS = """你是资深的中国医疗器械（含AI/SaMD）注册法规专家，精通 NMPA 法规、YY/T 0664、
GB/T 42062、YY/T 1833 系列、IEC 62304/62366、网络安全与可用性工程等标准。
你的任务是为「含AI医疗器械软件全流程注册对照表」补充遗漏的文档/活动条目。
要求：
- 只引用真实存在的中国法规、部门规章、注册审查指导原则或 YY/T、GB/T 国标行标，禁止编造法规名称或文号
- 若不确定具体条款号，clause 字段可写"（待核对）"，但法规名称必须真实
- 补充的条目要是该阶段企业真实会产出/需要的文档，覆盖要尽量全
- 不要重复"已有条目"里已经列出的活动"""


def build_prompt(stage: dict, existing: list[dict]) -> str:
    existing_lines = "\n".join(
        f"- [{e['sub']}] {e['activity']} → {e['output']}" for e in existing
    )
    return f"""阶段：{stage['no']} {stage['name']}（{stage['en']}）
阶段目标：{stage['goal']}

## 该阶段【已有条目】（不要重复这些活动）
{existing_lines}

## 任务
请补充该阶段【还可能用到、但上面没列出】的文档/活动条目，尽量穷尽企业实际会产出的文档。
每条输出以下字段，严格输出一个 JSON 数组，不要任何额外文字、不要 markdown 代码块：
[
  {{
    "sub": "子类/工作包（沿用已有子类命名，如 '2A 软件生命周期'；若是新子类自拟简洁名）",
    "activity": "活动（要做什么）",
    "output": "输出文档（交付物名称）",
    "basis": "法规/标准依据（真实名称）",
    "clause": "具体条款/章节（不确定写 待核对）",
    "note": "关键说明（实务要点）"
  }}
]"""


def parse_json_array(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        # 截断容错：逐个对象提取
        objs = re.findall(r"\{[^{}]*\}", m.group(0), re.S)
        out = []
        for o in objs:
            try:
                out.append(json.loads(o))
            except Exception:
                pass
        return out


def expand_stage(engine, stage: dict) -> list[dict]:
    existing = [c for c in CHECKLIST if c["stage"] == stage["key"]]
    prompt = build_prompt(stage, existing)
    # 用流式累积：非流式一次等 8192 token 会超过 client 的 120s read timeout
    stream = engine.llm.chat.completions.create(
        model=settings.claude_model,
        max_tokens=8192,
        messages=[{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        stream=True,
    )
    content = ""
    for chunk in stream:
        if chunk.choices and getattr(chunk.choices[0].delta, "content", None):
            content += chunk.choices[0].delta.content
    items = parse_json_array(content)
    # 去重：与已有 activity 比对（去空格）
    existing_acts = {re.sub(r"\s+", "", e["activity"]) for e in existing}
    fresh = []
    seen = set()
    for it in items:
        act = re.sub(r"\s+", "", str(it.get("activity", "")))
        if not act or act in existing_acts or act in seen:
            continue
        seen.add(act)
        it["stage"] = stage["key"]
        it.setdefault("doc_id", None)
        fresh.append(it)
    return fresh


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "S2"
    engine = get_engine()
    stages = STAGES if target == "all" else [s for s in STAGES if s["key"] == target]
    for stage in stages:
        print(f"\n=== 扩充 {stage['no']} {stage['name']} ===", flush=True)
        fresh = expand_stage(engine, stage)
        print(f"新增 {len(fresh)} 条：", flush=True)
        for f in fresh:
            print(f"  [{f.get('sub')}] {f.get('activity')} → {f.get('output')}  ({f.get('basis')})", flush=True)
        out_path = f"/tmp/checklist_expanded_{stage['key']}.json"
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(fresh, fp, ensure_ascii=False, indent=2)
        print(f"已写入 {out_path}", flush=True)


if __name__ == "__main__":
    main()
