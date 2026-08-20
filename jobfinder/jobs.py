"""Public job-board clients (no login required)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import json
import re
from typing import Any, Callable, Iterable
from urllib.parse import urlencode

import requests

from jobfinder.config import USER_AGENT

TIMEOUT = 20


@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str
    tags: list[str] = field(default_factory=list)
    salary: str | None = None
    posted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def blob(self) -> str:
        tags = " ".join(self.tags)
        return f"{self.title} {self.company} {self.location} {tags} {self.description}"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )
    return session


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _job_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fetch_remotive(query: str, limit: int = 25) -> list[Job]:
    params = {"search": query} if query else {}
    url = "https://remotive.com/api/remote-jobs"
    if params:
        url = f"{url}?{urlencode(params)}"
    response = _session().get(url, timeout=TIMEOUT)
    response.raise_for_status()
    jobs: list[Job] = []
    for item in response.json().get("jobs", []):
        jobs.append(
            Job(
                id=_job_id("remotive", str(item.get("id", item.get("url", "")))),
                title=item.get("title") or "Untitled",
                company=item.get("company_name") or "Unknown",
                location=item.get("candidate_required_location") or "Remote",
                url=item.get("url") or item.get("short_url") or "",
                description=_strip_html(item.get("description") or ""),
                source="remotive",
                tags=list(item.get("tags") or []),
                salary=item.get("salary") or None,
                posted_at=item.get("publication_date"),
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


def fetch_arbeitnow(query: str, limit: int = 25) -> list[Job]:
    response = _session().get(
        "https://www.arbeitnow.com/api/job-board-api", timeout=TIMEOUT
    )
    response.raise_for_status()
    needle = query.lower().strip()
    jobs: list[Job] = []
    for item in response.json().get("data", []):
        title = item.get("title") or "Untitled"
        company = item.get("company_name") or "Unknown"
        description = _strip_html(item.get("description") or "")
        tags = [str(t) for t in (item.get("tags") or [])]
        haystack = f"{title} {company} {' '.join(tags)} {description}".lower()
        if needle and needle not in haystack:
            continue
        location = item.get("location") or ("Remote" if item.get("remote") else "")
        jobs.append(
            Job(
                id=_job_id("arbeitnow", item.get("slug") or item.get("url") or title),
                title=title,
                company=company,
                location=location or "Unknown",
                url=item.get("url") or "",
                description=description,
                source="arbeitnow",
                tags=tags,
                posted_at=str(item.get("created_at") or "") or None,
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


def fetch_remoteok(query: str, limit: int = 25) -> list[Job]:
    response = _session().get("https://remoteok.com/api", timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    needle = query.lower().strip()
    jobs: list[Job] = []
    for item in payload:
        if not isinstance(item, dict) or (
            "position" not in item and "title" not in item
        ):
            continue
        title = item.get("position") or item.get("title") or "Untitled"
        company = item.get("company") or "Unknown"
        description = _strip_html(item.get("description") or "")
        tags = [str(t) for t in (item.get("tags") or [])]
        haystack = f"{title} {company} {' '.join(tags)} {description}".lower()
        if needle and needle not in haystack:
            continue
        jobs.append(
            Job(
                id=_job_id("remoteok", str(item.get("id") or item.get("url") or title)),
                title=title,
                company=company,
                location=item.get("location") or "Remote",
                url=item.get("url") or item.get("apply_url") or "",
                description=description,
                source="remoteok",
                tags=tags,
                salary=_remoteok_salary(item),
                posted_at=_epoch_to_iso(item.get("epoch") or item.get("date")),
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


def _remoteok_salary(item: dict[str, Any]) -> str | None:
    low, high = item.get("salary_min"), item.get("salary_max")
    if low and high:
        return f"{low}-{high}"
    if item.get("salary"):
        return str(item["salary"])
    return None


def _epoch_to_iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        ts = int(float(value))
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(value)


SOURCES: dict[str, Callable[[str, int], list[Job]]] = {
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "remoteok": fetch_remoteok,
}


def search_jobs(
    query: str,
    *,
    sources: Iterable[str] | None = None,
    limit: int = 30,
    per_source: int | None = None,
) -> list[Job]:
    """Fetch jobs from public APIs and de-duplicate by URL/title+company."""
    selected = list(sources) if sources else list(SOURCES)
    unknown = [name for name in selected if name not in SOURCES]
    if unknown:
        raise ValueError(f"Unknown job sources: {', '.join(unknown)}")

    cap = per_source or max(10, limit)
    collected: list[Job] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {pool.submit(SOURCES[name], query, cap): name for name in selected}
        for future in as_completed(futures):
            name = futures[future]
            try:
                collected.extend(future.result())
            except Exception as exc:  # network / schema issues should not abort all sources
                errors.append(f"{name}: {exc}")

    unique: list[Job] = []
    seen: set[str] = set()
    for job in collected:
        key = (job.url or f"{job.source}:{job.title}:{job.company}").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
        if len(unique) >= limit:
            break

    if not unique and errors:
        raise RuntimeError("All job sources failed: " + "; ".join(errors))
    return unique


def jobs_to_json(jobs: list[Job]) -> str:
    return json.dumps([job.to_dict() for job in jobs], indent=2)
