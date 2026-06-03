from __future__ import annotations

import mimetypes
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

BASE_URL = os.getenv("QMS_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = PROJECT_ROOT / "data" / "source_docs" / "ai_product_guidance_20260603"
COLLECTION = "guidance-ai-product"


def doc_to_text(path: Path) -> Optional[str]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "txt:Text",
                     "--outdir", str(tmp_path), str(path)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                )
                txts = list(tmp_path.glob("*.txt"))
                if txts:
                    text = txts[0].read_text(encoding="utf-8", errors="ignore").strip()
                    if len(text) > 200:
                        return text
            except Exception as exc:
                print(f"   soffice 转换异常：{exc}")
    for tool in ("antiword", "catdoc"):
        exe = shutil.which(tool)
        if exe:
            try:
                r = subprocess.run([exe, str(path)], check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                text = r.stdout.decode("utf-8", errors="ignore").strip()
                if len(text) > 200:
                    return text
            except Exception:
                pass
    return None


def upload(path: Path) -> bool:
    mime = mimetypes.guess_type(path.name)[0] or "text/plain"
    for endpoint in (f"{BASE_URL}/api/documents/upload", f"{BASE_URL}/api/documents"):
        for key in ("collection", "category"):
            try:
                with path.open("rb") as f:
                    resp = requests.post(endpoint, files={"file": (path.name, f, mime)},
                                         data={key: COLLECTION}, timeout=300)
                if resp.status_code < 400:
                    print(f"📚 已入库：{path.name}")
                    return True
                if resp.status_code not in {404, 422}:
                    print(f"⚠️ 上传失败 {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as exc:
                print(f"⚠️ 上传异常：{exc}")
                return False
    return False


def main() -> None:
    docs = sorted(DOC_DIR.glob("*.doc"))
    if not docs:
        print("未找到 .doc 文件")
        return
    if not (shutil.which("soffice") or shutil.which("libreoffice") or shutil.which("antiword")):
        print("❌ 未检测到 libreoffice / antiword，请先安装：sudo apt-get install -y libreoffice-writer")
        return

    ok = 0
    for doc in docs:
        print(f"\n🔄 处理：{doc.name}")
        text = doc_to_text(doc)
        if not text:
            print(f"   ⚠️ 仍提取失败：{doc.name}")
            continue
        txt_path = doc.with_suffix(".txt")
        header = (f"标题：{doc.stem.split('__', 1)[-1]}\n原始附件：{doc.name}\n"
                  f"提取时间：{datetime.now().isoformat(timespec='seconds')}\n"
                  f"集合：{COLLECTION}\n\n正文：\n")
        txt_path.write_text(header + text, encoding="utf-8")
        print(f"   ✅ 已生成：{txt_path.name}（{len(text)} 字）")
        if upload(txt_path):
            ok += 1

    print(f"\n====== 重新处理完成：{ok} / {len(docs)} 入库 ======")


if __name__ == "__main__":
    main()
