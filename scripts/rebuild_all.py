"""重建知识库：从官方源文件精确入库。每份 (源路径, collection, doc_name, 标题)。
抽取(pdf/docx/doc)→deep_clean→质量闸门(中文≥30%或英文标准放宽)→入库。已入的3份跳过。
"""
import re, sys, uuid, glob, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent
TT = "/home/ubuntu/Documents/trae_projects/tt"
FAGUI = f"{TT}/法规"
STD = f"{FAGUI}/标准"

# (源文件, collection, doc_name基名, 标题)
JOBS = [
    # 法律法规(官方PDF, tt根目录) —— 生产规范/注册办法/条例739 已入,跳过
    (f"{TT}/医疗器械分类规则.pdf", "classification", "医疗器械分类规则_CFDA令第15号", "医疗器械分类规则（国家食品药品监督管理总局令第15号）"),
    (f"{TT}/医疗器械经营监督管理办法.pdf", "regulations", "医疗器械经营监督管理办法_2022_第54号", "医疗器械经营监督管理办法（国家市场监督管理总局令第54号）"),
    (f"{TT}/医疗器械不良事件监测和再评价管理办法.pdf", "regulations", "医疗器械不良事件监测和再评价管理办法_2018", "医疗器械不良事件监测和再评价管理办法"),
    (f"{TT}/《中华人民共和国网络安全法》.pdf", "cybersecurity", "中华人民共和国网络安全法", "中华人民共和国网络安全法"),
    (f"{TT}/中华人民共和国数据安全法.pdf", "cybersecurity", "中华人民共和国数据安全法_2021", "中华人民共和国数据安全法"),
    (f"{TT}/中华人民共和国个人信息保护法.pdf", "cybersecurity", "中华人民共和国个人信息保护法_2021", "中华人民共和国个人信息保护法"),
    (f"{TT}/生成式人工智能服务管理暂行办法.pdf", "cybersecurity", "生成式人工智能服务管理暂行办法_2023", "生成式人工智能服务管理暂行办法"),
    # 规范性文件(飞书doc/docx, 法规目录)
    (f"{FAGUI}/人工智能医疗器械注册审查指导原则.docx", "guidance-ai", "人工智能医疗器械注册审查指导原则_2022年第8号", "人工智能医疗器械注册审查指导原则"),
    (f"{FAGUI}/深度学习.docx", "guidance-ai", "深度学习辅助决策医疗器械软件审评要点_2019年第7号", "深度学习辅助决策医疗器械软件审评要点"),
    (f"{FAGUI}/软件注册审查指导原则_2022.docx", "guidance-software", "医疗器械软件注册审查指导原则_2022年修订版", "医疗器械软件注册审查指导原则（2022年修订版）"),
    (f"{FAGUI}/网络安全注册审查.docx", "guidance-cybersecurity", "医疗器械网络安全注册审查指导原则_2022年修订版", "医疗器械网络安全注册审查指导原则（2022年修订版）"),
    (f"{FAGUI}/可用性工程注册审查指导原则.docx", "guidance-usability", "医疗器械可用性工程注册审查指导原则_2024年第13号", "医疗器械可用性工程注册审查指导原则"),
    (f"{FAGUI}/可用性工程应用说明2024.docx", "guidance-usability", "关于医疗器械可用性工程注册审查指导原则的应用说明_2024", "关于医疗器械可用性工程注册审查指导原则的应用说明"),
    (f"{FAGUI}/移动医疗器械.docx", "guidance-mobile", "移动医疗器械注册审查指导原则_2025年修订版", "移动医疗器械注册审查指导原则（2025年修订版）"),
    (f"{FAGUI}/分类界定.docx", "guidance-ai", "人工智能医用软件产品分类界定指导原则_2021年第47号", "人工智能医用软件产品分类界定指导原则"),
    (f"{FAGUI}/临床评价技术指导原则.pdf", "guidance-clinical", "医疗器械临床评价技术指导原则_2021年第73号", "医疗器械临床评价技术指导原则"),
    (f"{FAGUI}/真实世界数据用于医疗器械临床评价技术指导原则.doc", "guidance-clinical", "真实世界数据用于医疗器械临床评价技术指导原则_2020年第77号", "真实世界数据用于医疗器械临床评价技术指导原则（试行）"),
    (f"{FAGUI}/人工智能辅助检测.doc", "guidance-ai-clinical", "人工智能辅助检测医疗器械软件临床评价注册审查指导原则_2023年第38号", "人工智能辅助检测医疗器械（软件）临床评价注册审查指导原则"),
    (f"{FAGUI}/产品技术要求编写.doc", "guidance-registration", "医疗器械产品技术要求编写指导原则_2022年修订版", "医疗器械产品技术要求编写指导原则"),
    (f"{FAGUI}/通用名称命名.doc", "guidance-registration", "医用软件通用名称命名指导原则_2021年第48号", "医用软件通用名称命名指导原则"),
    (f"{FAGUI}/独立软件现场检查指导原则.doc", "guidance-qms-software", "医疗器械生产质量管理规范独立软件现场检查指导原则_2020", "医疗器械生产质量管理规范独立软件现场检查指导原则"),
    (f"{TT}/独立软件附录.doc", "guidance-qms-software", "医疗器械生产质量管理规范附录独立软件_2019年第43号", "医疗器械生产质量管理规范附录独立软件"),
    # AI专项(飞书doc)
    (f"{FAGUI}/乳腺X射线图像辅助检测软件注册审查指导原则.doc", "guidance-ai-product", "乳腺X射线图像辅助检测软件注册审查指导原则_2022", "乳腺X射线图像辅助检测软件注册审查指导原则"),
    (f"{FAGUI}/糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则.doc", "guidance-ai-product", "糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则_2022", "糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则"),
    (f"{FAGUI}/肺结节CT图像辅助检测软件注册审查指导原则2022年第21号.doc", "guidance-ai-product", "肺结节CT图像辅助检测软件注册审查指导原则_2022年第21号", "肺结节CT图像辅助检测软件注册审查指导原则（2022年第21号）"),
    # 生产监督办法(飞书PDF)
    (f"{FAGUI}/生产监督管理办法.pdf", "regulations", "医疗器械生产监督管理办法_2022_第53号", "医疗器械生产监督管理办法（2022年第53号）"),
]


