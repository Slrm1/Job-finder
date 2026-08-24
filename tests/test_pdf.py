from jobfinder.match import Profile
from jobfinder.pdf import render_resume_pdf


def test_simple_and_professional_pdf(tmp_path):
    profile = Profile(
        name="Ada Lovelace",
        headline="Python intern",
        location="London",
        experience_level="intern",
        skills=["Python", "Flask"],
        keywords=["intern"],
        notes="Built APIs for civic data.",
        resume_text="Ada Lovelace\nPython intern",
    )
    simple = render_resume_pdf(profile, tmp_path / "simple.pdf", template="simple")
    professional = render_resume_pdf(
        profile, tmp_path / "pro.pdf", template="professional"
    )
    assert simple.read_bytes()[:5] == b"%PDF-"
    assert professional.read_bytes()[:5] == b"%PDF-"
    assert simple.stat().st_size > 200
    assert professional.stat().st_size > 200


def test_unknown_template_rejected(tmp_path):
    try:
        render_resume_pdf(Profile(name="Ada"), tmp_path / "x.pdf", template="fancy")
    except ValueError as exc:
        assert "fancy" in str(exc)
    else:
        raise AssertionError("expected ValueError")
