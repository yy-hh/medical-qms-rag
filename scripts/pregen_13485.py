"""按 ISO 13485:2016 的 8 个正文章节重构「ISO 13485 质量管理体系概览」教程：
每章 = 一节课 = 一个较长的黑板讲解视频，逐句讲解，中英双语字幕。

数据落地约定（复用现有表结构）：
- 每章一个 segment（seg_kind=board）。
- narration      : 本章中文讲解全文（TTS 朗读，句子自然连贯）。
- narration_en   : 对应英文讲解全文。
- visual_prompt  : JSON {"points":[小节名...], "zh":[中文句...], "en":[英文句...]}
                   points 用于黑板板书（章标题+小节名），zh/en 逐句配对用于双语字幕。

用法：
  python scripts/pregen_13485.py            # 生成大纲并渲染全部 8 章
  python scripts/pregen_13485.py --outline  # 只生成/覆盖大纲，不渲染
"""
import sys
import os
import re
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, audio_gen
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.api.training import _board_points, _board_sentences

TOPIC = "ISO 13485 质量管理体系概览"

# ISO 13485:2016 正文 8 章（第1-3章较短也各成一节课）
CHAPTERS = [
    ("第1章 范围", "Clause 1: Scope"),
    ("第2章 规范性引用文件", "Clause 2: Normative references"),
    ("第3章 术语和定义", "Clause 3: Terms and definitions"),
    ("第4章 质量管理体系", "Clause 4: Quality management system"),
    ("第5章 管理职责", "Clause 5: Management responsibility"),
    ("第6章 资源管理", "Clause 6: Resource management"),
    ("第7章 产品实现", "Clause 7: Product realization"),
    ("第8章 测量、分析和改进", "Clause 8: Measurement, analysis and improvement"),
]

CHAPTER_SYSTEM = """你是资深的医疗器械 QMS 培训讲师，正在为 ISO 13485:2016 标准录制逐章精讲课程。
本节课只讲解指定的一个章节，要求「逐句讲解」——把该章的核心要求讲透，条理清晰、口语自然、可直接朗读。

请严格按以下纯文本格式输出（不要 JSON、不要 markdown、不要多余说明）：

第一行固定以「小节：」开头，后面跟本章 3-6 个小节名，用「｜」分隔（每个小节名 4-12 字，作为黑板板书大纲）。
从第二行起，每行是一句讲解，格式为「中文句 ||| 英文句」（用三个竖线加空格分隔中英文）。

要求：
- 中文句口语化、完整、可朗读，每句 15-40 字；英文句是地道准确的英文翻译。
- 句子按讲课逻辑连贯推进：先点出本章主旨，再逐条讲解主要条款要求，最后小结。
- 句子数量按内容多少而定：短章（范围/引用/术语）12-18 句，长章（产品实现）24-36 句。
- 讲解具体、有信息量，避免空话；涉及条款编号用中文表述（如「第7.3条设计开发」）。
- 不要给句子编号，不要在句子里使用「｜」或「|||」以外的竖线。

输出示例：
小节：标准适用范围｜适用对象｜法规衔接
本标准规定了医疗器械质量管理体系的要求。 ||| This standard specifies requirements for a medical device quality management system.
它适用于医疗器械的设计、生产和服务全过程。 ||| It applies to the entire process of design, production and servicing of medical devices."""


def _find_tutorial():
    for t in training_store.list_tutorials():
        if t["kind"] == "video" and t["topic"] == TOPIC:
            return t
    return None


def gen_chapter(zh_title: str, en_title: str) -> dict:
    """调 LLM 生成单章内容，返回 {title, narration, narration_en, visual_prompt}。"""
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": CHAPTER_SYSTEM},
            {"role": "user", "content":
                f"请讲解 ISO 13485:2016 的「{zh_title}」（{en_title}）。"
                f"结合医疗器械行业实际，把本章要求讲清楚。"},
        ],
    )
    raw = resp.choices[0].message.content or ""
    sections, zh_list, en_list = [], [], []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("小节：") or line.startswith("小节:"):
            body = line.split("：", 1)[-1] if "：" in line else line.split(":", 1)[-1]
            sections = [s.strip() for s in re.split(r"[｜|]", body) if s.strip()][:6]
            continue
        if "|||" in line:
            zh, en = line.split("|||", 1)
            zh, en = zh.strip(), en.strip()
            if zh:
                zh_list.append(zh)
                en_list.append(en)
    if not zh_list:
        raise RuntimeError("章节内容解析失败：无有效句子")
    narration = "".join(z if z.endswith(("。", "！", "？", ".", "!", "?")) else z + "。" for z in zh_list)
    narration_en = " ".join(en_list)
    visual = {"points": sections, "zh": zh_list, "en": en_list}
    return {
        "title": zh_title,
        "seg_kind": "board",
        "narration": narration,
        "narration_en": narration_en,
        "visual_prompt": json.dumps(visual, ensure_ascii=False),
    }


