"""清洗从政府网站爬取的法规 txt：剥离导航栏/页脚/URL/时间戳/元信息头等网页噪声，
保留法规正文，然后 del 旧 chunk + 重新 ingest 入库。

用法：
    python scripts/clean_source_docs.py --dry           # 干洗预览(不入库),打印每份 原字数→净字数+删除样本
    python scripts/clean_source_docs.py --dry --show 文件关键词   # 看某份清洗前后对照
    python scripts/clean_source_docs.py --apply         # 洗+重新入库(先del旧chunk再ingest)

只处理 file_type='txt' 的 34 份；pdf 不动。collection/doc_name/doc_id 保持不变。
"""
import argparse
import glob
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "qms.db"

# 元信息头(爬虫加的),整行删
META_PREFIX = ("标题：", "来源URL：", "下载时间：", "集合：", "正文：")

# 导航/页脚噪声词：短行命中即删
NAV_WORDS = {
    "首页", "简", "繁", "EN", "登录", "个人中心", "退出", "邮箱", "无障碍",
    "字号", "分享", "打印", "扫一扫", "手机版", "中国政府网", "回到顶部",
    "您的位置", "政务", "大", "中", "小", "关闭", "下一篇", "上一篇",
    "注册", "×", "当前位置", "政策法规", "其他工作文件", "默认",
    # 上海药监等网站的"保护视力色"配色控件
    "保护视力色", "保护视力色:", "杏仁黄", "秋叶褐", "胭脂红", "芥末绿",
    "天蓝", "雪青", "灰", "【字体:", "】",
}
# 页脚起始标志：命中则从此行到文末全删（含政府网站友情链接块）
FOOTER_START = ("网站标识码", "ICP备", "京公网安备", "公网安备", "版权所有",
                "主办单位", "承办单位", "网站地图", "联系我们",
                "友情链接", "关于本网", "网站声明", "国务院部门网站",
                "地方政府网站", "驻外机构", "驻港澳机构")

# 面包屑/元信息行：整行匹配即删（网页导航残留）
CRUMB_RE = re.compile(r"^(>|＞|当前位置|保护视力色|【字体|来源[:：]|原文地址[:：]|相关附件[:：]|正文[:：]?$|浏览次数|打印本?页?$|分享$|字号$)")

# 页眉页脚水印行：PDF每页重复的标准号/机构名（去重时用，匹配即视为可删的重复噪声）
HEADER_RE = re.compile(
    r"^(GB/?T?\s*\d+[\.\d]*\s*[—一\-]\s*\d{4}"      # GB/T 42061—2022(/ISO...后缀不影响)
    r"|YY/?V?T?\s*\d+[\.\d]*\s*[—一\-]\s*\d{4}"      # YY/T 0664一2020
    r"|国家药品监督管理局医?疗?器?械?技?术?审?评?中?心?$"  # 完整或OCR断行的机构名页脚
    r"|疗器械技术审评中心$"
    r"|医疗器械技术审评中心$)")

# 正文起点标志：第X条/第X章/颁布语
ART_RE = re.compile(r"^第[一二三四五六七八九十百千零〇\d]+[条章节篇]")
PROMULGATE_RE = re.compile(r"（.*(令第|第).*号.*(公布|发布|通过|修订|施行)")
URL_RE = re.compile(r"^https?://\S+$")
TS_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}[\sT:\d]*$")
SEP_RE = re.compile(r"^[|｜\s]+$")


def _is_noise_line(ln: str) -> bool:
    s = ln.strip()
    if not s:
        return False  # 空行单独处理(压缩)
    if s in NAV_WORDS:
        return True
    if URL_RE.match(s) or TS_RE.match(s) or SEP_RE.match(s):
        return True
    # 面包屑/护眼色/字体控件/来源/原文地址/相关附件行（多为短行，限≤30字避免误删正文）
    if len(s) <= 30 and CRUMB_RE.match(s):
        return True
    # 短行(≤6字)且含导航词
    if len(s) <= 6 and any(w in s for w in NAV_WORDS):
        return True
    return False


def clean_regulation_text(raw: str):
    """返回 (cleaned, stats)。保守策略：全文逐行只删【确定噪声】(元信息头/导航词短行/URL/
    时间戳/分隔符) + 尾部页脚块。不做"正文起点前全删"(那会误删'一、二、'体例指导原则的正文)。"""
    lines = raw.replace("\r\n", "\n").split("\n")
    n0 = len(lines)

    # 1) 删元信息头(开头连续的 标题：/来源URL：/下载时间：/集合：/正文： 及夹杂空行)
    i = 0
    while i < len(lines) and (
        any(lines[i].strip().startswith(p) for p in META_PREFIX) or not lines[i].strip()
    ):
        i += 1
    lines = lines[i:]

    # 2) 逐行删确定噪声；命中页脚标志则截断到文末
    out_lines = []
    footer_hit = False
    for ln in lines:
        s = ln.strip()
        if any(f in s for f in FOOTER_START):
            footer_hit = True
            break
        if _is_noise_line(ln):
            continue
        out_lines.append(ln)

    # 2.5) 去页眉页脚水印：只删【明确匹配 HEADER_RE】(标准号 GB/T xxx—年份、完整机构名)的行。
    #      这些绝对是 PDF 每页页眉/水印，删了安全，不做"高频短行通用去重"(会误伤表格表头/正文小标题)。
    out_lines = [l for l in out_lines if not HEADER_RE.match(l.strip())]

    # 3) 压缩连续空行
    compact = []
    blank = False
    for ln in out_lines:
        if not ln.strip():
            if not blank:
                compact.append("")
            blank = True
        else:
            compact.append(ln.rstrip())
            blank = False
    cleaned = "\n".join(compact).strip() + "\n"

    drop = 1 - len(cleaned) / max(len(raw), 1)
    stats = {
        "lines_before": n0,
        "lines_after": len(compact),
        "chars_before": len(raw),
        "chars_after": len(cleaned),
        "footer_removed": footer_hit,
        "drop": drop,
        # 保守自检：删除比例>35% 视为可疑(正常网页噪声占比通常<25%)
        "suspect": drop > 0.35,
    }
    return cleaned, stats


