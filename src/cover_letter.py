import re
from dataclasses import dataclass

from src.job_finder import Job

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")


@dataclass
class Candidate:
    name: str
    email: str | None
    phone: str | None
    location: str | None
    summary: str
    skills: str
    highlights: list[str]


def extract_candidate(resume: str) -> Candidate:
    lines = [line.strip() for line in resume.splitlines() if line.strip()]
    name = lines[0] if lines else "Applicant"
    email_match = EMAIL_RE.search(resume)
    phone_match = PHONE_RE.search(resume)
    location = _first_location(lines)
    summary = _section_text(resume, "Professional Summary") or _first_paragraph(lines)
    skills = _section_text(resume, "Technical Skills")
    highlights = _collect_highlights(resume)
    return Candidate(
        name=name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        location=location,
        summary=_squeeze(summary),
        skills=_squeeze(skills),
        highlights=highlights[:6],
    )


def generate_cover_letter(resume: str, job: Job, reasoning: str = "") -> str:
    candidate = extract_candidate(resume)
    relevant = _relevant_highlights(candidate.highlights, job)
    if not relevant:
        relevant = candidate.highlights[:3]
    bullets = "\n".join(f"- {item}" for item in relevant)
    skills_line = _overlap_skills(candidate.skills or resume, job)
    why = reasoning.strip()
    if why.lower().startswith("shared signals"):
        why = (
            f"This opening matches work I have already shipped, especially the overlap "
            f"with {job.title} at {job.company}."
        )
    elif not why:
        why = f"My background aligns with {job.title} at {job.company}."

    contact_bits = [part for part in [candidate.email, candidate.phone, candidate.location] if part]
    contact = " | ".join(contact_bits)

    return (
        f"Dear {job.company} Hiring Team,\n\n"
        f"I am writing to apply for the {job.title} role at {job.company}. "
        f"{candidate.summary or 'I am a software engineer and AI researcher seeking an applied role.'}\n\n"
        f"{why}\n\n"
        f"Relevant experience:\n{bullets or '- See attached resume.'}\n\n"
        f"{skills_line}\n\n"
        f"I would welcome the chance to contribute to {job.company} and can start from the DC / Maryland area "
        f"or remotely. Thank you for your time.\n\n"
        f"Sincerely,\n"
        f"{candidate.name}\n"
        f"{contact}\n"
    )


def generate_cover_letter_with_model(resume: str, job: Job, use_api: bool = False) -> str:
    from src.model import create_model

    model = create_model(use_api=use_api)
    messages = [
        {
            "role": "system",
            "content": (
                "Write a concise, specific cover letter. 250-350 words. "
                "No fluff, no generic claims. Use only facts from the resume. "
                "Output the letter only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Resume:\n{resume}\n\n"
                f"Job: {job.title} at {job.company} ({job.location})\n"
                f"{job.description}"
            ),
        },
    ]
    return model.generate(messages).content.strip()


def _first_location(lines: list[str]) -> str | None:
    if len(lines) < 2:
        return None
    header = lines[1]
    part = header.split("|")[0].strip()
    if "@" in part or re.search(r"\d", part):
        return None
    return part or None


def _section_text(resume: str, heading: str) -> str:
    pattern = rf"{re.escape(heading)}\s*\n(.*?)(?=\n[A-Z][A-Za-z0-9 /&|]{{2,}}\n|\Z)"
    match = re.search(pattern, resume, re.DOTALL)
    return match.group(1).strip() if match else ""


def _first_paragraph(lines: list[str]) -> str:
    return " ".join(lines[2:6]) if len(lines) > 2 else ""


def _collect_highlights(resume: str) -> list[str]:
    bullets: list[str] = []
    current = ""
    for line in resume.splitlines():
        stripped = line.strip()
        if stripped.startswith(("•", "-", "*")):
            if current:
                bullets.append(current)
            current = stripped.lstrip("•-* ").strip()
        elif current and stripped and not _looks_like_heading(stripped) and not _looks_like_new_role(stripped):
            current += " " + stripped
        else:
            if current:
                bullets.append(current)
                current = ""
    if current:
        bullets.append(current)
    return [item for item in bullets if len(item) > 40]


def _looks_like_new_role(line: str) -> bool:
    if len(line) < 80 and re.search(r"\b(19|20)\d{2}\b", line):
        return True
    if len(line) < 80 and " | " in line:
        return True
    return False


def _looks_like_heading(line: str) -> bool:
    letters = [ch for ch in line if ch.isalpha()]
    if len(line) > 48 or len(letters) < 3:
        return False
    return line == line.upper() or line in {
        "EDUCATION",
        "EXPERIENCE",
        "PROJECTS",
        "Achievements",
        "Technical Skills",
        "Leadership & Involvement",
        "Professional Summary",
    }


def _relevant_highlights(highlights: list[str], job: Job) -> list[str]:
    haystack = f"{job.title} {job.description}".lower()
    keywords = [
        "agent",
        "rag",
        "nlp",
        "transformer",
        "pytorch",
        "aws",
        "react",
        "api",
        "sql",
        "unity",
        "ocr",
        "dataset",
        "full-stack",
        "fullstack",
        "guardrail",
        "ontology",
    ]
    scored = []
    for item in highlights:
        low = item.lower()
        hits = sum(1 for word in keywords if word in low and word in haystack)
        scored.append((hits, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for hits, item in scored if hits][:4]


def _overlap_skills(skills: str, job: Job) -> str:
    text = skills.lower()
    job_text = f"{job.title} {job.description}".lower()
    tokens = [
        "Python",
        "PyTorch",
        "Hugging Face",
        "NLP",
        "RAG",
        "SQL",
        "React",
        "Node.js",
        "TypeScript",
        "AWS",
        "PostgreSQL",
        "Unity",
        "LoRA",
        "multi-agent systems",
    ]
    found = [token for token in tokens if token.lower() in text and token.lower() in job_text]
    if not found:
        return "My attached resume has additional project and research detail."
    return "Skills that map to this listing include " + ", ".join(found) + "."


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
