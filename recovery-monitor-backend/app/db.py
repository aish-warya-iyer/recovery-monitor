"""SQLite persistence (#12). One file, no ORM; JSON columns for the analysis result and rep labels."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    condition TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS protocols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    version INTEGER NOT NULL,
    exercise TEXT NOT NULL,
    target_reps INTEGER NOT NULL,
    target_depth_deg REAL NOT NULL,
    pain_threshold INTEGER NOT NULL,
    tempo TEXT,
    reference_video_id INTEGER REFERENCES reference_videos(id),
    notes TEXT,
    approved_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (patient_id, version)
);
CREATE TABLE IF NOT EXISTS reference_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise TEXT NOT NULL,
    title TEXT NOT NULL,
    path TEXT NOT NULL,
    source TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    protocol_id INTEGER REFERENCES protocols(id),
    exercise TEXT NOT NULL,
    status TEXT NOT NULL,          -- uploaded | processing | complete | uncertain | rejected_quality | failed
    stage TEXT,                    -- current processing stage for the progress UI
    progress REAL DEFAULT 0,
    error TEXT,
    source TEXT,
    video_path TEXT,
    annotated_path TEXT,
    thumbnail_path TEXT,
    duration_s REAL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS check_ins (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    pain_score INTEGER NOT NULL,
    stiffness INTEGER,
    comment TEXT,
    transcript TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,        -- approve | request_changes
    notes TEXT,
    rep_labels_json TEXT,          -- {"3": "incorrect", "5": "correct"} physio corrections per rep
    reference_video_id INTEGER REFERENCES reference_videos(id),
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_patient ON sessions(patient_id, created_at);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
        _conn.executescript(SCHEMA)
    return _conn


@contextmanager
def tx():
    """Serialized write transaction (analysis jobs run in worker threads)."""
    with _lock:
        c = conn()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise


def one(sql: str, *args) -> dict | None:
    with _lock:
        row = conn().execute(sql, args).fetchone()
    return dict(row) if row else None


def all_(sql: str, *args) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def loads(s: str | None):
    return json.loads(s) if s else None


def reset_for_tests(path) -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None
    import app.config as cfg

    cfg.DB_PATH = path
    globals()["DB_PATH"] = path
