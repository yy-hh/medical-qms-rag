import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.rag_engine import get_engine
from app.core.config import settings
from app.models.schemas import QueryRequest, StreamQueryRequest, QueryResponse, HealthResponse

router = APIRouter(tags=["query"])


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
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
async def stream_query(request: StreamQueryRequest):
    """SSE streaming endpoint — emits: sources → delta* → [DONE]"""
    engine = get_engine()
    history = [m.model_dump() for m in (request.history or [])]

    sources = engine.retrieve(
        request.question,
        request.top_k or settings.top_k,
        request.collection,
    )
    context = engine.build_context(sources)

    async def event_gen():
        # 1. Send retrieved sources immediately
        yield f"data: {json.dumps({'type':'sources','sources':[s.model_dump() for s in sources]}, ensure_ascii=False)}\n\n"

        # 2. Stream LLM response (sync iterator → async via executor)
        loop = asyncio.get_event_loop()
        gen = engine.generate_stream(request.question, context, history)
        while True:
            try:
                delta = await loop.run_in_executor(None, next, gen)
                yield f"data: {json.dumps({'type':'delta','content':delta}, ensure_ascii=False)}\n\n"
            except StopIteration:
                break
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
