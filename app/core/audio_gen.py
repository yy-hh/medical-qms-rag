"""中文语音讲解（TTS）+ 音视频合成 + 中英双语字幕烧录。

- TTS 走 Poe gemini-2.5-pro-tts（专业播音腔、比 minimax 更自然），流式返回
  末尾带音频直链（.wav），去掉机器人感。
- 合成策略「语音为主、视频铺底」：以语音时长为成片时长，短视频不够长就循环铺满、
  超出则截断；音轨用 TTS 语音。
- 字幕：按语音时长把中文讲解词、英文翻译各自均分到分句，生成 SRT（中文在上、英文在下），
  用 ffmpeg subtitles 滤镜烧录进画面（Noto CJK 字体，双语常显）。
"""
import logging
import re
import subprocess
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.rag_engine import curl_chat_stream

logger = logging.getLogger(__name__)

TTS_MODEL = "gemini-2.5-pro-tts"

# 播音风格提示：让 Gemini TTS 用沉稳专业的播音腔朗读，去掉机器人感
_TTS_STYLE = "你是专业播音员。请用沉稳、专业、亲和的中文播音腔，语速平稳自然地朗读用户提供的培训讲解文本。只朗读文本本身，不要念出任何说明或指令。"

BASE_DIR = Path(__file__).resolve().parent.parent.parent
VIDEO_DIR = BASE_DIR / "static" / "videos"
AUDIO_DIR = BASE_DIR / "static" / "audio"
CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_FALLBACK_FONT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"

# 音频链接可能是 markdown [Download Audio](url) 或裸 URL；宽松匹配 http(s) 的音频文件
_AUDIO_URL_RE = re.compile(r"https?://[^\s)\"'<>]+\.(?:mp3|wav|m4a|aac)(?:\?[^\s)\"'<>]*)?", re.I)


def _api_key() -> str:
    return settings.api_key or settings.anthropic_api_key


def _font_path() -> str:
    if Path(CJK_FONT).exists():
        return CJK_FONT
    return _FALLBACK_FONT


def generate_speech(text: str, retries: int = 2) -> str:
    """把中文讲解词转成语音，返回音频直链 URL。

    TTS 偶发返回空/无链接，重试几次；全部失败才抛 RuntimeError。
    """
    last = ""
    for attempt in range(retries + 1):
        try:
            gen = curl_chat_stream(
                api_key=_api_key(),
                base_url=settings.api_base_url,
                model=TTS_MODEL,
                messages=[
                    {"role": "system", "content": _TTS_STYLE},
                    {"role": "user", "content": text},
                ],
                max_tokens=512,
                connect_timeout=15,
                max_time=180,
            )
            full = ""
            for chunk in gen:
                if not chunk.choices:
                    continue
                piece = getattr(chunk.choices[0].delta, "content", None)
                if piece:
                    full += piece
            m = _AUDIO_URL_RE.search(full)
            if m:
                return m.group(0)
            last = full[:200]
        except Exception as e:
            last = str(e)[:200]
        logger.warning("TTS 无有效音频链接（第 %d 次）：%s", attempt + 1, last)
    raise RuntimeError(f"未能从 TTS 返回中解析音频链接：{last}")


