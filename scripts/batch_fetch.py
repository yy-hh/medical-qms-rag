#!/usr/bin/env python
"""
批量抓取医疗器械法规文件（HTML页面 + PDF）并导入 QMS 知识库。

用法：
    python scripts/batch_fetch.py
"""
import sys
import os
import uuid
import time
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from app.core.rag_engine import RAGEngine
from app.core.config import settings

# ── URL 清单 ────────────────────────────────────────────────────────────────

URLS = [
    # ─── 法规文件 (regulations) ─────────────────────────────────────────────
    ("https://www.gov.cn/zhengce/content/2021-03/18/content_5593739.htm",     "regulations", "医疗器械监督管理条例(2021).txt"),
    ("https://www.gov.cn/gongbao/content/2021/content_5654783.htm",           "regulations", "医疗器械监督管理条例国务院令第739号.txt"),
    ("https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_24dbff6e15494c9cb112ea15ed158001.html", "regulations", "SAMR医疗器械相关公告2023.txt"),
    ("https://www.nifdc.org.cn/directory/web/nifdc/xxgk/zcfg/flfg/20260105103302172.html", "regulations", "NIFDC法规文件2026.txt"),
    ("https://www.cncsdr.org/ggtz/ggzz/202203/t20220311_304189.html",         "regulations", "CNCSDR公告2022_304189.txt"),
    ("https://www.cncsdr.org/ggtz/ggzz/202203/t20220311_304187.html",         "regulations", "CNCSDR公告2022_304187.txt"),
    ("https://www.ydcmdei.org.cn/article/620",                                 "regulations", "YDCMDEI文章620.txt"),
    ("https://www.ydcmdei.org.cn/article/261",                                 "regulations", "YDCMDEI文章261.txt"),
    ("https://www.ydcmdei.org.cn/article/401",                                 "regulations", "YDCMDEI文章401.txt"),
    ("https://m.cnpharm.com/c/2022-03-09/819658.shtml",                       "regulations", "医疗器械注册管理办法2022.txt"),
    ("https://mpa.xinjiang.gov.cn/xjyjj/gjjdt/202202/489119998f8549a3af7d64e500c08bdd.shtml", "regulations", "新疆药监局通知2022.txt"),
    ("https://www.gov.cn/gongbao/2026/issue_12506/202601/content_7055196.html","regulations", "国务院公报2026.txt"),
    ("https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_51afc62ef3c84455b28b113a628f9e35.html", "regulations", "SAMR法规司文件2023.txt"),
    ("https://www.nmpa.gov.cn/xxgk/fgwj/gzwj/gzwjylqx/20200604162801601.html","regulations", "NMPA医疗器械工作文件2020.txt"),
    ("https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20190712113301132.html", "regulations", "NMPA医疗器械公告2019.txt"),
    ("https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzbmgz/201810/t20181016_146244.html", "regulations", "司法部网络安全等级保护条例2018.txt"),
    # ─── 网络安全法规 (regulations) ──────────────────────────────────────────
    ("https://www.cac.gov.cn/2016-11/07/c_1119867116.htm",                    "regulations", "网络安全法2016.txt"),
    ("https://www.cac.gov.cn/2021-06/11/c_1624994566919140.htm",              "regulations", "数据安全法2021.txt"),
    ("https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm",              "regulations", "个人信息保护法2021.txt"),
    ("https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm",              "regulations", "网络安全法修正2023.txt"),
    # ─── 标准文件 (standards) ────────────────────────────────────────────────
    ("https://mdcpp.com/doc/materialDownload/ISO13485-2016%E4%B8%AD%E6%96%87%E7%89%88.pdf",       "standards",    "ISO13485-2016中文版.pdf"),
    ("https://www.nifdc.org.cn/directory/web/nifdc/images/obbSvcHGxvfQtSDWysGudzA7czlz7UgWVktVDAyODctMjAxN9Om08PWuMTPobfV98fz0uK8+7jlLnBkZg==.pdf", "standards", "YY_T0287-2017医疗器械质量管理体系.pdf"),
    ("https://pro5323b5d3-pic11.ysjianzhan.cn/upload/33_GB-T42061-2022YLQJZLGLTXYYFGDYQ.pdf",     "standards",    "GBT42061-2022医疗器械质量管理体系.pdf"),
    ("https://www.hzynd.net/upload/20221230134214.pdf",                                             "standards",    "医疗器械标准文件2022.pdf"),
    ("https://www.skhosp.cn/UploadFiles/kyjx/2023/8/202308101637200522.pdf",                       "standards",    "医疗器械相关标准2023.pdf"),
    ("https://www.samr.gov.cn/cms_files/filemanager/samr/www/samrnew/samrgkml/nsjg/fgs/202203/W020220322602924081129.pdf", "standards", "SAMR标准文件2022.pdf"),
    ("https://www.cmde.org.cn/hbpdf/YY0664-2020.pdf",                                              "standards",    "YY0664-2020医疗器械软件文档.pdf"),
    ("https://www.cmde.org.cn/hbpdf/YY1474-2016.pdf",                                              "standards",    "YY1474-2016移动医疗器件软件.pdf"),
    ("https://www.nifdc.org.cn/directory/web/nifdc/infoAttach/9218a3d5-6e22-4607-9b3d-318aec189b5f.pdf", "standards", "NIFDC标准文件.pdf"),
    ("https://mdcpp.com/doc/materialDownload/GBT25000.51-2016..pdf",                               "standards",    "GBT25000.51-2016软件质量模型.pdf"),
    ("https://www.cmde.org.cn/hbpdf/YY1833.1-2022.pdf",                                            "standards",    "YY1833.1-2022医疗器件网络安全.pdf"),
]

