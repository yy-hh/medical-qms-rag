"""统一深度清洗全库：对每一份文档跑同一套完整规则，一次性清干净。
从 qms.db 现有内容读 → deep_clean → 写 data/source_docs/clean/ → 覆盖入库。
规则覆盖：元信息头/文件名前缀/网页title尾巴/政务元数据块/导航面包屑/护眼色/页眉页脚水印/友情链接。
"""
import re, sqlite3, sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent

# 开头噪声行（正文起点前，逐行删）
HEAD_NOISE = re.compile(
    r"^(标题[:：]|来源URL|来源文件|下载时间[:：]|生成时间[:：]|集合[:：]|正文[:：]?$|原始附件"
    r"|索\s*引\s*号|主题分类|发文机关|发文字号|成文日期|发布日期|信息来源|浏览次数"
    r"|政策$|国务院政策文件库$|收藏$|留言$|字号$|打印$|分享$|当前位置|您的位置"
    r"|保护视力色|杏仁黄|秋叶褐|胭脂红|芥末绿|天蓝|雪青|默认$|【字体"
    r"|(classification|guidance|standards|regulations|cybersecurity)(-[a-z]+)?__)")
# 导航单字/短词行
NAV = {"首页","简","繁","EN","登录","个人中心","退出","邮箱","无障碍","中国政府网",
       "回到顶部","政务","关闭","下一篇","上一篇","注册","×","灰","大","中","小",">","＞"}
# 页脚起点（到文末全删）
FOOTER = ("网站标识码","ICP备","京公网安备","公网安备","版权所有","主办单位","承办单位",
          "网站地图","联系我们","友情链接","关于本网","网站声明","国务院部门网站",
          "地方政府网站","驻外机构","驻港澳机构","全国政协","国家监察委员会",
          "最高人民法院","最高人民检察院")
# title 网页后缀（行内出现→截断该行到后缀前）
TITLE_TAIL = re.compile(r"(_其他工作文件_.*|_国务院公报_.*|_国务院文件_.*|_中国政府网.*|__\d{4}年第.*号国务院公报.*)$")
# 页眉页脚水印（标准号/机构名，高频重复才删）
HEADER = re.compile(r"^(GB/?T?\s*\d+[\.\d]*\s*[—一\-]\s*\d{4}|YY/?V?T?\s*\d+[\.\d]*\s*[—一\-]\s*\d{4}"
                    r"|国家药品监督管理局医?疗?器?械?技?术?审?评?中?心?$|疗器械技术审评中心$|医疗器械技术审评中心$)")
URL = re.compile(r"^https?://\S+$")
TS = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}[\sT:\d]*$")
SEP = re.compile(r"^[|｜>＞\s:：]+$")
# 正文起点：实质内容行
BODY = re.compile(r"(^第[一二三四五六七八九十百千零〇\d]+[条章]|^为(了|贯|加强|规范|落实|保证|指导)"
                  r"|^根据《|^按照《|.*管理总局令（第|^中华人民共和国|^附件$|^ICS\s|^—\s*\d+\s*—|^附表)")


ART_START = re.compile(r"^第[一二三四五六七八九十]+[条章]")
PROMU = re.compile(r"^[（(]\d{4}年.*(公布|通过|修订|施行|令第)")

