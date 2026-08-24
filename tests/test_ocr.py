from jobfinder.jobs import Job
from jobfinder.match import Profile
from jobfinder.ocr import ocr_via_paperless


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or str(payload)

    def json(self):
        return self._payload


def test_paperless_ocr_logs_in_and_reads_content(monkeypatch):
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_URL", "http://paperless.test")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_USER", "admin")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_PASSWORD", "secret")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_TOKEN", "")
    calls = []

    def poster(url, **kwargs):
        calls.append(("post", url))
        if url.endswith("/api/token/"):
            assert kwargs["json"]["username"] == "admin"
            return FakeResponse({"token": "tok-1"})
        return FakeResponse("task-uuid")

    def getter(url, **kwargs):
        calls.append(("get", url))
        if "/api/tasks/" in url:
            return FakeResponse([{"status": "SUCCESS", "related_document": "9"}])
        return FakeResponse(
            {
                "id": 9,
                "content": "Ada Lovelace\nPython intern\n" + ("skills " * 20),
            }
        )

    text = ocr_via_paperless(
        b"%PDF-fake",
        "resume.pdf",
        poster=poster,
        getter=getter,
        sleeper=lambda _s: None,
    )
    assert "Ada Lovelace" in text
    assert any(url.endswith("/api/token/") for _, url in calls)
    assert not any("secret" in str(item) for item in calls)


def test_paperless_ready_needs_login(monkeypatch):
    from jobfinder.ocr import paperless_ready

    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_URL", "")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_USER", "")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_PASSWORD", "")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_TOKEN", "")
    assert paperless_ready() is False
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_URL", "http://localhost:8000")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_USER", "admin")
    monkeypatch.setattr("jobfinder.ocr.PAPERLESS_PASSWORD", "secret")
    assert paperless_ready() is True
