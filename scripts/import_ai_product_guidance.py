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
OUT_DIR = PROJECT_ROOT / "data" / "source_docs" / "ai_product_guidance_20260603"
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
        "title": "肺结节CT图像辅助检测软件注册审查指导原则_2022年第21号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://www.cmde.org.cn/directory/web/cmde/images/8Zyf18a0vbHzz9LkmcaY0w.doc",
            "https://www.gov.cn/zhengce/zhengceku/2022-04/13/content_5685076.htm",
            "https://www.ccfdie.org/cn/yjxx/ylqx/webinfo/2022/04/1649296800000067.htm",
        ],
    },
    {
        "title": "乳腺X射线图像辅助检测软件注册审查指导原则_2022年第22号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://www.cmde.org.cn/directory/web/cmde/images/k3FNz7HkxOvqz7C1mca0vw.doc",
            "https://www.ccfdie.org/cn/yjxx/ylqx/webinfo/2022/04/1649296800000068.htm",
        ],
    },
    {
        "title": "糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则_2022年第26号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://www.cmde.org.cn/directory/web/cmde/images/vsHUz7HkxOvqz7C1mca0vw.doc",
            "https://www.ccfdie.org/cn/yjxx/ylqx/webinfo/2022/05/1651795200000069.htm",
        ],
    },
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = True
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "article", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = False
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "article", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
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


def response_suffix(resp: requests.Response, url: str) -> str:
    content_type = resp.headers.get("content-type", "").lower()
    clean_url = url.lower().split("?", 1)[0]
    if resp.content.startswith(b"%PDF") or clean_url.endswith(".pdf") or "application/pdf" in content_type:
        return ".pdf"
    if clean_url.endswith(".docx") or "officedocument.wordprocessingml.document" in content_type:
        return ".docx"
    if clean_url.endswith(".doc") or "msword" in content_type:
        return ".doc"
    return ".html"


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
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
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
                result = subprocess.run([executable, str(path)], check=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
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
            item = re.sub(r"\n{2,}", "\n", item).strip()
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


def download_doc(doc: Dict) -> Path:
    title = doc["title"]
    collection = doc["collection"]
    print(f"\n⬇️  下载：{title}")

    url, resp = fetch_first(doc["urls"])
    suffix = response_suffix(resp, url)
    base = f"{collection}__{safe_name(title)}"

    if suffix == ".html":
        text = html_to_text(resp)
        path = OUT_DIR / f"{base}.txt"
        header = (f"标题：{title}\n来源URL：{url}\n"
                  f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n集合：{collection}\n\n正文：\n")
        path.write_text(header + text, encoding="utf-8")
    elif suffix in {".doc", ".docx"}:
        raw_path = OUT_DIR / f"{base}{suffix}"
        raw_path.write_bytes(resp.content)
        if suffix == ".docx":
            return raw_path
        text = extract_doc_with_external_tool(raw_path) or extract_doc_heuristic(raw_path)
        if len(text) < 200:
            raise RuntimeError(f".doc 提取过短：{raw_path}，建议安装 libreoffice/antiword 后重试")
        path = OUT_DIR / f"{base}.txt"
        header = (f"标题：{title}\n来源URL：{url}\n原始附件：{raw_path.name}\n"
                  f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n集合：{collection}\n\n正文：\n")
        path.write_text(header + text, encoding="utf-8")
    else:
        path = OUT_DIR / f"{base}{suffix}"
        path.write_bytes(resp.content)

    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps({"title": title, "collection": collection, "source_url": url,
                    "all_urls": doc["urls"],
                    "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                    "local_path": str(path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ 已保存：{path.relative_to(PROJECT_ROOT)}")
    return path


def upload_doc(path: Path, collection: str) -> bool:
    endpoints = [f"{BASE_URL}/api/documents/upload", f"{BASE_URL}/api/documents"]
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    for endpoint in endpoints:
        for form_key in ("collection", "category"):
            try:
                with path.open("rb") as f:
                    resp = requests.post(endpoint, files={"file": (path.name, f, mime)},
                                         data={form_key: collection}, timeout=300)
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

    downloaded, failed, uploaded = [], [], 0
    for doc in DOCS:
        try:
            path = download_doc(doc)
            downloaded.append(path)
            if upload_doc(path, doc["collection"]):
                uploaded += 1
            time.sleep(0.8)
        except Exception as exc:
            failed.append((doc["title"], doc["urls"], str(exc)))
            print(f"❌ 失败：{doc['title']} -> {exc}")

    report = {"total": len(DOCS), "downloaded": len(downloaded), "uploaded": uploaded,
              "failed": failed, "output_dir": str(OUT_DIR), "base_url": BASE_URL}
    (OUT_DIR / "import_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n====== 第三部分 AI 产品专项导入完成 ======")
    print(f"下载成功：{len(downloaded)} / {len(DOCS)}")
    print(f"上传成功：{uploaded} / {len(DOCS)}")
    print(f"失败数量：{len(failed)}")
    if failed:
        print("\n失败清单：")
        for title, urls, err in failed:
            print(f"- {title}: {err}")
            for url in urls:
                print(f"  {url}")


if __name__ == "__main__":
    main()
