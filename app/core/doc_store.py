"""已生成文档的存档（SQLite）。

生成完成后把整篇 Markdown + 元信息存档，供"文件管理"页查看/下载/删除。
用独立的 generated_docs.db，与知识库 chunks 库解耦（重建知识库不影响存档）。
"""
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORE_PATH = BASE_DIR / "data" / "generated_docs.db"

_lock = Lock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(STORE_PATH), check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_docs (
                id TEXT PRIMARY KEY,
                doc_id TEXT,
                doc_name TEXT NOT NULL,
                product_name TEXT,
                company_name TEXT,
                content TEXT NOT NULL,
                char_count INTEGER,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        _conn.commit()
    return _conn


def save_doc(doc_id, doc_name, content, product_name="", company_name="", ts=None):
    """保存一份生成文档。同一 (doc_id, product_name) 已存在则更新（视为重新生成）。"""
    if not (content or "").strip():
        return None
    now = ts if ts is not None else time.time()
    db = _db()
    with _lock:
        row = None
        if doc_id:
            row = db.execute(
                "SELECT id FROM generated_docs WHERE doc_id=? AND product_name=?",
                (doc_id, product_name or ""),
            ).fetchone()
        if row:
            rid = row[0]
            db.execute(
                "UPDATE generated_docs SET doc_name=?, content=?, char_count=?, "
                "company_name=?, updated_at=? WHERE id=?",
                (doc_name, content, len(content), company_name or "", now, rid),
            )
        else:
            rid = uuid.uuid4().hex[:12]
            db.execute(
                "INSERT INTO generated_docs (id, doc_id, doc_name, product_name, "
                "company_name, content, char_count, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, doc_id or "", doc_name, product_name or "", company_name or "",
                 content, len(content), now, now),
            )
        db.commit()
    return rid


def list_docs(product_name=None):
    """列出存档（不含正文，轻量）。传 product_name 则只返回该产品的文档（按产品隔离）。"""
    db = _db()
    if product_name is not None:
        rows = db.execute(
            "SELECT id, doc_id, doc_name, product_name, company_name, char_count, "
            "created_at, updated_at FROM generated_docs WHERE product_name=? ORDER BY updated_at DESC",
            (product_name,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, doc_id, doc_name, product_name, company_name, char_count, "
            "created_at, updated_at FROM generated_docs ORDER BY updated_at DESC"
        ).fetchall()
    cols = ["id", "doc_id", "doc_name", "product_name", "company_name",
            "char_count", "created_at", "updated_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_doc(rid):
    db = _db()
    r = db.execute(
        "SELECT id, doc_id, doc_name, product_name, company_name, content, "
        "char_count, created_at, updated_at FROM generated_docs WHERE id=?",
        (rid,),
    ).fetchone()
    if not r:
        return None
    cols = ["id", "doc_id", "doc_name", "product_name", "company_name", "content",
            "char_count", "created_at", "updated_at"]
    return dict(zip(cols, r))


def delete_doc(rid):
    db = _db()
    with _lock:
        cur = db.execute("DELETE FROM generated_docs WHERE id=?", (rid,))
        db.commit()
    return cur.rowcount > 0
