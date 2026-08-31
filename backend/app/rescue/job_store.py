"""
Persistence for RescueJob state.

Jobs are kept as an in-memory dict while actively running (so the
orchestrator's mutations are immediately visible to API reads without a
round-trip), and persisted to SQLite as a JSON blob on every save_job()
call so job history survives across requests within the same server
process. See orchestrator.py's module docstring for the exact disclosed
limitation: this does NOT survive a server restart mid-job - there is no
external queue/broker in this build.
"""
import json
import time

from app.models.db import get_conn, db_cursor, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS rescue_jobs (
    job_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    state_json TEXT NOT NULL
);
"""

_ACTIVE_JOBS = {}  # job_id -> live dict, mutated in place by the orchestrator


def init_rescue_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def create_job(dataset_id, aux_dataset_id=None, target_column=None, objective=None) -> dict:
    job_id = new_id()
    now = time.time()
    job = {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "aux_dataset_id": aux_dataset_id,
        "target_column": target_column,
        "objective": objective,
        "current_stage": "queued",
        "status": "queued",
        "discovered_issues": [],
        "ml_findings": [],
        "proposed_actions": [],
        "approved_actions": [],
        "rejected_actions": [],
        "pending_action_id": None,
        "before_metrics": None,
        "after_metrics": None,
        "privacy_before": None,
        "privacy_after": None,
        "utility": None,
        "rescue_score": None,
        "verification": None,
        "audit_events": [],
        "final_dataset_id": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    _ACTIVE_JOBS[job_id] = job
    save_job(job)
    return job


def get_job(job_id: str):
    if job_id in _ACTIVE_JOBS:
        return _ACTIVE_JOBS[job_id]
    with db_cursor() as conn:
        row = conn.execute("SELECT * FROM rescue_jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        return None
    job = json.loads(row["state_json"])
    _ACTIVE_JOBS[job_id] = job
    return job


def save_job(job: dict):
    job["updated_at"] = time.time()
    with db_cursor() as conn:
        conn.execute(
            """INSERT INTO rescue_jobs (job_id, dataset_id, status, created_at, updated_at, state_json)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(job_id) DO UPDATE SET
                 status=excluded.status, updated_at=excluded.updated_at, state_json=excluded.state_json""",
            (job["job_id"], job["dataset_id"], job["status"], job["created_at"], job["updated_at"], json.dumps(job)),
        )


def list_jobs(limit=50):
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT job_id, dataset_id, status, created_at, updated_at FROM rescue_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
