"""Follow-up notes for applications that have had no reply."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jobfinder.config import FOLLOWUP_DAYS
from jobfinder.match import Profile
from jobfinder.tracker import TrackedJob, list_tracked


def due_followups(
    *,
    days: int | None = None,
    now: datetime | None = None,
    db_path=None,
) -> list[TrackedJob]:
    wait = days if days is not None else FOLLOWUP_DAYS
    stamp = now or datetime.now(timezone.utc)
    cutoff = stamp - timedelta(days=wait)
    due: list[TrackedJob] = []
    for row in list_tracked(status="applied", db_path=db_path):
        applied = _parse_time(row.applied_at or row.updated_at)
        if applied is None:
            continue
        if applied <= cutoff:
            due.append(row)
    return due


def draft_followup(row: TrackedJob, profile: Profile) -> str:
    name = profile.name or "the applicant"
    email = profile.email
    return (
        f"Hello {row.company} hiring team,\n\n"
        f"I'm {name}. I applied for the {row.title} role"
        + (f" on {row.applied_at[:10]}" if row.applied_at else "")
        + " and wanted to check whether you need anything else from me. "
        "Happy to share more about my work or a tailored resume.\n\n"
        "Thank you,\n"
        f"{name}"
        + (f"\n{email}" if email else "")
        + "\n"
    )


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
