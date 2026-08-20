from pathlib import Path

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def load_resume(path: str | Path) -> str:
    resume_path = Path(path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    suffix = resume_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported resume type: {suffix}. Use .txt, .md, or .pdf")

    if suffix == ".pdf":
        return _load_pdf(resume_path)
    return resume_path.read_text(encoding="utf-8", errors="replace")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(f"Could not extract text from PDF: {path}")
    return text
