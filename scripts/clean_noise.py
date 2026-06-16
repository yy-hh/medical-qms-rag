#!/usr/bin/env python
"""标记知识库中的噪声 chunk（is_active=0），使其不入检索索引。

不删除 DB 行，可逆：随时可 UPDATE chunks SET is_active=1 还原。
可重复运行（幂等）：每次先全置 1 再按规则置 0。

噪声类别（经全库验证，零误杀实质内容）：
  1. 目录页：抓取时混入的"相关指导原则列表"页，密集罗列标题、几乎无句子。
     规则同 rag_engine._is_toc_noise：(指导原则+审查原则) >= 4 且 句号 <= 2。
  2. 论坛页脚：Discuz 等站点抓取残留（翻页/相关阅读/友情链接/ICP备/Powered by Discuz）。

Usage:
    python scripts/clean_noise.py            # 执行标记
    python scripts/clean_noise.py --dry-run  # 只预览命中，不改库
"""
import sys
import argparse
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.rag_engine import _is_toc_noise, DB_PATH


def _is_forum_footer(text: str) -> bool:
    # 论坛/CMS 页脚残留：整段几乎全是导航与版权，靠多个站点级标志词共现判定。
    markers = ["Powered by Discuz", "下一页", "友情链接", "ICP备", "相关阅读",
               "路过", "雷人", "握手", "鲜花", "网站导航", "返回顶部"]
    return sum(m in text for m in markers) >= 4


def main():
    parser = argparse.ArgumentParser(description="标记知识库噪声 chunk（is_active=0）")
    parser.add_argument("--dry-run", action="store_true", help="只预览命中，不改库")
    args = parser.parse_args()

    db = sqlite3.connect(str(DB_PATH))

    cols = {r[1] for r in db.execute("PRAGMA table_info(chunks)").fetchall()}
    if "is_active" not in cols:
        if args.dry_run:
            print("[dry-run] 缺 is_active 列（运行时会自动补）")
        else:
            db.execute("ALTER TABLE chunks ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    rows = db.execute("SELECT id, doc_name, chunk_index, text FROM chunks").fetchall()
    toc, forum = [], []
    for cid, nm, ci, t in rows:
        if _is_toc_noise(t):
            toc.append((cid, nm, ci))
        elif _is_forum_footer(t):
            forum.append((cid, nm, ci))

    print(f"总 chunk: {len(rows)}")
    print(f"  目录页噪声:   {len(toc)} 条")
    print(f"  论坛页脚残留: {len(forum)} 条")
    for cid, nm, ci in toc[:3] + forum[:3]:
        print(f"    - {nm[:30]} c{ci}")

    if args.dry_run:
        print("\n[dry-run] 未改库。去掉 --dry-run 执行标记。")
        return

    kill_ids = [(cid,) for cid, _, _ in toc + forum]
    db.execute("UPDATE chunks SET is_active=1")
    db.executemany("UPDATE chunks SET is_active=0 WHERE id=?", kill_ids)
    db.commit()
    n_inactive = db.execute("SELECT COUNT(*) FROM chunks WHERE is_active=0").fetchone()[0]
    print(f"\n已标记 {n_inactive} 条 is_active=0（重启服务后生效）。")


if __name__ == "__main__":
    main()