def _txt_sources():
    return {os.path.basename(p): p for p in glob.glob(str(ROOT / "data/source_docs/**/*.txt"), recursive=True)}


def _txt_docs():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT DISTINCT doc_id,doc_name,collection FROM chunks WHERE file_type='txt' ORDER BY collection"
    ).fetchall()
    con.close()
    return rows


def dry_run(show=None):
    srcs = _txt_sources()
    docs = _txt_docs()
    print(f"{'状态':<4}{'原字':>8}{'净字':>8}{'删%':>5}  文档")
    print("-" * 78)
    for r in docs:
        fn = r["doc_name"] if r["doc_name"].endswith(".txt") else r["doc_name"] + ".txt"
        path = srcs.get(fn) or srcs.get(r["doc_name"])
        if not path:
            print(f"⚠️源缺 {r['doc_name'][:50]}")
            continue
        raw = open(path, encoding="utf-8").read()
        cleaned, st = clean_regulation_text(raw)
        drop = 100 * st["drop"]
        flag = "⚠️" if st["suspect"] else "✓"
        name = os.path.basename(path)
        print(f"{flag:<4}{st['chars_before']:>8}{st['chars_after']:>8}{drop:>4.0f}%  {name[:48]}")
        if show and show in name:
            print("    ===== 清洗后开头 600 字 =====")
            print("    " + cleaned[:600].replace("\n", "\n    "))
            print("    ===== 清洗后结尾 300 字 =====")
            print("    " + cleaned[-300:].replace("\n", "\n    "))


# 源数据损坏(爬到公司官网/无正文)的文件——不清洗、不入库，列清单待补正文
BROKEN_KEYWORDS = [
    "医疗器械临床评价技术指导原则", "真实世界数据用于医疗器械临床评价",
    "医疗器械软件注册审查指导原则_2022", "人工智能医疗器械注册审查指导原则",
    "医疗器械网络安全注册审查指导原则", "深度学习辅助决策医疗器械软件审评要点",
    "医疗器械生产质量管理规范附录独立软件", "医疗器械生产质量管理规范独立软件现场检查",
    "医疗器械产品技术要求编写指导原则", "肺结节CT图像辅助检测软件注册审查",
    "乳腺X射线图像辅助检测软件注册审查", "糖尿病视网膜病变眼底图像辅助诊断软件",
]

def _is_broken(name: str) -> bool:
    return any(k in name for k in BROKEN_KEYWORDS)


def apply():
    from app.core.rag_engine import get_engine
    engine = get_engine()
    srcs = _txt_sources()
    docs = _txt_docs()
    ok = 0; skipped = []
    for r in docs:
        fn = r["doc_name"] if r["doc_name"].endswith(".txt") else r["doc_name"] + ".txt"
        path = srcs.get(fn) or srcs.get(r["doc_name"])
        if not path:
            print(f"  跳过(源缺): {r['doc_name'][:40]}")
            continue
        name = os.path.basename(path)
        # 坏源数据：不动、不入库(保留原样，待补正文)
        if _is_broken(name):
            skipped.append(name)
            continue
        raw = open(path, encoding="utf-8").read()
        cleaned, st = clean_regulation_text(raw)
        # 安全阀：清洗后若删>85%(疑似源坏但没列入清单)，跳过不入库，报警
        if st["drop"] > 0.85:
            print(f"  ⚠️跳过(删{st['drop']*100:.0f}%疑似坏源): {name[:40]}")
            skipped.append(name)
            continue
        open(path, "w", encoding="utf-8").write(cleaned)
        engine.delete_document(r["doc_id"], r["collection"])
        n = engine.ingest_document(Path(path), r["doc_name"], r["doc_id"], r["collection"])
        print(f"  OK {st['chars_before']}→{st['chars_after']}字 {n}chunk  {name[:40]}")
        ok += 1
    print(f"\n清洗重新入库 {ok} 份；跳过(坏源待补) {len(skipped)} 份")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", default=None)
    args = ap.parse_args()
    if args.apply:
        apply()
    else:
        dry_run(show=args.show)


if __name__ == "__main__":
    main()
