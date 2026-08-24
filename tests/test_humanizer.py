from jobfinder.humanizer import (
    draft_pitch,
    heuristic_humanize,
    humanize_ranked,
    humanize_text,
)
from jobfinder.jobs import Job
from jobfinder.match import Profile, RankedJob


def test_heuristic_strips_common_ai_tells():
    original = (
        "It is important to note that I can leverage my robust Python skills "
        "to delve into this cutting-edge landscape. Furthermore, I will "
        "utilize Flask to play a vital role in the team."
    )
    out = heuristic_humanize(original)
    lowered = out.lower()
    assert "leverage" not in lowered
    assert "robust" not in lowered
    assert "delve into" not in lowered
    assert "cutting-edge" not in lowered
    assert "utilize" not in lowered
    assert "it is important to note" not in lowered
    assert "python" in lowered
    assert "flask" in lowered


def test_humanize_text_defaults_to_heuristic_without_gguf():
    result = humanize_text(
        "I am writing to express my strong interest in this robust backend role.",
        backend="heuristic",
    )
    assert result.backend == "heuristic"
    assert "mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF" in result.model
    assert "robust" not in result.humanized.lower()
    assert "interested" in result.humanized.lower()


def test_humanize_skips_short_text():
    result = humanize_text("Too short")
    assert result.backend == "passthrough"
    assert result.humanized == "Too short"


def test_humanize_ranked_rewrites_summaries():
    job = Job(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Python",
        source="remotive",
    )
    ranked = [
        RankedJob(
            job=job,
            score=80,
            summary="It is important to note that this is a robust Python internship.",
        )
    ]
    humanize_ranked(ranked, backend="heuristic")
    assert "robust" not in ranked[0].summary.lower()
    assert ranked[0].humanized is True


def test_draft_pitch_includes_job_and_skills():
    profile = Profile(skills=["Python", "Flask"], headline="New-grad engineer")
    pitch = draft_pitch("Backend Intern", "Acme", profile)
    assert "Backend Intern" in pitch
    assert "Acme" in pitch
    assert "Python" in pitch
