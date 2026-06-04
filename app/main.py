import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.documents import router as doc_router
from app.api.query import router as query_router
from app.api.company import router as company_router
from app.api.generate import router as generate_router
from app.api.roadmap import router as roadmap_router
from app.core.rag_engine import get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Warming up RAG engine...")
    get_engine()
    logger.info("RAG engine ready")
    yield


app = FastAPI(
    title="QMS 体系搭建助手",
    description="医疗器械软件（SaMD）质量管理体系搭建平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(doc_router)
app.include_router(query_router)
app.include_router(company_router)
app.include_router(generate_router)
app.include_router(roadmap_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
