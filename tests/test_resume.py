from pathlib import Path

from jobfinder.match import Profile, affine_rank_prompt, keyword_score
from jobfinder.resume import (
    parse_resume,
    profile_from_resume,
    read_resume,
    resolve_profile,
)


SAMPLE = Path(__file__).resolve().parents[1] / "resume.example.txt"


def test_parse_example_resume():
    profile = parse_resume(SAMPLE.read_text())
    assert profile["name"] == "Ada Lovelace"
    assert profile["email"] == "ada@example.com"
    assert "Python" in profile["skills"]
    assert "Flask" in profile["skills"]
    assert any("intern" in item for item in profile["keywords"])
    assert "Washington" in profile["location"]
    assert "resume" in profile["resume_text"].lower() or "Flask" in profile["resume_text"]


def test_read_resume_txt(tmp_path):
    path = tmp_path / "me.txt"
    path.write_text(SAMPLE.read_text(), encoding="utf-8")
    text = read_resume(path)
    assert "Ada Lovelace" in text
    loaded = profile_from_resume(path)
    assert loaded.name == "Ada Lovelace"
    assert loaded.source == "resume"


def test_resolve_profile_prefers_resume_over_example(tmp_path):
    resume = tmp_path / "resume.txt"
    resume.write_text(SAMPLE.read_text(), encoding="utf-8")
    profile = resolve_profile(resume_path=resume, search_dir=tmp_path)
    assert profile.name == "Ada Lovelace"
    assert profile.resume_text


def test_resolve_profile_merges_yaml_avoid_list(tmp_path):
    resume = tmp_path / "resume.txt"
    resume.write_text(SAMPLE.read_text(), encoding="utf-8")
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text("name: Override\navoid:\n  - unpaid\n", encoding="utf-8")
    profile = resolve_profile(profile_path=yaml_path, resume_path=resume)
    assert profile.name == "Override"
    assert "unpaid" in profile.avoid
    assert "Python" in profile.skills


def test_keyword_score_uses_resume_overlap():
    from jobfinder.jobs import Job

    profile = Profile(
        skills=["Python"],
        keywords=["intern"],
        resume_text="Python intern at Civic Tech Lab. Flask APIs.",
    )
    job = Job(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Need Go programmers",
        source="remotive",
    )
    ranked = keyword_score(job, profile)
    assert any("Resume overlaps" in reason for reason in ranked.reasons)


def test_affine_prompt_includes_resume_text():
    profile = Profile(name="Ada", skills=["Python"], resume_text="Built Flask APIs")
    prompt = affine_rank_prompt(
        __import__("jobfinder.jobs", fromlist=["Job"]).Job(
            id="1",
            title="Backend Intern",
            company="Acme",
            location="Remote",
            url="https://example.com/1",
            description="Python",
            source="remotive",
        ),
        profile,
    )
    assert "Built Flask APIs" in prompt
    assert "RESUME" in prompt
