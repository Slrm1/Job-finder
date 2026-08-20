"""Unit tests that do not require HF_TOKEN or network."""

from backend.jobs import Job, heuristic_rank
from backend.model import strip_thinking


def test_strip_thinking_removes_blocks():
    raw = "<think>secret plan</think>\n\nHello world"
    assert strip_thinking(raw) == "Hello world"


def test_strip_thinking_handles_orphan_close():
    raw = "hidden reasoning</think>\nVisible answer"
    assert "Visible answer" in strip_thinking(raw)
    assert "hidden" not in strip_thinking(raw).lower() or strip_thinking(raw).startswith("Visible")


def test_heuristic_rank_prefers_keyword_overlap():
    jobs = [
        Job(
            id=1,
            title="Python Backend Engineer",
            company="Acme",
            category="software-dev",
            tags=["python", "fastapi"],
            job_type="full_time",
            location="Worldwide",
            salary="",
            url="https://example.com/1",
            published="",
            description="Build APIs with Python and FastAPI",
        ),
        Job(
            id=2,
            title="Retail Associate",
            company="ShopCo",
            category="other",
            tags=["retail"],
            job_type="full_time",
            location="US",
            salary="",
            url="https://example.com/2",
            published="",
            description="In-store customer service",
        ),
    ]
    ranked = heuristic_rank("Senior Python FastAPI engineer", jobs, top_n=2)
    assert ranked[0]["id"] == 1
    assert ranked[0]["score"] >= ranked[1]["score"]
