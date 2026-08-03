"""给已生成的 13485 各章补充「句子→小节」映射和小节板书要点，用于分屏黑板渲染。

不重新生成讲解内容、不重新生成音频，只做纯文本加工：
让 LLM 读现有逐句讲解，把句子按小节分组，并为每小节提炼 2-4 个板书要点。
结果写回 segment.visual_prompt 的新字段 "secmap"：
  secmap = [{"title": 小节名, "points": [要点...], "start_idx": 起始句号(0基), "end_idx": 结束句号(含)}]
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store
from app.core.rag_engine import get_engine
from app.core.config import settings

TOPIC = "ISO 13485 质量管理体系概览"

ANNOTATE_SYSTEM = """你是课程编辑。下面给你一节课的逐句讲解（每句前有编号）和该章的小节名列表。
请把这些句子按讲课进程划分给各个小节（每句只属于一个小节，按顺序连续切分，不跳跃、不重叠、全覆盖），
并为每个小节提炼 2-4 个「黑板板书要点」（每个 4-14 字的极短中文短语，概括该小节要讲的关键点）。

严格只输出一个 JSON 数组，每个元素形如：
{"title":"小节名","points":["要点1","要点2"],"start":起始句号,"end":结束句号}
其中 start/end 是该小节覆盖的句子编号范围（含两端，从 1 开始，与输入编号一致）。
第一个小节的 start 必须是 1，最后一个小节的 end 必须是最后一句的编号，各小节首尾相接。
不要输出任何额外文字，不要 markdown。"""


def annotate_chapter(seg):
    v = json.loads(seg["visual_prompt"])
    zh = v.get("zh") or []
    sections = v.get("points") or []
    if not zh or not sections:
        raise RuntimeError("缺 zh 或 points")

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(zh))
    user = (f"小节名列表：{ '、'.join(sections) }\n\n"
            f"逐句讲解（共 {len(zh)} 句）：\n{numbered}")
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model, max_tokens=4096,
        messages=[{"role": "system", "content": ANNOTATE_SYSTEM},
                  {"role": "user", "content": user}],
    )
    raw = resp.choices[0].message.content or ""
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        raise RuntimeError("secmap 解析失败：无 JSON")
    arr = json.loads(m.group(0))
    secmap = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        start = int(x.get("start", 0))
        end = int(x.get("end", 0))
        pts = [str(p).strip() for p in (x.get("points") or []) if str(p).strip()][:4]
        title = str(x.get("title", "")).strip()
        if start >= 1 and end >= start and title:
            secmap.append({"title": title, "points": pts,
                           "start_idx": start - 1, "end_idx": end - 1})
    # 校验覆盖：修正首尾
    if not secmap:
        raise RuntimeError("secmap 为空")
    secmap[0]["start_idx"] = 0
    secmap[-1]["end_idx"] = len(zh) - 1
    v["secmap"] = secmap
    training_store.update_segment(seg["id"], visual_prompt=json.dumps(v, ensure_ascii=False))
    return len(secmap)


def main():
    get_engine()
    t = [x for x in training_store.list_tutorials()
         if x["kind"] == "video" and x["topic"] == TOPIC][0]
    for seg in training_store.list_segments(t["id"]):
        try:
            n = annotate_chapter(seg)
            print(f"  ✓ {seg['title']} → {n} 小节映射", flush=True)
        except Exception as e:
            print(f"  ✗ {seg['title']}：{e}", flush=True)
    print("=== 补标结束 ===", flush=True)


if __name__ == "__main__":
    main()
