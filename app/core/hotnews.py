"""热点速递：联网搜索中国医疗器械注册相关热点新闻并缓存。

数据源：Bing 中文新闻搜索（www.bing.com/news/search，NMPA 官网 412 反爬不可直接抓）。
抓取 → 去重 → 可选 LLM 提炼要点 → 写 data/hotnews.json 缓存。前端读缓存，调度每天 10:00 刷新。
"""
import json
import re
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

# 超过此天数的新闻视为过期，从热点速递中剔除（Bing 结果常混入数年前旧闻）。
MAX_AGE_DAYS = 90

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


def _age_days(time_str: str, now: datetime | None = None) -> float | None:
    """把 Bing 新闻的时间字段解析成「距今天数」。无法解析返回 None（调用方按宁漏勿杀保留）。

    Bing 时间格式很杂，需覆盖：
    - 相对：「15 小时前」「7 天前」「3 周前」「2 个月前」「1 年前」，以及无「前」的「1 天」
    - 绝对：「8/6/2026」「1/6/2021」（D/M/YYYY）
    - 带源后缀：「格隆汇 on MSN1 天」「雷达财经网 on MSN15 小时」——取末尾的相对时间片段
    """
    if not time_str:
        return None
    now = now or datetime.now()
    s = time_str.strip()

    # 相对时间：抓取「数字 + 单位(+可选 前)」，单位含 分钟/小时/天/周/月/年。
    # 带源后缀的形如「…MSN15 小时」也能被这个正则从尾部匹配到。
    m = re.search(r"(\d+)\s*(分钟|小时|天|周|个月|月|年)\s*前?", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        per = {"分钟": 1 / 1440, "小时": 1 / 24, "天": 1,
               "周": 7, "个月": 30, "月": 30, "年": 365}[unit]
        return n * per
    if "刚刚" in s or "分钟前" in s:
        return 0.0

    # 绝对日期 D/M/YYYY（Bing 中文区常用此序）。
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return (now - datetime(y, mon, d)).total_seconds() / 86400
        except ValueError:
            return None
    # 绝对日期 YYYY-MM-DD / YYYY年MM月DD日
    m = re.search(r"(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})", s)
    if m:
        y, mon, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return (now - datetime(y, mon, d)).total_seconds() / 86400
        except ValueError:
            return None
    return None


def _filter_recent(items: list[dict], max_age_days: int = MAX_AGE_DAYS) -> list[dict]:
    """剔除超过 max_age_days 的旧闻；时间解析不出的保留（宁漏勿杀）。
    按距今天数升序排列（新的在前），解析不出时间的排在最后。"""
    now = datetime.now()
    kept = []
    for it in items:
        age = _age_days(it.get("time", ""), now)
        if age is not None and age > max_age_days:
            continue
        it = dict(it)
        it["_age"] = age
        kept.append(it)
    # 排序键：有 age 的按 age 升序；None 视为很大值排末尾。
    kept.sort(key=lambda x: (x["_age"] is None, x["_age"] if x["_age"] is not None else 0))
    for it in kept:
        it.pop("_age", None)
    return kept


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
    # 先剔除过期旧闻并按时间排序（新的在前），再截断，保证 MAX_ITEMS 都是较新的条目。
    merged = _filter_recent(merged)[:MAX_ITEMS]
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
