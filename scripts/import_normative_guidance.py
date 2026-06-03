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
OUT_DIR = PROJECT_ROOT / "data" / "source_docs" / "normative_guidance_20260603"
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
        "title": "人工智能医用软件产品分类界定指导原则_2021年第47号",
        "collection": "guidance-ai",
        "urls": [
            "https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/202204/W020220408381230477584.docx",
            "https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/202204/t20220408_2669468.html",
        ],
    },
    {
        "title": "医疗器械软件注册审查指导原则_2022年修订版",
        "collection": "guidance-software",
        "urls": [
            "https://docs.team-ra.org/zh/nmpa/guidance/cmde-2022-9",
            "https://www.ccfdie.org/zryyxxw/zxdt/webinfo/2022/03/1648289422552123.htm",
        ],
    },
    {
        "title": "医疗器械生产质量管理规范独立软件现场检查指导原则_药监综械管2020_57号",
        "collection": "guidance-qms-software",
        "urls": [
            "https://sigma-stat.com/index.php?a=index&aid=743&c=View&m=home",
        ],
    },
    {
        "title": "医疗器械生产质量管理规范附录独立软件_2019年第43号",
        "collection": "guidance-qms-software",
        "urls": [
            "https://www.iivd.net/article-18404-1.html",
            "https://www.fjamdi.org.cn/default.aspx?id=365&pageType=detail&pageid=44",
        ],
    },
    {
        "title": "移动医疗器械注册审查指导原则_2025年修订版_2025年第9号",
        "collection": "guidance-mobile",
        "urls": [
            "https://www.cmde.org.cn/directory/web/cmde/images/1746596431585065407.docx",
            "https://www.ydcmdei.org.cn/article/620",
        ],
    },
    {
        "title": "人工智能医疗器械注册审查指导原则_2022年第8号",
        "collection": "guidance-ai",
        "urls": [
            "https://www.med-regissolution.com/index.php?a=index&c=Show&cid=13&id=425&m=",
            "https://www.duyaonet.com/News/Detail/5172A3D6-92AB-4E67-B9C4-6E12FBBAD8AA",
        ],
    },
    {
        "title": "医疗器械网络安全注册审查指导原则_2022年修订版_2022年第7号",
        "collection": "guidance-cybersecurity",
        "urls": [
            "https://docs.team-ra.org/zh/nmpa/guidance/cmde-2022-7",
            "https://www.secrss.com/articles/40158",
        ],
    },
    {
        "title": "医疗器械可用性工程注册审查指导原则_2024年第13号",
        "collection": "guidance-usability",
        "urls": [
            "https://ydcmdei.org.cn/attachment/20240531/70541a310a694c19a4de28dc696e6af1.docx",
            "https://ydcmdei.org.cn/article/401",
        ],
    },
    {
        "title": "关于医疗器械可用性工程注册审查指导原则的应用说明_2024年第13号附件",
        "collection": "guidance-usability",
        "urls": [
            "https://ydcmdei.org.cn/attachment/20240531/0860b8a5ae3d4d028e4c8c4dd76e324c.docx",
            "https://ydcmdei.org.cn/article/401",
        ],
    },
    {
        "title": "医疗器械临床评价技术指导原则_2021年第73号",
        "collection": "guidance-clinical",
        "urls": [
            "https://docs.team-ra.org/zh/nmpa/guidance/cmde-2021-73",
            "https://www.cnpharm.com/c/2021-09-28/804335.shtml",
        ],
    },
    {
        "title": "真实世界数据用于医疗器械临床评价技术指导原则_试行_2020年第77号",
        "collection": "guidance-clinical",
        "urls": [
            "https://docs.team-ra.org/zh/nmpa/guidance/cmde-2021-73-1",
            "https://mpa.gd.gov.cn/zwgk/zcfg/fgjd/ylqx/content/post_3140501.html",
        ],
    },
    {
        "title": "人工智能辅助检测医疗器械软件临床评价注册审查指导原则_2023年第38号",
        "collection": "guidance-ai-clinical",
        "urls": [
            "https://www.ydcmdei.org.cn/attachment/20231108/bf77957f267b48d2bf6073b258a761a2.doc",
            "https://www.ydcmdei.org.cn/article/261",
        ],
    },
    {
        "title": "医疗器械产品技术要求编写指导原则_2022年修订版_2022年第8号",
        "collection": "guidance-registration",
        "urls": [
            "https://docs.team-ra.org/zh/nmpa/guidance/cmde-2022-8",
            "https://www.smei.net.cn/news/noticeDetail.do?id=1051",
        ],
    },
    {
        "title": "深度学习辅助决策医疗器械软件审评要点_2019年第7号_历史参考",
        "collection": "guidance-ai",
        "urls": [
            "https://www.sigma-stat.com/index.php?a=index&aid=389&c=View&m=home",
            "https://cardiology.medsci.cn/article/show_article.do?id=8a741e5005a9",
        ],
    },
    {
        "title": "医用软件通用名称命名指导原则_2021年第48号",
        "collection": "guidance-registration",
        "urls": [
            "https://www.zyqjg.com/article-11285-1.html",
            "https://www.ccfdie.org/cn/yjxx/ylqx/webinfo/2021/08/1622499299051709.htm",
        ],
    },
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.skip_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_stack.append(tag)
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_stack and self.skip_stack[-1] == tag:
            self.skip_stack.pop()
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_stack:
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
    last_error: Optional[Exception] = None
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=90, allow_redirects=True)
            resp.raise_for_status()
            return url, resp
        except Exception as exc:
            last_error = exc
            print(f"⚠️ 备用 URL 失败：{url} -> {exc}")
            time.sleep(0.8)
    raise RuntimeError(f"全部 URL 下载失败：{last_error}")


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
        header = (
            f"标题：{title}\n"
            f"来源URL：{url}\n"
            f"下载时间：{datetime.now().isoformat(timespec='seconds')}\n"
            f"集合：{collection}\n\n"
            "正文：\n"
        )
        path.write_text(header + text, encoding="utf-8")
    elif suffix == ".doc":
        raw_path = OUT_DIR / f"{base}.doc"
        raw_path.write_bytes(resp.content)

        text = extract_doc_with_external_tool(raw_path) or extract_doc_heuristic(raw_path)
        if len(text) < 200:
            raise RuntimeError(f".doc 已下载但文本提取过短：{raw_path}，建议安装 antiword 或 libreoffice 后重试。")

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
        path = OUT_DIR / f"{base}{suffix}"
        path.write_bytes(resp.content)

    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "title": title,
                "collection": collection,
                "source_url": url,
                "all_urls": doc["urls"],
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


