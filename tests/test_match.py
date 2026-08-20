from jobfinder.jobs import Job
from jobfinder.match import (
    Profile,
    affine_rank_prompt,
    apply_affine_result,
    keyword_score,
    rank_jobs,
    rank_jobs_with_affine,
)


def _job(**kwargs) -> Job:
    data = dict(
        id="1",
        title="Python Backend Engineer",
        company="Acme",
        location="Remote, USA",
        url="https://example.com/1",
        description="We need Python, Flask, and SQL. Senior crypto trading desk.",
        source="remotive",
        tags=["python", "backend"],
    )
    data.update(kwargs)
    return Job(**data)


def test_keyword_score_rewards_skills_and_penalizes_avoid():
    profile = Profile(
        skills=["Python", "Go"],
        keywords=["backend"],
        avoid=["crypto trading"],
        remote_ok=True,
    )
    ranked = keyword_score(_job(), profile)
    assert ranked.score > 0
    assert any("Python" in reason for reason in ranked.reasons)
    assert any("avoided" in reason.lower() for reason in ranked.reasons)
    assert "Go" in ranked.missing_skills


def test_rank_jobs_orders_by_score():
    profile = Profile(skills=["Python"], keywords=["intern"])
    jobs = [
        _job(id="a", title="Rust Engineer", description="Systems"),
        _job(id="b", title="Python Intern", description="Python intern role"),
    ]
    ranked = rank_jobs(jobs, profile)
    assert ranked[0].job.title == "Python Intern"


def test_profile_from_mapping_and_prompt():
    profile = Profile.from_mapping(
        {
            "name": "Ada",
            "skills": "Python, SQL",
            "keywords": ["backend"],
            "notes": "New grad",
        }
    )
    assert profile.skills == ["Python", "SQL"]
    prompt = profile.as_prompt()
    assert "Ada" in prompt
    assert "Python" in prompt


def test_apply_affine_result_clamps_score():
    ranked = apply_affine_result(
        _job(),
        {
            "score": "150",
            "reasons": ["Strong Python"],
            "missing_skills": ["Kubernetes"],
            "summary": "Good fit.",
        },
    )
    assert ranked.score == 100
    assert ranked.method == "affine-s6"
    assert ranked.summary == "Good fit."


def test_affine_rank_prompt_includes_job_and_profile():
    prompt = affine_rank_prompt(_job(), Profile(name="Ada", skills=["Python"]))
    assert "Ada" in prompt
    assert "Python Backend Engineer" in prompt
    assert "JSON" in prompt


def test_rank_jobs_with_affine_uses_model_and_falls_back():
    profile = Profile(skills=["Python"], keywords=["backend"])
    jobs = [_job(), _job(id="2", title="Gardener", description="plants")]

    def fake_generate(prompt: str):
        if "Gardener" in prompt:
            raise RuntimeError("model down")
        return {
            "score": 88,
            "reasons": ["Python match"],
            "missing_skills": [],
            "summary": "Solid backend fit.",
        }

    ranked = rank_jobs_with_affine(jobs, profile, generate_json=fake_generate, limit=2)
    methods = {item.job.title: item.method for item in ranked}
    assert methods["Python Backend Engineer"] == "affine-s6"
    assert methods["Gardener"] == "keywords"
