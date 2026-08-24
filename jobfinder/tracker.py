"""Local application tracker inspired by JobSync's save-and-status workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from jobfinder.config import JOBFINDER_DB
from jobfinder.jobs import Job

STATUSES = (
    "saved",
    "applied",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    url TEXT,
    source TEXT,
    score REAL,
    status TEXT NOT NULL DEFAULT 'saved',
    notes TEXT NOT NULL DEFAULT '',
    saved_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass
class TrackedJob:
    id: int
    job_key: str
    title: str
    company: str
    location: str
    url: str
    source: str
    score: float | None
    status: str
    notes: str
    saved_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrackerError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else JOBFINDER_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute(_SCHEMA)
    return connection


def _row(row: sqlite3.Row) -> TrackedJob:
    return TrackedJob(
        id=row["id"],
        job_key=row["job_key"],
        title=row["title"],
        company=row["company"],
        location=row["location"] or "",
        url=row["url"] or "",
        source=row["source"] or "",
        score=row["score"],
        status=row["status"],
        notes=row["notes"] or "",
        saved_at=row["saved_at"],
        updated_at=row["updated_at"],
    )


def job_key(job: Job) -> str:
    return (job.url or f"{job.source}:{job.title}:{job.company}").lower()


def save_job(
    job: Job,
    *,
    status: str = "saved",
    score: float | None = None,
    notes: str = "",
    db_path: Path | None = None,
) -> TrackedJob:
    if status not in STATUSES:
        raise TrackerError(f"Unknown status {status!r}. Use one of: {', '.join(STATUSES)}")
    stamp = _now()
    key = job_key(job)
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM applications WHERE job_key = ?", (key,)
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE applications
                SET title=?, company=?, location=?, url=?, source=?,
                    score=COALESCE(?, score), status=?, notes=?, updated_at=?
                WHERE job_key=?
                """,
                (
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.source,
                    score,
                    status,
                    notes,
                    stamp,
                    key,
                ),
            )
            row_id = existing["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    job_key, title, company, location, url, source,
                    score, status, notes, saved_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.source,
                    score,
                    status,
                    notes,
                    stamp,
                    stamp,
                ),
            )
            row_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (row_id,)
        ).fetchone()
    return _row(row)


def save_ranked(ranked, *, limit: int | None = None, db_path: Path | None = None) -> list[TrackedJob]:
    saved = []
    for item in ranked[: limit or len(ranked)]:
        saved.append(
            save_job(
                item.job,
                status="saved",
                score=getattr(item, "score", None),
                notes=getattr(item, "summary", "") or "",
                db_path=db_path,
            )
        )
    return saved


def list_tracked(
    status: str | None = None, db_path: Path | None = None
) -> list[TrackedJob]:
    query = "SELECT * FROM applications"
    params: tuple[str, ...] = ()
    if status:
        if status not in STATUSES:
            raise TrackerError(f"Unknown status {status!r}.")
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY updated_at DESC"
    with _connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row(row) for row in rows]


def get_tracked(entry_id: int, db_path: Path | None = None) -> TrackedJob:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM applications WHERE id = ?", (entry_id,)
        ).fetchone()
    if not row:
        raise TrackerError(f"No saved job with id {entry_id}")
    return _row(row)


def set_status(entry_id: int, status: str, db_path: Path | None = None) -> TrackedJob:
    if status not in STATUSES:
        raise TrackerError(f"Unknown status {status!r}. Use one of: {', '.join(STATUSES)}")
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE applications SET status=?, updated_at=? WHERE id=?",
            (status, _now(), entry_id),
        )
        changed = connection.execute("SELECT changes()").fetchone()[0]
        if changed == 0:
            raise TrackerError(f"No saved job with id {entry_id}")
    return get_tracked(entry_id, db_path=db_path)


def set_notes(entry_id: int, notes: str, db_path: Path | None = None) -> TrackedJob:
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE applications SET notes=?, updated_at=? WHERE id=?",
            (notes, _now(), entry_id),
        )
        changed = connection.execute("SELECT changes()").fetchone()[0]
        if changed == 0:
            raise TrackerError(f"No saved job with id {entry_id}")
    return get_tracked(entry_id, db_path=db_path)


def remove_tracked(entry_id: int, db_path: Path | None = None) -> None:
    with _connect(db_path) as connection:
        connection.execute("DELETE FROM applications WHERE id = ?", (entry_id,))
        changed = connection.execute("SELECT changes()").fetchone()[0]
        if changed == 0:
            raise TrackerError(f"No saved job with id {entry_id}")


def counts(db_path: Path | None = None) -> dict[str, int]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
        ).fetchall()
    tallies = {status: 0 for status in STATUSES}
    for row in rows:
        tallies[row["status"]] = row["n"]
    return tallies


def dashboard_stats(db_path: Path | None = None) -> dict[str, Any]:
    tallies = counts(db_path=db_path)
    rows = list_tracked(db_path=db_path)
    total = sum(tallies.values())
    progressed = tallies["applied"] + tallies["interview"] + tallies["offer"] + tallies["rejected"]
    offers = tallies["offer"]
    interviews = tallies["interview"] + tallies["offer"]
    return {
        "counts": tallies,
        "total": total,
        "applied": progressed,
        "interviews": interviews,
        "offers": offers,
        "apply_rate": round(100.0 * progressed / total, 1) if total else 0.0,
        "interview_rate": round(100.0 * interviews / total, 1) if total else 0.0,
        "offer_rate": round(100.0 * offers / total, 1) if total else 0.0,
        "recent": rows[:8],
    }
