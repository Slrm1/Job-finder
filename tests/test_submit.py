from jobfinder.match import Profile
from jobfinder.submit import (
    discover_apply_target,
    greenhouse_payload,
    parse_greenhouse,
    split_name,
    submit_greenhouse,
)


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