def download_audio(url: str, filename: str = None) -> Path:
    """下载音频到 static/audio/，返回本地绝对路径。"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = filename or f"{uuid.uuid4().hex[:16]}.mp3"
    dest = AUDIO_DIR / name
    proc = subprocess.run(
        ["curl", "-sSL", "--max-time", "60", "-o", str(dest), url],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"音频下载失败（curl 退出 {proc.returncode}）：{proc.stderr[:200]}")
    return dest


def _detect_silences(path: Path, noise_db: int = -30, min_dur: float = 0.18):
    """检测音频中的静音段，返回 [(start, end)...]（秒）。用于把句边界对齐到真实停顿。"""
    try:
        out = subprocess.run(
            ["ffmpeg", "-i", str(path), "-af",
             f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120).stderr
    except Exception:
        return []
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def _align_sentences_by_silence(group: list, cdur: float, path: Path):
    """把一块内各句时长对齐到真实语音停顿：先用字数占比得先验边界，再就近吸附到
    检测出的静音段中点（TTS 在句末/句间的停顿），使字幕起止贴合实际语音，消除块内累积漂移。

    仅在检测到足够停顿时启用；否则回退到字数占比估算。返回该块每句时长列表。"""
    n = len(group)
    weights = [max(len(s), 1) for s in group]
    tot = sum(weights)
    est_dur = [cdur * w / tot if tot else 0.0 for w in weights]
    if n <= 1 or cdur <= 0:
        return est_dur

    # 字数占比得到的先验「句末边界」（n-1 个内部边界，不含 0 和 cdur）
    est_bounds, acc = [], 0.0
    for w in weights[:-1]:
        acc += w
        est_bounds.append(cdur * acc / tot)

    sils = _detect_silences(path)
    # 取时长 >= 0.22s 的较明显停顿的中点作为候选句边界（滤掉极短的词间气口）
    cands = sorted((s + e) / 2 for s, e in sils if (e - s) >= 0.22 and 0 < (s + e) / 2 < cdur)
    if len(cands) < len(est_bounds):
        return est_dur  # 停顿点不足，无法可靠对齐，回退

    # 每个先验边界就近吸附到最近候选停顿；保证单调、不同边界不吸到同一点
    used, snapped, last = set(), [], 0.0
    for e in est_bounds:
        order = sorted(range(len(cands)), key=lambda k: abs(cands[k] - e))
        pick = next((k for k in order if k not in used and cands[k] > last + 0.15), None)
        if pick is None:
            snapped.append(max(e, last + 0.15))  # 无合适候选，退回先验
        else:
            used.add(pick)
            snapped.append(cands[pick])
        last = snapped[-1]
    # 边界 → 每句时长
    bounds = [0.0] + snapped + [cdur]
    return [max(bounds[i + 1] - bounds[i], 0.05) for i in range(n)]


def generate_speech_sentences(zh_sents: list, base_name: str, chunk_sents: int = 8):
    """把逐句中文列表分块合成语音并拼接成一整段音频。

    长章节整段 TTS 会超时（curl 28），故按 chunk_sents 句一组分块，逐块生成+下载，
    再用 ffmpeg concat 拼成一个 mp3。返回 (整段音频路径, 每句时长列表)。

    每句时长由「块内静音检测对齐真实停顿」得出（_align_sentences_by_silence），
    避免旧的纯字数占比估算在块内造成的字幕漂移；检测不到足够停顿时回退字数占比。
    """
    zh_sents = [s for s in zh_sents if s and s.strip()]
    if not zh_sents:
        raise RuntimeError("无可合成的句子")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    chunk_paths = []
    per_sentence_dur = []
    for ci in range(0, len(zh_sents), chunk_sents):
        group = zh_sents[ci:ci + chunk_sents]
        text = "".join(g if g.endswith(("。", "！", "？", ".", "!", "?")) else g + "。" for g in group)
        url = generate_speech(text)
        cpath = download_audio(url, filename=f"{base_name}_c{ci//chunk_sents}.mp3")
        cdur = _probe_duration(cpath) or 0.0
        chunk_paths.append(cpath)
        # 块内按真实语音停顿对齐每句时长（消除累积漂移）
        per_sentence_dur.extend(_align_sentences_by_silence(group, cdur, cpath))

    # ffmpeg concat 拼接
    out = AUDIO_DIR / f"{base_name}.mp3"
    if len(chunk_paths) == 1:
        chunk_paths[0].rename(out)
    else:
        listfile = AUDIO_DIR / f"{base_name}_list.txt"
        listfile.write_text("".join(f"file '{p}'\n" for p in chunk_paths), encoding="utf-8")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
               "-c", "copy", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            # copy 失败（编码不一致）时退回重新编码
            proc = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
                 "-c:a", "libmp3lame", "-b:a", "128k", str(out)],
                capture_output=True, text=True, timeout=180)
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(f"音频拼接失败：{proc.stderr[-300:]}")
        listfile.unlink(missing_ok=True)
        for p in chunk_paths:
            p.unlink(missing_ok=True)
    return out, per_sentence_dur


def build_bilingual_srt_timed(zh_sents: list, en_sents: list, per_dur: list, dest: Path) -> Path:
    """用每句实际时长（per_dur）生成中英双语逐句 SRT，时间轴与分块语音精确对齐。"""
    n = min(len(zh_sents), len(en_sents), len(per_dur))
    lines, acc = [], 0.0
    for i in range(n):
        start = acc
        acc += per_dur[i]
        body = zh_sents[i] + ("\n" + en_sents[i] if en_sents[i] else "")
        lines.append(f"{i+1}\n{_fmt_ts(start)} --> {_fmt_ts(acc)}\n{body}\n")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def _wrap_cjk(text: str, limit: int = 22) -> list:
    """把一整句中文按次级标点切成不超过 limit 字的短块（720p 单行不溢出）；仍超长则硬断。"""
    parts = re.split(r"(?<=[，、：；。？！,;?!])", (text or "").strip())
    out, buf = [], ""
    for p in parts:
        if len(buf) + len(p) <= limit:
            buf += p
        else:
            if buf:
                out.append(buf)
            while len(p) > limit:
                out.append(p[:limit]); p = p[limit:]
            buf = p
    if buf:
        out.append(buf)
    return [c for c in (s.strip() for s in out) if c] or ([text.strip()] if text.strip() else [])


def build_zh_srt_timed(zh_sents: list, per_dur: list, dest: Path) -> Path:
    """用每句实际时长生成仅中文单语 SRT。长句按标点二次折成多条短 cue（按字数比例分时），
    保证单行不横向溢出画面，也不向上顶到黑板要点。"""
    n = min(len(zh_sents), len(per_dur))
    lines, acc, idx = [], 0.0, 1
    for i in range(n):
        sent_start = acc
        sent_dur = per_dur[i]
        acc += sent_dur
        chunks = _wrap_cjk(zh_sents[i])
        total_chars = sum(len(c) for c in chunks) or 1
        cur = sent_start
        for j, c in enumerate(chunks):
            if j == len(chunks) - 1:
                cend = acc  # 末块对齐句尾，避免累积误差
            else:
                cend = cur + sent_dur * len(c) / total_chars
            lines.append(f"{idx}\n{_fmt_ts(cur)} --> {_fmt_ts(cend)}\n{c}\n")
            idx += 1
            cur = cend
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def _probe_duration(path: Path) -> float:
    """用 ffprobe 取媒体时长（秒）。失败返回 0。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def _fmt_ts(sec: float) -> str:
    """秒 → SRT 时间戳 HH:MM:SS,mmm。"""
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_sentences(text: str) -> list:
    """按中文/英文标点切句，去空。"""
    parts = re.split(r"(?<=[。！？；.!?;])\s*", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(text: str, limit: int = 20) -> list:
    """把讲解词切成适合单行字幕的短块：先按句末标点切，过长的再按逗号/顿号切，仍超长则硬断。"""
    out = []
    for sent in _split_sentences(text) or ([text] if text else []):
        # 按次级标点（逗号/顿号/冒号）进一步切
        parts = re.split(r"(?<=[，、：,])", sent)
        buf = ""
        for p in parts:
            if len(buf) + len(p) <= limit:
                buf += p
            else:
                if buf:
                    out.append(buf)
                # 单块仍超长则按 limit 硬断
                while len(p) > limit:
                    out.append(p[:limit]); p = p[limit:]
                buf = p
        if buf:
            out.append(buf)
    return [c.strip("，、：,") for c in out if c.strip()]


def build_srt(text: str, duration: float, dest: Path) -> Path:
    """按总时长把中文讲解词切成短块并均分时间，生成单语中文 SRT。"""
    chunks = _chunk_text(text)
    n = len(chunks)
    if n == 0 or duration <= 0:
        dest.write_text(f"1\n00:00:00,000 --> {_fmt_ts(max(duration, 1))}\n{text}\n\n", encoding="utf-8")
        return dest
    seg = duration / n
    lines = [f"{i+1}\n{_fmt_ts(i*seg)} --> {_fmt_ts((i+1)*seg)}\n{c}\n" for i, c in enumerate(chunks)]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def build_bilingual_srt(zh: str, en: str, duration: float, dest: Path,
                        zh_sents: list = None, en_sents: list = None) -> Path:
    """按总时长生成中英双语 SRT（中文行在上、英文行在下），逐句对齐。

    优先用调用方传入的逐句配对列表 zh_sents/en_sents（长度相同、一一对应），
    这样时间轴天然对齐、双语常显；未传时退回按标点切句 + 比例对齐。
    """
    if zh_sents and en_sents and len(zh_sents) == len(en_sents):
        zh_s, en_s = zh_sents, en_sents
        n = len(zh_s)
        if n == 0 or duration <= 0:
            dest.write_text(f"1\n00:00:00,000 --> {_fmt_ts(max(duration, 1))}\n{zh}\n{en}\n\n", encoding="utf-8")
            return dest
        # 按各句中文字数占比分配时长（长句停留更久），更贴合语音节奏
        weights = [max(len(s), 1) for s in zh_s]
        tot = sum(weights)
        lines, acc = [], 0.0
        for i in range(n):
            start = acc
            acc += duration * weights[i] / tot
            end = duration if i == n - 1 else acc
            body = zh_s[i] + ("\n" + en_s[i] if en_s[i] else "")
            lines.append(f"{i+1}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{body}\n")
        dest.write_text("\n".join(lines), encoding="utf-8")
        return dest

    zh_s = _split_sentences(zh) or [zh or ""]
    en_s = _split_sentences(en) or [en or ""]
    n = max(len(zh_s), len(en_s))
    if n == 0 or duration <= 0:
        dest.write_text(
            f"1\n00:00:00,000 --> {_fmt_ts(max(duration, 1))}\n{zh}\n{en}\n\n",
            encoding="utf-8")
        return dest
    seg = duration / n
    lines = []
    for i in range(n):
        z = zh_s[int(i * len(zh_s) / n)] if zh_s else ""
        e = en_s[int(i * len(en_s) / n)] if en_s else ""
        start = _fmt_ts(i * seg)
        end = _fmt_ts((i + 1) * seg)
        body = z + ("\n" + e if e else "")
        lines.append(f"{i+1}\n{start} --> {end}\n{body}\n")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def compose(video_path: Path, audio_path: Path, srt_path: Path, out_name: str = None) -> str:
    """把语音合进视频（语音为主、视频铺底循环/截断）并烧录双语字幕。

    返回相对 static 的成片路径（如 videos/xxx_final.mp4）。
    """
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or f"{uuid.uuid4().hex[:16]}_final.mp4"
    if not name.endswith(".mp4"):
        name += ".mp4"
    out = VIDEO_DIR / name

    dur = _probe_duration(audio_path)  # 以语音时长为成片时长
    if dur <= 0:
        dur = _probe_duration(video_path) or 10.0

    font = _font_path()
    # subtitles 滤镜：force_style 指定中文字体，避免方块；字号/描边保证可读
    srt_esc = str(srt_path).replace("'", r"\'").replace(":", r"\:")
    vf = (
        f"subtitles='{srt_esc}':force_style="
        f"'FontName=Noto Sans CJK SC,Fontsize=18,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=24'"
    )
    # -stream_loop -1 让铺底视频无限循环，-t dur 按语音时长截断；音轨用 TTS 语音。
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(video_path),
        "-i", str(audio_path),
        "-t", f"{dur:.3f}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg 合成失败（退出 {proc.returncode}）：{proc.stderr[-400:]}")
    _ = font  # font 已在 force_style 里按名指定，这里仅保留探测
    return f"videos/{name}"


