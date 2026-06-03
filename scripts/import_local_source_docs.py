from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import requests

BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "data" / "source_docs"
SUPPORTED_SUFFIXES = {".txt", ".pdf", ".docx"}

def infer_collection(path: Path) -> str:
    name = path.name
    if "__" in name:
        return name.split("__", 1)[0]

    lower = name.lower()
    if "classification" in lower or "分类" in name:
        return "classification"
    if any(k in name for k in ["网络", "数据", "个人信息", "人工智能", "算法", "深度合成"]):
        return "cybersecurity"
    if "qms" in lower or "体系" in name or "流程" in name:
        return "qms-framework"
    return "regulations"

def upload_file(path: Path, collection: str) -> bool:
    endpoint = f"{BASE_URL}/api/documents/upload"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    with path.open("rb") as f:
        resp = requests.post(
            endpoint,
            files={"file": (path.name, f, mime)},
            data={"collection": collection},
            timeout=240,
        )

    if resp.status_code >= 400:
        print(f"❌ 入库失败：{path.name} -> {resp.status_code} {resp.text[:300]}")
        return False

    print(f"✅ 已入库：{path.relative_to(PROJECT_ROOT)} -> {collection}")
    return True

def main() -> None:
    if not SOURCE_DIR.exists():
        raise SystemExit(f"源文件目录不存在：{SOURCE_DIR}")

    files = [
        p for p in SOURCE_DIR.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_SUFFIXES
        and not p.name.endswith(".meta.json")
    ]

    print(f"源文件目录：{SOURCE_DIR}")
    print(f"上传目标：{BASE_URL}")
    print(f"待导入文件数：{len(files)}")

    ok = 0
    for path in sorted(files):
        if upload_file(path, infer_collection(path)):
            ok += 1

    print("\n====== 本地源文件导入完成 ======")
    print(f"成功：{ok} / {len(files)}")

if __name__ == "__main__":
    main()
