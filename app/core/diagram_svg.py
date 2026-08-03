"""代码绘制的内联 SVG 结构图（供图文教程配图，非 AI 生图）。

四个参数化生成器返回自适应宽度的内联 <svg> 字符串（viewBox + width:100%），
文字全部由代码写入 <text>，保证清晰无乱码、风格统一。配色对齐应用主题：
深蓝 #1a365d / 蓝 #2b6cb0·#3182ce / 浅蓝底 #ebf8ff / 灰边 #e2e8f0。

用法：diagram_svg.flow([...])、cycle([...])、hierarchy([[...],[...]])、cards([(t,d),...])
"""
import html
import math

# 主题配色
DARK = "#1a365d"
BLUE = "#2b6cb0"
ACCENT = "#3182ce"
FILL = "#ebf8ff"
EDGE = "#e2e8f0"
TEXT = "#2d3748"
SUB = "#718096"
FONT = ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "'PingFang SC','Microsoft YaHei',sans-serif")


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _wrap(text, limit):
    """按字数硬折行（中文按字符计），返回行列表。"""
    text = str(text or "").strip()
    if not text:
        return [""]
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= limit:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return lines or [""]


def _tspans(lines, x, y0, dy, cls):
    out = []
    for i, ln in enumerate(lines):
        out.append(f'<tspan x="{x}" y="{y0 + i * dy}">{_esc(ln)}</tspan>')
    return f'<text class="{cls}" text-anchor="middle">{"".join(out)}</text>'


def _svg(w, h, body, extra_css=""):
    css = (f"text{{{FONT}}}"
           f".t-title{{fill:{DARK};font-weight:700}}"
           f".t-body{{fill:{TEXT}}}"
           f".t-sub{{fill:{SUB}}}"
           f".t-white{{fill:#fff;font-weight:600}}" + extra_css)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" style="max-width:{w}px;height:auto;display:block;margin:0 auto">'
            f'<style>{css}</style>{body}</svg>')


def flow(steps, vertical=False):
    """箭头流程图。steps: list[str]（每步一个短语）。"""
    steps = [s for s in (steps or []) if str(s).strip()]
    if not steps:
        return ""
    if vertical:
        bw, bh, gap, pad = 300, 58, 34, 20
        w = bw + pad * 2
        h = pad * 2 + len(steps) * bh + (len(steps) - 1) * gap
        parts = []
        for i, s in enumerate(steps):
            y = pad + i * (bh + gap)
            cx = w / 2
            lines = _wrap(s, 18)
            ty = y + bh / 2 - (len(lines) - 1) * 9 + 6
            parts.append(
                f'<rect x="{pad}" y="{y}" width="{bw}" height="{bh}" rx="10" '
                f'fill="{FILL}" stroke="{ACCENT}" stroke-width="1.5"/>'
                + _tspans(lines, cx, ty, 18, "t-body"))
            if i < len(steps) - 1:
                ay = y + bh
                parts.append(
                    f'<line x1="{cx}" y1="{ay}" x2="{cx}" y2="{ay + gap}" '
                    f'stroke="{ACCENT}" stroke-width="2" marker-end="url(#ah)"/>')
        body = _arrow_marker() + "".join(parts)
        return _svg(w, h, body, ".t-body{font-size:15px}")
    # 横向：自动分行，每行最多 3 步
    per_row = 3 if len(steps) > 4 else min(len(steps), 4)
    bw, bh, hgap, vgap, pad = 200, 74, 46, 40, 20
    rows = [steps[i:i + per_row] for i in range(0, len(steps), per_row)]
    ncol = max(len(r) for r in rows)
    w = pad * 2 + ncol * bw + (ncol - 1) * hgap
    h = pad * 2 + len(rows) * bh + (len(rows) - 1) * vgap
    parts = [_arrow_marker()]
    idx = 0
    for r, row in enumerate(rows):
        y = pad + r * (bh + vgap)
        for c, s in enumerate(row):
            x = pad + c * (bw + hgap)
            cx = x + bw / 2
            lines = _wrap(s, 12)
            ty = y + bh / 2 - (len(lines) - 1) * 9 + 6
            parts.append(
                f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="10" '
                f'fill="{FILL}" stroke="{ACCENT}" stroke-width="1.5"/>'
                + _tspans(lines, cx, ty, 18, "t-body"))
            # 箭头到同行下一个
            if c < len(row) - 1:
                ax = x + bw
                parts.append(
                    f'<line x1="{ax}" y1="{y + bh/2}" x2="{ax + hgap}" y2="{y + bh/2}" '
                    f'stroke="{ACCENT}" stroke-width="2" marker-end="url(#ah)"/>')
            idx += 1
        # 行末到下一行行首的折返箭头
        if r < len(rows) - 1 and rows[r + 1]:
            lastx = pad + (len(row) - 1) * (bw + hgap) + bw / 2
            firstx = pad + bw / 2
            y1 = y + bh
            y2 = y + bh + vgap
            parts.append(
                f'<path d="M {lastx} {y1} v {vgap/2} H {firstx} v {vgap/2}" '
                f'fill="none" stroke="{ACCENT}" stroke-width="2" '
                f'stroke-dasharray="4 3" marker-end="url(#ah)"/>')
    return _svg(w, h, "".join(parts), ".t-body{font-size:15px}")


