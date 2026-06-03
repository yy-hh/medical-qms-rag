#!/usr/bin/env python
"""Clear all chunks and re-ingest every file in data/documents/ with the current chunker."""
import sys, uuid, sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()

from app.core.rag_engine import RAGEngine, DB_PATH
from app.core.config import settings

# doc_id and collection are stored in the file names as: <collection>/<doc_id>_<original_name>
# We keep a simple mapping file next to the DB.

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"

# Mapping: file stem prefix → collection
COLLECTION_MAP = {
    "regulations": "regulations",
    "standards": "standards",
    "guidelines": "guidelines",
}

# Known collection for specific files (by suffix/name keywords)
def guess_collection(fname: str) -> str:
    name = fname.lower()
    std_keywords = ["iso", "yy", "gb", "iec", "标准"]
    for kw in std_keywords:
        if kw in name:
            return "standards"
    return "regulations"


def main():
    print("Clearing existing chunks...")
    db = sqlite3.connect(str(DB_PATH))
    db.execute("DELETE FROM chunks")
    db.commit()
    db.close()
    print("Done.\n")

    allowed = {".pdf", ".docx", ".txt", ".md"}
    files = sorted([f for f in DOCS_DIR.iterdir() if f.suffix.lower() in allowed])
    if not files:
        print("No files found in", DOCS_DIR)
        return

    print(f"Re-ingesting {len(files)} files with new chunker...\n")
    engine = RAGEngine()

    ok = fail = 0
    for f in files:
        # Derive doc_id from file name prefix (e.g. "a1b2c3d4_xxx.pdf" → "a1b2c3d4")
        doc_id = f.stem[:8] if len(f.stem) >= 8 else str(uuid.uuid4())[:8]
        collection = guess_collection(f.name)
        print(f"  [{collection}] {f.name[:60]:<60} ", end="", flush=True)
        try:
            n = engine.ingest_document(f, f.name, doc_id, collection)
            print(f"{n:4d} chunks ✓")
            ok += 1
        except Exception as e:
            print(f"FAILED: {e}")
            fail += 1

    print(f"\n✓ {ok} 成功  ✗ {fail} 失败")
    h = engine.health()
    print(f"知识库: {h['total_documents']} 篇文档 / {h['total_chunks']} 个文本块")


if __name__ == "__main__":
    main()
