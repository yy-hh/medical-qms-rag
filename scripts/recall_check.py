#!/usr/bin/env python
"""召回自检：对一组"已知正确答案"的查询，断言关键 chunk 必须进 top-k。

用途：改检索算法/清洗数据/重切分后跑一次，防止召回悄悄退化（如条例第十四条
原文掉出 top-k）。锚点用"文档名 + content 文本特征"定位，不写死 chunk_index，
因此对重新切分鲁棒。

Usage:
    python scripts/recall_check.py            # 跑全部用例，失败则退出码 1
    python scripts/recall_check.py -v         # 额外打印每个查询的 top-k 命中

退出码 0=全过，1=有失败（可接入 CI / pre-commit）。
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.core.rag_engine import get_engine

# 每条用例：(描述, 查询, 文档名子串, content 必含的全部关键词, top_k)
# 关键词全部出现才算命中该锚点 chunk —— 取自人工确认过的实质内容。
CASES = [
    ("条例第十四条·提交注册资料",
     "医疗器械注册申请应当提交哪些资料",
     "监督管理条例", ["第十四条", "提交下列资料"], 6),
    ("分类规则·判定表",
     "医疗器械如何进行分类判定",
     "分类规则", ["分类判定表"], 8),
    ("网络安全法·基本方针",
     "网络安全的国家方针是什么",
     "网络安全法", ["第四条", "网络安全"], 8),
]

# 已知召回缺口：换种问法后锚点排名偏后（用词与原文不同，BM25 对不上、向量没顶够）。
# 仍会跑并打印当前 rank（便于修复时观察），但不计入失败、不影响退出码。
# 修复检索后应逐条提升进 top-k 并迁回 CASES。
KNOWN_GAPS = [
    ("条例第十四条·换问法[材料]  当前约 rank28",
     "第二类第三类医疗器械产品注册需要哪些材料",
     "监督管理条例", ["第十四条", "提交下列资料"], 8),
    ("软件注册·软件组件整体注册  当前约 rank14",
     "软件组件能不能单独注册",
     "软件注册审查指导原则", ["软件组件", "整体注册"], 8),
]


def _hit(sources, doc_sub, keywords):
    """命中：某 source 的 doc_name 含 doc_sub 且 content 含全部 keywords。返回 rank(1-based) 或 None。"""
    for rank, s in enumerate(sources, 1):
        if doc_sub in s.doc_name and all(k in s.content for k in keywords):
            return rank
    return None


PROBE_DEPTH = 40  # known-gap 深探深度，用于报告锚点当前真实名次


def main():
    parser = argparse.ArgumentParser(description="召回自检")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印每个查询的 top-k 命中")
    args = parser.parse_args()

    engine = get_engine()
    passed, failed = 0, 0
    print(f"召回自检：{len(CASES)} 条断言用例 + {len(KNOWN_GAPS)} 条已知缺口\n" + "=" * 60)
    for desc, query, doc_sub, kws, top_k in CASES:
        sources = engine.retrieve(query, top_k=top_k)
        rank = _hit(sources, doc_sub, kws)
        ok = rank is not None
        passed += ok
        failed += not ok
        mark = "✓ PASS" if ok else "✗ FAIL"
        pos = f"rank {rank}/{top_k}" if ok else f"未进 top{top_k}"
        print(f"{mark}  {desc}  [{pos}]")
        if not ok or args.verbose:
            print(f"        查询: {query}")
            print(f"        锚点: {doc_sub} 含 {kws}")
            for r, s in enumerate(sources, 1):
                print(f"          {r}. [{s.score:.3f}] {s.doc_name[:34]} c{s.chunk_index}")

    if KNOWN_GAPS:
        print("-" * 60 + "\n已知缺口（仅观察，不计入失败）：")
        for desc, query, doc_sub, kws, top_k in KNOWN_GAPS:
            deep = engine.retrieve(query, top_k=PROBE_DEPTH)
            rank = _hit(deep, doc_sub, kws)
            now = f"现 rank {rank}" if rank else f"未进 top{PROBE_DEPTH}"
            target = "进 top%d" % top_k
            flag = "  ← 已达标！可迁回 CASES" if (rank and rank <= top_k) else ""
            print(f"  ⚠ {desc}  [{now}，目标 {target}]{flag}")

    print("=" * 60)
    print(f"断言通过 {passed}/{len(CASES)}，失败 {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
