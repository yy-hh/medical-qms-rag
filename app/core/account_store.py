"""账号 / 会话 / 验证码存储（SQLite）。

账号体系：每个账号身份即飞书 open_id。用独立的 accounts.db，与知识库、文档存档、
笔记库解耦。三张表：accounts（账号）、sessions（登录会话）、pending_codes（待验证码）。
"""
import sqlite3
import time
import secrets
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORE_PATH = BASE_DIR / "data" / "accounts.db"

# 属主账号（梁洋洋）：存量数据迁移归属、离线脚本默认账号
DEFAULT_ACCOUNT = "ou_931ad8e23161f0e605fa8783e1a05c3c"
DEFAULT_ACCOUNT_NAME = "梁洋洋"

SESSION_TTL = 30 * 24 * 3600   # 会话 30 天
CODE_TTL = 300                 # 验证码 5 分钟
MAX_CODE_ATTEMPTS = 5          # 单个验证码最多试 5 次

_lock = Lock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(STORE_PATH), check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                open_id      TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email        TEXT,
                created_at   REAL NOT NULL,
                last_login   REAL
            )
        """)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                open_id    TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_codes (
                open_id    TEXT PRIMARY KEY,
                code       TEXT NOT NULL,
                expires_at REAL NOT NULL,
                attempts   INTEGER NOT NULL DEFAULT 0
            )
        """)
        _conn.commit()
    return _conn


# ── 账号 ──────────────────────────────────────────────────────────────────────

def upsert_account(open_id, display_name, email=""):
    """新建或更新账号（刷新 display_name/email，不动 created_at/last_login）。"""
    now = time.time()
    db = _db()
    with _lock:
        row = db.execute("SELECT open_id FROM accounts WHERE open_id=?", (open_id,)).fetchone()
        if row:
            db.execute(
                "UPDATE accounts SET display_name=?, email=? WHERE open_id=?",
                (display_name, email or "", open_id),
            )
        else:
            db.execute(
                "INSERT INTO accounts (open_id, display_name, email, created_at) VALUES (?,?,?,?)",
                (open_id, display_name, email or "", now),
            )
        db.commit()


def get_account(open_id):
    db = _db()
    r = db.execute(
        "SELECT open_id, display_name, email, created_at, last_login FROM accounts WHERE open_id=?",
        (open_id,),
    ).fetchone()
    if not r:
        return None
    cols = ["open_id", "display_name", "email", "created_at", "last_login"]
    return dict(zip(cols, r))


def touch_login(open_id):
    db = _db()
    with _lock:
        db.execute("UPDATE accounts SET last_login=? WHERE open_id=?", (time.time(), open_id))
        db.commit()


# ── 验证码 ────────────────────────────────────────────────────────────────────

def set_code(open_id, code, ttl=CODE_TTL):
    """写入/覆盖某人的待验证码（重发即覆盖，attempts 归零）。"""
    db = _db()
    with _lock:
        db.execute(
            "INSERT OR REPLACE INTO pending_codes (open_id, code, expires_at, attempts) "
            "VALUES (?,?,?,0)",
            (open_id, code, time.time() + ttl),
        )
        db.commit()


def verify_code(open_id, code) -> bool:
    """校验验证码：未过期且匹配则成功并删除；否则自增 attempts，超限即失效删除。"""
    db = _db()
    with _lock:
        r = db.execute(
            "SELECT code, expires_at, attempts FROM pending_codes WHERE open_id=?",
            (open_id,),
        ).fetchone()
        if not r:
            return False
        stored_code, expires_at, attempts = r
        if time.time() > expires_at or attempts >= MAX_CODE_ATTEMPTS:
            db.execute("DELETE FROM pending_codes WHERE open_id=?", (open_id,))
            db.commit()
            return False
        if secrets.compare_digest(str(stored_code), str(code)):
            db.execute("DELETE FROM pending_codes WHERE open_id=?", (open_id,))
            db.commit()
            return True
        db.execute("UPDATE pending_codes SET attempts=attempts+1 WHERE open_id=?", (open_id,))
        db.commit()
        return False


# ── 会话 ──────────────────────────────────────────────────────────────────────

def create_session(open_id, ttl=SESSION_TTL) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    db = _db()
    with _lock:
        db.execute(
            "INSERT INTO sessions (token, open_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, open_id, now, now + ttl),
        )
        db.commit()
    return token


def resolve_session(token) -> str | None:
    """token 有效且未过期则返回 open_id；过期则删除并返回 None。"""
    if not token:
        return None
    db = _db()
    r = db.execute(
        "SELECT open_id, expires_at FROM sessions WHERE token=?", (token,)
    ).fetchone()
    if not r:
        return None
    open_id, expires_at = r
    if time.time() > expires_at:
        with _lock:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
            db.commit()
        return None
    return open_id


def delete_session(token):
    db = _db()
    with _lock:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        db.commit()
