import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

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
from app.api.compliance import router as compliance_router
from app.api.docs import router as docs_router
from app.api.notes import router as notes_router
from app.api.hotnews import router as hotnews_router
from app.api.training import router as training_router
from app.api.auth import router as auth_router
from app.api.review import router as review_router
from app.core.rag_engine import get_engine
from app.core import hotnews
from app.core.migrate_accounts import run_migration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

HOTNEWS_HOUR = 10  # 每天本地 10:00 刷新热点


def _seconds_until_next_run(hour: int = HOTNEWS_HOUR) -> float:
    """距下一个本地 hour:00 的秒数。"""
    now = datetime.now()
    nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


async def _hotnews_scheduler():
    """后台循环：当日无缓存先补抓一次，然后每天 10:00 刷新。单次失败不杀循环。"""
    loop = asyncio.get_event_loop()
    # 启动补抓：当日还没缓存才抓，避免每次重启都抓
    try:
        if hotnews.cached_date() != datetime.now().strftime("%Y-%m-%d"):
            logger.info("热点速递：当日无缓存，启动时补抓一次")
            await loop.run_in_executor(None, hotnews.refresh)
    except Exception as e:
        logger.warning("热点速递启动补抓失败: %s", e)
    while True:
        delay = _seconds_until_next_run()
        logger.info("热点速递：%.0f 分钟后（次日 %d:00）刷新", delay / 60, HOTNEWS_HOUR)
        try:
            await asyncio.sleep(delay)
            logger.info("热点速递：定时刷新开始")
            await loop.run_in_executor(None, hotnews.refresh)
            logger.info("热点速递：定时刷新完成")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("热点速递定时刷新失败，等待下一轮: %s", e)
            await asyncio.sleep(60)  # 失败后短暂等待，避免紧凑重试


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running account migration...")
    run_migration()
    logger.info("Warming up RAG engine...")
    get_engine()
    logger.info("RAG engine ready")
    task = asyncio.create_task(_hotnews_scheduler())
    yield
    task.cancel()


app = FastAPI(
    title="医械注册助手",
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
app.include_router(compliance_router)
app.include_router(docs_router)
app.include_router(notes_router)
app.include_router(hotnews_router)
app.include_router(training_router)
app.include_router(auth_router)
app.include_router(review_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    # 禁缓存：index.html 内联了 JS，缓存旧版会导致登录/生成逻辑用到过期代码
    return FileResponse(
        str(STATIC_DIR / "index.html"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )
