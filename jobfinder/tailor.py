"""Reorder resume facts so a listing's overlapping skills come first."""

from __future__ import annotations

from dataclasses import replace
import re

from jobfinder.jobs import Job
from jobfinder.match import Profile


def tailor_profile(job: Job, profile: Profile) -> Profile:
    """Copy of the profile with JD-overlapping skills and bullets first."""
    blob = job.blob().lower()
    overlap = [skill for skill in profile.skills if skill.lower() in blob]
    rest = [skill for skill in profile.skills if skill not in overlap]
    skills = overlap + rest
    bullets = _matching_bullets(job, profile) or _fallback_bullets(profile)
    headline = profile.headline
    if overlap and job.title:
        headline = f"{profile.headline or job.title} · {', '.join(overlap[:4])}"
    notes = "\n".join(f"- {bullet}" for bullet in bullets)
    return replace(
        profile,
        skills=skills,
        headline=headline[:160],
        notes=notes,
    )


def _matching_bullets(job: Job, profile: Profile) -> list[str]:
    terms = {skill.lower() for skill in profile.skills if skill.lower() in job.blob().lower()}
    terms.update(token for token in re.findall(r"[a-z]{3,}", job.title.lower()))
    found: list[str] = []
    for raw in (profile.notes or profile.resume_text or "").splitlines():
        line = raw.strip(" -•*\t")
        if len(line) < 30:
            continue
        lower = line.lower()
        if terms and not any(term in lower for term in terms):
            continue
        found.append(line[:240].rstrip(" ."))
        if len(found) >= 6:
            break
    return found


def _fallback_bullets(profile: Profile) -> list[str]:
    found: list[str] = []
    for raw in (profile.notes or profile.resume_text or "").splitlines():
        line = raw.strip(" -•*\t")
        if len(line) >= 40:
            found.append(line[:240].rstrip(" ."))
        if len(found) >= 4:
            break
    return found
