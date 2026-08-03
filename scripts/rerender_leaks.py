"""定向重渲「TTS 提示词泄漏」的段，带 whisper 泄漏守卫。

背景：Poe gemini-2.5-pro-tts **偶发**把 system 里的播音风格提示（_TTS_STYLE）念进音频
开头（分块合成时只可能出现在第一块）。改 system/user 消息结构不能根除（偶发）。故这里
「合成→whisper 转写开头→命中提示词特征则重新合成，最多 N 次」直到干净，再渲染分屏。

whisper 模型用本地 /tmp/wmodel（faster-whisper base，见项目记忆）。合成走修复后的
generate_speech_sentences（system 放风格、user 只放正文）。

用法：python scripts/rerender_leaks.py            # 重渲下方 LEAK_IDS 全部
      python scripts/rerender_leaks.py <sid> ...   # 只重渲指定 sid
"""
import sys, os, time, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core import training_store, audio_gen  # noqa
from app.api.training import _board_sentences

WMODEL = "/tmp/wmodel"
MAX_SYNTH = 6  # 单块最多重合成次数

# 泄漏特征（含 whisper 对语音的谐音误转写变体）
_LEAK_PAT = re.compile(
    r'請用|请用|播音|部印|波音|波英|不英|博音|博印|朗讀|朗读|廊毒|廊獨|浪都|浪獨|'
    r'培訓講|培训讲|培訓獎|培訓將|講解內容|讲解内容|獎解內容|將解內容|'
    r'亲和|親和|沉穩|沉稳|語速平|语速平|平穩自然|平文自然')

LEAK_IDS = [
    "0bcbcaaee1d7", "40dafc4bc7ce", "6cf4373dab58",   # 62304
    "33e7770d7571", "6f1d6cd08e8f", "ebb27cf554ae",   # 62366
    "3ebc7a6bd037", "486bd66d96cb",                   # 14971
    "5d079fdcd1ac",                                   # 注册办法
    "df381922d514",                                   # GMP
    "5b49b53c9b99",                                   # 条例
    "041ac11a2461", "3decab1f827e",                   # GSP
]

# faster-whisper 只装在系统 python（/usr/bin，~/.local），medical_qms 环境没有。
# 故转写检测走系统 python 子进程，主脚本仍在 medical_qms 跑（需 jieba/app 依赖）。
_SYS_PY = "/usr/bin/python3"
_ASR_SNIPPET = (
    "import sys;from faster_whisper import WhisperModel;"
    f"m=WhisperModel(r'{WMODEL}',device='cpu',compute_type='int8');"
    "segs,_=m.transcribe(sys.argv[1],beam_size=1,clip_timestamps='0,12');"
    "print(''.join(s.text for s in segs).strip()[:60])"
)