def deep_clean(text: str, keep_title: str = "") -> str:
    lines = text.replace("\r\n", "\n").split("\n")

    # A) 法条类强清：若正文含"第一章/第一条"，正文起点=首个第X章/条；
    #    起点前只保留【首个非噪声标题行】+【颁布语行】，其余(网站菜单/目录)全删。
    #    这比列举噪声词可靠——不同网站菜单词各异，追不全。
    art_idx = next((i for i, ln in enumerate(lines) if ART_START.match(ln.strip())), None)
    if art_idx is not None and art_idx > 2:
        head_keep = []
        title_taken = False
        for ln in lines[:art_idx]:
            s = ln.strip()
            if not s:
                continue
            if PROMU.match(s):                     # 颁布语，保留
                head_keep.append(s); continue
            if not title_taken and not (HEAD_NOISE.match(s) or s in NAV or URL.match(s)
                                        or TS.match(s) or SEP.match(s) or TITLE_TAIL.search(s)):
                # 首个实质行当标题保留(标题通常是文件名/法规名)，其余起点前的行全丢
                if 4 <= len(s) <= 40 and ('法' in s or '条例' in s or '办法' in s
                                          or '规则' in s or '规范' in s or '指导原则' in s
                                          or '要点' in s or '目录' in s or '程序' in s or '标准' in s):
                    head_keep.append(s); title_taken = True
        body = head_keep + [""] + lines[art_idx:]
        start = 0
    else:
        # 非法条类：逐行跳过开头噪声(原逻辑)
        start = 0
        for i, ln in enumerate(lines[:60]):
            s = ln.strip()
            if not s:
                start = i + 1; continue
            if HEAD_NOISE.match(s) or s in NAV or URL.match(s) or TS.match(s) or SEP.match(s):
                start = i + 1; continue
            if TITLE_TAIL.search(s) and len(s) < 60:
                start = i + 1; continue
            if BODY.search(s) or len(s) >= 25:
                start = i; break
            start = i + 1
        body = lines[start:]

    # B) 逐行清：页脚截断 + 行内噪声删
    out = []
    for ln in body:
        s = ln.strip()
        if any(f in s for f in FOOTER):
            break
        if not s:
            out.append(""); continue
        if s in NAV or URL.match(s) or TS.match(s) or SEP.match(s):
            continue
        if HEAD_NOISE.match(s):
            continue
        # title 尾巴：截掉行内网页后缀
        m = TITLE_TAIL.search(s)
        if m:
            ln = s[:m.start()].rstrip()
            if not ln.strip():
                continue
        out.append(ln)

    # C) 去页眉页脚水印（只删明确 HEADER 匹配且重复>3次的）
    cnt = Counter(l.strip() for l in out if l.strip())
    hn = {l for l, n in cnt.items() if n > 3 and HEADER.match(l)}
    if hn:
        out = [l for l in out if l.strip() not in hn]

    # D) 压缩空行
    res, blank = [], False
    for l in out:
        if not l.strip():
            if not blank: res.append("")
            blank = True
        else:
            res.append(l.rstrip()); blank = False
    cleaned = "\n".join(res).strip()
    if keep_title and not cleaned.startswith(keep_title[:10]):
        cleaned = keep_title + "\n\n" + cleaned
    return cleaned + "\n"


def main():
    from app.core.rag_engine import get_engine
    con = sqlite3.connect(ROOT / "qms.db"); con.row_factory = sqlite3.Row
    e = get_engine()
    CLEAN = ROOT / "data/source_docs/clean"; CLEAN.mkdir(parents=True, exist_ok=True)

    docs = {}
    for r in con.execute("SELECT doc_id,doc_name,collection,chunk_index,text FROM chunks ORDER BY doc_id,chunk_index"):
        docs.setdefault(r["doc_id"], {"name": r["doc_name"], "col": r["collection"], "ch": []})["ch"].append(r["text"] or "")

    done = 0
    for did, d in docs.items():
        raw = "\n".join(d["ch"])
        cleaned = deep_clean(raw)
        if len(cleaned) < 200:   # 安全阀：清太狠不覆盖，保留原样报警
            print(f"  ⚠️跳过(清后过短{len(cleaned)}): {d['name'][:40]}")
            continue
        sp = CLEAN / (re.sub(r"[/\\]", "_", d["name"]).rsplit(".", 1)[0] + ".txt")
        sp.write_text(cleaned, encoding="utf-8")
        e.delete_document(did, d["col"])
        e.ingest_document(sp, d["name"], did, d["col"])
        done += 1
    print(f"\n深度清洗完成：{done}/{len(docs)} 份")


if __name__ == "__main__":
    main()
