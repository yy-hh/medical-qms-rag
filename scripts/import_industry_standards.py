from __future__ import annotations
import json, mimetypes, os
from pathlib import Path
import requests

BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STD_DIR = PROJECT_ROOT / "data" / "source_docs" / "industry_standards_yyt_20260603"


def upload(path: Path, collection: str = "standards") -> bool:
    mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
    for endpoint in (f"{BASE_URL}/api/documents/upload", f"{BASE_URL}/api/documents"):
        for key in ("collection", "category"):
            try:
                with path.open("rb") as f:
                    r = requests.post(endpoint, files={"file": (path.name, f, mime)},
                                      data={key: collection}, timeout=600)
                if r.status_code < 400:
                    try:
                        n = json.loads(r.text).get("chunk_count", "?")
                    except Exception:
                        n = "?"
                    print(f"📚 已入库：{path.name}（{n} 块）")
                    return True
                if r.status_code not in {404, 422}:
                    print(f"⚠️ 失败 {r.status_code}: {r.text[:200]}")
            except requests.RequestException as exc:
                print(f"⚠️ 异常：{exc}")
                return False
    return False


def main() -> None:
    if not STD_DIR.exists():
        raise SystemExit(f"目录不存在：{STD_DIR}")
    pdfs = sorted([p for p in STD_DIR.iterdir()
                   if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".doc", ".txt"}])
    if not pdfs:
        print(f"⚠️ 目录为空，请先拷入 YY/T 标准 PDF：{STD_DIR}")
        return
    print(f"目录：{STD_DIR}\n待入库：{len(pdfs)} 个\n")
    ok = 0
    for p in pdfs:
        print(f"🔄 {p.name}")
        if upload(p):
            ok += 1
    print(f"\n====== YY/T 行业标准导入完成：{ok} / {len(pdfs)} ======")


if __name__ == "__main__":
    main()
