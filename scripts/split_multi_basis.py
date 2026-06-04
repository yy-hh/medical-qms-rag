"""把 checklist 中"一格多法规"的条目，用模型按法规拆分条款。

每条多法规条目 → 让模型输出 [{regulation, clause}]，每部法规配它自己的条款。
结果写到 /tmp/multi_basis_split.json，审核后用于 compliance_graph 精确建模。
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.core.registration_checklist import CHECKLIST

SYS = """你是中国医疗器械注册法规专家。任务：把一条"同时引用多部法规"的合规要求，
按法规拆开，让每部法规对应它自己的具体条款。
只引用给定的法规名，不要新增法规；条款须忠于原始 clause 文本，把属于各法规的部分分给对应法规；
若某法规在原文里没有明确条款，clause 写"（全文/未指明具体条款）"。"""


def split_one(engine, item):
    regs = [r.strip() for r in re.split(r"[；;]", item["basis"]) if r.strip()]
    prompt = f"""活动：{item['activity']}
输出文档：{item['output']}
原始法规依据(basis)：{item['basis']}
原始条款(clause)：{item['clause']}

请把上面拆成 {len(regs)} 条，每条对应一部法规。严格输出 JSON 数组，不要多余文字：
[{{"regulation":"法规名","clause":"该法规对应的具体条款"}}]
法规名必须是这些之一：{regs}"""
    stream = engine.llm.chat.completions.create(
        model=settings.claude_model, max_tokens=2048, stream=True,
        messages=[{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
    )
    content = ""
    for ch in stream:
        if ch.choices and getattr(ch.choices[0].delta, "content", None):
            content += ch.choices[0].delta.content
    m = re.search(r"\[.*\]", content, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def main():
    engine = get_engine()
    multi = [i for i in CHECKLIST if len(re.split(r"[；;]", i["basis"])) > 1]
    out = {}
    for item in multi:
        print(f"\n=== seq {item['seq']} ===", flush=True)
        print("原 basis:", item["basis"], flush=True)
        res = split_one(engine, item)
        if res:
            for r in res:
                print(f"   {r.get('regulation')}  →  {r.get('clause')}", flush=True)
            out[str(item["seq"])] = res
        else:
            print("   [拆分失败]", flush=True)
    with open("/tmp/multi_basis_split.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 /tmp/multi_basis_split.json（{len(out)} 条）", flush=True)


if __name__ == "__main__":
    main()
