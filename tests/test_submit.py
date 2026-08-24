from jobfinder.match import Profile
from jobfinder.submit import (
    discover_apply_target,
    email_backend,
    greenhouse_payload,
    key_status,
    parse_greenhouse,
    send_application_email,
    split_name,
    submit_greenhouse,
)


def test_key_status_has_no_secrets(monkeypatch):
    monkeypatch.setattr("jobfinder.config.RESEND_API_KEY", "re_super_secret")
    monkeypatch.setattr("jobfinder.config.APPLY_API_KEY", "re_super_secret")
    status = key_status()
    blob = " ".join(f"{k}={v}" for k, v in status.items())
    assert "re_super_secret" not in blob
    assert status["RESEND_API_KEY"] == "set"
    assert status["APPLY_API_KEY"] == "set"


def test_parse_greenhouse_urls():
    board, job_id = parse_greenhouse(
        "https://boards.greenhouse.io/stripe/jobs/12345?gh_jid=12345"
    )
    assert board == "stripe"
    assert job_id == "12345"
    board, job_id = parse_greenhouse(
        "https://job-boards.greenhouse.io/notion/jobs/999"
    )
    assert board == "notion"
    assert job_id == "999"


def test_discover_uses_listing_html_without_live_http():
    html = """
    <html><a href="mailto:jobs@acme.test">apply</a>
    Apply at https://boards.greenhouse.io/acme/jobs/42
    </html>
    """
    target = discover_apply_target(
        "https://jobs.acme.test/role",
        getter=lambda url: (url, html),
    )
    assert target.email == "jobs@acme.test"
    assert target.greenhouse_board == "acme"
    assert target.greenhouse_job_id == "42"


def test_split_name_and_payload():
    first, last = split_name("Ada Lovelace")
    assert first == "Ada"
    assert last == "Lovelace"
    profile = Profile(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="202-555-0100",
        location="Washington, DC",
        resume_text="Python intern",
    )
    payload = greenhouse_payload(profile, "Please consider me.\n")
    assert payload["first_name"] == "Ada"
    assert payload["email"] == "ada@example.com"
    assert payload["cover_letter_text"].startswith("Please")
    assert payload["resume_text"] == "Python intern"


def test_submit_greenhouse_posts_json():
    profile = Profile(name="Ada Lovelace", email="ada@example.com", resume_text="resume")
    seen = {}

    class FakeResponse:
        status_code = 200
        text = '{"id": 9}'

    def poster(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["json"] = json
        seen["headers"] = headers
        return FakeResponse()

    result = submit_greenhouse(
        "acme",
        "42",
        profile,
        "Cover letter body",
        api_key="board-secret",
        poster=poster,
    )
    assert result.submitted is True
    assert result.method == "greenhouse"
    assert seen["url"].endswith("/boards/acme/jobs/42")
    assert seen["json"]["email"] == "ada@example.com"
    assert "Basic " in seen["headers"]["Authorization"]


def test_submit_greenhouse_without_key_does_not_post():
    profile = Profile(name="Ada", email="ada@example.com")
    result = submit_greenhouse("acme", "42", profile, "letter", api_key="")
    assert result.submitted is False
    assert "GREENHOUSE_JOB_BOARD_KEY" in result.message


def test_email_backend_prefers_resend_key(monkeypatch):
    monkeypatch.setattr("jobfinder.submit.APPLY_EMAIL_BACKEND", "auto")
    monkeypatch.setattr("jobfinder.submit.RESEND_API_KEY", "re_test")
    monkeypatch.setattr("jobfinder.submit.SENDGRID_API_KEY", "")
    monkeypatch.setattr("jobfinder.submit.MAILGUN_API_KEY", "")
    assert email_backend() == "resend"


def test_send_resend_api(monkeypatch):
    monkeypatch.setattr("jobfinder.submit.APPLY_EMAIL_BACKEND", "resend")
    monkeypatch.setattr("jobfinder.submit.RESEND_API_KEY", "re_test")
    seen = {}

    class FakeResponse:
        status_code = 200
        text = '{"id": "msg"}'

    def poster(url, json=None, headers=None, timeout=None, **kwargs):
        seen["url"] = url
        seen["json"] = json
        seen["auth"] = headers["Authorization"]
        return FakeResponse()

    result = send_application_email(
        to="jobs@acme.test",
        from_addr="ada@example.com",
        subject="Application: Python Intern",
        body="Please consider me.",
        poster=poster,
    )
    assert result.submitted is True
    assert result.method == "resend"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["json"]["to"] == ["jobs@acme.test"]
    assert seen["auth"] == "Bearer re_test"


def test_send_sendgrid_api(monkeypatch):
    monkeypatch.setattr("jobfinder.submit.APPLY_EMAIL_BACKEND", "sendgrid")
    monkeypatch.setattr("jobfinder.submit.SENDGRID_API_KEY", "SG.test")
    seen = {}

    class FakeResponse:
        status_code = 202
        text = ""

    def poster(url, json=None, headers=None, timeout=None, **kwargs):
        seen["url"] = url
        seen["json"] = json
        return FakeResponse()

    result = send_application_email(
        to="jobs@acme.test",
        from_addr="ada@example.com",
        subject="Application",
        body="Hello",
        poster=poster,
    )
    assert result.method == "sendgrid"
    assert seen["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert seen["json"]["personalizations"][0]["to"][0]["email"] == "jobs@acme.test"
