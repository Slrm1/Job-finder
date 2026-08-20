from jobfinder.jobs import Job, fetch_arbeitnow, fetch_remoteok, fetch_remotive, search_jobs


def _remotive_payload():
    return {
        "jobs": [
            {
                "id": 1,
                "title": "Python Backend Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Remote",
                "url": "https://example.com/jobs/1",
                "description": "<p>Build APIs in Python</p>",
                "tags": ["python", "backend"],
                "salary": "120k",
                "publication_date": "2026-01-01",
            }
        ]
    }


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_remotive(monkeypatch):
    def fake_get(self, url, timeout=None):
        assert "remotive.com" in url
        return FakeResponse(_remotive_payload())

    monkeypatch.setattr("jobfinder.jobs.requests.Session.get", fake_get)
    jobs = fetch_remotive("python", limit=5)
    assert len(jobs) == 1
    assert jobs[0].title == "Python Backend Engineer"
    assert "Build APIs" in jobs[0].description
    assert "<p>" not in jobs[0].description
    assert jobs[0].source == "remotive"


def test_fetch_arbeitnow_filters_query(monkeypatch):
    payload = {
        "data": [
            {
                "title": "Rust Engineer",
                "company_name": "Ferris",
                "description": "Systems work",
                "tags": ["rust"],
                "url": "https://example.com/r",
                "slug": "rust-engineer",
                "remote": True,
                "location": "Remote",
            },
            {
                "title": "Python Intern",
                "company_name": "Snake",
                "description": "Write tests",
                "tags": ["python"],
                "url": "https://example.com/p",
                "slug": "python-intern",
                "remote": True,
                "location": "Remote",
            },
        ]
    }
    monkeypatch.setattr(
        "jobfinder.jobs.requests.Session.get",
        lambda self, url, timeout=None: FakeResponse(payload),
    )
    jobs = fetch_arbeitnow("python intern")
    assert [job.title for job in jobs] == ["Python Intern"]


def test_fetch_remoteok_skips_metadata(monkeypatch):
    payload = [
        {"last_updated": 1},
        {
            "id": "99",
            "position": "ML Engineer",
            "company": "Labs",
            "description": "Train models",
            "tags": ["ml"],
            "url": "https://example.com/ml",
            "location": "Remote",
            "epoch": 1700000000,
        },
    ]
    monkeypatch.setattr(
        "jobfinder.jobs.requests.Session.get",
        lambda self, url, timeout=None: FakeResponse(payload),
    )
    jobs = fetch_remoteok("ml")
    assert len(jobs) == 1
    assert jobs[0].company == "Labs"
    assert jobs[0].posted_at is not None


def test_search_jobs_dedupes(monkeypatch):
    job = Job(
        id="a",
        title="Engineer",
        company="Acme",
        location="Remote",
        url="https://example.com/same",
        description="Python",
        source="remotive",
    )

    monkeypatch.setattr("jobfinder.jobs.fetch_remotive", lambda q, limit: [job])
    monkeypatch.setattr(
        "jobfinder.jobs.fetch_arbeitnow",
        lambda q, limit: [
            Job(
                id="b",
                title="Engineer",
                company="Acme",
                location="Remote",
                url="https://example.com/same",
                description="Python",
                source="arbeitnow",
            )
        ],
    )
    monkeypatch.setattr("jobfinder.jobs.fetch_remoteok", lambda q, limit: [])
    results = search_jobs("python", limit=10)
    assert len(results) == 1
