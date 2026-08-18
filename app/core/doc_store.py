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
        # 幂等补列：账号隔离维度（仿 chunks.is_active 补列套路）
        cols = [r[1] for r in _conn.execute("PRAGMA table_info(generated_docs)").fetchall()]
        if "account_id" not in cols:
            _conn.execute("ALTER TABLE generated_docs ADD COLUMN account_id TEXT NOT NULL DEFAULT ''")
        _conn.commit()
    return _conn


def save_doc(account_id, doc_id, doc_name, content, product_name="", company_name="", ts=None):
    """保存一份生成文档。同一 (account_id, doc_id, product_name) 已存在则更新（视为重新生成）。"""
    if not (content or "").strip():
        return None
    now = ts if ts is not None else time.time()
    db = _db()
    with _lock:
        row = None
        if doc_id:
            row = db.execute(
                "SELECT id FROM generated_docs WHERE account_id=? AND doc_id=? AND product_name=?",
                (account_id, doc_id, product_name or ""),
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
                "INSERT INTO generated_docs (id, account_id, doc_id, doc_name, product_name, "
                "company_name, content, char_count, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rid, account_id, doc_id or "", doc_name, product_name or "", company_name or "",
                 content, len(content), now, now),
            )
        db.commit()
    return rid


def list_docs(account_id, product_name=None):
    """列出某账号的存档（不含正文，轻量）。传 product_name 则再按产品过滤。"""
    db = _db()
    sql = ("SELECT id, doc_id, doc_name, product_name, company_name, char_count, "
           "created_at, updated_at FROM generated_docs WHERE account_id=?")
    params = [account_id]
    if product_name is not None:
        sql += " AND product_name=?"
        params.append(product_name)
    sql += " ORDER BY updated_at DESC"
    rows = db.execute(sql, params).fetchall()
    cols = ["id", "doc_id", "doc_name", "product_name", "company_name",
            "char_count", "created_at", "updated_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_doc(rid, account_id):
    db = _db()
    r = db.execute(
        "SELECT id, doc_id, doc_name, product_name, company_name, content, "
        "char_count, created_at, updated_at FROM generated_docs WHERE id=? AND account_id=?",
        (rid, account_id),
    ).fetchone()
    if not r:
        return None
    cols = ["id", "doc_id", "doc_name", "product_name", "company_name", "content",
            "char_count", "created_at", "updated_at"]
    return dict(zip(cols, r))


def get_doc_by_doc_id(account_id, product_name, doc_id):
    """按 (account_id, product_name, doc_id) 取一份已保存文档（含 content）——用于生成时读依赖文件内容。"""
    db = _db()
    r = db.execute(
        "SELECT id, doc_id, doc_name, product_name, content, char_count, updated_at "
        "FROM generated_docs WHERE account_id=? AND doc_id=? AND product_name=?",
        (account_id, doc_id, product_name),
    ).fetchone()
    if not r:
        return None
    cols = ["id", "doc_id", "doc_name", "product_name", "content", "char_count", "updated_at"]
    return dict(zip(cols, r))


def delete_doc(rid, account_id):
    db = _db()
    with _lock:
        cur = db.execute("DELETE FROM generated_docs WHERE id=? AND account_id=?", (rid, account_id))
        db.commit()
    return cur.rowcount > 0