def _transcribe_head(mp3_path) -> str:
    import subprocess
    out = subprocess.run([_SYS_PY, "-c", _ASR_SNIPPET, str(mp3_path)],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(f"转写检测失败：{out.stderr[-200:]}")
    return out.stdout.strip()


def _head_leaks(mp3_path) -> bool:
    """转写音频开头 12s，命中提示词特征返回 True。"""
    return bool(_LEAK_PAT.search(_transcribe_head(mp3_path)))


def _synth_clean_first_chunk(zh_s, base_name):
    """分块合成整章语音，但对第一块加泄漏守卫：泄漏则重合成该块，最多 MAX_SYNTH 次。
    返回 (整段音频路径, 每句时长列表)。逻辑同 generate_speech_sentences，仅第一块加守卫。
    """
    chunk_sents = 8
    audio_gen.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    chunk_paths, per = [], []
    for ci in range(0, len(zh_s), chunk_sents):
        group = zh_s[ci:ci + chunk_sents]
        text = "".join(g if g.endswith(("。", "！", "？", ".", "!", "?")) else g + "。"
                       for g in group)
        cpath = audio_gen.AUDIO_DIR / f"{base_name}_c{ci // chunk_sents}.mp3"
        is_first = (ci == 0)
        for attempt in range(1, MAX_SYNTH + 1):
            url = audio_gen.generate_speech(text)
            audio_gen.download_audio(url, filename=cpath.name)
            if not is_first or not _head_leaks(cpath):
                if is_first and attempt > 1:
                    print(f"      第一块第{attempt}次合成干净", flush=True)
                break
            print(f"      第一块第{attempt}次仍泄漏，重合成…", flush=True)
        else:
            raise RuntimeError(f"第一块 {MAX_SYNTH} 次合成均泄漏")
        cdur = audio_gen._probe_duration(cpath) or 0.0
        chunk_paths.append(cpath)
        per.extend(audio_gen._align_sentences_by_silence(group, cdur, cpath))

    out = audio_gen.AUDIO_DIR / f"{base_name}.mp3"
    if len(chunk_paths) == 1:
        chunk_paths[0].rename(out)
    else:
        listfile = audio_gen.AUDIO_DIR / f"{base_name}_list.txt"
        listfile.write_text("".join(f"file '{p}'\n" for p in chunk_paths), encoding="utf-8")
        import subprocess
        proc = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
                               str(listfile), "-c", "copy", str(out)],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            proc = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i",
                                   str(listfile), "-c:a", "libmp3lame", "-b:a", "128k",
                                   str(out)], capture_output=True, text=True, timeout=180)
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(f"音频拼接失败：{proc.stderr[-300:]}")
        listfile.unlink(missing_ok=True)
        for p in chunk_paths:
            p.unlink(missing_ok=True)
    return out, per


def render_seg_guarded(seg):
    sid = seg["id"]
    v = json.loads(seg["visual_prompt"])
    zh = v.get("zh") or []
    secmap = v.get("secmap") or []
    zh_s, _ = _board_sentences(seg)
    zh_s = zh_s or zh
    apath, per = _synth_clean_first_chunk(zh_s, base_name=f"seg_{sid}")
    dur = audio_gen._probe_duration(apath) or 0.0
    if dur <= 0:
        raise RuntimeError("音频时长为 0")
    starts = [0.0]
    for d in per:
        starts.append(starts[-1] + d)
    srt = audio_gen.AUDIO_DIR / f"{sid}.srt"
    audio_gen.build_zh_srt_timed(zh_s, per, srt)
    sections = []
    for sm in secmap:
        si = max(0, min(sm["start_idx"], len(zh_s) - 1))
        ei = max(si, min(sm["end_idx"], len(zh_s) - 1))
        sections.append({"title": sm["title"], "points": sm.get("points") or [],
                         "start": starts[si],
                         "end": starts[ei + 1] if ei + 1 < len(starts) else dur})
    if sections:
        sections[0]["start"] = 0.0
        sections[-1]["end"] = dur
    final = audio_gen.compose_board_sections(seg["title"], sections, apath, srt,
                                             out_name=f"seg_{sid}.mp4")
    training_store.update_segment(sid, final_path=final, status="ready")
    return dur, len(sections)


def main():
    ids = sys.argv[1:] or LEAK_IDS
    print(f"待重渲 {len(ids)} 段（带泄漏守卫）", flush=True)
    ok = 0
    for i, sid in enumerate(ids, 1):
        seg = training_store.get_segment(sid)
        if not seg:
            print(f"[{i}/{len(ids)}] {sid} 不存在，跳过", flush=True)
            continue
        title = seg["title"]
        t0 = time.time()
        try:
            training_store.update_segment(sid, status="generating")
            dur, ns = render_seg_guarded(training_store.get_segment(sid))
            print(f"[{i}/{len(ids)}] ✓ {title[:22]} {time.time()-t0:.0f}s "
                  f"{dur:.0f}s {ns}屏", flush=True)
            ok += 1
        except Exception as e:
            training_store.update_segment(sid, status="failed")
            print(f"[{i}/{len(ids)}] ✗ {title[:22]} 失败({time.time()-t0:.0f}s)：{e}",
                  flush=True)
    print(f"=== 完成 {ok}/{len(ids)} ===", flush=True)


if __name__ == "__main__":
    main()
