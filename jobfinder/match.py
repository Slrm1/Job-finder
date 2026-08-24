"""Rank jobs against a candidate profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any

import yaml

from jobfinder.jobs import Job

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "for",
    "of",
    "in",
    "on",
    "with",
    "or",
    "at",
    "is",
    "as",
    "by",
}


@dataclass
class Profile:
    name: str = ""
    headline: str = ""
    location: str = ""
    remote_ok: bool = True
    experience_level: str = ""
    skills: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    notes: str = ""
    resume_text: str = ""
    source: str = "yaml"

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "Profile":
        data = data or {}
        return cls(
            name=str(data.get("name") or ""),
            headline=str(data.get("headline") or ""),
            location=str(data.get("location") or ""),
            remote_ok=bool(data.get("remote_ok", True)),
            experience_level=str(data.get("experience_level") or ""),
            skills=_as_list(data.get("skills")),
            keywords=_as_list(data.get("keywords")),
            avoid=_as_list(data.get("avoid")),
            notes=str(data.get("notes") or "").strip(),
            resume_text=str(data.get("resume_text") or "").strip(),
            source=str(data.get("source") or "yaml"),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Profile":
        with Path(path).open(encoding="utf-8") as handle:
            return cls.from_mapping(yaml.safe_load(handle) or {})

    def terms(self) -> list[str]:
        parts = list(self.skills) + list(self.keywords)
        parts.extend(_tokenize(self.headline))
        parts.extend(_tokenize(self.notes))
        parts.extend(_tokenize(self.resume_text[:2000]))
        return [term for term in parts if term]

    def as_prompt(self) -> str:
        skills = ", ".join(self.skills) or "unspecified"
        keywords = ", ".join(self.keywords) or "unspecified"
        avoid = ", ".join(self.avoid) or "none"
        resume = self.resume_text[:6000]
        prompt = (
            f"Name: {self.name or 'Candidate'}\n"
            f"Headline: {self.headline}\n"
            f"Location: {self.location}\n"
            f"Remote OK: {self.remote_ok}\n"
            f"Experience: {self.experience_level}\n"
            f"Skills: {skills}\n"
            f"Keywords: {keywords}\n"
            f"Avoid: {avoid}\n"
            f"Notes: {self.notes}"
        )
        if resume:
            prompt += f"\n\nRESUME\n{resume}"
        return prompt


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,}", text.lower())
        if token not in STOPWORDS
    ]


@dataclass
class RankedJob:
    job: Job
    score: float
    reasons: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    summary: str = ""
    method: str = "keywords"
    humanized: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["job"] = self.job.to_dict()
        return payload


def keyword_score(job: Job, profile: Profile, query: str = "") -> RankedJob:
    blob = job.blob().lower()
    reasons: list[str] = []
    hits = 0
    considered = 0

    for term in profile.skills + profile.keywords:
        needle = term.lower().strip()
        if not needle:
            continue
        considered += 1
        if needle in blob:
            hits += 1
            reasons.append(f"Mentions {term}")

    avoid_hits = [term for term in profile.avoid if term.lower() in blob]
    score = 0.0
    if considered:
        score = 100.0 * hits / considered
    if job.title and any(k.lower() in job.title.lower() for k in profile.keywords):
        score = min(100.0, score + 10)
        reasons.append("Title matches a target keyword")
    query_terms = [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,}", query.lower())
        if token not in STOPWORDS
    ]
    title_hits = [term for term in query_terms if term in (job.title or "").lower()]
    if title_hits:
        score = min(100.0, score + 15)
        reasons.append("Title matches search terms")
    if profile.resume_text:
        resume_blob = profile.resume_text.lower()
        title_in_resume = [
            term
            for term in _tokenize(job.title)
            if term in resume_blob and term not in STOPWORDS
        ]
        if title_in_resume:
            score = min(100.0, score + 10)
            reasons.append("Resume overlaps the job title")
    if profile.remote_ok and "remote" in (job.location or "").lower():
        score = min(100.0, score + 5)
        reasons.append("Remote-friendly location")
    if avoid_hits:
        score = max(0.0, score - 25 * len(avoid_hits))
        reasons.append("Contains avoided terms: " + ", ".join(avoid_hits))

    missing = [
        skill
        for skill in profile.skills
        if skill.lower() not in blob and skill.strip()
    ]
    summary = (
        f"{hits} of {considered} profile terms appear in this listing."
        if considered
        else "No profile keywords were provided; showing an unweighted match."
    )
    return RankedJob(
        job=job,
        score=round(score, 1),
        reasons=reasons[:8],
        missing_skills=missing[:8],
        summary=summary,
        method="keywords",
    )


def rank_jobs(jobs: list[Job], profile: Profile, query: str = "") -> list[RankedJob]:
    ranked = [keyword_score(job, profile, query=query) for job in jobs]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def affine_rank_prompt(job: Job, profile: Profile) -> str:
    description = job.description[:4000]
    return (
        "Score how well this job fits the candidate. "
        "Return ONLY JSON with keys score (0-100 number), reasons (array of short strings), "
        "missing_skills (array of strings), and summary (one or two sentences).\n\n"
        f"CANDIDATE\n{profile.as_prompt()}\n\n"
        f"JOB\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Location: {job.location}\nTags: {', '.join(job.tags)}\n"
        f"URL: {job.url}\nDescription:\n{description}"
    )


def apply_affine_result(job: Job, payload: dict[str, Any]) -> RankedJob:
    try:
        score = float(payload.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(100.0, score))
    reasons = [str(item) for item in payload.get("reasons") or []]
    missing = [str(item) for item in payload.get("missing_skills") or []]
    summary = str(payload.get("summary") or "").strip()
    return RankedJob(
        job=job,
        score=round(score, 1),
        reasons=reasons[:8],
        missing_skills=missing[:8],
        summary=summary,
        method="affine-s6",
    )


def rank_jobs_with_affine(
    jobs: list[Job],
    profile: Profile,
    *,
    generate_json=None,
    limit: int = 8,
    query: str = "",
) -> list[RankedJob]:
    """Rank a shortlist with Affine-S6. Falls back to keyword scores on errors."""
    if generate_json is None:
        from jobfinder.affine import generate_json as generate_json

    shortlist = rank_jobs(jobs, profile, query=query)[:limit]
    ranked: list[RankedJob] = []
    for item in shortlist:
        try:
            payload = generate_json(affine_rank_prompt(item.job, profile))
            ranked.append(apply_affine_result(item.job, payload))
        except Exception:
            ranked.append(item)
    ranked.sort(key=lambda entry: entry.score, reverse=True)
    return ranked


def dump_ranked(ranked: list[RankedJob]) -> str:
    return json.dumps([item.to_dict() for item in ranked], indent=2)
