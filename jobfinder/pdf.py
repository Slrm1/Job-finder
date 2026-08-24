"""Export a parsed resume to a simple or professional PDF."""

from __future__ import annotations

from pathlib import Path

from jobfinder.match import Profile

TEMPLATES = ("simple", "professional")


def _safe(text: str) -> str:
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def render_resume_pdf(
    profile: Profile,
    dest: str | Path,
    *,
    template: str = "simple",
) -> Path:
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template {template!r}. Use: {', '.join(TEMPLATES)}")
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("PDF export needs fpdf2. Run: pip install fpdf2") from exc

    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    if template == "professional":
        _professional(pdf, profile)
    else:
        _simple(pdf, profile)
    pdf.output(str(path))
    return path


def _simple(pdf, profile: Profile) -> None:
    pdf.set_text_color(20, 24, 28)
    pdf.set_font("Helvetica", "B", 20)
    _line(pdf, 12, profile.name or "Resume", style="B", size=20)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 90, 100)
    pdf.multi_cell(0, 6, _safe(profile.headline or profile.experience_level))
    meta = " · ".join(part for part in (profile.location, profile.experience_level) if part)
    if meta:
        _line(pdf, 8, meta)
    pdf.ln(2)
    _section(pdf, "Skills", ", ".join(profile.skills) or "-")
    _section(pdf, "Focus", ", ".join(profile.keywords) or "-")
    body = profile.notes or profile.resume_text
    if body:
        _section(pdf, "Experience", body[:3500])


def _professional(pdf, profile: Profile) -> None:
    pdf.set_fill_color(16, 51, 84)
    pdf.rect(0, 0, 210, 36, "F")
    pdf.set_xy(16, 10)
    pdf.set_text_color(255, 255, 255)
    _line(pdf, 10, profile.name or "Resume", style="B", size=20)
    pdf.set_x(16)
    _line(pdf, 8, profile.headline or "Job seeker", size=11)
    pdf.set_y(44)
    pdf.set_text_color(20, 24, 28)
    meta = " · ".join(part for part in (profile.location, profile.experience_level) if part)
    if meta:
        _line(pdf, 8, meta, style="I", size=11)
        pdf.ln(2)
    _section(pdf, "Skills", ", ".join(profile.skills) or "-")
    _section(pdf, "Keywords", ", ".join(profile.keywords) or "-")
    body = profile.notes or profile.resume_text
    if body:
        _section(pdf, "Summary", body[:3500])


def _line(pdf, height: float, text: str, *, style: str = "", size: int | None = None) -> None:
    if size is not None:
        pdf.set_font("Helvetica", style, size)
    pdf.cell(0, height, _safe(text), new_x="LMARGIN", new_y="NEXT")


def _section(pdf, title: str, body: str) -> None:
    pdf.set_text_color(16, 51, 84)
    _line(pdf, 9, title, style="B", size=13)
    pdf.set_draw_color(180, 190, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(30, 36, 42)
    pdf.multi_cell(0, 6, _safe(body))
    pdf.ln(3)