def cycle(steps, title=""):
    """环形流程（PDCA / 生命周期迭代）。steps: 3-8 个短语。"""
    steps = [s for s in (steps or []) if str(s).strip()][:8]
    n = len(steps)
    if n < 2:
        return flow(steps)
    size = 460
    cx = cy = size / 2
    R = 150          # 结点圆心所在半径
    node_r = 52
    parts = [_arrow_marker()]
    # 中心标题
    if title:
        tl = _wrap(title, 8)
        ty = cy - (len(tl) - 1) * 11 + 6
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="70" fill="{DARK}"/>')
        parts.append(_tspans(tl, cx, ty, 22, "t-white"))
    pts = []
    for i in range(n):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        x = cx + R * math.cos(ang)
        y = cy + R * math.sin(ang)
        pts.append((x, y))
    # 连接弧箭头（顺时针）
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        # 从当前结点边缘到下一结点边缘
        a = math.atan2(y2 - y1, x2 - x1)
        sx = x1 + node_r * math.cos(a)
        sy = y1 + node_r * math.sin(a)
        ex = x2 - (node_r + 8) * math.cos(a)
        ey = y2 - (node_r + 8) * math.sin(a)
        parts.append(
            f'<path d="M {sx:.1f} {sy:.1f} Q {cx} {cy} {ex:.1f} {ey:.1f}" '
            f'fill="none" stroke="{ACCENT}" stroke-width="2" marker-end="url(#ah)"/>')
    # 结点
    for i, (x, y) in enumerate(pts):
        lines = _wrap(steps[i], 7)
        ty = y - (len(lines) - 1) * 9 + 5
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{node_r}" fill="{FILL}" '
            f'stroke="{BLUE}" stroke-width="2"/>'
            + _tspans(lines, x, ty, 17, "t-body"))
    return _svg(size, size, "".join(parts), ".t-body{font-size:14px}.t-white{font-size:16px}")


def hierarchy(layers):
    """分层结构（体系层级 / 文档金字塔）。layers: list[list[str]]，从上到下。"""
    layers = [[c for c in (row or []) if str(c).strip()] for row in (layers or [])]
    layers = [row for row in layers if row]
    if not layers:
        return ""
    bh, vgap, pad, hgap = 62, 30, 20, 16
    ncol = max(len(r) for r in layers)
    bw = 200
    w = pad * 2 + ncol * bw + (ncol - 1) * hgap
    h = pad * 2 + len(layers) * bh + (len(layers) - 1) * vgap
    shades = [DARK, BLUE, ACCENT, "#4299e1", "#63b3ed", "#90cdf4"]
    parts = []
    for r, row in enumerate(layers):
        y = pad + r * (bh + vgap)
        color = shades[min(r, len(shades) - 1)]
        roww = len(row) * bw + (len(row) - 1) * hgap
        x0 = (w - roww) / 2
        for c, s in enumerate(row):
            x = x0 + c * (bw + hgap)
            cx = x + bw / 2
            lines = _wrap(s, 13)
            ty = y + bh / 2 - (len(lines) - 1) * 9 + 6
            parts.append(
                f'<rect x="{x:.1f}" y="{y}" width="{bw}" height="{bh}" rx="8" '
                f'fill="{color}"/>' + _tspans(lines, cx, ty, 18, "t-white"))
    return _svg(w, h, "".join(parts), ".t-white{font-size:15px}")


def cards(items):
    """要点卡片网格。items: list[(标题, 说明)]。"""
    items = [(t, d) for t, d in
             [(i if isinstance(i, (list, tuple)) else (i, "")) for i in (items or [])]
             if str(t).strip()]
    if not items:
        return ""
    ncol = 2 if len(items) <= 4 else 3
    cw, gap, pad = 250, 20, 20
    rows = math.ceil(len(items) / ncol)
    # 卡高按最长说明估算
    ch = 110
    w = pad * 2 + ncol * cw + (ncol - 1) * gap
    h = pad * 2 + rows * ch + (rows - 1) * gap
    parts = []
    for i, (t, d) in enumerate(items):
        r, c = divmod(i, ncol)
        x = pad + c * (cw + gap)
        y = pad + r * (ch + gap)
        tlines = _wrap(t, 14)
        dlines = _wrap(d, 15)[:3]
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="10" '
            f'fill="#fff" stroke="{EDGE}" stroke-width="1.5"/>'
            f'<rect x="{x}" y="{y}" width="6" height="{ch}" rx="3" fill="{ACCENT}"/>')
        # 标题左对齐
        tx = x + 22
        tsp = "".join(f'<tspan x="{tx}" y="{y + 30 + j * 20}">{_esc(l)}</tspan>'
                      for j, l in enumerate(tlines[:2]))
        parts.append(f'<text class="t-title" style="font-size:15px">{tsp}</text>')
        dy0 = y + 30 + min(len(tlines), 2) * 20 + 4
        dsp = "".join(f'<tspan x="{tx}" y="{dy0 + j * 18}">{_esc(l)}</tspan>'
                      for j, l in enumerate(dlines))
        parts.append(f'<text class="t-sub" style="font-size:12.5px">{dsp}</text>')
    return _svg(w, h, "".join(parts))


def _arrow_marker():
    return (f'<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" '
            f'orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L7,3 L0,6 Z" fill="{ACCENT}"/></marker></defs>')


def render(spec):
    """按 {"type":..., "data":..., "caption":...} 生成一个 <figure>；无法识别返回 ""。"""
    if not spec or not isinstance(spec, dict):
        return ""
    typ = (spec.get("type") or "").strip()
    data = spec.get("data")
    caption = spec.get("caption") or ""
    svg = ""
    try:
        if typ == "flow":
            svg = flow(data, vertical=bool(spec.get("vertical")))
        elif typ == "cycle":
            svg = cycle(data, title=spec.get("title", ""))
        elif typ == "hierarchy":
            svg = hierarchy(data)
        elif typ == "cards":
            svg = cards(data)
    except Exception:
        return ""
    if not svg:
        return ""
    cap = f'<figcaption>{_esc(caption)}</figcaption>' if caption else ""
    return f'<figure>{svg}{cap}</figure>'
