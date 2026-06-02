from fastapi import APIRouter, HTTPException
from app.core.rag_engine import get_engine
from app.models.schemas import QueryRequest, QueryResponse, HealthResponse

router = APIRouter(tags=["query"])


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    engine = get_engine()
    try:
        return engine.query(
            question=request.question,
            top_k=request.top_k,
            collection_name=request.collection,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/health", response_model=HealthResponse)
async def health():
    engine = get_engine()
    info = engine.health()
    return HealthResponse(**info)
