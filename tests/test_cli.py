from io import BytesIO

from jobfinder.cli import build_parser, main
from jobfinder.jobs import Job
from jobfinder.match import RankedJob
from jobfinder.web import create_app


def test_parser_search_flags():
    args = build_parser().parse_args(
        ["search", "python intern", "--affine", "--limit", "5", "--resume", "me.pdf"]
    )
    assert args.query == "python intern"
    assert args.affine is True
    assert args.limit == 5
    assert args.resume == "me.pdf"


def test_profile_command_reads_resume(capsys):
    assert main(["profile", "--resume", "resume.example.txt"]) == 0
    out = capsys.readouterr().out
    assert "Ada Lovelace" in out
    assert "Python" in out


def test_model_command(capsys):
    assert main(["model"]) == 0
    out = capsys.readouterr().out
    assert "WebScraper991923/Affine-S6" in out
    assert "huggingface.co/WebScraper991923/Affine-S6" in out


def test_search_command_uses_keyword_rank(monkeypatch, capsys):
    job = Job(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Python internship",
        source="remotive",
        tags=["python"],
    )
    monkeypatch.setattr("jobfinder.cli.search_jobs", lambda *a, **k: [job])
    monkeypatch.setattr(
        "jobfinder.cli._load_profile",
        lambda path: __import__("jobfinder.match", fromlist=["Profile"]).Profile(
            skills=["Python"], keywords=["intern"]
        ),
    )
    assert main(["search", "python intern", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "Python Intern" in out
    assert "Acme" in out


def test_web_index_and_search(monkeypatch):
    job = Job(
        id="1",
        title="Python Intern",
        company="Acme",
        location="Remote",
        url="https://example.com/1",
        description="Python internship",
        source="remotive",
        tags=["python"],
    )
    monkeypatch.setattr("jobfinder.web.search_jobs", lambda *a, **k: [job])
    app = create_app()
    client = app.test_client()
    home = client.get("/")
    assert home.status_code == 200
    assert b"WebScraper991923/Affine-S6" in home.data
    assert b'name="resume"' in home.data

    ranked = RankedJob(job=job, score=90, summary="Good intern fit", method="keywords")
    monkeypatch.setattr(
        "jobfinder.web.rank_jobs", lambda jobs, profile, query="": [ranked]
    )
    response = client.post("/search", data={"query": "python intern", "limit": "10"})
    assert response.status_code == 200
    assert b"Python Intern" in response.data
    assert b"Good intern fit" in response.data

    sample = (
        b"Ada Lovelace\nPython intern\n\nSkills\nPython, Flask, SQL, Git\n\n"
        b"Experience\nBuilt APIs for civic data matching and dashboards.\n"
    )
    upload = client.post(
        "/search",
        data={
            "query": "python intern",
            "limit": "10",
            "resume": (BytesIO(sample), "resume.txt"),
        },
    )
    assert upload.status_code == 200
    assert b"Ada Lovelace" in upload.data or b"resume" in upload.data.lower()
