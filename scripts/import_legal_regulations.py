from __future__ import annotations

import json
import mimetypes
import os
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List

import requests


BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "source_docs" / "legal_regulations_20260603"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


DOCS: List[Dict[str, str]] = [
    {
        "title": "医疗器械监督管理条例_国务院令第739号",
        "collection": "regulations",
        "url": "https://www.gov.cn/zhengce/zhengceku/2021-03/18/content_5593739.htm",
    },
    {
        "title": "医疗器械注册与备案管理办法_市场监管总局令第47号",
        "collection": "regulations",
        "url": "https://www.gov.cn/gongbao/content/2021/content_5654783.htm",
    },
    {
        "title": "医疗器械分类规则_CFDA令第15号_2015",
        "collection": "classification",
        "url": "https://www.gov.cn/gongbao/content/2015/content_2961719.htm",
    },
    {
        "title": "医疗器械分类目录_2017版_104号公告",
        "collection": "classification",
        "url": "https://www.okaybio.com/file/%E5%8C%BB%E7%96%97%E5%99%A8%E6%A2%B0%E5%88%86%E7%B1%BB%E7%9B%AE%E5%BD%9520170831.pdf",
    },
    {
        "title": "国家药监局关于调整医疗器械分类目录部分内容的公告_2025年第132号",
        "collection": "classification",
        "url": "https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20260104173409116.html",
    },
    {
        "title": "国家药监局关于医疗器械分类调整有关工作的公告_2026年第52号",
        "collection": "classification",
        "url": "https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20260601172053198.html",
    },
    {
        "title": "医疗器械分类目录动态调整工作程序_2026年第53号",
        "collection": "classification",
        "url": "https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20260601173941178.html",
    },
    {
        "title": "创新医疗器械特别审查程序_2018年第83号",
        "collection": "regulations",
        "url": "https://www.cmde.org.cn/sqrzc/zxfw/lcjtcn/lcfj/chengxu201883.pdf",
    },
    {
        "title": "医疗器械生产质量管理规范_新版_2026年11月1日施行",
        "collection": "regulations",
        "url": "https://www.gov.cn/zhengce/zhengceku/202511/content_7047263.htm",
    },
    {
        "title": "医疗器械生产监督管理办法_2022_第53号",
        "collection": "regulations",
        "url": "https://sjfg.samr.gov.cn/law/file/pdf/3235243/1663501228275.pdf",
    },
    {
        "title": "医疗器械经营监督管理办法_2022_第54号",
        "collection": "regulations",
        "url": "https://www.gov.cn/gongbao/content/2022/content_5692860.htm",
    },
    {
        "title": "医疗器械不良事件监测和再评价管理办法_2018",
        "collection": "regulations",
        "url": "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_4b69cde387db4c4fa4465aad987157e0.html",
    },
    {
        "title": "中华人民共和国网络安全法_2025修正版",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2025-12/29/c_1768735112911946.htm",
    },
    {
        "title": "中华人民共和国数据安全法_2021",
        "collection": "cybersecurity",
        "url": "https://www.npc.gov.cn/npc/c2/c30834/202106/t20210610_311888.html",
    },
    {
        "title": "中华人民共和国个人信息保护法_2021",
        "collection": "cybersecurity",
        "url": "https://www.npc.gov.cn/WZWSREL25wYy9jMi9jMzA4MzQvMjAyMTA4L3QyMDIxMDgyMF8zMTMwODguaHRtbD9yZWY9aW1i",
    },
    {
        "title": "生成式人工智能服务管理暂行办法_2023",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm",
    },
    {
        "title": "网络数据安全管理条例_国务院令第790号_2025年施行",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2024-09/30/c_1729384452307680.htm",
    },
    {
        "title": "互联网信息服务算法推荐管理规定_2022",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2022-01/04/c_1642894606364259.htm",
    },
    {
        "title": "互联网信息服务深度合成管理规定_2023",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2022-12/11/c_1672221949354811.htm?eqid=b8c802050000bc5500000006649272b5",
    },
    {
        "title": "人工智能生成合成内容标识办法_2025",
        "collection": "cybersecurity",
        "url": "https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm",
    },
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip = True
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip = False
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        raw = "\n".join(self.parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def safe_name(title: str) -> str:
    title = re.sub(r'[\\/:*?"<>|]+', "_", title)
    title = re.sub(r"\s+", "_", title)
    return title[:140]


def is_pdf(resp: requests.Response, url: str) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    return (
        "application/pdf" in content_type
        or url.lower().split("?")[0].endswith(".pdf")
        or resp.content.startswith(b"%PDF")
    )


def decode_html(resp: requests.Response) -> str:
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def download_doc(doc: Dict[str, str]) -> Path:
    title = doc["title"]
    url = doc["url"]
    collection = doc["collection"]

    print(f"\n⬇️  下载：{title}")
    resp = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    resp.raise_for_status()

    base = f"{collection}__{safe_name(title)}"

    if is_pdf(resp, url):
        path = OUT_DIR / f"{base}.pdf"
        path.write_bytes(resp.content)
    else:
        html = decode_html(resp)
        parser = TextExtractor()
        parser.feed(html)
        text = parser.text()

        header = (
            f"标题：{title}\n"
            f"来源URL：{url}\n"
            f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"集合：{collection}\n\n"
            "正文：\n"
        )
        path = OUT_DIR / f"{base}.txt"
        path.write_text(header + text, encoding="utf-8")

    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "title": title,
                "url": url,
                "collection": collection,
                "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                "local_path": str(path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"✅ 已保存：{path.relative_to(PROJECT_ROOT)}")
    return path


def upload_doc(path: Path, collection: str) -> bool:
    endpoints = [
        f"{BASE_URL}/api/documents/upload",
        f"{BASE_URL}/api/documents",
    ]
    form_keys = ["collection", "category"]

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    for endpoint in endpoints:
        for form_key in form_keys:
            try:
                with path.open("rb") as f:
                    resp = requests.post(
                        endpoint,
                        files={"file": (path.name, f, mime)},
                        data={form_key: collection},
                        timeout=180,
                    )
                if resp.status_code < 400:
                    print(f"📚 已入库：{path.name} -> {collection}")
                    return True
                if resp.status_code not in {404, 422}:
                    print(f"⚠️ 上传失败 {resp.status_code}: {resp.text[:300]}")
            except requests.RequestException as exc:
                print(f"⚠️ 上传接口暂不可用：{exc}")
                return False

    print(f"⚠️ 未找到可用上传接口，请手动上传：{path}")
    return False


def main() -> None:
    print(f"项目目录：{PROJECT_ROOT}")
    print(f"下载目录：{OUT_DIR}")
    print(f"上传目标：{BASE_URL}")

    downloaded = []
    failed = []
    uploaded = 0

    for doc in DOCS:
        try:
            path = download_doc(doc)
            downloaded.append(path)
            if upload_doc(path, doc["collection"]):
                uploaded += 1
            time.sleep(0.8)
        except Exception as exc:
            failed.append((doc["title"], doc["url"], str(exc)))
            print(f"❌ 失败：{doc['title']} -> {exc}")

    report = {
        "total": len(DOCS),
        "downloaded": len(downloaded),
        "uploaded": uploaded,
        "failed": failed,
        "output_dir": str(OUT_DIR),
        "base_url": BASE_URL,
    }
    report_path = OUT_DIR / "import_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n====== 导入完成 ======")
    print(f"下载成功：{len(downloaded)} / {len(DOCS)}")
    print(f"上传成功：{uploaded} / {len(DOCS)}")
    print(f"失败数量：{len(failed)}")
    print(f"报告文件：{report_path}")

    if failed:
        print("\n失败清单：")
        for title, url, err in failed:
            print(f"- {title}: {err}\n  {url}")


if __name__ == "__main__":
    main()
