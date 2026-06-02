from app.core.config import settings


def chunk_pages(pages: list[dict], chunk_size: int | None = None, overlap: int | None = None) -> list[dict]:
    """Split pages into overlapping text chunks.

    Returns list of {page, chunk_index, text}.
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    chunks = []
    idx = 0
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "page": page_num,
                    "chunk_index": idx,
                    "text": chunk_text,
                })
                idx += 1
            if end >= len(text):
                break
            start = end - overlap
    return chunks
