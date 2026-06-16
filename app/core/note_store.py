"""笔记存档（SQLite）。

记录使用过程中的想法和心得，全局共享（不按产品隔离）。
用独立的 notes.db，与知识库 chunks 库和文档存档解耦。
"""
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORE_PATH = BASE_DIR / "data" / "notes.db"

_lock = Lock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(STORE_PATH), check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        _conn.commit()
    return _conn


def _split_tags(tags: str) -> list[str]:
    return [t for t in (x.strip() for x in (tags or "").split(",")) if t]


def save_note(note_id, title, content="", tags="", ts=None):
    """保存一条笔记。note_id 为空=新建，否则更新已存在的笔记。返回 rid（不存在则当新建）。"""
    now = ts if ts is not None else time.time()
    db = _db()
    with _lock:
        row = None
        if note_id:
            row = db.execute("SELECT id FROM notes WHERE id=?", (note_id,)).fetchone()
        if row:
            rid = row[0]
            db.execute(
                "UPDATE notes SET title=?, content=?, tags=?, updated_at=? WHERE id=?",
                (title, content or "", tags or "", now, rid),
            )
        else:
            rid = uuid.uuid4().hex[:12]
            db.execute(
                "INSERT INTO notes (id, title, content, tags, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (rid, title, content or "", tags or "", now, now),
            )
        db.commit()
    return rid


def list_notes(q=None, tag=None):
    """列出笔记（含正文，笔记体量小）。q 关键词匹配标题/正文，tag 匹配标签。按更新时间倒序。"""
    db = _db()
    sql = "SELECT id, title, content, tags, created_at, updated_at FROM notes"
    clauses, params = [], []
    if q:
        clauses.append("(title LIKE ? OR content LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if tag:
        clauses.append("(',' || tags || ',') LIKE ?")
        params.append(f"%,{tag},%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"
    rows = db.execute(sql, params).fetchall()
    cols = ["id", "title", "content", "tags", "created_at", "updated_at"]
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        d["tags"] = _split_tags(d["tags"])
        out.append(d)
    return out


def get_note(rid):
    db = _db()
    r = db.execute(
        "SELECT id, title, content, tags, created_at, updated_at FROM notes WHERE id=?",
        (rid,),
    ).fetchone()
    if not r:
        return None
    cols = ["id", "title", "content", "tags", "created_at", "updated_at"]
    d = dict(zip(cols, r))
    d["tags"] = _split_tags(d["tags"])
    return d


def delete_note(rid):
    db = _db()
    with _lock:
        cur = db.execute("DELETE FROM notes WHERE id=?", (rid,))
        db.commit()
    return cur.rowcount > 0


def all_tags():
    """汇总去重所有标签，按字母排序。"""
    db = _db()
    rows = db.execute("SELECT tags FROM notes WHERE tags IS NOT NULL AND tags != ''").fetchall()
    seen = set()
    for (t,) in rows:
        seen.update(_split_tags(t))
    return sorted(seen)
