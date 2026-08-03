"""重渲染 14971/62304/62366 三门短课的字幕：去掉拼音第二行，改为仅中文单语折行。

不重新生成音频、不改黑板板书（points）。做法：解析每段现有的双语 SRT，取出中文行与每
个 cue 的时长，用 audio_gen.build_zh_srt_timed 重写成单中文折行 SRT，再用现有音频经
compose_board 复用铺底黑板重渲染。时间轴沿用旧 SRT，天然与语音对齐。
"""
import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, audio_gen
from app.api.training import _board_points

TOPICS = [
    "ISO 14971 风险管理流程",
    "IEC 62304 医疗器械软件生命周期",
    "IEC 62366 可用性工程与人因",
]

_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _to_sec(ts: str) -> float:
    h, m, s, ms = _TS.match(ts).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _is_pinyin_or_ascii(line: str) -> bool:
    """判断是否为拼音/ASCII 行（无 CJK 字符即视为非中文正文行，丢弃）。"""
    return not re.search(r"[一-鿿]", line)


def parse_srt_zh(srt_path):
    """解析双语 SRT，返回 (zh_sents, per_dur)：每个 cue 的中文行与时长。"""
    zh_sents, per_dur = [], []
    blocks = re.split(r"\n\s*\n", srt_path.read_text(encoding="utf-8").strip())
    for blk in blocks:
        lines = [l for l in blk.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.search(r"([\d:,\.]+)\s*-->\s*([\d:,\.]+)", lines[1])
        if not m:
            continue
        start, end = _to_sec(m.group(1)), _to_sec(m.group(2))
        zh = " ".join(l for l in lines[2:] if not _is_pinyin_or_ascii(l)).strip()
        if not zh:
            continue
        zh_sents.append(zh)
        per_dur.append(max(end - start, 0.1))
    return zh_sents, per_dur


def rerender(seg):
    sid = seg["id"]
    apath = audio_gen.AUDIO_DIR / f"seg_{sid}.mp3"
    old_srt = audio_gen.AUDIO_DIR / f"{sid}.srt"
    if not apath.exists():
        raise RuntimeError(f"音频不存在：{apath}")
    if not old_srt.exists():
        raise RuntimeError(f"旧字幕不存在：{old_srt}")

    zh, per = parse_srt_zh(old_srt)
    if not zh:
        raise RuntimeError("旧字幕未解析出中文行")

    # 覆盖写回单中文折行 SRT（build_zh_srt_timed 已含折行逻辑）
    audio_gen.build_zh_srt_timed(zh, per, old_srt)

    final = audio_gen.compose_board(
        seg["title"], _board_points(seg), apath, old_srt, out_name=f"seg_{sid}.mp4")
    training_store.update_segment(sid, final_path=final, status="ready")
    return len(zh)


def main():
    tuts = {t["topic"]: t for t in training_store.list_tutorials() if t["kind"] == "video"}
    for topic in TOPICS:
        t = tuts.get(topic)
        if not t:
            print(f"跳过（未找到）：{topic}", flush=True)
            continue
        print(f"\n=== {topic} ===", flush=True)
        segs = training_store.list_segments(t["id"])
        for i, seg in enumerate(segs, 1):
            t0 = time.time()
            print(f"  [{i}/{len(segs)}] {seg['title']} …", flush=True)
            try:
                n = rerender(seg)
                print(f"      ✓ {time.time()-t0:.0f}s, {n} 句", flush=True)
            except Exception as e:
                print(f"      ✗ 失败：{e}", flush=True)
        if all(s["status"] == "ready" for s in training_store.list_segments(t["id"])):
            training_store.update_tutorial(t["id"], status="ready")
            print("  ✓ 教程就绪", flush=True)
    print("\n=== 结束 ===", flush=True)


if __name__ == "__main__":
    main()