SKIP_URLS = {
    "file:///D:/google_download/GBT+35273-2020.pdf",          # 本地 Windows 文件
    "https://erps.cmde.org.cn/entinfo/entinfoRegAction!toRegSaveOrUpdate.do",  # Web 应用表单
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/pdf,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"


def clean_html(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove navigation, scripts, styles
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
        tag.decompose()

    # Try to find main content area
    main = (
        soup.find("div", class_=re.compile(r"content|article|main|text|body", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )
    text = main.get_text(separator="\n", strip=True)
    # Remove excessive blank lines
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines)


def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return clean_html(r.text, url)
    except Exception as e:
        print(f"    HTML fetch error: {e}")
        return None


def download_pdf(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True, verify=False)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest.stat().st_size > 1000
    except Exception as e:
        print(f"    PDF download error: {e}")
        return False


def main():
    import urllib3
    urllib3.disable_warnings()

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print("Initializing RAG engine...")
    engine = RAGEngine()

    ok, fail = 0, 0
    for url, collection, filename in URLS:
        if url in SKIP_URLS:
            print(f"  [SKIP] {filename}")
            continue

        print(f"  [{collection}] {filename}")
        save_path = DOWNLOAD_DIR / filename
        doc_id = str(uuid.uuid4())[:8]

        if filename.endswith(".pdf"):
            if not download_pdf(url, save_path):
                print(f"    => FAILED (download)")
                fail += 1
                time.sleep(1)
                continue
        else:
            text = fetch_html(url)
            if not text or len(text) < 100:
                print(f"    => FAILED (empty content, len={len(text) if text else 0})")
                fail += 1
                time.sleep(1)
                continue
            # Prepend URL as context
            save_path.write_text(f"来源URL：{url}\n\n{text}", encoding="utf-8")

        try:
            n = engine.ingest_document(save_path, filename, doc_id, collection)
            print(f"    => OK ({n} chunks)")
            ok += 1
        except Exception as e:
            print(f"    => INGEST FAILED: {e}")
            fail += 1

        time.sleep(0.5)

    print(f"\n完成：成功 {ok} 个，失败 {fail} 个")


if __name__ == "__main__":
    main()
