import logging
from pathlib import Path
import fitz  # pymupdf
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)


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


def _ocr_page(page) -> str:
    """OCR fallback for image-based PDF pages."""
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
    except Exception as e:
        logger.warning("OCR failed on page %s: %s", page.number + 1, e)
        return ""


def _load_pdf(path: Path) -> list[dict]:
    pages = []
    doc = fitz.open(str(path))
    total = len(doc)
    text_pages = sum(1 for p in doc if p.get_text("text").strip())
    use_ocr = text_pages == 0 and total > 0

    if use_ocr:
        logger.info("Scanned PDF detected (%s), using OCR (%d pages)", path.name, total)

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text and use_ocr:
            text = _ocr_page(page)
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
