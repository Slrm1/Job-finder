from jobfinder.jobs import Job
from jobfinder.match import RankedJob
from jobfinder.tracker import (
    STATUSES,
    counts,
    dashboard_stats,
    list_tracked,
    remove_tracked,
    save_job,
    save_ranked,
    set_status,
)


def _job(**kwargs) -> Job:
    data = dict(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Python",
        source="remotive",
    )
    data.update(kwargs)
    return Job(**data)


def test_save_list_status_and_remove(tmp_path):
    db = tmp_path / "apps.db"
    saved = save_job(_job(), score=88, db_path=db)
    assert saved.status == "saved"
    assert saved.score == 88
    rows = list_tracked(db_path=db)
    assert len(rows) == 1
    updated = set_status(saved.id, "applied", db_path=db)
    assert updated.status == "applied"
    assert counts(db_path=db)["applied"] == 1
    remove_tracked(saved.id, db_path=db)
    assert list_tracked(db_path=db) == []


def test_save_ranked_and_dedupe(tmp_path):
    db = tmp_path / "apps.db"
    job = _job()
    ranked = [RankedJob(job=job, score=70, summary="Good intern fit")]
    first = save_ranked(ranked, db_path=db)
    second = save_ranked(ranked, db_path=db)
    assert len(first) == 1
    assert first[0].id == second[0].id
    assert len(list_tracked(db_path=db)) == 1


def test_unknown_status_rejected(tmp_path):
    db = tmp_path / "apps.db"
    try:
        save_job(_job(), status="ghosted", db_path=db)
    except ValueError as exc:
        assert "ghosted" in str(exc)
    else:
        raise AssertionError("expected TrackerError")
    assert "applied" in STATUSES


def test_dashboard_stats(tmp_path):
    db = tmp_path / "apps.db"
    first = save_job(_job(), score=80, db_path=db)
    save_job(_job(id="2", title="Backend Intern", url="https://example.com/2"), db_path=db)
    set_status(first.id, "applied", db_path=db)
    stats = dashboard_stats(db_path=db)
    assert stats["total"] == 2
    assert stats["applied"] == 1
    assert stats["counts"]["applied"] == 1
    assert stats["counts"]["saved"] == 1
    assert stats["apply_rate"] == 50.0
    assert len(stats["recent"]) == 2
