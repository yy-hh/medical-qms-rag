import re
from app.core.config import settings

# Chinese legal doc: 第X章/条/节
_REG_SPLIT = re.compile(
    r'(?=第[零一二三四五六七八九十百千]+[章条节]\s*\S)'
)
# ISO/YY/GB standard: 4.1, 4.2.3 section headings at line start
_STD_SPLIT = re.compile(
    r'(?=(?:^|\n)\d+(?:\.\d+){1,3}\s+\S)'
)
# Chinese sentence boundaries for fallback splitting
_SENTENCE_END = re.compile(r'(?<=[。！？；\n])')


def chunk_pages(pages: list[dict], chunk_size: int | None = None, overlap: int | None = None) -> list[dict]:
    chunk_size = chunk_size or settings.chunk_size
    max_size = max(chunk_size, 800)  # regulatory articles can be long
    min_size = 60

    chunks = []
    idx = 0
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]

        raw = _smart_split(text, max_size)
        for chunk_text in raw:
            chunk_text = chunk_text.strip()
            if len(chunk_text) < min_size:
                continue
            chunks.append({"page": page_num, "chunk_index": idx, "text": chunk_text})
            idx += 1

    return chunks


def _smart_split(text: str, max_size: int) -> list[str]:
    # Try regulatory (第X条) split first
    parts = _REG_SPLIT.split(text)
    if len(parts) > 2:
        return _merge_and_cap(parts, max_size)

    # Try ISO/standard section split
    parts = _STD_SPLIT.split(text)
    if len(parts) > 2:
        return _merge_and_cap(parts, max_size)

    # Fallback: sentence-aware split
    return _sentence_split(text, max_size)


def _merge_and_cap(parts: list[str], max_size: int) -> list[str]:
    """Merge tiny adjacent parts; hard-split oversized ones."""
    result = []
    buf = ""
    for p in parts:
        if not p.strip():
            continue
        if len(buf) + len(p) <= max_size:
            buf += p
        else:
            if buf:
                result.append(buf)
            buf = p if len(p) <= max_size else ""
            if len(p) > max_size:
                result.extend(_sentence_split(p, max_size))
    if buf:
        result.append(buf)
    return result or [parts[0]] if parts else []


def _sentence_split(text: str, max_size: int) -> list[str]:
    sentences = _SENTENCE_END.split(text)
    result = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) <= max_size:
            buf += s
        else:
            if buf:
                result.append(buf)
            # Hard split if single sentence is too long
            if len(s) > max_size:
                for i in range(0, len(s), max_size):
                    result.append(s[i:i + max_size])
                buf = ""
            else:
                buf = s
    if buf:
        result.append(buf)
    return result or [text]
