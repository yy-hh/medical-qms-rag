"""Seedance 视频生成（走 Poe /chat/completions 流式端点）。

用途：生成"黑板板书 + 中文旁白"的培训短视频——Seedance 自带音频，无需外接 TTS/字幕。

实测要点（seedance-2.0）：
- 必须 stream=True。非流式请求会在 180s 超时前拿不到任何结果。
- 生成过程中持续吐进度文本 "Generating video (N/900s elapsed)"。
- 完成时最后一条文本给出视频直链，形如 "...find the video here: https://.../video.mp4"。
- 默认约 5s；传顶层参数 duration=10 可出 ~10s，且带 aac 音轨（中文旁白）。
- 画面能渲染黑板粉笔手写中文（偶有错字，属视频模型渲染文字的固有局限，故提示词要求字少而精）。

复用 rag_engine.curl_chat_stream（curl 子进程流式，绕开本机 httpx 连 Poe/Cloudflare
的 HTTP2 握手不稳问题）。
"""
import logging
import re
import subprocess
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.rag_engine import curl_chat_stream

logger = logging.getLogger(__name__)

# seedance-2.0 画面/板书质量优于 2-fast，且支持 duration 拉长到 10s 带音频
SEEDANCE_MODEL = "seedance-2.0"
SEGMENT_DURATION = 10

BASE_DIR = Path(__file__).resolve().parent.parent.parent
VIDEO_DIR = BASE_DIR / "static" / "videos"

# 从最终文本里抽视频直链：http(s) 开头、.mp4 结尾
_URL_RE = re.compile(r"https?://[^\s\"'<>]+\.mp4")
# 进度文本："Generating video (206/900s elapsed)" → 抽 (206, 900)
_PROGRESS_RE = re.compile(r"\((\d+)\s*/\s*(\d+)s", re.I)


def _api_key() -> str:
    return settings.api_key or settings.anthropic_api_key


def generate_video(prompt: str, on_progress=None, duration: int = SEGMENT_DURATION) -> str:
    """生成视频，返回 Seedance 给出的 mp4 直链 URL。

    duration：目标时长（秒），作为顶层参数传给 Seedance（10s 带中文旁白音频）。
    on_progress(elapsed:int, total:int) 可选回调，每收到一条进度就触发。
    抓不到 URL 抛 RuntimeError。
    """
    messages = [{"role": "user", "content": prompt}]
    # 带 duration 时上限抬到 900s，max_time 留足余量避免出片瞬间被 curl 掐断
    gen = curl_chat_stream(
        api_key=_api_key(),
        base_url=settings.api_base_url,
        model=SEEDANCE_MODEL,
        messages=messages,
        max_tokens=1024,
        connect_timeout=15,
        max_time=920,
        extra={"duration": duration} if duration else None,
    )
    full = ""
    for chunk in gen:
        if not chunk.choices:
            continue
        piece = getattr(chunk.choices[0].delta, "content", None)
        if not piece:
            continue
        full += piece
        if on_progress:
            m = _PROGRESS_RE.search(piece)
            if m:
                try:
                    on_progress(int(m.group(1)), int(m.group(2)))
                except Exception:
                    pass

    m = _URL_RE.search(full)
    if not m:
        raise RuntimeError(f"未能从 Seedance 返回中解析视频链接：{full[:300]}")
    return m.group(0)


def _is_valid_video(path: Path) -> bool:
    """用 ffprobe 确认文件是可解析的视频（有视频流）。

    Seedance 的 CDN 偶发返回错误正文（如 21 字节的 "Internal server error"），
    仅凭 size>0 无法识破，必须探测视频流，否则后续 ffmpeg 合成必然失败。
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return "video" in out.stdout
    except Exception:
        return False


def download_video(url: str, filename: str = None, retries: int = 2) -> str:
    """下载 mp4 到 static/videos/，返回相对 static 的路径（如 videos/xxx.mp4）。

    下载后校验确为可解析视频；无效则重试（CDN 偶发返回错误正文）。
    """
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    name = filename or f"{uuid.uuid4().hex[:16]}.mp4"
    if not name.endswith(".mp4"):
        name += ".mp4"
    dest = VIDEO_DIR / name
    last = ""
    for attempt in range(retries + 1):
        proc = subprocess.run(
            ["curl", "-sSL", "--max-time", "120", "-o", str(dest), url],
            capture_output=True, text=True,
        )
        if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 1024 and _is_valid_video(dest):
            return f"videos/{name}"
        # 无效：记录原因、删除坏文件后重试
        try:
            size = dest.stat().st_size if dest.exists() else 0
            head = dest.read_bytes()[:60] if dest.exists() and size < 200 else b""
        except Exception:
            size, head = 0, b""
        last = f"curl={proc.returncode} size={size} head={head!r}"
        if dest.exists():
            try:
                dest.unlink()
            except Exception:
                pass
        logger.warning("视频下载无效（第 %d 次）：%s", attempt + 1, last)
    raise RuntimeError(f"视频下载失败/非有效视频：{last}")


def build_blackboard_prompt(board_title: str, board_points: list, narration: str) -> str:
    """构造"黑板板书 + 中文旁白"的 Seedance 提示词。

    - 画面：绿色黑板，粉笔逐行手写标题 + 要点，无人物、无讲师出镜。
    - 声音：Seedance 自带音频，用中文男声朗读 narration（逐句讲解）。
    - 板书文字要少而精（视频模型渲染中文偶有错字），故只放标题 + 3~4 个短要点。
    """
    title = (board_title or "").strip()
    pts = [p.strip() for p in (board_points or []) if p.strip()][:4]
    board_lines = "；".join(f"{i+1}.{p}" for i, p in enumerate(pts)) if pts else title
    narr = (narration or "").strip()
    return (
        f"教学板书视频，时长10秒，医疗器械质量管理体系培训课堂。"
        f"画面：一块绿色黑板，用白色粉笔逐行手写工整的中文板书，"
        f"标题「{title}」，下面列出要点：{board_lines}。"
        f"只有黑板和粉笔字，没有任何人物、没有讲师出镜、没有教室观众。"
        f"镜头完全固定不动，正面平视黑板的稳定机位，不要推拉、不要摇移、不要旋转、不要变焦，"
        f"全程静止如同架在三脚架上；画面里唯一的运动只是粉笔逐字书写出现的板书。安静专业的课堂氛围。"
        f"配一位清晰沉稳的中文男声旁白，逐句讲解以下内容：{narr}"
    )


# 兼容旧调用名
def build_video_prompt(topic: str, lecture: str = "") -> str:
    return build_blackboard_prompt(topic, [], lecture)
