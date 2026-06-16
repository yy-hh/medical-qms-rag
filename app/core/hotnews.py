"""热点速递：联网搜索中国医疗器械注册相关热点新闻并缓存。

数据源：Bing 中文新闻搜索（www.bing.com/news/search，NMPA 官网 412 反爬不可直接抓）。
抓取 → 去重 → 可选 LLM 提炼要点 → 写 data/hotnews.json 缓存。前端读缓存，调度每天 10:00 刷新。
"""
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORE_PATH = BASE_DIR / "data" / "hotnews.json"

KEYWORDS = [
    "医疗器械注册",
    "NMPA 医疗器械",
    "医疗器械 监管 新规",
    "医疗器械 注册审查 指导原则",
]

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MAX_ITEMS = 20


def _fetch_bing(keyword: str) -> list[dict]:
    """抓取单个关键词的 Bing 新闻搜索结果。任何异常返回空列表（不影响其它关键词）。"""
    url = f"https://www.bing.com/news/search?q={quote(keyword)}&setlang=zh-CN"
    items = []
    try:
        r = httpx.get(url, headers=_UA, timeout=15.0, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for card in soup.select("div.news-card"):
            a = card.select_one("a.title") or card.select_one("a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or not href:
                continue
            href = urljoin("https://www.bing.com/", href) if href.startswith("/") else href
            src_el = card.select_one("div.source a") or card.select_one("div.source")
            snip_el = card.select_one("div.snippet") or card.select_one(".snippet")
            time_el = card.select_one("span[aria-label]") or card.select_one("div.source span")
            items.append({
                "title": title,
                "url": href,
                "source": (src_el.get_text(strip=True) if src_el else "")[:40],
                "time": (time_el.get("aria-label") if time_el and time_el.has_attr("aria-label")
                         else (time_el.get_text(strip=True) if time_el else "")),
                "summary": (snip_el.get_text(strip=True) if snip_el else "")[:200],
                "keyword": keyword,
            })
    except Exception as e:
        logger.warning("热点抓取失败 keyword=%s: %s", keyword, e)
    return items


def _summarize(items: list[dict]) -> list[dict]:
    """用 LLM 过滤无关项并为每条生成一句话要点。失败则原样返回（降级）。"""
    if not items:
        return items
    try:
        import httpx as _httpx
        from openai import OpenAI
        from app.core.config import settings

        api_key = settings.api_key or settings.anthropic_api_key
        if not api_key:
            return items
        client = OpenAI(
            api_key=api_key, base_url=settings.api_base_url,
            timeout=_httpx.Timeout(connect=15.0, read=60.0, write=30.0, pool=15.0),
            max_retries=1,
        )
        listing = "\n".join(f"{i}. {it['title']}" for i, it in enumerate(items))
        prompt = (
            "下面是一批新闻标题，主题应为「中国医疗器械注册/监管」。请：\n"
            "1) 剔除与医疗器械注册/监管明显无关的条目；\n"
            "2) 为保留的每条生成一句话中文要点（≤40字）。\n"
            "严格只输出 JSON 数组，每个元素 {\"index\": 原序号, \"point\": \"要点\"}，不要其它文字。\n\n"
            f"{listing}"
        )
        resp = client.chat.completions.create(
            model=settings.claude_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        text = resp.choices[0].message.content or ""
        # 容错提取 JSON 数组
        l, rdx = text.find("["), text.rfind("]")
        if l == -1 or rdx == -1:
            return items
        arr = json.loads(text[l:rdx + 1])
        keep = []
        for o in arr:
            idx = o.get("index")
            if isinstance(idx, int) and 0 <= idx < len(items):
                it = dict(items[idx])
                it["point"] = (o.get("point") or "").strip()
                keep.append(it)
        return keep or items
    except Exception as e:
        logger.warning("热点 LLM 提炼失败，降级用原始摘要: %s", e)
        return items


def fetch_all() -> list[dict]:
    """遍历关键词抓取 → 按 url 去重 → 截断 → LLM 提炼。"""
    seen, merged = set(), []
    for kw in KEYWORDS:
        for it in _fetch_bing(kw):
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            merged.append(it)
    merged = merged[:MAX_ITEMS]
    return _summarize(merged)


def save_cache(items: list[dict]) -> dict:
    now = time.time()
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "fetched_at": now,
        "items": items,
    }
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_cache() -> dict:
    if not STORE_PATH.exists():
        return {"date": None, "fetched_at": None, "items": []}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"date": None, "fetched_at": None, "items": []}


def refresh() -> dict:
    """抓取并写缓存，返回最新缓存结构。供调度和手动刷新共用。"""
    items = fetch_all()
    # 抓取为空（如网络异常）时不覆盖已有缓存，保留旧数据
    if not items:
        cached = load_cache()
        if cached.get("items"):
            logger.warning("本次抓取为空，保留上次缓存")
            return cached
    return save_cache(items)


def cached_date() -> str | None:
    return load_cache().get("date")
