"""培训教程 API：LLM 生成图文讲义 + Seedance 生成分段教学视频（配中文语音 + 中英双语字幕）。

- 讲义：复用现有 engine.llm 与生成线程池，SSE 流式返回 markdown。
- 视频教程：由 LLM 把主题拆成若干小段（每段一个知识点，含中文讲解词 + 英文翻译 + 画面提示），
  再逐段（分批）生成短视频 + 中文 TTS 语音，用 ffmpeg 合成（语音为主、视频铺底）并烧录中英双语字幕。
  分段+分批让单段几分钟内出片，避免一次等太久。
"""
import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core import training_store
from app.core import video_gen
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.api.company import load_profile

router = APIRouter(prefix="/api/training", tags=["training"])

# 独立线程池：讲义 LLM 调用与视频生成（长阻塞）都放这里，不占用默认池
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="training")

# 预置培训主题：贴合 QMS/SaMD 各核心领域
TOPICS = [
    "ISO 13485 质量管理体系概览",
    "IEC 62304 医疗器械软件生命周期",
    "ISO 14971 风险管理流程",
    "IEC 62366 可用性工程与人因",
    "SaMD 数据与算法治理（AI 专项）",
    "软件验证与确认（V&V）",
    "临床评价与注册申报要点",
    "上市后监督与持续合规",
    "设计开发文档与设计历史文档（DHF）",
    "CAPA 纠正与预防措施",
]

LECTURE_SYSTEM = """你是一位拥有 15 年经验的医疗器械 QMS 培训讲师，专精 SaMD（医疗器械软件）
质量管理体系。你熟悉 ISO 13485、IEC 62304、ISO 14971、IEC 62366 等核心标准，以及
NMPA / FDA / CE 的注册合规要求。

你的任务是为一次内部培训生成一份**图文讲义**，要求：
- 面向质量、研发、注册团队的新成员，深入浅出
- 结构清晰：培训目标 → 核心概念 → 关键流程/要求 → 常见误区 → 实操要点
- 使用 Markdown：标题用 # ## ###，要点用列表，必要处用表格
- 内容具体实用，结合 SaMD 软件特点，避免泛泛而谈
- 篇幅适中（可一屏到两屏读完），不要过长"""


class LectureRequest(BaseModel):
    topic: str
    tutorial_id: Optional[str] = None


class VideoRequest(BaseModel):
    topic: str
    lecture: Optional[str] = ""
    tutorial_id: Optional[str] = None


@router.get("/topics")
async def get_topics():
    return {"topics": TOPICS}


@router.get("/list")
async def list_tutorials():
    return {"tutorials": training_store.list_tutorials()}


@router.get("/{tutorial_id}")
async def get_tutorial(tutorial_id: str):
    t = training_store.get_tutorial(tutorial_id)
    if not t:
        raise HTTPException(status_code=404, detail="未找到该教程")
    return t


