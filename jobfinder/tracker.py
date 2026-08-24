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
    cover_letter: str = ""
    apply_email: str = ""
    description: str = ""
    applied_via: str = ""
    applied_at: str = ""

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
    _migrate(connection)
    return connection


def _migrate(connection: sqlite3.Connection) -> None:
    existing = {row[1] for row in connection.execute("PRAGMA table_info(applications)")}
    columns = {
        "cover_letter": "TEXT NOT NULL DEFAULT ''",
        "apply_email": "TEXT NOT NULL DEFAULT ''",
        "description": "TEXT NOT NULL DEFAULT ''",
        "applied_via": "TEXT NOT NULL DEFAULT ''",
        "applied_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, spec in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE applications ADD COLUMN {name} {spec}")


def _cell(row: sqlite3.Row, name: str, default: str = "") -> str:
    if name not in row.keys():
        return default
    value = row[name]
    return default if value is None else value


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
        cover_letter=_cell(row, "cover_letter"),
        apply_email=_cell(row, "apply_email"),
        description=_cell(row, "description"),
        applied_via=_cell(row, "applied_via"),
        applied_at=_cell(row, "applied_at"),
    )


def job_key(job: Job) -> str:
    return (job.url or f"{job.source}:{job.title}:{job.company}").lower()


def save_job(
    job: Job,
    *,
    status: str = "saved",
    score: float | None = None,
    notes: str = "",
    cover_letter: str | None = None,
    apply_email: str | None = None,
    description: str | None = None,
    applied_via: str | None = None,
    applied_at: str | None = None,
    db_path: Path | None = None,
) -> TrackedJob:
    if status not in STATUSES:
        raise TrackerError(f"Unknown status {status!r}. Use one of: {', '.join(STATUSES)}")
    stamp = _now()
    key = job_key(job)
    email = apply_email if apply_email is not None else (job.apply_email or "")
    desc = description if description is not None else (job.description or "")
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM applications WHERE job_key = ?", (key,)
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE applications
                SET title=?, company=?, location=?, url=?, source=?,
                    score=COALESCE(?, score), status=?, notes=?, updated_at=?,
                    cover_letter=COALESCE(?, cover_letter),
                    apply_email=COALESCE(?, apply_email),
                    description=COALESCE(?, description),
                    applied_via=COALESCE(?, applied_via),
                    applied_at=COALESCE(?, applied_at)
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
                    cover_letter,
                    email or None,
                    desc or None,
                    applied_via,
                    applied_at,
                    key,
                ),
            )
            row_id = existing["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO applications (
                    job_key, title, company, location, url, source,
                    score, status, notes, saved_at, updated_at,
                    cover_letter, apply_email, description, applied_via, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    cover_letter or "",
                    email,
                    desc,
                    applied_via or "",
                    applied_at or "",
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


def set_cover_letter(entry_id: int, cover_letter: str, db_path: Path | None = None) -> TrackedJob:
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE applications SET cover_letter=?, updated_at=? WHERE id=?",
            (cover_letter, _now(), entry_id),
        )
        changed = connection.execute("SELECT changes()").fetchone()[0]
        if changed == 0:
            raise TrackerError(f"No saved job with id {entry_id}")
    return get_tracked(entry_id, db_path=db_path)


def record_application(
    entry_id: int,
    *,
    via: str,
    db_path: Path | None = None,
) -> TrackedJob:
    stamp = _now()
    with _connect(db_path) as connection:
        connection.execute(
            """
            UPDATE applications
            SET status=?, applied_via=?, applied_at=?, updated_at=?
            WHERE id=?
            """,
            ("applied", via, stamp, stamp, entry_id),
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


def applied_today_count(db_path: Path | None = None, today: str | None = None) -> int:
    day = today or datetime.now(timezone.utc).date().isoformat()
    n = 0
    for row in list_tracked(status="applied", db_path=db_path):
        stamp = row.applied_at or ""
        if stamp.startswith(day):
            n += 1
    return n


def tracked_keys(db_path: Path | None = None) -> set[str]:
    return {row.job_key for row in list_tracked(db_path=db_path)}


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