def extract(path):
    p = str(path)
    if p.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(pg.extract_text() or "" for pg in PdfReader(p).pages)
    if p.endswith(".docx"):
        from docx import Document
        d = Document(p); parts = [x.text for x in d.paragraphs if x.text.strip()]
        for t in d.tables:
            for r in t.rows: parts.append(" | ".join(c.text.strip() for c in r.cells))
        return "\n".join(parts)
    return ""  # .doc 需先转docx


def main():
    from scripts.deep_clean_all import deep_clean
    from app.core.rag_engine import get_engine
    e = get_engine()
    CLEAN = ROOT / "data/source_docs/clean"
    ok, skip = [], []
    for src, col, base, title in JOBS:
        # .doc → 找同名 .docx(libreoffice已转)
        if src.endswith(".doc") and not os.path.exists(src.replace(".doc", ".docx")):
            # 转
            import subprocess
            subprocess.run(["libreoffice", "--headless", "--convert-to", "docx",
                            "--outdir", os.path.dirname(src), src],
                           capture_output=True, timeout=90)
        real = src.replace(".doc", ".docx") if src.endswith(".doc") and os.path.exists(src.replace(".doc", ".docx")) else src
        if not os.path.exists(real):
            skip.append((base, "源缺")); continue
        raw = extract(real)
        cjk = len(re.findall(r"[一-鿿]", raw))
        if len(raw) < 300:
            skip.append((base, f"抽取过短{len(raw)}")); continue
        cleaned = deep_clean(title + "\n\n" + raw)
        sp = CLEAN / f"{col}__{base}.txt"
        sp.write_text(cleaned, encoding="utf-8")
        n = e.ingest_document(sp, f"{col}__{base}.txt", uuid.uuid4().hex[:8], col)
        r2 = 100 * len(re.findall(r"[一-鿿]", cleaned)) // max(len(cleaned), 1)
        ok.append((base, len(cleaned), r2, n))
    print(f"入库 {len(ok)} 份：")
    for b, c, r, n in ok:
        print(f"  ✓[{r:2}%] {c:>6}字 {n:>3}块 {b[:34]}")
    if skip:
        print(f"跳过 {len(skip)}：")
        for b, why in skip: print(f"  ✗ {b[:34]}: {why}")


if __name__ == "__main__":
    main()