BLACKBOARD_BG = VIDEO_DIR / "blackboard_bg.jpg"


def _ass_escape(text: str) -> str:
    """drawtext 文本转义：反斜杠、冒号、百分号。

    ffmpeg filtergraph 的 text='...' 用单引号包裹，内部单引号无法用反斜杠转义
    （\\' 不生效，会提前闭合 text 破坏整个 filtergraph），故把 ASCII 单/双引号
    统一换成中文弯引号——既规避 filter 语法冲突，中文板书里也更规范。
    """
    text = (text or "").replace("'", "’").replace('"', "”")
    return text.replace("\\", r"\\").replace(":", r"\:").replace("%", r"\%")


def compose_board(title: str, points: list, audio_path: Path, srt_path: Path,
                  out_name: str = None) -> str:
    """固定黑板底图 + 准确中文板书（drawtext 渲染标题与要点）+ TTS 语音 + 底部讲解字幕。

    与 Seedance 生成不同：文字由 ffmpeg 精确渲染，不会出现错字，适合展示具体条款/要点。
    返回相对 static 的成片路径。
    """
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or f"{uuid.uuid4().hex[:16]}_board.mp4"
    if not name.endswith(".mp4"):
        name += ".mp4"
    out = VIDEO_DIR / name
    if not BLACKBOARD_BG.exists():
        raise RuntimeError(f"黑板底图不存在：{BLACKBOARD_BG}")

    dur = _probe_duration(audio_path) or 10.0
    font = _font_path()
    pts = [p.strip() for p in (points or []) if p.strip()][:5]

    # drawtext 逐条叠加：标题居中偏上，要点依次左对齐向下排列（粉笔白字）
    draws = []
    draws.append(
        f"drawtext=fontfile='{font}':text='{_ass_escape(title)}':"
        f"fontcolor=white:fontsize=52:x=(w-text_w)/2:y=140:"
        f"shadowcolor=black@0.3:shadowx=2:shadowy=2"
    )
    for i, p in enumerate(pts):
        draws.append(
            f"drawtext=fontfile='{font}':text='{_ass_escape(str(i+1)+'. '+p)}':"
            f"fontcolor=white:fontsize=40:x=260:y={250 + i*72}:"
            f"shadowcolor=black@0.3:shadowx=2:shadowy=2"
        )
    # 底部讲解字幕（narration SRT）
    srt_esc = str(srt_path).replace("'", r"\'").replace(":", r"\:")
    # MarginL/R 留边强制换行，避免长句超出画面；MarginV 抬高离底边
    draws.append(
        f"subtitles='{srt_esc}':force_style="
        f"'FontName=Noto Sans CJK SC,Fontsize=18,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,"
        f"MarginV=40,MarginL=80,MarginR=80'"
    )
    vf = ",".join(draws)

    # 底图 loop 成视频流，配 TTS 语音，按语音时长截断
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(BLACKBOARD_BG),
        "-i", str(audio_path),
        "-t", f"{dur:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"黑板合成失败（退出 {proc.returncode}）：{proc.stderr[-400:]}")
    return f"videos/{name}"


