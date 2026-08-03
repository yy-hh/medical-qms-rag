"""培训教程存档（SQLite）。

每条教程 = 一个 QMS 主题的图文讲义 + 一段 Seedance 生成的教学视频。
用独立的 training.db，与知识库 chunks 库、笔记库、文档存档解耦。
video_path 存 static 下的相对路径（如 videos/xxx.mp4），视频文件永久落地本地。
"""
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORE_PATH = BASE_DIR / "data" / "training.db"

_lock = Lock()
_conn = None


def _db():
    global _conn
    if _conn is None:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(STORE_PATH), check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS tutorials (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'article',
                lecture TEXT,
                video_prompt TEXT,
                video_path TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        # 兼容旧库：无 kind 列则补加（article=图文教程 / video=视频教程）
        cols = [r[1] for r in _conn.execute("PRAGMA table_info(tutorials)").fetchall()]
        if "kind" not in cols:
            _conn.execute("ALTER TABLE tutorials ADD COLUMN kind TEXT NOT NULL DEFAULT 'article'")
        # 视频教程分段表：一个视频教程拆成若干小段，每段一个短视频 + 中文语音 + 中英双语字幕。
        # final_path 是合成后（视频铺底 + 语音 + 烧录双语字幕）的成片，供前端播放。
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id TEXT PRIMARY KEY,
                tutorial_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                title TEXT NOT NULL,
                seg_kind TEXT NOT NULL DEFAULT 'seedance',
                narration TEXT,
                narration_en TEXT,
                visual_prompt TEXT,
                video_path TEXT,
                audio_path TEXT,
                final_path TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        # 兼容旧库：seg_kind 区分 seedance(背景概念，Seedance生成) / board(具体内容，固定黑板+TTS+字幕)
        seg_cols = [r[1] for r in _conn.execute("PRAGMA table_info(segments)").fetchall()]
        if "seg_kind" not in seg_cols:
            _conn.execute("ALTER TABLE segments ADD COLUMN seg_kind TEXT NOT NULL DEFAULT 'seedance'")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_seg_tid ON segments(tutorial_id, seq)")
        _conn.commit()
    return _conn


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "topic": row[1],
        "kind": row[2],
        "lecture": row[3] or "",
        "video_prompt": row[4] or "",
        "video_path": row[5] or "",
        "status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


_SELECT_COLS = ("SELECT id, topic, kind, lecture, video_prompt, video_path, "
                "status, created_at, updated_at FROM tutorials")


def save_tutorial(tutorial_id=None, topic="", kind="article", lecture="", video_prompt="",
                  video_path="", status="draft", ts=None):
    """新建或更新一条教程。tutorial_id 为空=新建。kind: article(图文) / video(视频)。返回 id。"""
    now = ts if ts is not None else time.time()
    db = _db()
    with _lock:
        row = None
        if tutorial_id:
            row = db.execute("SELECT id FROM tutorials WHERE id=?", (tutorial_id,)).fetchone()
        if row:
            rid = row[0]
            db.execute(
                "UPDATE tutorials SET topic=?, kind=?, lecture=?, video_prompt=?, "
                "video_path=?, status=?, updated_at=? WHERE id=?",
                (topic, kind, lecture or "", video_prompt or "", video_path or "", status, now, rid),
            )
        else:
            rid = uuid.uuid4().hex[:12]
            db.execute(
                "INSERT INTO tutorials (id, topic, kind, lecture, video_prompt, video_path, "
                "status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, topic, kind, lecture or "", video_prompt or "", video_path or "", status, now, now),
            )
        db.commit()
    return rid


def update_tutorial(tutorial_id, **fields):
    """局部更新指定字段（topic/kind/lecture/video_prompt/video_path/status）。返回是否命中。"""
    allowed = {"topic", "kind", "lecture", "video_prompt", "video_path", "status"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    sets["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in sets)
    vals = list(sets.values()) + [tutorial_id]
    db = _db()
    with _lock:
        cur = db.execute(f"UPDATE tutorials SET {cols} WHERE id=?", vals)
        db.commit()
    return cur.rowcount > 0


def list_tutorials():
    db = _db()
    with _lock:
        rows = db.execute(
            _SELECT_COLS + " ORDER BY updated_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_tutorial(tutorial_id):
    db = _db()
    with _lock:
        row = db.execute(
            _SELECT_COLS + " WHERE id=?", (tutorial_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_tutorial(tutorial_id):
    db = _db()
    with _lock:
        cur = db.execute("DELETE FROM tutorials WHERE id=?", (tutorial_id,))
        db.execute("DELETE FROM segments WHERE tutorial_id=?", (tutorial_id,))
        db.commit()
    return cur.rowcount > 0


# ── 分段（视频教程小段）────────────────────────────────────────────
_SEG_COLS = ("SELECT id, tutorial_id, seq, title, seg_kind, narration, narration_en, "
             "visual_prompt, video_path, audio_path, final_path, status, "
             "created_at, updated_at FROM segments")


def _seg_to_dict(row) -> dict:
    return {
        "id": row[0],
        "tutorial_id": row[1],
        "seq": row[2],
        "title": row[3],
        "seg_kind": row[4],
        "narration": row[5] or "",
        "narration_en": row[6] or "",
        "visual_prompt": row[7] or "",
        "video_path": row[8] or "",
        "audio_path": row[9] or "",
        "final_path": row[10] or "",
        "status": row[11],
        "created_at": row[12],
        "updated_at": row[13],
    }


def replace_segments(tutorial_id, segments):
    """用新的分段列表覆盖某教程的全部分段。segments: [{title,seg_kind,narration,narration_en,visual_prompt}]。"""
    now = time.time()
    db = _db()
    with _lock:
        db.execute("DELETE FROM segments WHERE tutorial_id=?", (tutorial_id,))
        out = []
        for i, s in enumerate(segments):
            sid = uuid.uuid4().hex[:12]
            db.execute(
                "INSERT INTO segments (id, tutorial_id, seq, title, seg_kind, narration, narration_en, "
                "visual_prompt, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sid, tutorial_id, i, s.get("title", f"第{i+1}段"), s.get("seg_kind", "seedance"),
                 s.get("narration", ""), s.get("narration_en", ""), s.get("visual_prompt", ""),
                 "pending", now, now),
            )
            out.append(sid)
        db.commit()
    return out


def list_segments(tutorial_id):
    db = _db()
    with _lock:
        rows = db.execute(_SEG_COLS + " WHERE tutorial_id=? ORDER BY seq", (tutorial_id,)).fetchall()
    return [_seg_to_dict(r) for r in rows]


def get_segment(seg_id):
    db = _db()
    with _lock:
        row = db.execute(_SEG_COLS + " WHERE id=?", (seg_id,)).fetchone()
    return _seg_to_dict(row) if row else None


def update_segment(seg_id, **fields):
    allowed = {"title", "seg_kind", "narration", "narration_en", "visual_prompt",
               "video_path", "audio_path", "final_path", "status"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    sets["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in sets)
    vals = list(sets.values()) + [seg_id]
    db = _db()
    with _lock:
        cur = db.execute(f"UPDATE segments SET {cols} WHERE id=?", vals)
        db.commit()
    return cur.rowcount > 0