def build_outline() -> str:
    """生成 8 章大纲并落库，返回 tutorial_id。"""
    existing = _find_tutorial()
    tid = existing["id"] if existing else training_store.save_tutorial(
        topic=TOPIC, kind="video", status="draft")
    segs = []
    for i, (zh, en) in enumerate(CHAPTERS, 1):
        print(f"  生成大纲 [{i}/{len(CHAPTERS)}] {zh} …", flush=True)
        try:
            segs.append(gen_chapter(zh, en))
            n = len(json.loads(segs[-1]["visual_prompt"])["zh"])
            print(f"      ✓ {n} 句", flush=True)
        except Exception as e:
            print(f"      ✗ 失败：{e}", flush=True)
            raise
    training_store.replace_segments(tid, segs)
    training_store.update_tutorial(tid, status="draft")
    print(f"  大纲 {len(segs)} 章 → tutorial={tid}", flush=True)
    return tid


def render_all(tid: str):
    segs = training_store.list_segments(tid)
    for i, seg in enumerate(segs, 1):
        if seg["status"] == "ready" and seg["final_path"]:
            print(f"  [{i}/{len(segs)}] {seg['title']} 已就绪，跳过", flush=True)
            continue
        t0 = time.time()
        print(f"  [{i}/{len(segs)}] {seg['title']} 渲染中…", flush=True)
        try:
            seg_id = seg["id"]
            training_store.update_segment(seg_id, status="generating")
            zh_s, en_s = _board_sentences(seg)
            # 分块合成整章语音（避免长文本 TTS 超时），拿到每句实际时长
            apath, per_dur = audio_gen.generate_speech_sentences(zh_s, base_name=f"seg_{seg_id}")
            dur = audio_gen._probe_duration(apath)
            srt = audio_gen.AUDIO_DIR / f"{seg_id}.srt"
            audio_gen.build_bilingual_srt_timed(zh_s, en_s, per_dur, srt)
            final = audio_gen.compose_board(seg["title"], _board_points(seg), apath, srt,
                                            out_name=f"seg_{seg_id}.mp4")
            training_store.update_segment(seg_id, final_path=final, status="ready")
            print(f"      ✓ 完成 ({time.time()-t0:.0f}s, {dur:.0f}s 视频)", flush=True)
        except Exception as e:
            training_store.update_segment(seg["id"], status="failed")
            print(f"      ✗ 失败 ({time.time()-t0:.0f}s)：{e}", flush=True)

    segs2 = training_store.list_segments(tid)
    if segs2 and all(s["status"] == "ready" for s in segs2):
        training_store.update_tutorial(tid, status="ready")
        print(f"  ✓ 教程「{TOPIC}」全部就绪", flush=True)
    else:
        done = sum(1 for s in segs2 if s["status"] == "ready")
        print(f"  ⚠ {done}/{len(segs2)} 章就绪", flush=True)


def main():
    only_outline = "--outline" in sys.argv
    force_outline = "--force-outline" in sys.argv
    print(f"=== 重构 {TOPIC}：8 章逐句讲解 + 中英双语字幕 ===", flush=True)
    get_engine()

    existing = _find_tutorial()
    if existing and training_store.list_segments(existing["id"]) and not force_outline:
        tid = existing["id"]
        print(f"  复用已有大纲 tutorial={tid}（{len(training_store.list_segments(tid))} 章），不重新生成", flush=True)
    else:
        tid = build_outline()
    if only_outline:
        print("=== 仅大纲，结束 ===", flush=True)
        return
    render_all(tid)
    print("=== 结束 ===", flush=True)


if __name__ == "__main__":
    main()
