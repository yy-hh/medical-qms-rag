#!/usr/bin/env python
"""CLI tool for batch document ingestion.

Usage:
    python scripts/ingest.py data/documents/
    python scripts/ingest.py path/to/file.pdf --collection regulations
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.core.rag_engine import RAGEngine
from app.core.config import settings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch ingest documents into the QMS knowledge base")
    parser.add_argument("path", help="File or directory to ingest")
    parser.add_argument("--collection", default=settings.default_collection, help="Collection name")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)

    files = list(target.glob("**/*")) if target.is_dir() else [target]
    allowed = {".pdf", ".docx", ".txt", ".md"}
    files = [f for f in files if f.suffix.lower() in allowed and f.is_file()]

    if not files:
        print("No supported files found.")
        sys.exit(0)

    print(f"Found {len(files)} files. Initializing engine...")
    engine = RAGEngine()

    for f in files:
        doc_id = str(uuid.uuid4())[:8]
        print(f"  [{doc_id}] {f.name} ... ", end="", flush=True)
        try:
            n = engine.ingest_document(f, f.name, doc_id, args.collection)
            print(f"{n} chunks")
        except Exception as e:
            print(f"FAILED: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
