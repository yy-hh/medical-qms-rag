from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional

import requests


BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "source_docs" / "legal_regulations_20260603_missing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


DOCS: List[Dict] = [
    {
        "title": "国家药监局关于调整《医疗器械分类目录》部分内容的公告_2025年第132号_公告正文",
        "collection": "classification",
        "type": "html",
        "urls": [
            "https://yjj.sh.gov.cn/qtgzwj/20260105/166bf07a9c3f47df8c8bdefc0ab7e12f.html",
        ],
    },
    {
        "title": "国家药品监督管理局2025年第132号公告附件_医疗器械分类目录部分内容调整表",
        "collection": "classification",
        "type": "doc",
        "urls": [
            "https://yjj.sh.gov.cn/cmsres/85/8566a188dab1456b96b5128ff23d080b/f1569bd37c84da78fa56e73eb92099c0.doc",
        ],
    },
    {
        "title": "国家药监局关于医疗器械分类调整有关工作的公告_2026年第52号",
        "collection": "classification",
        "type": "html",
        "urls": [
            "https://yjj.sh.gov.cn/qtgzwj/20260601/99980ea6a252434a8bfbea0e33111d29.html",
        ],
    },
    {
        "title": "国家药监局关于发布医疗器械分类目录动态调整工作程序的公告_2026年第53号_公告正文",
        "collection": "classification",
        "type": "html",
        "urls": [
            "https://yjj.sh.gov.cn/qtgzwj/20260601/0a62a32a100b49e89ddc56008ef8d11d.html",
        ],
    },
    {
        "title": "国家药品监督管理局2026年第53号公告附件_医疗器械分类目录动态调整工作程序",
        "collection": "classification",
        "type": "doc",
        "urls": [
            "https://yjj.sh.gov.cn/cmsres/bb/bb5a3c9a7405472ab06dd0a97dd73530/35a7fd076e5c2be536b12a18019c9fb7.doc",
        ],
    },
    {
        "title": "中华人民共和国数据安全法_2021",
        "collection": "cybersecurity",
        "type": "html",
        "urls": [
            "https://www.ncsti.gov.cn/zcfg/flfg/202106/t20210611_34190.html",
            "https://www.gjbmj.gov.cn/n1/2025/1208/c409088-40619671.html",
        ],
    },
    {
        "title": "中华人民共和国个人信息保护法_2021",
        "collection": "cybersecurity",
        "type": "html",
        "urls": [
            "https://www.samr.gov.cn/wljys/gzzd/art/2023/art_3ef1e889c1e644d4b65b5f5c7f432386.html",
            "https://www.miit.gov.cn/zwgk/zcwj/flfg/art/2022/art_04a0f1fb5df244e39688fd5372623a8d.html",
        ],
    },
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = True
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "article", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = False
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "article", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
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
    return title[:150]


def fetch_first(urls: List[str]) -> tuple[str, requests.Response]:
    last_err: Optional[Exception] = None
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=90, allow_redirects=True)
            resp.raise_for_status()
            return url, resp
        except Exception as exc:
            last_err = exc
            print(f"⚠️ 备用失败：{url} -> {exc}")
            time.sleep(0.8)
    raise RuntimeError(f"全部 URL 下载失败：{last_err}")


def html_to_text(resp: requests.Response) -> str:
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    parser = TextExtractor()
    parser.feed(resp.text)
    return parser.text()


