"""把生成的 Markdown 文档转成 .docx（python-docx）。

只覆盖生成内容里实际用到的 Markdown 元素：ATX 标题(#~####)、表格(| 分隔)、
有序/无序列表、引用块、水平线、段落，以及行内 **加粗**。中文字体设为宋体/Noto。
"""
import re
from io import BytesIO

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn


CJK_FONT = "宋体"          # Word 里中文显示；Linux 上无宋体时按字体回退仍可读
HEADING_FONT = "黑体"


def _set_cell_text(cell, text: str):
    cell.text = ""
    para = cell.paragraphs[0]
    _add_inline(para, text.strip())


def _apply_cjk(run, font_name: str):
    run.font.name = font_name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font_name)


def _add_inline(para, text: str, font_name: str = CJK_FONT, size: int = None, bold: bool = False):
    """处理 **加粗** 行内标记，逐段加 run。"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if not part:
            continue
        is_bold = bold
        content = part
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            is_bold = True
            content = part[2:-2]
        run = para.add_run(content)
        run.bold = is_bold
        if size:
            run.font.size = Pt(size)
        _apply_cjk(run, font_name)


def _is_table_sep(line: str) -> bool:
    # |---|---| 这种分隔行
    s = line.strip()
    return bool(re.match(r"^\|?\s*:?-{2,}.*$", s)) and set(s) <= set("|-: \t")


def _parse_table_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def markdown_to_docx(md: str, title: str = "") -> bytes:
    doc = Document()

    # 默认正文字体
    normal = doc.styles["Normal"]
    normal.font.size = Pt(10.5)
    normal.font.name = CJK_FONT

    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 跳过结束标记残留
        if "<!--DOC_END-->" in stripped:
            stripped = stripped.replace("<!--DOC_END-->", "").strip()
            if not stripped:
                i += 1
                continue

        # 空行
        if not stripped:
            i += 1
            continue

        # 水平线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            i += 1
            continue

        # 标题 # ~ ######
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            p = doc.add_paragraph()
            sizes = {1: 18, 2: 15, 3: 13, 4: 12, 5: 11, 6: 11}
            _add_inline(p, text, font_name=HEADING_FONT, size=sizes.get(level, 11), bold=True)
            i += 1
            continue

        # 表格：当前行是 |...| 且下一行是分隔行
        if stripped.startswith("|") and i + 1 < n and _is_table_sep(lines[i + 1]):
            header = _parse_table_row(lines[i])
            i += 2  # 跳过表头和分隔行
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_parse_table_row(lines[i]))
                i += 1
            ncol = len(header)
            table = doc.add_table(rows=1, cols=ncol)
            table.style = "Table Grid"
            for j, h in enumerate(header):
                if j < ncol:
                    _set_cell_text(table.rows[0].cells[j], h)
            for r in rows:
                cells = table.add_row().cells
                for j in range(ncol):
                    _set_cell_text(cells[j], r[j] if j < len(r) else "")
            continue

        # 引用块 >
        if stripped.startswith(">"):
            text = stripped.lstrip(">").strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            _add_inline(p, text, size=10)
            i += 1
            continue

        # 有序列表 1. / 1、
        m = re.match(r"^(\d+)[\.、]\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph(style="List Number")
            _add_inline(p, m.group(2).strip())
            i += 1
            continue

        # 无序列表 - / * / •
        m = re.match(r"^[-*•]\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            _add_inline(p, m.group(1).strip())
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        _add_inline(p, stripped)
        i += 1

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