def compose_board_sections(chapter_title: str, sections: list, audio_path: Path,
                           srt_path: Path, out_name: str = None) -> str:
    """按小节分屏的黑板讲解视频：随讲解推进整屏切换。

    sections: [{"title": 小节名, "points": [要点...], "start": 起始秒, "end": 结束秒}]
      每个小节在 [start, end) 时段显示一屏：顶部章标题（常显）+ 中部「▶ 小节名」+ 下方该小节要点。
    字幕：底部仅中文单行（srt_path 已是中文单语 SRT）。
    """
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    name = out_name or f"{uuid.uuid4().hex[:16]}_board.mp4"
    if not name.endswith(".mp4"):
        name += ".mp4"
    out = VIDEO_DIR / name
    if not BLACKBOARD_BG.exists():
        raise RuntimeError(f"黑板底图不存在：{BLACKBOARD_BG}")

    dur = _probe_duration(audio_path) or 10.0
    font = _font_path()

    draws = []
    # 章标题：常显，居中偏上
    draws.append(
        f"drawtext=fontfile='{font}':text='{_ass_escape(chapter_title)}':"
        f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=90:"
        f"shadowcolor=black@0.3:shadowx=2:shadowy=2"
    )
    # 各小节分屏：用 enable=between(t,start,end) 控制该屏出现时段
    for sec in sections:
        s = float(sec.get("start", 0))
        e = float(sec.get("end", dur))
        en = f"between(t,{s:.2f},{e:.2f})"
        sec_title = "▶ " + str(sec.get("title", "")).strip()
        draws.append(
            f"drawtext=fontfile='{font}':text='{_ass_escape(sec_title)}':"
            f"fontcolor=white:fontsize=40:x=200:y=210:enable='{en}':"
            f"shadowcolor=black@0.3:shadowx=2:shadowy=2"
        )
        pts = [p.strip() for p in (sec.get("points") or []) if p.strip()][:5]
        for i, p in enumerate(pts):
            draws.append(
                f"drawtext=fontfile='{font}':text='{_ass_escape('• ' + p)}':"
                f"fontcolor=white:fontsize=32:x=260:y={300 + i*60}:enable='{en}':"
                f"shadowcolor=black@0.3:shadowx=2:shadowy=2"
            )
    # 底部中文字幕（单行）
    srt_esc = str(srt_path).replace("'", r"\'").replace(":", r"\:")
    draws.append(
        f"subtitles='{srt_esc}':force_style="
        f"'FontName=Noto Sans CJK SC,Fontsize=18,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,"
        f"MarginV=32,MarginL=60,MarginR=60'"
    )
    vf = ",".join(draws)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(BLACKBOARD_BG),
        "-i", str(audio_path),
        "-t", f"{dur:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"分屏黑板合成失败（退出 {proc.returncode}）：{proc.stderr[-400:]}")
    return f"videos/{name}"
