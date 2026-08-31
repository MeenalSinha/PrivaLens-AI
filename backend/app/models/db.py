"""
SQLite persistence layer.

Stores dataset metadata, analysis runs and audit log entries. Dataframes
themselves are persisted to disk as parquet/pickle under data/uploads and
data/generated -- SQLite only tracks metadata and JSON-serialized results,
keeping this file swappable for PostgreSQL later (see README > Roadmap).
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    row_count INTEGER,
    column_count INTEGER,
    created_at REAL NOT NULL,
    is_demo INTEGER DEFAULT 0,
    parent_id TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    kind TEXT NOT NULL,          -- profile | attack | risk | mitigation | retest
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    dataset_id TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    created_at REAL NOT NULL
);
"""


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def log_audit(dataset_id: str, action: str, detail: str = ""):
    """Security requirement: audit logging. Never logs raw record content,
    only action metadata, to avoid sensitive data leaking into logs."""
    with db_cursor() as conn:
        conn.execute(
            "INSERT INTO audit_log (id, dataset_id, action, detail, created_at) VALUES (?,?,?,?,?)",
            (new_id(), dataset_id, action, detail, time.time()),
        )


def save_dataset_record(dataset_id, name, file_path, row_count, column_count,
                         is_demo=False, parent_id=None):
    with db_cursor() as conn:
        conn.execute(
            """INSERT INTO datasets (id, name, file_path, row_count, column_count,
               created_at, is_demo, parent_id) VALUES (?,?,?,?,?,?,?,?)""",
            (dataset_id, name, file_path, row_count, column_count,
             time.time(), int(is_demo), parent_id),
        )


def get_dataset_record(dataset_id):
    with db_cursor() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None


def save_analysis(dataset_id, kind, result: dict):
    aid = new_id()
    with db_cursor() as conn:
        conn.execute(
            "INSERT INTO analyses (id, dataset_id, kind, result_json, created_at) VALUES (?,?,?,?,?)",
            (aid, dataset_id, kind, json.dumps(result), time.time()),
        )
    return aid


def get_latest_analysis(dataset_id, kind):
    with db_cursor() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE dataset_id=? AND kind=? ORDER BY created_at DESC LIMIT 1",
            (dataset_id, kind),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json"))
        return d


def list_audit(dataset_id=None, limit=200):
    with db_cursor() as conn:
        if dataset_id:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE dataset_id=? ORDER BY created_at DESC LIMIT ?",
                (dataset_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
