"""预生成培训视频教程（分段黑板板书 + Seedance 自带中文旁白）。

供管理员离线批量生成好，用户端只需观看。直接在进程内调用核心模块（不走 HTTP/SSE），
串行处理避免 Poe 限流。可重入：已 ready 的分段/教程跳过。

用法：
  python scripts/pregen_training.py                # 生成默认核心主题
  python scripts/pregen_training.py "主题A" "主题B"  # 生成指定主题
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, video_gen, audio_gen
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.api.training import SEGMENT_SYSTEM, _parse_segments, _board_points, _board_sentences

# 默认预生成的核心主题
DEFAULT_TOPICS = [
    "ISO 13485 质量管理体系概览",
    "IEC 62304 医疗器械软件生命周期",
    "ISO 14971 风险管理流程",
    "IEC 62366 可用性工程与人因",
]


def _find_tutorial(topic: str):
    """按主题找已有的视频教程（避免重复建）。"""
    for t in training_store.list_tutorials():
        if t["kind"] == "video" and t["topic"] == topic:
            return t
    return None


def make_outline(topic: str) -> str:
    """调 LLM 生成分段大纲，落库，返回 tutorial_id。已存在分段则复用。"""
    existing = _find_tutorial(topic)
    if existing and training_store.list_segments(existing["id"]):
        print(f"  已有分段，复用 tutorial={existing['id']}", flush=True)
        return existing["id"]

    tid = existing["id"] if existing else training_store.save_tutorial(
        topic=topic, kind="video", status="draft")
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SEGMENT_SYSTEM},
            {"role": "user", "content": f"请把培训主题「{topic}」拆成若干知识小段用于制作分段培训短视频。"},
        ],
    )
    segs = _parse_segments(resp.choices[0].message.content or "")
    if not segs:
        raise RuntimeError("分段解析失败")
    training_store.replace_segments(tid, segs)
    print(f"  大纲 {len(segs)} 段 → tutorial={tid}", flush=True)
    return tid


def render_segment(seg: dict):
    """渲染单段，按 seg_kind 分流：seedance=AI黑板动画+自带配音；board=固定黑板+TTS+中文字幕。落库。"""
    seg_id = seg["id"]
    training_store.update_segment(seg_id, status="generating")
    if seg["seg_kind"] == "board":
        aurl = audio_gen.generate_speech(seg["narration"] or seg["title"])
        apath = audio_gen.download_audio(aurl, filename=f"seg_{seg_id}.mp3")
        dur = audio_gen._probe_duration(apath)
        srt = audio_gen.AUDIO_DIR / f"{seg_id}.srt"
        zh_s, en_s = _board_sentences(seg)
        audio_gen.build_bilingual_srt(seg["narration"], seg.get("narration_en", ""), dur, srt,
                                      zh_sents=zh_s, en_sents=en_s)
        final = audio_gen.compose_board(seg["title"], _board_points(seg), apath, srt,
                                        out_name=f"seg_{seg_id}.mp4")
    else:
        vprompt = video_gen.build_blackboard_prompt(seg["title"], _board_points(seg), seg["narration"])
        vurl = video_gen.generate_video(vprompt)
        final = video_gen.download_video(vurl, filename=f"seg_{seg_id}.mp4")
    training_store.update_segment(seg_id, final_path=final, status="ready")
    return final


def main():
    topics = sys.argv[1:] or DEFAULT_TOPICS
    print(f"预生成 {len(topics)} 个主题：{topics}", flush=True)
    get_engine()  # 预热

    for ti, topic in enumerate(topics, 1):
        print(f"\n=== [{ti}/{len(topics)}] {topic} ===", flush=True)
        try:
            tid = make_outline(topic)
        except Exception as e:
            print(f"  ✗ 大纲失败，跳过：{e}", flush=True)
            continue

        segs = training_store.list_segments(tid)
        for si, seg in enumerate(segs, 1):
            if seg["status"] == "ready" and seg["final_path"]:
                print(f"  [{si}/{len(segs)}] {seg['title']} 已就绪，跳过", flush=True)
                continue
            t0 = time.time()
            print(f"  [{si}/{len(segs)}] {seg['title']} 渲染中…", flush=True)
            try:
                render_segment(seg)
                print(f"      ✓ 完成 ({time.time()-t0:.0f}s)", flush=True)
            except Exception as e:
                training_store.update_segment(seg["id"], status="failed")
                print(f"      ✗ 失败 ({time.time()-t0:.0f}s)：{e}", flush=True)

        # 全部 ready 则教程 ready
        segs2 = training_store.list_segments(tid)
        if segs2 and all(s["status"] == "ready" for s in segs2):
            training_store.update_tutorial(tid, status="ready")
            print(f"  ✓ 教程「{topic}」全部就绪", flush=True)
        else:
            done = sum(1 for s in segs2 if s["status"] == "ready")
            print(f"  ⚠ 教程「{topic}」{done}/{len(segs2)} 段就绪", flush=True)

    print("\n=== 预生成结束 ===", flush=True)


if __name__ == "__main__":
    main()
