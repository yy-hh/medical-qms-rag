import asyncio
import json

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.models.schemas import QueryRequest, StreamQueryRequest, QueryResponse, HealthResponse
from app.api.deps import get_current_account

router = APIRouter(tags=["query"])


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
        gen = engine.generate_stream(request.question, context, history)
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