def extract_doc_with_external_tool(path: Path) -> Optional[str]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "txt:Text", "--outdir", str(tmp_path), str(path)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                )
                txt_files = list(tmp_path.glob("*.txt"))
                if txt_files:
                    text = txt_files[0].read_text(encoding="utf-8", errors="ignore").strip()
                    if len(text) > 200:
                        return text
            except Exception:
                pass

    for tool in ("antiword", "catdoc"):
        executable = shutil.which(tool)
        if executable:
            try:
                result = subprocess.run(
                    [executable, str(path)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                )
                text = result.stdout.decode("utf-8", errors="ignore").strip()
                if len(text) > 200:
                    return text
            except Exception:
                pass

    return None


def extract_doc_heuristic(path: Path) -> str:
    data = path.read_bytes()
    candidates: List[str] = []
    pattern = re.compile(r"[\u4e00-\u9fffA-Za-z0-9（）()《》、，。；：:！!？?%％—\-_/.\s]{8,}")

    for enc in ("utf-16le", "gb18030", "utf-8"):
        try:
            decoded = data.decode(enc, errors="ignore")
        except Exception:
            continue

        decoded = decoded.replace("\x00", "\n")
        for item in pattern.findall(decoded):
            item = re.sub(r"[ \t]+", " ", item)
            item = re.sub(r"\n{2,}", "\n", item)
            item = item.strip()
            if len(item) >= 8 and re.search(r"[\u4e00-\u9fff]", item):
                candidates.append(item)

    seen = set()
    lines = []
    for item in candidates:
        key = item[:120]
        if key not in seen:
            seen.add(key)
            lines.append(item)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def download_as_txt(doc: Dict) -> Path:
    title = doc["title"]
    collection = doc["collection"]
    kind = doc["type"]

    print(f"\n⬇️  补齐：{title}")
    url, resp = fetch_first(doc["urls"])

    base = f"{collection}__{safe_name(title)}"

    if kind == "html":
        text = html_to_text(resp)
        path = OUT_DIR / f"{base}.txt"
        header = (
            f"标题：{title}\n"
            f"来源URL：{url}\n"
            f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"集合：{collection}\n\n"
            "正文：\n"
        )
        path.write_text(header + text, encoding="utf-8")

    elif kind == "doc":
        raw_path = OUT_DIR / f"{base}.doc"
        raw_path.write_bytes(resp.content)

        text = extract_doc_with_external_tool(raw_path)
        if not text:
            text = extract_doc_heuristic(raw_path)

        if len(text) < 200:
            raise RuntimeError(
                f".doc 附件已下载但文本提取过短：{raw_path}。"
                "建议安装 libreoffice 或 antiword 后重试。"
            )

        path = OUT_DIR / f"{base}.txt"
        header = (
            f"标题：{title}\n"
            f"来源URL：{url}\n"
            f"原始附件：{raw_path.name}\n"
            f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"集合：{collection}\n\n"
            "正文：\n"
        )
        path.write_text(header + text, encoding="utf-8")

    else:
        raise ValueError(f"未知类型：{kind}")

    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps(
            {
                "title": title,
                "url": url,
                "collection": collection,
                "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                "local_path": str(path),
                "note": "用于补齐第一部分失败的法律法规/分类目录调整文件",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def upload_doc(path: Path, collection: str) -> bool:
    endpoints = [
        f"{BASE_URL}/api/documents/upload",
        f"{BASE_URL}/api/documents",
    ]
    form_keys = ["collection", "category"]
    mime = mimetypes.guess_type(path.name)[0] or "text/plain"

    for endpoint in endpoints:
        for form_key in form_keys:
            try:
                with path.open("rb") as f:
                    resp = requests.post(
                        endpoint,
                        files={"file": (path.name, f, mime)},
                        data={form_key: collection},
                        timeout=240,
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
            path = download_as_txt(doc)
            downloaded.append(path)
            print(f"✅ 已保存：{path.relative_to(PROJECT_ROOT)}")

            if upload_doc(path, doc["collection"]):
                uploaded += 1

            time.sleep(0.8)
        except Exception as exc:
            failed.append((doc["title"], doc.get("urls", []), str(exc)))
            print(f"❌ 失败：{doc['title']} -> {exc}")

    report = {
        "total_items": len(DOCS),
        "downloaded": len(downloaded),
        "uploaded": uploaded,
        "failed": failed,
        "output_dir": str(OUT_DIR),
        "base_url": BASE_URL,
    }
    report_path = OUT_DIR / "missing_import_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n====== 第一部分缺失文件补齐完成 ======")
    print(f"下载成功：{len(downloaded)} / {len(DOCS)}")
    print(f"上传成功：{uploaded} / {len(DOCS)}")
    print(f"失败数量：{len(failed)}")
    print(f"报告文件：{report_path}")

    if failed:
        print("\n失败清单：")
        for title, urls, err in failed:
            print(f"- {title}: {err}")
            for url in urls:
                print(f"  {url}")


if __name__ == "__main__":
    main()
