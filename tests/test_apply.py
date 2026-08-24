from jobfinder.apply import apply_to_job, apply_to_tracked
from jobfinder.coverletter import draft_cover_letter
from jobfinder.jobs import Job, extract_apply_email
from jobfinder.match import Profile
from jobfinder.submit import SubmitResult
from jobfinder.tracker import save_job


def _job(**kwargs) -> Job:
    data = dict(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://boards.example.org/jobs/1",
        description="Python internship. Apply at jobs@acme.test or via the listing.",
        source="remotive",
        apply_email="jobs@acme.test",
    )
    data.update(kwargs)
    return Job(**data)


def _profile() -> Profile:
    return Profile(
        name="Ada Lovelace",
        headline="New-grad software engineer",
        location="Washington, DC",
        email="ada@example.com",
        skills=["Python", "Flask", "SQL"],
        keywords=["intern"],
        notes="Built Flask APIs and dashboards used by 200 weekly users",
        resume_text="Ada Lovelace\nPython intern\nBuilt Flask APIs",
    )


def test_extract_apply_email_skips_placeholders():
    assert extract_apply_email("mailto:jobs@acme.test") == "jobs@acme.test"
    assert extract_apply_email("Contact noreply@github.com then jobs@labs.io") == "jobs@labs.io"
    assert extract_apply_email("demo@example.com") == ""


def test_draft_cover_letter_uses_resume_facts():
    letter = draft_cover_letter(_job(), _profile())
    assert "Ada Lovelace" in letter
    assert "Python Intern" in letter
    assert "Acme" in letter
    assert "Flask" in letter or "Python" in letter
    assert "leverage" not in letter.lower()


def test_apply_writes_package_and_can_email(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    out = tmp_path / "packets"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    sent = []

    result = apply_to_job(
        _job(),
        _profile(),
        send=False,
        db_path=db,
        apply_dir=out,
        humanize=False,
    )
    assert result.tracked.cover_letter
    assert "Python Intern" in result.tracked.cover_letter
    assert (result.package_dir / "cover-letter.txt").is_file()
    assert (result.package_dir / "application.eml").is_file()
    assert result.submitted is False
    assert result.tracked.status == "saved"

    mailed = apply_to_tracked(
        result.tracked.id,
        _profile(),
        send=True,
        db_path=db,
        apply_dir=out,
        smtp_send=sent.append,
        humanize=False,
    )
    assert mailed.submitted is True
    assert mailed.method == "email"
    assert mailed.tracked.status == "applied"
    payload = sent[0].as_string()
    assert "jobs@acme.test" in payload
    assert "Python Intern" in payload


def test_apply_without_email_packages_url_job(tmp_path, monkeypatch):
    monkeypatch.setattr("jobfinder.submit.get_url", lambda url: (url, ""))
    db = tmp_path / "apps.db"
    job = _job(apply_email="", description="No email here, use the site.", url="https://jobs.acme.test/1")
    result = apply_to_job(
        job,
        _profile(),
        send=True,
        mark_applied=True,
        db_path=db,
        apply_dir=tmp_path / "out",
        humanize=False,
    )
    assert result.method in {"url", "package"}
    assert result.tracked.status == "applied"
    assert result.package_dir and (result.package_dir / "cover-letter.txt").is_file()
    assert "https://jobs.acme.test/1" in (result.package_dir / "HOW_TO_SUBMIT.txt").read_text()


def test_save_job_keeps_cover_letter_on_update(tmp_path):
    db = tmp_path / "apps.db"
    first = save_job(_job(), cover_letter="Hello Acme\n", db_path=db)
    again = save_job(_job(), notes="updated", db_path=db)
    assert first.id == again.id
    assert again.cover_letter == "Hello Acme\n"
    assert again.apply_email == "jobs@acme.test"


def test_apply_posts_greenhouse_when_key_ready(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    monkeypatch.setattr("jobfinder.apply.greenhouse_ready", lambda: True)
    monkeypatch.setattr(
        "jobfinder.apply.submit_greenhouse",
        lambda *a, **k: SubmitResult(
            submitted=True, method="greenhouse", message="posted"
        ),
    )
    job = _job(
        apply_email="",
        url="https://boards.greenhouse.io/acme/jobs/42",
        description="Python internship on a Greenhouse board.",
    )
    result = apply_to_job(
        job,
        _profile(),
        send=True,
        db_path=db,
        apply_dir=tmp_path / "out",
        humanize=False,
    )
    assert result.submitted is True
    assert result.method == "greenhouse"
    assert result.tracked.status == "applied"


def test_apply_sends_via_resend_api(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    monkeypatch.setattr("jobfinder.apply.email_api_ready", lambda: True)
    monkeypatch.setattr("jobfinder.apply.smtp_ready", lambda profile=None: True)
    monkeypatch.setattr(
        "jobfinder.apply.send_application_email",
        lambda **kwargs: SubmitResult(
            submitted=True,
            method="resend",
            message=f"Sent via resend to {kwargs['to']}",
            email=kwargs["to"],
        ),
    )
    result = apply_to_job(
        _job(),
        _profile(),
        send=True,
        db_path=db,
        apply_dir=tmp_path / "out",
        humanize=False,
    )
    assert result.submitted is True
    assert result.method == "resend"
    assert "jobs@acme.test" in result.message
