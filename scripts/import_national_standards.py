from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import requests

BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STD_DIR = PROJECT_ROOT / "data" / "source_docs" / "national_standards_20260603"


def infer_collection(name: str) -> str:
    # 信息安全/数据类国标归 cybersecurity，其余质量/软件标准归 standards
    if any(k in name for k in ["35273", "39477", "信息安全", "个人信息", "数据安全"]):
        return "cybersecurity"
    return "standards"


def upload(path: Path, collection: str) -> bool:
    mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
    for endpoint in (f"{BASE_URL}/api/documents/upload", f"{BASE_URL}/api/documents"):
        for key in ("collection", "category"):
            try:
                with path.open("rb") as f:
                    r = requests.post(endpoint, files={"file": (path.name, f, mime)},
                                      data={key: collection}, timeout=600)
                if r.status_code < 400:
                    import json
                    try:
                        n = json.loads(r.text).get("chunk_count", "?")
                    except Exception:
                        n = "?"
                    print(f"📚 已入库：{path.name} -> {collection}（{n} 块）")
                    return True
                if r.status_code not in {404, 422}:
                    print(f"⚠️ 上传失败 {r.status_code}: {r.text[:200]}")
            except requests.RequestException as exc:
                print(f"⚠️ 上传异常：{exc}")
                return False
    return False


def main() -> None:
    if not STD_DIR.exists():
        raise SystemExit(f"目录不存在：{STD_DIR}")

    pdfs = sorted([p for p in STD_DIR.iterdir()
                   if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".doc", ".txt"}])
    if not pdfs:
        print(f"⚠️ 目录里没有文件，请先拷入 PDF：{STD_DIR}")
        return

    print(f"目录：{STD_DIR}")
    print(f"待入库文件：{len(pdfs)}\n")

    ok = 0
    for p in pdfs:
        coll = infer_collection(p.name)
        print(f"🔄 {p.name}  ->  {coll}")
        if upload(p, coll):
            ok += 1

    print(f"\n====== 国家标准导入完成：{ok} / {len(pdfs)} ======")


if __name__ == "__main__":
    main()
