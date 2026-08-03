"""用已生成的整章音频重渲染 13485 各章视频：分屏黑板（按小节切换）+ 仅中文单行字幕。

不重新生成音频（沿用 static/audio/seg_<id>.mp3）；每句时长按字数占总时长比例估算，
与合成时的分配方式一致，足够驱动字幕与分屏切换。
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, audio_gen

TOPIC = "ISO 13485 质量管理体系概览"


def per_sentence_durations(zh_sents, total):
    weights = [max(len(s), 1) for s in zh_sents]
    tot = sum(weights) or 1
    return [total * w / tot for w in weights]


def rerender(seg):
    sid = seg["id"]
    v = json.loads(seg["visual_prompt"])
    zh = v.get("zh") or []
    secmap = v.get("secmap") or []
    apath = audio_gen.AUDIO_DIR / f"seg_{sid}.mp3"
    if not apath.exists():
        raise RuntimeError(f"音频不存在：{apath}")
    dur = audio_gen._probe_duration(apath) or 0.0
    if dur <= 0:
        raise RuntimeError("音频时长为 0")

    per = per_sentence_durations(zh, dur)
    # 句累计起始时间
    starts = [0.0]
    for d in per:
        starts.append(starts[-1] + d)

    # 仅中文字幕
    srt = audio_gen.AUDIO_DIR / f"{sid}.srt"
    audio_gen.build_zh_srt_timed(zh, per, srt)

    # secmap → 时间区间
    sections = []
    for sm in secmap:
        si = max(0, min(sm["start_idx"], len(zh) - 1))
        ei = max(si, min(sm["end_idx"], len(zh) - 1))
        sections.append({
            "title": sm["title"],
            "points": sm.get("points") or [],
            "start": starts[si],
            "end": starts[ei + 1] if ei + 1 < len(starts) else dur,
        })
    if sections:
        sections[0]["start"] = 0.0
        sections[-1]["end"] = dur

    final = audio_gen.compose_board_sections(
        seg["title"], sections, apath, srt, out_name=f"seg_{sid}.mp4")
    training_store.update_segment(sid, final_path=final, status="ready")
    return dur, len(sections)


def main():
    t = [x for x in training_store.list_tutorials()
         if x["kind"] == "video" and x["topic"] == TOPIC][0]
    for i, seg in enumerate(training_store.list_segments(t["id"]), 1):
        t0 = time.time()
        print(f"  [{i}] {seg['title']} 重渲染中…", flush=True)
        try:
            dur, ns = rerender(seg)
            print(f"      ✓ 完成 ({time.time()-t0:.0f}s, {dur:.0f}s, {ns} 分屏)", flush=True)
        except Exception as e:
            print(f"      ✗ 失败：{e}", flush=True)
    segs = training_store.list_segments(t["id"])
    if all(s["status"] == "ready" for s in segs):
        training_store.update_tutorial(t["id"], status="ready")
        print("  ✓ 教程全部就绪", flush=True)
    print("=== 重渲染结束 ===", flush=True)


if __name__ == "__main__":
    main()