def create_traceability_excerpt(source_path: Path) -> Optional[Path]:
    if source_path.suffix.lower() != ".txt":
        return None

    text = source_path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    indices = [i for i, line in enumerate(lines) if "可追溯性" in line or "追溯性" in line]

    if not indices:
        return None

    selected = []
    used = set()
    for idx in indices:
        for j in range(max(0, idx - 8), min(len(lines), idx + 14)):
            if j not in used:
                selected.append(lines[j])
                used.add(j)

    excerpt = "\n".join(selected)
    if len(excerpt) < 200:
        return None

    path = OUT_DIR / "guidance-software__软件可追溯性要求摘录_来自医疗器械软件注册审查指导原则2022.txt"
    header = (
        "标题：软件可追溯性要求摘录\n"
        f"来源文件：{source_path.name}\n"
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}\n"
        "集合：guidance-software\n\n"
        "说明：该文件用于替代清单中的“可追溯性.pdf”。如果后续提供原 PDF，可再单独导入。\n\n"
        "正文：\n"
    )
    path.write_text(header + excerpt, encoding="utf-8")
    print(f"✅ 已生成追溯性摘录：{path.relative_to(PROJECT_ROOT)}")
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
                        timeout=300,
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

    downloaded: List[tuple[Path, str, str]] = []
    failed = []
    uploaded = 0
    software_guidance_path: Optional[Path] = None

    for doc in DOCS:
        try:
            path = download_doc(doc)
            downloaded.append((path, doc["collection"], doc["title"]))

            if "医疗器械软件注册审查指导原则" in doc["title"]:
                software_guidance_path = path

            if upload_doc(path, doc["collection"]):
                uploaded += 1

            time.sleep(0.8)
        except Exception as exc:
            failed.append((doc["title"], doc["urls"], str(exc)))
            print(f"❌ 失败：{doc['title']} -> {exc}")

    if software_guidance_path:
        try:
            excerpt_path = create_traceability_excerpt(software_guidance_path)
            if excerpt_path:
                downloaded.append((excerpt_path, "guidance-software", "软件可追溯性要求摘录"))
                if upload_doc(excerpt_path, "guidance-software"):
                    uploaded += 1
        except Exception as exc:
            failed.append(("软件可追溯性要求摘录", [str(software_guidance_path)], str(exc)))
            print(f"❌ 追溯性摘录生成失败：{exc}")

    report = {
        "total_source_items": len(DOCS),
        "downloaded_files": len(downloaded),
        "uploaded_files": uploaded,
        "failed": failed,
        "output_dir": str(OUT_DIR),
        "base_url": BASE_URL,
    }
    report_path = OUT_DIR / "import_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n====== 第二部分规范性文件导入完成 ======")
    print(f"源清单数量：{len(DOCS)}")
    print(f"下载/生成文件：{len(downloaded)}")
    print(f"上传成功：{uploaded}")
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
