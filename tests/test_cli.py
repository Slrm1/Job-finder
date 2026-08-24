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


def test_parser_dashboard_resume_pdf_and_mcp():
    parser = build_parser()
    assert parser.parse_args(["dashboard"]).func.__name__ == "cmd_dashboard"
    pdf = parser.parse_args(
        ["resume-pdf", "--resume", "resume.example.txt", "-o", "out.pdf", "--template", "professional"]
    )
    assert pdf.output == "out.pdf"
    assert pdf.template == "professional"
    assert parser.parse_args(["mcp"]).func.__name__ == "cmd_mcp"
    apply_args = parser.parse_args(["apply", "3", "--send", "--mark-applied"])
    assert apply_args.id == 3
    assert apply_args.send is True
    assert apply_args.mark_applied is True


def test_humanize_command(capsys):
    assert (
        main(
            [
                "humanize",
                "--backend",
                "heuristic",
                "It is important to note that I can leverage this robust role.",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "leverage" not in out.lower()
    assert "Ai-Humanizer-Llama-3.2-3B-GGUF" in out


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
    assert "mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF" in out
    assert "Apply:" in out


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


def test_dashboard_command(tmp_path, monkeypatch, capsys):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    from jobfinder.tracker import save_job

    save_job(
        Job(
            id="1",
            title="Python Intern",
            company="Acme",
            location="Remote",
            url="https://example.com/1",
            description="Python",
            source="remotive",
        ),
        db_path=db,
    )
    assert main(["dashboard"]) == 0
    out = capsys.readouterr().out
    assert "Python Intern" in out
    assert "Acme" in out
    assert "total=1" in out


def test_resume_pdf_command(tmp_path, capsys):
    dest = tmp_path / "ada.pdf"
    assert (
        main(
            [
                "resume-pdf",
                "--resume",
                "resume.example.txt",
                "-o",
                str(dest),
                "--template",
                "professional",
            ]
        )
        == 0
    )
    assert dest.read_bytes()[:5] == b"%PDF-"
    assert "professional" in capsys.readouterr().out


def test_apply_command_drafts_letter(tmp_path, monkeypatch, capsys):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    monkeypatch.setattr("jobfinder.apply.APPLY_DIR", tmp_path / "packets")
    from jobfinder.tracker import save_job

    save_job(
        Job(
            id="1",
            title="Python Intern",
            company="Acme",
            location="Remote",
            url="https://jobs.acme.test/1",
            description="Python internship",
            source="remotive",
            apply_email="jobs@acme.test",
        ),
        db_path=db,
    )
    assert main(["apply", "1", "--resume", "resume.example.txt", "--mark-applied"]) == 0
    out = capsys.readouterr().out
    assert "Python Intern" in out
    assert "Ada Lovelace" in out
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
    assert b"humanize" in home.data
    assert b"mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF" in home.data
    assert b"Dashboard" in home.data
    assert b"Tracker" in home.data

    ranked = RankedJob(job=job, score=90, summary="Good intern fit", method="keywords")
    monkeypatch.setattr(
        "jobfinder.web.rank_jobs", lambda jobs, profile, query="": [ranked]
    )
    response = client.post("/search", data={"query": "python intern", "limit": "10"})
    assert response.status_code == 200
    assert b"Python Intern" in response.data
    assert b"Good intern fit" in response.data
    assert b"Save to tracker" in response.data
    assert b"Submit resume over the internet" in response.data

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

    rewritten = client.post(
        "/humanize",
        data={
            "text": "It is important to note that I can leverage this robust Python internship."
        },
    )
    assert rewritten.status_code == 200
    assert b"heuristic" in rewritten.data or b"Humanizer" in rewritten.data
    assert b"Python" in rewritten.data


def test_web_tracker_save_and_list(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    app = create_app()
    client = app.test_client()
    page = client.get("/tracker")
    assert page.status_code == 200
    assert b"Application tracker" in page.data
    saved = client.post(
        "/track",
        data={
            "title": "Python Intern",
            "company": "Acme",
            "location": "Remote",
            "url": "https://example.com/1",
            "source": "remotive",
            "score": "90",
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert b"Python Intern" in saved.data
    assert b"Acme" in saved.data

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert b"Dashboard" in dash.data
    assert b"Python Intern" in dash.data
    assert b"Moved forward" in dash.data

    payload = client.get("/api/jobs").get_json()
    assert payload[0]["title"] == "Python Intern"
    stats = client.get("/api/dashboard").get_json()
    assert stats["total"] == 1
    assert stats["counts"]["saved"] == 1


def test_web_apply_writes_cover_letter(tmp_path, monkeypatch):
    db = tmp_path / "apps.db"
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", db)
    monkeypatch.setattr("jobfinder.apply.APPLY_DIR", tmp_path / "packets")
    app = create_app(resume_path="resume.example.txt")
    client = app.test_client()
    applied = client.post(
        "/apply",
        data={
            "title": "Python Intern",
            "company": "Acme",
            "location": "Remote",
            "url": "https://jobs.acme.test/1",
            "source": "remotive",
            "score": "90",
            "description": "Python internship. Email jobs@acme.test",
            "mark_applied": "on",
        },
        follow_redirects=True,
    )
    assert applied.status_code == 200
    assert b"Python Intern" in applied.data
    assert b"Ada Lovelace" in applied.data or b"cover letter" in applied.data.lower()
    letter = client.get("/tracker/1/cover-letter.txt")
    assert letter.status_code == 200
    assert b"Python Intern" in letter.data
    assert b"Acme" in letter.data


def test_web_resume_pdf():
    app = create_app(resume_path="resume.example.txt")
    client = app.test_client()
    simple = client.get("/resume.pdf")
    assert simple.status_code == 200
    assert simple.data[:5] == b"%PDF-"
    assert simple.mimetype == "application/pdf"
    professional = client.get("/resume.pdf?template=professional")
    assert professional.status_code == 200
    assert professional.data[:5] == b"%PDF-"
    bad = client.get("/resume.pdf?template=fancy")
    assert bad.status_code == 400