@router.delete("/{tutorial_id}")
async def delete_tutorial(tutorial_id: str):
    ok = training_store.delete_tutorial(tutorial_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该教程")
    return {"ok": True}


def _lecture_prompt(topic: str) -> str:
    profile = load_profile()
    pfields = [
        ("产品名称", profile.get("product_name")),
        ("核心功能", profile.get("core_functions")),
        ("AI类型", profile.get("ai_type")),
        ("适应症/临床场景", profile.get("clinical_indication")),
    ]
    pctx = "；".join(f"{k}：{v}" for k, v in pfields if (v or "").strip())
    pctx_line = f"\n\n（可结合本企业产品背景举例：{pctx}）" if pctx else ""
    return f"请就培训主题「{topic}」生成一份面向 SaMD 团队新成员的培训讲义。{pctx_line}"


@router.post("/lecture")
async def generate_lecture(request: LectureRequest):
    """SSE 流式生成培训讲义 markdown，并落库（status=draft）。"""
    topic = (request.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="主题不能为空")

    engine = get_engine()
    prompt = _lecture_prompt(topic)

    async def event_gen():
        # 先建/占位一条记录，拿到 id 回传前端（图文教程）
        tid = training_store.save_tutorial(
            tutorial_id=request.tutorial_id, topic=topic, kind="article", status="draft")
        yield f"data: {json.dumps({'type': 'meta', 'tutorial_id': tid, 'topic': topic}, ensure_ascii=False)}\n\n"

        loop = asyncio.get_event_loop()

        def _open_stream():
            from app.core.rag_engine import curl_chat_stream
            return curl_chat_stream(
                api_key=settings.api_key or settings.anthropic_api_key,
                base_url=settings.api_base_url,
                model=settings.claude_model,
                messages=[
                    {"role": "system", "content": LECTURE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=8192,
                connect_timeout=15,
                max_time=300,
            )

        _END = object()
        full = ""
        try:
            gen = await asyncio.wait_for(
                loop.run_in_executor(_POOL, _open_stream), timeout=100)
            it = iter(gen)
            while True:
                chunk = await asyncio.wait_for(
                    loop.run_in_executor(_POOL, next, it, _END), timeout=100)
                if chunk is _END:
                    break
                if not chunk.choices:
                    continue
                piece = getattr(chunk.choices[0].delta, "content", None)
                if not piece:
                    continue
                full += piece
                yield f"data: {json.dumps({'type': 'delta', 'content': piece}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': '讲义生成失败：' + str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        training_store.update_tutorial(tid, lecture=full, status="draft")
        yield f"data: {json.dumps({'type': 'done', 'tutorial_id': tid}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── 视频教程：分段大纲 + 分段（分批）渲染 ────────────────────────────

SEGMENT_SYSTEM = """你是医疗器械 QMS 培训课程设计师。请把一个培训主题拆成若干"知识小段"，
每段聚焦一个知识点，做成一个约 10 秒的短视频。段数由内容多少自定（一般 4-6 段，最多 8 段），
不要为凑数硬拆。

每段要判定类型 kind（很重要）：
- "seedance"：背景、概念、导入等**不涉及必须精确呈现的具体文字**的段。用 AI 生成的黑板动画（画面生动，
  但手写文字可能有错别字，故只适合不依赖文字准确性的内容）。
- "board"：涉及**具体条款、编号、术语、要点清单**等必须文字准确的段。用固定黑板底图精确渲染文字，
  保证零错字。凡是要点、步骤、定义、法规条款，一律用 board。

每段需要给出：
- kind："seedance" 或 "board"
- title：小段标题（中文，简短）
- board_points：黑板上要写的要点，2-4 个极短的中文短语（每个 4-12 字，像板书提纲，精炼不要整句）
- narration：中文讲解词（口语化、可朗读，约 2-3 句、30-60 字，10 秒内能讲完），作为旁白朗读

严格只输出一个 JSON 数组，元素为对象，字段为 kind / title / board_points（字符串数组）/ narration，
不要任何额外文字、不要 markdown 代码块。"""


def _parse_segments(text: str) -> list:
    text = (text or "").strip()
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        title = str(x.get("title", "")).strip()
        narration = str(x.get("narration", "")).strip()
        if not title and not narration:
            continue
        pts = x.get("board_points") or []
        if isinstance(pts, str):
            pts = [pts]
        pts = [str(p).strip() for p in pts if str(p).strip()]
        # 全部走 board（固定黑板底图 + TTS + 拼音字幕），不再用 seedance 生成动画
        kind = "board"
        out.append({
            "title": title or "小段",
            "seg_kind": kind,
            "narration": narration,
            # 板书要点存进 visual_prompt 字段（JSON 编码），复用现有列不改表结构
            "visual_prompt": json.dumps(pts, ensure_ascii=False),
        })
    return out


@router.post("/segments")
async def generate_segments(request: VideoRequest):
    """让 LLM 把主题拆成若干小段（含中文讲解词/英文翻译/画面提示），落库为待生成分段。"""
    topic = (request.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="主题不能为空")

    tid = request.tutorial_id
    if tid and not training_store.get_tutorial(tid):
        tid = None
    if not tid:
        tid = training_store.save_tutorial(topic=topic, kind="video", status="draft")
    else:
        training_store.update_tutorial(tid, kind="video")

    engine = get_engine()
    loop = asyncio.get_event_loop()
    prompt = f"请把培训主题「{topic}」拆成若干知识小段用于制作分段培训短视频。"

    def _call():
        return engine.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SEGMENT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )

    try:
        resp = await loop.run_in_executor(_POOL, _call)
        content = resp.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"分段大纲生成失败：{e}")

    segs = _parse_segments(content)
    if not segs:
        raise HTTPException(status_code=502, detail="分段解析失败，请重试")

    training_store.replace_segments(tid, segs)
    training_store.update_tutorial(tid, status="draft")
    return {"tutorial_id": tid, "topic": topic, "segments": training_store.list_segments(tid)}


@router.get("/{tutorial_id}/segments")
async def get_segments(tutorial_id: str):
    if not training_store.get_tutorial(tutorial_id):
        raise HTTPException(status_code=404, detail="未找到该教程")
    return {"tutorial_id": tutorial_id, "segments": training_store.list_segments(tutorial_id)}


def _board_points(seg: dict) -> list:
    """从 visual_prompt 解析板书要点。兼容两种格式：
    - 旧：JSON 数组（要点短语列表）
    - 新：JSON 对象 {"points":[...], "zh":[...], "en":[...]}，取 points
    """
    try:
        v = json.loads(seg.get("visual_prompt") or "[]")
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return v.get("points") or []
    except Exception:
        pass
    return []


def _board_sentences(seg: dict):
    """从 visual_prompt 取逐句配对的中英文列表 (zh_list, en_list)，无则 (None, None)。"""
    try:
        v = json.loads(seg.get("visual_prompt") or "{}")
        if isinstance(v, dict):
            zh, en = v.get("zh") or [], v.get("en") or []
            if zh and en and len(zh) == len(en):
                return zh, en
    except Exception:
        pass
    return None, None


@router.post("/segment/{seg_id}/render")
async def render_segment(seg_id: str):
    """渲染单个分段，按 seg_kind 分流：
    - seedance：Seedance 直接生成黑板动画 + 中文旁白（画面生动，适合背景/概念）。
    - board：固定黑板底图 + 精确渲染标题/要点 + TTS 中文语音 + 中文讲解字幕（文字零错字，适合具体内容）。
    SSE 进度。单段处理，前端分批逐段触发。
    """
    seg = training_store.get_segment(seg_id)
    if not seg:
        raise HTTPException(status_code=404, detail="未找到该分段")

    training_store.update_segment(seg_id, status="generating")

    async def event_gen():
        yield f"data: {json.dumps({'type': 'meta', 'seg_id': seg_id, 'title': seg['title'], 'seg_kind': seg['seg_kind']}, ensure_ascii=False)}\n\n"
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _on_progress(elapsed, total):
            loop.call_soon_threadsafe(
                q.put_nowait, {"type": "progress", "stage": "video", "elapsed": elapsed, "total": total})

        def _stage(msg):
            loop.call_soon_threadsafe(q.put_nowait, {"type": "stage", "message": msg})

        def _work_seedance():
            # Seedance 一步到位：黑板板书画面 + 中文旁白音频。成片即最终视频。
            vprompt = video_gen.build_blackboard_prompt(seg["title"], _board_points(seg), seg["narration"])
            vurl = video_gen.generate_video(vprompt, on_progress=_on_progress)
            return video_gen.download_video(vurl, filename=f"seg_{seg_id}.mp4")

        def _work_board():
            # 固定黑板底图 + 精确文字 + TTS 语音 + 中英双语逐句字幕
            from app.core import audio_gen
            _stage("生成中文语音…")
            aurl = audio_gen.generate_speech(seg["narration"] or seg["title"])
            apath = audio_gen.download_audio(aurl, filename=f"seg_{seg_id}.mp3")
            _stage("合成黑板讲解视频…")
            dur = audio_gen._probe_duration(apath)
            srt = audio_gen.AUDIO_DIR / f"{seg_id}.srt"
            zh_s, en_s = _board_sentences(seg)
            audio_gen.build_bilingual_srt(seg["narration"], seg.get("narration_en", ""), dur, srt,
                                          zh_sents=zh_s, en_sents=en_s)
            return audio_gen.compose_board(seg["title"], _board_points(seg), apath, srt,
                                           out_name=f"seg_{seg_id}.mp4")

        _work = _work_board if seg["seg_kind"] == "board" else _work_seedance
        fut = loop.run_in_executor(_POOL, _work)
        while True:
            get_task = asyncio.ensure_future(q.get())
            done, _ = await asyncio.wait({fut, get_task}, return_when=asyncio.FIRST_COMPLETED)
            if get_task in done:
                yield f"data: {json.dumps(get_task.result(), ensure_ascii=False)}\n\n"
            else:
                get_task.cancel()
            if fut.done():
                while not q.empty():
                    yield f"data: {json.dumps(q.get_nowait(), ensure_ascii=False)}\n\n"
                break

        try:
            final = fut.result()
        except Exception as e:
            training_store.update_segment(seg_id, status="failed")
            yield f"data: {json.dumps({'type': 'error', 'message': '分段生成失败：' + str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        training_store.update_segment(seg_id, final_path=final, status="ready")
        # 若全部分段就绪，教程标记 ready
        segs = training_store.list_segments(seg["tutorial_id"])
        if segs and all(s["status"] == "ready" for s in segs):
            training_store.update_tutorial(seg["tutorial_id"], status="ready")
        yield f"data: {json.dumps({'type': 'done', 'seg_id': seg_id, 'final_path': final, 'final_url': '/static/' + final}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
