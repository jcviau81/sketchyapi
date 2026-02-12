"""Job queue abstraction — SQLite MVP, interface for Redis/SQS later."""

from __future__ import annotations
import abc
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import ComicRequest, JobStatus


class Job:
    def __init__(self, job_id, api_key, status, request, created_at, updated_at,
                 result=None, error=None, progress=None, panels_completed=0):
        self.job_id = job_id
        self.api_key = api_key
        self.status = status
        self.request = request
        self.created_at = created_at
        self.updated_at = updated_at
        self.result = result or {}
        self.error = error
        self.progress = progress
        self.panels_completed = panels_completed


class QueueBackend(abc.ABC):
    @abc.abstractmethod
    def enqueue(self, api_key: str, request: ComicRequest) -> Job: ...
    @abc.abstractmethod
    def get_job(self, job_id: str) -> Optional[Job]: ...
    @abc.abstractmethod
    def next_pending(self) -> Optional[Job]: ...
    @abc.abstractmethod
    def update_status(self, job_id: str, status: JobStatus, **kwargs) -> None: ...
    @abc.abstractmethod
    def count_requests(self, api_key: str, since: datetime) -> int: ...


class SQLiteQueue(QueueBackend):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    request TEXT NOT NULL,
                    result TEXT DEFAULT '{}',
                    error TEXT,
                    progress TEXT,
                    panels_completed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_api_key ON jobs(api_key)")

    def _row_to_job(self, row) -> Job:
        return Job(
            job_id=row["job_id"], api_key=row["api_key"],
            status=JobStatus(row["status"]), request=json.loads(row["request"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            result=json.loads(row["result"] or "{}"), error=row["error"],
            progress=row["progress"], panels_completed=row["panels_completed"],
        )

    def enqueue(self, api_key: str, request: ComicRequest) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, api_key, status, request, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (job_id, api_key, JobStatus.pending.value, request.model_dump_json(), now, now),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def next_pending(self) -> Optional[Job]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                (JobStatus.pending.value,),
            ).fetchone()
            if not row:
                return None
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ? AND status = ?",
                (JobStatus.writing_script.value, now, row["job_id"], JobStatus.pending.value),
            )
        return self.get_job(row["job_id"])

    def update_status(self, job_id: str, status: JobStatus, **kwargs) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sets = ["status = ?", "updated_at = ?"]
        vals: list = [status.value, now]
        for k in ("error", "progress", "panels_completed"):
            if k in kwargs:
                sets.append(f"{k} = ?")
                vals.append(kwargs[k])
        if "result" in kwargs:
            sets.append("result = ?")
            vals.append(json.dumps(kwargs["result"]))
        vals.append(job_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", vals)

    def count_requests(self, api_key: str, since: datetime) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM jobs WHERE api_key = ? AND created_at >= ?",
                (api_key, since.isoformat()),
            ).fetchone()
        return row["cnt"] if row else 0


def create_queue() -> QueueBackend:
    from .config import settings
    if settings.queue_backend == "sqlite":
        settings.resolved_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return SQLiteQueue(str(settings.resolved_sqlite_path))
    raise ValueError(f"Unknown queue backend: {settings.queue_backend}")
