from pathlib import Path
import fitz  # pymupdf
from docx import Document as DocxDocument


def load_document(file_path: Path) -> list[dict]:
    """Load document and return list of {page, text} dicts."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(file_path)
    elif suffix == ".docx":
        return _load_docx(file_path)
    elif suffix in (".txt", ".md"):
        return _load_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path) -> list[dict]:
    pages = []
    doc = fitz.open(str(path))
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append({"page": page_num, "text": text})
    doc.close()
    return pages


def _load_docx(path: Path) -> list[dict]:
    doc = DocxDocument(str(path))
    # Group paragraphs into logical pages (~50 paragraphs each)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    page_size = 50
    pages = []
    for i in range(0, len(paragraphs), page_size):
        text = "\n".join(paragraphs[i:i + page_size])
        pages.append({"page": i // page_size + 1, "text": text})
    return pages


def _load_text(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Split into chunks of ~3000 chars as "pages"
    size = 3000
    pages = []
    for i in range(0, len(text), size):
        chunk = text[i:i + size].strip()
        if chunk:
            pages.append({"page": i // size + 1, "text": chunk})
    return pages
