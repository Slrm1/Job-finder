"""Turn a resume file into a ranking profile."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from jobfinder.config import ROOT_DIR

RESUME_NAMES = (
    "resume.pdf",
    "resume.txt",
    "resume.md",
    "resume.docx",
    "Resume.pdf",
    "CV.pdf",
    "cv.pdf",
    "cv.txt",
    "cv.docx",
)
RESUME_SUFFIXES = {".pdf", ".txt", ".md", ".docx", ".text", ".markdown"}
MAX_RESUME_CHARS = 40_000
MAX_RESUME_BYTES = 2 * 1024 * 1024

COMMON_SKILLS = (
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C++",
    "C#",
    "Go",
    "Rust",
    "SQL",
    "HTML",
    "CSS",
    "React",
    "Node.js",
    "Flask",
    "Django",
    "FastAPI",
    "Git",
    "Linux",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Pandas",
    "NumPy",
    "PyTorch",
    "TensorFlow",
    "scikit-learn",
    "REST",
    "GraphQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Bash",
    "Excel",
    "Figma",
    "Swift",
    "Kotlin",
    "R",
    "MATLAB",
    "Spark",
    "Hadoop",
    "Tableau",
    "Power BI",
    "Next.js",
    "Vue",
    "Angular",
    "Spring",
    "PHP",
    "Ruby",
    "Scala",
    "Hugging Face",
    "LangChain",
    "OpenCV",
    "Jira",
    "Agile",
)

ROLE_KEYWORDS = (
    "software engineer",
    "software developer",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "data scientist",
    "data analyst",
    "machine learning",
    "ml engineer",
    "internship",
    "intern",
    "research assistant",
    "new grad",
    "devops",
    "mobile",
    "android",
    "ios",
    "product manager",
    "web developer",
)

SECTION_RE = re.compile(
    r"^(education|experience|work history|employment|skills|technical skills|"
    r"tech stack|projects|summary|objective|certifications|languages|"
    r"relevant coursework|coursework)\s*:?\s*$",
    re.I,
)


class ResumeError(ValueError):
    pass


def discover_resume(directory: Path | None = None) -> Path | None:
    root = directory or ROOT_DIR
    for name in RESUME_NAMES:
        path = root / name
        if path.is_file():
            return path
    return None


def read_resume(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise ResumeError(f"Resume not found: {file_path}")
    if file_path.stat().st_size > MAX_RESUME_BYTES:
        raise ResumeError("Resume is larger than 2 MB.")
    suffix = file_path.suffix.lower()
    if suffix not in RESUME_SUFFIXES:
        raise ResumeError(
            "Use a .pdf, .txt, .md, or .docx resume. Scanned image PDFs need OCR first."
        )
    if suffix == ".pdf":
        text = _read_pdf(file_path)
    elif suffix == ".docx":
        text = _read_docx(file_path)
    else:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    text = _clean_text(text)
    if len(text) < 40:
        raise ResumeError(
            "Could not read enough text from that resume. "
            "If it is a scanned PDF, export it as text first."
        )
    return text[:MAX_RESUME_CHARS]


def read_resume_bytes(data: bytes, filename: str) -> str:
    suffix = Path(filename or "resume.txt").suffix.lower() or ".txt"
    if len(data) > MAX_RESUME_BYTES:
        raise ResumeError("Resume is larger than 2 MB.")
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(suffix=suffix, delete=True) as handle:
        handle.write(data)
        handle.flush()
        return read_resume(handle.name)


def parse_resume(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = _sections(text)
    skills = _skills_from_section(sections.get("skills", ""))
    skills.extend(_skills_from_section(sections.get("technical skills", "")))
    skills.extend(_scan_common_skills(text))
    skills = _unique(skills)
    keywords = _scan_keywords(text)
    name = _guess_name(lines)
    location = _guess_location(text)
    headline = _guess_headline(lines, sections)
    notes = _notes(sections, text)
    return {
        "name": name,
        "headline": headline,
        "location": location,
        "email": _guess_email(text),
        "remote_ok": True,
        "experience_level": _experience_level(text),
        "skills": skills,
        "keywords": keywords,
        "avoid": [],
        "notes": notes,
        "resume_text": text,
        "source": "resume",
    }


def profile_from_resume(path: str | Path):
    from jobfinder.match import Profile

    text = read_resume(path)
    return Profile.from_mapping(parse_resume(text))


def profile_from_resume_text(text: str):
    from jobfinder.match import Profile

    return Profile.from_mapping(parse_resume(_clean_text(text)))


def resolve_profile(
    *,
    profile_path: str | Path | None = None,
    resume_path: str | Path | None = None,
    resume_text: str | None = None,
    search_dir: Path | None = None,
):
    """Load a candidate profile from a resume, YAML, or both."""
    from jobfinder.config import DEFAULT_PROFILE_PATH
    from jobfinder.match import Profile

    profile = Profile()
    yaml_path = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if yaml_path.is_file():
        profile = Profile.from_yaml(yaml_path)
    elif not profile_path:
        example = (search_dir or ROOT_DIR) / "profile.example.yaml"
        if example.is_file() and resume_path is None and resume_text is None and not discover_resume(search_dir):
            profile = Profile.from_yaml(example)

    resume_profile = None
    if resume_text:
        resume_profile = profile_from_resume_text(resume_text)
    elif resume_path:
        resume_profile = profile_from_resume(resume_path)
    else:
        found = discover_resume(search_dir)
        if found:
            resume_profile = profile_from_resume(found)

    if resume_profile:
        return _merge_profiles(profile, resume_profile)
    return profile


def _merge_profiles(base, resume):
    """Resume fills empty YAML fields and always supplies resume_text and skills."""
    skills = _unique(list(resume.skills) + list(base.skills))
    keywords = _unique(list(resume.keywords) + list(base.keywords))
    return type(base)(
        name=base.name or resume.name,
        headline=base.headline or resume.headline,
        location=base.location or resume.location,
        email=base.email or resume.email,
        remote_ok=base.remote_ok,
        experience_level=base.experience_level or resume.experience_level,
        skills=skills,
        keywords=keywords,
        avoid=base.avoid or resume.avoid,
        notes=resume.notes if resume.resume_text else base.notes,
        resume_text=resume.resume_text or base.resume_text,
        source="resume" if resume.resume_text else base.source,
    )


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ResumeError("PDF support needs pypdf. Run: pip install pypdf") from exc
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ResumeError(
            "Word support needs python-docx. Run: pip install python-docx"
        ) from exc
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _sections(text: str) -> dict[str, str]:
    current = "summary"
    buckets: dict[str, list[str]] = {current: []}
    for raw in text.splitlines():
        line = raw.strip()
        match = SECTION_RE.match(re.sub(r"[\s•\-]+$", "", line))
        if match:
            current = match.group(1).lower()
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(raw)
    return {key: "\n".join(value).strip() for key, value in buckets.items()}


def _skills_from_section(blob: str) -> list[str]:
    if not blob:
        return []
    parts = re.split(r"[,;/|•\n]+", blob)
    skills = []
    for part in parts:
        item = re.sub(r"\s+", " ", part).strip(" -•\t")
        if 1 < len(item) <= 40 and len(item.split()) <= 4 and not SECTION_RE.match(item):
            skills.append(item)
    return skills[:40]


def _scan_common_skills(text: str) -> list[str]:
    haystack = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, haystack):
            found.append(skill)
    return found


def _scan_keywords(text: str) -> list[str]:
    haystack = text.lower()
    found = []
    for keyword in ROLE_KEYWORDS:
        if keyword in haystack:
            found.append(keyword)
    return _unique(found)


def _guess_name(lines: list[str]) -> str:
    for line in lines[:6]:
        if "@" in line or "http" in line.lower() or "linkedin" in line.lower():
            continue
        if SECTION_RE.match(line):
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(word[:1].isupper() for word in words if word.isalpha()):
            if not re.search(r"\d", line):
                return line
    return ""


def _guess_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", text, re.I)
    return match.group(0) if match else ""


def _guess_location(text: str) -> str:
    labeled = re.search(
        r"(?:location|based in|lives in)\s*[:\-]\s*([A-Za-z .,]{3,40})",
        text,
        re.I,
    )
    if labeled:
        return labeled.group(1).strip(" .,")
    match = re.search(
        r"\b([A-Z][a-zA-Z.]+(?:,\s*[A-Z]{2}|,\s*[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?))\b",
        text,
    )
    if match:
        return match.group(1).strip()
    return ""


def _guess_headline(lines: list[str], sections: dict[str, str]) -> str:
    summary = sections.get("summary") or sections.get("objective") or ""
    first = summary.strip().splitlines()[0].strip() if summary.strip() else ""
    if first and not _guess_name([first]):
        return first[:160]
    for line in lines[1:8]:
        lower = line.lower()
        if any(token in lower for token in ("engineer", "developer", "intern", "student", "analyst")):
            return line[:160]
    return first[:160]


def _experience_level(text: str) -> str:
    lower = text.lower()
    if "intern" in lower or "internship" in lower:
        return "internship / early career"
    if "new grad" in lower or "new-grad" in lower or "recent graduate" in lower:
        return "new grad"
    if "senior" in lower:
        return "senior"
    if "junior" in lower:
        return "junior"
    return "entry"


def _notes(sections: dict[str, str], text: str) -> str:
    chunks = [
        sections.get("summary", ""),
        sections.get("experience", ""),
        sections.get("projects", ""),
        sections.get("education", ""),
    ]
    notes = "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    return (notes or text)[:4000]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered
