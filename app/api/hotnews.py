import asyncio

from fastapi import APIRouter

from app.core import hotnews

router = APIRouter(prefix="/api/hotnews", tags=["hotnews"])


@router.get("")
async def get_hotnews():
    """返回当日热点缓存（秒回，不现抓）。"""
    return hotnews.load_cache()


@router.post("/refresh")
async def refresh_hotnews():
    """手动刷新：联网抓取并写缓存，返回最新结果。抓取是同步阻塞，放进 executor。"""
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, hotnews.refresh)
    return data
