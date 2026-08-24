"""Draft a cover letter from a resume and a job listing."""

from __future__ import annotations

import re

from jobfinder.jobs import Job
from jobfinder.match import Profile

COVER_SYSTEM = (
    "You write short, specific job application cover letters. "
    "Use only facts from the resume. Do not invent employers, degrees, or skills. "
    "Keep it under 220 words. No cliches like leverage, passionate, or excited to apply. "
    "Output only the letter."
)


def draft_cover_letter(job: Job, profile: Profile) -> str:
    """Always-available letter from parsed resume facts (no model required)."""
    name = profile.name or "the applicant"
    skills = _overlap_skills(job, profile) or profile.skills[:5]
    skill_line = ", ".join(skills[:6]) if skills else "the work on my resume"
    proof = _proof_sentence(profile)
    role = job.title or "this role"
    company = job.company or "your team"
    location = profile.location or job.location
    remote = "I'm open to remote work. " if profile.remote_ok else ""
    email = profile.email
    greeting = f"Hello {company} hiring team,"
    intro = (
        f"I'm {name}"
        + (f", {profile.headline.rstrip('.')}." if profile.headline else ".")
        + f" I'd like to apply for the {role} role."
    )
    body = proof or (
        f"My background is a fit for this listing, especially around {skill_line}."
    )
    close = (
        f"I work with {skill_line}. {remote}"
        f"I've attached my resume"
        + (f" and can be reached at {email}" if email else "")
        + ". Thank you for considering me."
    )
    if location:
        close = f"I'm based in {location}. " + close
    parts = [greeting, "", intro, "", body, "", close, "", name]
    if email:
        parts.append(email)
    letter = "\n".join(parts)
    return re.sub(r"\n{3,}", "\n\n", letter).strip() + "\n"


def generate_cover_letter(
    job: Job,
    profile: Profile,
    *,
    humanize: bool = True,
    affine: bool = False,
) -> str:
    letter = draft_cover_letter(job, profile)
    if affine:
        try:
            from jobfinder.affine import generate

            prompt = (
                "Write a cover letter for this job using only the candidate facts.\n\n"
                f"CANDIDATE\n{profile.as_prompt()}\n\n"
                f"JOB\nTitle: {job.title}\nCompany: {job.company}\n"
                f"Location: {job.location}\nURL: {job.url}\n"
                f"Description:\n{(job.description or '')[:2500]}\n\n"
                "If you cannot be specific, use this fallback letter:\n"
                f"{letter}"
            )
            reply = generate(prompt, system=COVER_SYSTEM, max_new_tokens=512)
            drafted = (reply.text() or "").strip()
            if len(drafted.split()) >= 40:
                letter = drafted
        except Exception:
            pass
    if humanize:
        from jobfinder.humanizer import humanize_text

        letter = humanize_text(letter).text()
    return letter.strip() + "\n"


def _overlap_skills(job: Job, profile: Profile) -> list[str]:
    blob = job.blob().lower()
    hits = [skill for skill in profile.skills if skill.lower() in blob]
    return hits[:6]


def _proof_sentence(profile: Profile) -> str:
    notes = (profile.notes or profile.resume_text or "").strip()
    if not notes:
        return ""
    for raw in notes.splitlines():
        line = raw.strip(" -•*\t")
        if len(line) < 40:
            continue
        if line.lower().startswith(("skills", "education", "summary")):
            continue
        sentence = line[:240].rstrip(" .,")
        return sentence + "."
    return ""
