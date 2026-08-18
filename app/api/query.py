import asyncio
import base64
import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.ingestion.loader import load_document
from app.models.schemas import QueryRequest, StreamQueryRequest, QueryResponse, HealthResponse
from app.api.deps import get_current_account

router = APIRouter(tags=["query"])

# 临时附件限制
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_ATTACH_TEXT = 20000
ATTACH_EXT = {".pdf", ".docx", ".txt", ".md"}


def _decode_checked(b64: str, limit: int) -> bytes:
    """解码前按 base64 长度粗校验，解码后二次校验字节数（防 base64 炸弹）。"""
    if len(b64) > limit * 4 // 3 + 1024:
        raise HTTPException(status_code=413, detail="附件超过大小限制")
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="附件 base64 解码失败")
    if len(raw) > limit:
        raise HTTPException(status_code=413, detail="附件超过大小限制")
    return raw


def _prepare_images(images) -> list[str]:
    """归一化为 data URL 列表，累计总大小校验。"""
    out, total = [], 0
    for img in images or []:
        d = (img.data or "").strip()
        if d.startswith("data:"):
            b64 = d.split(",", 1)[1] if "," in d else ""
            raw = _decode_checked(b64, MAX_IMAGE_BYTES)
            url = d
        else:
            raw = _decode_checked(d, MAX_IMAGE_BYTES)
            url = f"data:{img.mime or 'image/png'};base64,{d}"
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="附件总大小超限")
        out.append(url)
    return out


def _prepare_files_text(files) -> str:
    """文件落临时目录 → loader 抽文本 → 删除。解析失败注入占位不中断。"""
    blocks, total = [], 0
    for f in files or []:
        ext = Path(f.name).suffix.lower()
        if ext not in ATTACH_EXT:
            raise HTTPException(status_code=400, detail=f"不支持的附件类型：{ext}")
        raw = _decode_checked(f.content_base64, MAX_FILE_BYTES)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail="附件总大小超限")
        # mkstemp 随机名、只用后缀 → 文件名不进路径，防目录穿越
        fd, tmp = tempfile.mkstemp(suffix=ext)
        try:
            with os.fdopen(fd, "wb") as w:
                w.write(raw)
            pages = load_document(Path(tmp))
            text = "\n".join(p["text"] for p in pages).strip()
            blocks.append(f"【附件：{f.name}】\n{text}" if text
                          else f"【附件：{f.name}】（未能解析出文本）")
        except Exception as e:
            blocks.append(f"【附件：{f.name}】（解析失败：{e}）")
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return ("\n\n---\n\n".join(blocks))[:MAX_ATTACH_TEXT]


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest, account_id: str = Depends(get_current_account)):
    engine = get_engine()
    history = [m.model_dump() for m in (request.history or [])]
    try:
        return engine.query(
            question=request.question,
            top_k=request.top_k,
            collection_name=request.collection,
            history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/query/stream")
async def stream_query(request: StreamQueryRequest,
                       account_id: str = Depends(get_current_account)):
    """SSE streaming endpoint — emits: sources → delta* → [DONE]"""
    engine = get_engine()
    history = [m.model_dump() for m in (request.history or [])]

    # 临时附件预处理：在 event_gen 之前做，解码/解析失败直接 HTTP 4xx（不混进 SSE）
    image_urls = _prepare_images(request.images)
    attach_text = _prepare_files_text(request.files)

    # 检索仍只用原始问题：图片不可检索，文件文本作附件上下文直接给模型（不并入向量检索）
    sources = engine.retrieve(
        request.question,
        request.top_k or settings.top_k,
        request.collection,
    )
    context = engine.build_context(sources)

    # 双路召回：在 BM25 法规原文之外，再从合规知识图谱检索相关审查要点，
    # 让回答能给出「涉及哪个注册阶段 · 要哪些文档 · 满足哪条法规要求」的结构化关联。
    graph_block = ""
    try:
        from app.core.compliance_graph import retrieve_for_qa
        reqs = retrieve_for_qa(request.question, top_k=6)
        if reqs:
            lines = []
            for r in reqs:
                stages = "、".join(r["stages"]) or "—"
                docs = "、".join(d["doc_name"] for d in r["docs"]) or "—"
                lines.append(
                    f"- 审查要点：{r['clause']}（出自《{r['basis']}》）\n"
                    f"  注册阶段：{stages}；应由文档体现：{docs}"
                    + (f"\n  要点说明：{r['detail']}" if r.get('detail') else "")
                )
            graph_block = "\n".join(lines)
    except Exception:
        graph_block = ""

    if graph_block:
        context = (
            context
            + "\n\n===== 合规知识图谱关联（审查要点 → 注册阶段 / 应产出文档） =====\n"
            + graph_block
            + "\n\n（请在回答中结合上述关联，说明该问题涉及的注册阶段、需要产出/体现的文档，"
              "以及对应满足的法规审查要点；法规条款引用仍以前述法规原文为准。）"
        )

    async def event_gen():
        # 1. Send retrieved sources immediately
        yield f"data: {json.dumps({'type':'sources','sources':[s.model_dump() for s in sources]}, ensure_ascii=False)}\n\n"

        # 2. Stream LLM response (sync iterator → async via executor)
        loop = asyncio.get_event_loop()
        gen = engine.generate_stream(request.question, context, history,
                                     image_urls=image_urls, attachment_text=attach_text)
        _END = object()
        while True:
            try:
                # sentinel 避免 StopIteration 跨 run_in_executor 边界导致挂起（见 generate.py）
                delta = await loop.run_in_executor(None, next, gen, _END)
                if delta is _END:
                    break
                yield f"data: {json.dumps({'type':'delta','content':delta}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','message':str(e)}, ensure_ascii=False)}\n\n"
                break

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(**get_engine().health())
