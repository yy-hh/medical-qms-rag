from __future__ import annotations

import json, mimetypes, os, re, time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List

import requests

BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "source_docs" / "ai_product_guidance_20260603"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DOCS: List[Dict] = [
    {
        "title": "肺结节CT图像辅助检测软件注册审查指导原则_2022年第21号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://www.zgcsm.cn/?a=index&aid=1561&c=View&m=home",
            "https://m.cnpharm.com/c/2022-05-26/826754.shtml",
            "https://www.ciopharma.com/supervise/document/2827",
        ],
    },
    {
        "title": "乳腺X射线图像辅助检测软件注册审查指导原则_2022年第22号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://www.ciopharma.com/supervise/document/2828",
            "https://www.zgcsm.cn/?a=index&aid=1562&c=View&m=home",
            "https://m.situcro.com/news/m4314.html",
        ],
    },
    {
        "title": "糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则_2022年第23号",
        "collection": "guidance-ai-product",
        "urls": [
            "https://m.situcro.com/news/m4315.html",
            "https://chines.org.cn/guiding-principles-for-medicaldevices/tnbswmbbyd/",
            "https://www.ciopharma.com/supervise/document/2909",
        ],
    },
]


class E(HTMLParser):
    def __init__(self):
        super().__init__(); self.p=[]; self.sk=False
    def handle_starttag(self,t,a):
        if t in {"script","style","noscript","svg"}: self.sk=True
        if t in {"p","br","div","li","tr","h1","h2","h3","h4","td"}: self.p.append("\n")
    def handle_endtag(self,t):
        if t in {"script","style","noscript","svg"}: self.sk=False
        if t in {"p","div","li","tr","h1","h2","h3","h4","td"}: self.p.append("\n")
    def handle_data(self,d):
        if not self.sk and d.strip(): self.p.append(d.strip())
    def text(self):
        r="\n".join(self.p); r=re.sub(r"[ \t\r\f\v]+"," ",r); r=re.sub(r"\n{3,}","\n\n",r)
        return r.strip()


def safe(t): return re.sub(r"\s+","_",re.sub(r'[\\/:*?"<>|]+',"_",t))[:150]

def to_text(resp):
    if not resp.encoding or resp.encoding.lower()=="iso-8859-1":
        resp.encoding=resp.apparent_encoding or "utf-8"
    e=E(); e.feed(resp.text); return e.text()

def fetch_best(urls):
    bu,bt="",""
    for u in urls:
        try:
            r=requests.get(u,headers=HEADERS,timeout=90,allow_redirects=True)
            r.raise_for_status()
            t=to_text(r)
            print(f"   {u} -> {len(t)}字")
            if len(t)>len(bt): bu,bt=u,t
            if len(bt)>4000: break
        except Exception as ex:
            print(f"   ⚠️ {u} -> {ex}")
        time.sleep(0.6)
    return bu,bt

def upload(path,coll):
    mime=mimetypes.guess_type(path.name)[0] or "text/plain"
    for ep in (f"{BASE_URL}/api/documents/upload",f"{BASE_URL}/api/documents"):
        for k in ("collection","category"):
            try:
                with path.open("rb") as f:
                    r=requests.post(ep,files={"file":(path.name,f,mime)},data={k:coll},timeout=300)
                if r.status_code<400:
                    print(f"📚 已入库：{path.name}"); return True
                if r.status_code not in {404,422}:
                    print(f"⚠️ {r.status_code}: {r.text[:200]}")
            except requests.RequestException as ex:
                print(f"⚠️ {ex}"); return False
    return False

def main():
    ok,failed=0,[]
    for d in DOCS:
        print(f"\n⬇️  {d['title']}")
        u,t=fetch_best(d["urls"])
        if len(t)<800:
            failed.append((d["title"],d["urls"],f"正文过短({len(t)})")); print("   ❌ 都过短"); continue
        p=OUT_DIR/f"{d['collection']}__{safe(d['title'])}.txt"
        p.write_text(f"标题：{d['title']}\n来源URL：{u}\n下载时间：{datetime.now().isoformat(timespec='seconds')}\n集合：{d['collection']}\n\n正文：\n"+t,encoding="utf-8")
        print(f"   ✅ 已保存（{len(t)}字）")
        if upload(p,d["collection"]): ok+=1
    print(f"\n====== AI 产品专项重抓：{ok} / {len(DOCS)} 入库 ======")
    for t_,urls,err in failed:
        print(f"- {t_}: {err}")
        for u in urls: print(f"  {u}")

if __name__=="__main__":
    main()
