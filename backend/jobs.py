"""Remote job search via Remotive public API."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")
STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "in", "on", "for", "with", "over",
    "at", "by", "from", "or", "as", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "my", "our", "your", "years", "year",
}


def _plain(html: str, limit: int = 400) -> str:
    text = TAG_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


@dataclass
class Job:
    id: int
    title: str
    company: str
    category: str
    tags: list[str]
    job_type: str
    location: str
    salary: str
    url: str
    published: str
    description: str
    logo: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def blurb(self) -> str:
        tags = ", ".join(self.tags[:8]) if self.tags else "n/a"
        return (
            f"{self.title} @ {self.company} | {self.category} | {self.location} | "
            f"{self.job_type} | salary: {self.salary or 'n/a'} | tags: {tags}\n"
            f"{self.description}"
        )


def _from_api(raw: dict[str, Any]) -> Job:
    return Job(
        id=int(raw.get("id") or 0),
        title=str(raw.get("title") or "Untitled"),
        company=str(raw.get("company_name") or "Unknown"),
        category=str(raw.get("category") or ""),
        tags=list(raw.get("tags") or []),
        job_type=str(raw.get("job_type") or ""),
        location=str(raw.get("candidate_required_location") or "Remote"),
        salary=str(raw.get("salary") or ""),
        url=str(raw.get("url") or ""),
        published=str(raw.get("publication_date") or ""),
        description=_plain(str(raw.get("description") or "")),
        logo=raw.get("company_logo"),
    )


def fetch_jobs(
    settings: Settings,
    *,
    search: str = "",
    category: str = "",
    limit: int | None = None,
) -> list[Job]:
    """Fetch remote jobs from Remotive, then filter locally.

    Remotive's public query params are unreliable, so category/search are
    applied on the client after download.
    """
    url = settings.remotive_api_url
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()

    jobs = [_from_api(item) for item in payload.get("jobs", [])]

    cat = category.strip().lower().replace("_", "-").replace(" ", "-")
    if cat:
        cat_aliases = {
            "software-dev": ("software", "developer", "engineering", "devops"),
            "data": ("data", "analytics", "machine learning", "ml "),
            "devops": ("devops", "sre", "infrastructure", "platform"),
            "design": ("design", "ux", "ui"),
            "product": ("product manager", "product management", "product "),
            "marketing": ("marketing", "growth"),
            "sales": ("sales", "account executive", "account manager"),
            "customer-support": ("support", "customer success", "customer service"),
            "finance": ("finance", "accounting"),
            "hr": ("hr", "people", "recruiting", "talent"),
        }
        needles = cat_aliases.get(cat, (cat.replace("-", " "),))

        def cat_match(job: Job) -> bool:
            hay = f"{job.category} {job.title}".lower()
            return any(n.strip() in hay for n in needles)

        filtered = [j for j in jobs if cat_match(j)]
        if filtered:
            jobs = filtered

    q = search.strip().lower()
    if q:
        tokens = [t for t in re.findall(r"[a-z0-9+#.]{2,}", q)]
        if tokens:
            def search_score(job: Job) -> int:
                hay = f"{job.title} {job.company} {job.category} {' '.join(job.tags)} {job.description}".lower()
                return sum(1 for t in tokens if t in hay)

            scored = [(search_score(j), j) for j in jobs]
            scored = [(s, j) for s, j in scored if s > 0]
            scored.sort(key=lambda x: x[0], reverse=True)
            if scored:
                jobs = [j for _, j in scored]

    cap = limit if limit is not None else settings.max_jobs
    return jobs[:cap]



def summarize_jobs(jobs: list[Job], max_jobs: int = 15) -> str:
    lines = []
    for i, job in enumerate(jobs[:max_jobs], start=1):
        lines.append(f"{i}. {job.blurb()}")
    return "\n\n".join(lines) if lines else "No jobs available."


def heuristic_rank(profile: str, jobs: list[Job], top_n: int = 5) -> list[dict[str, Any]]:
    """Keyword overlap ranking when Affine-S6 is unavailable."""
    tokens = {
        t.lower()
        for t in re.findall(r"[a-zA-Z0-9+#.]{2,}", profile)
        if t.lower() not in STOPWORDS
    }
    scored: list[tuple[float, Job, list[str]]] = []
    for job in jobs:
        hay = " ".join(
            [
                job.title,
                job.company,
                job.category,
                " ".join(job.tags),
                job.description,
            ]
        ).lower()
        hits = sorted({t for t in tokens if t in hay and len(t) > 2})
        score = min(100.0, 12.0 * len(hits) + (8.0 if any(t in job.title.lower() for t in hits) else 0))
        scored.append((score, job, hits[:8]))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, job, hits in scored[:top_n]:
        why = (
            f"Matched keywords: {', '.join(hits)}."
            if hits
            else "Limited keyword overlap; review manually."
        )
        results.append(
            {
                "title": job.title,
                "company": job.company,
                "score": int(score),
                "why": why,
                "url": job.url,
                "id": job.id,
            }
        )
    return results
