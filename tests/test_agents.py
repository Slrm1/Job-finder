from jobfinder.agents import SearchAgent, Supervisor
from jobfinder.followup import draft_followup, due_followups
from jobfinder.jobs import Job
from jobfinder.match import Profile, drop_mismatched_seniority
from jobfinder.tailor import tailor_profile
from jobfinder.tracker import record_application, save_job


def _job(**kwargs) -> Job:
    data = dict(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Python internship using Flask and SQL.",
        source="remotive",
        apply_email="jobs@acme.test",
    )
    data.update(kwargs)
    return Job(**data)


def _profile() -> Profile:
    return Profile(
        name="Ada Lovelace",
        headline="New-grad software engineer",
        skills=["Python", "Flask", "SQL", "Excel"],
        keywords=["intern"],
        experience_level="internship / early career",
        email="ada@example.com",
        notes="Built Flask APIs for civic data.\nExcel dashboards for the lab.",
        resume_text="Ada Lovelace\nPython intern\nBuilt Flask APIs for civic data.",
    )


def test_drop_senior_roles_for_intern_profile():
    intern = _job()
    senior = _job(id="2", title="Senior Python Engineer", url="https://example.com/2")
    kept = drop_mismatched_seniority([intern, senior], _profile())
    assert [job.title for job in kept] == ["Python Intern"]


def test_tailor_puts_overlapping_skills_first():
    tailored = tailor_profile(_job(), _profile())
    assert tailored.skills[0] == "Python"
    assert "Flask" in tailored.notes or "Flask" in tailored.headline


def test_search_agent_hides_tracked_and_fetches_url(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    save_job(_job(), db_path=db)
    monkeypatch.setattr(
        "jobfinder.agents.search_jobs",
        lambda *a, **k: [_job(), _job(id="2", title="Senior Staff Engineer", url="https://example.com/2")],
    )
    monkeypatch.setattr(
        "jobfinder.agents.fetch_listing",
        lambda url: _job(id="url", title="Pasted Intern", url=url, source="url"),
    )
    jobs = SearchAgent().run(
        "python intern",
        _profile(),
        url="https://jobs.example/pasted",
        db_path=db,
    )
    titles = [job.title for job in jobs]
    assert "Python Intern" not in titles
    assert "Pasted Intern" in titles
    assert "Senior Staff Engineer" not in titles


def test_supervisor_previews_without_yes(tmp_path, monkeypatch):
    monkeypatch.setattr("jobfinder.agents.search_jobs", lambda *a, **k: [_job()])
    monkeypatch.setattr("jobfinder.agents.resolve_profile", lambda **k: _profile())
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", tmp_path / "apps.db")
    monkeypatch.setattr("jobfinder.apply.APPLY_DIR", tmp_path / "packets")
    result = Supervisor().run(
        "python intern",
        apply_count=1,
        yes=False,
        db_path=tmp_path / "apps.db",
        apply_dir=tmp_path / "packets",
        humanize=False,
    )
    assert result.applications
    assert result.applications[0].submitted is False
    assert any(event.agent == "writer" for event in result.log)


def test_followup_after_ten_days(tmp_path):
    db = tmp_path / "apps.db"
    saved = save_job(_job(), db_path=db)
    record_application(saved.id, via="smtp", db_path=db)
    from datetime import datetime, timedelta, timezone

    stale = datetime.now(timezone.utc) - timedelta(days=12)
    import sqlite3

    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE applications SET applied_at=? WHERE id=?",
            (stale.isoformat(), saved.id),
        )
    rows = due_followups(days=10, db_path=db)
    assert len(rows) == 1
    letter = draft_followup(rows[0], _profile())
    assert "Ada Lovelace" in letter
    assert "Python Intern" in letter
