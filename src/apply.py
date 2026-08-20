from __future__ import annotations

import json
import os
import smtplib
import time
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from src.config import load_config
from src.cover_letter import extract_candidate, generate_cover_letter, generate_cover_letter_with_model
from src.job_finder import Job, JobMatch, find_matching_jobs

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTBOX_DIR = DATA_DIR / "outbox"
LOG_PATH = DATA_DIR / "applications.json"


@dataclass
class ApplicationResult:
    job_title: str
    company: str
    score: float
    status: str
    method: str
    packet_dir: str
    apply_email: str | None
    apply_url: str | None
    detail: str
    created_at: str


def apply_to_jobs(
    resume: str,
    resume_path: Path | None,
    jobs: list[Job] | None = None,
    *,
    min_score: float | None = None,
    limit: int | None = None,
    send: bool = False,
    open_urls: bool = False,
    offline: bool = True,
    use_api: bool = False,
    force: bool = False,
) -> list[ApplicationResult]:
    config = load_config().get("apply", {})
    threshold = min_score if min_score is not None else float(config.get("min_score", 60))
    max_batch = limit if limit is not None else int(config.get("max_batch", 10))
    delay = float(config.get("delay_seconds", 2))

    matches, _ = find_matching_jobs(resume, jobs=jobs, use_api=use_api, offline=offline)
    selected = [match for match in matches if match.score >= threshold][:max_batch]
    log = _load_log()
    results: list[ApplicationResult] = []

    for match in selected:
        if not force and _already_applied(log, match.job):
            results.append(
                _result(
                    match,
                    status="skipped",
                    method="none",
                    packet_dir="",
                    detail="Already applied (use --force to re-apply).",
                )
            )
            continue
        results.append(
            _apply_one(
                resume=resume,
                resume_path=resume_path,
                match=match,
                send=send,
                open_urls=open_urls,
                offline=offline,
                use_api=use_api,
            )
        )
        if send:
            time.sleep(delay)

    _save_log(log + [asdict(item) for item in results if item.status != "skipped"])
    return results


def apply_to_named_jobs(
    resume: str,
    resume_path: Path | None,
    targets: list[Job],
    **kwargs,
) -> list[ApplicationResult]:
    return apply_to_jobs(resume, resume_path, jobs=targets, min_score=0, **kwargs)


def list_applications() -> list[dict]:
    return _load_log()


def _apply_one(
    resume: str,
    resume_path: Path | None,
    match: JobMatch,
    send: bool,
    open_urls: bool,
    offline: bool,
    use_api: bool,
) -> ApplicationResult:
    job = match.job
    if offline:
        letter = generate_cover_letter(resume, job, match.reasoning)
    else:
        letter = generate_cover_letter_with_model(resume, job, use_api=use_api)

    packet_dir = _write_packet(job, letter, match)
    methods = []
    details = [f"Packet saved to {packet_dir}"]
    status = "draft"

    if job.apply_email:
        methods.append("email")
        if send:
            try:
                _send_email(job, letter, resume, resume_path)
                status = "sent"
                details.append(f"Emailed {job.apply_email}")
            except Exception as exc:
                status = "error"
                details.append(f"Email failed: {exc}")
        else:
            details.append(f"Dry run: would email {job.apply_email}")

    if job.apply_url and (open_urls or job.apply_method == "url" and not job.apply_email):
        methods.append("url")
        if open_urls:
            webbrowser.open(job.apply_url)
            if status == "draft":
                status = "opened_url"
            details.append(f"Opened {job.apply_url}")
        else:
            details.append(f"Apply URL: {job.apply_url}")
    elif job.apply_url:
        details.append(f"Apply URL (not opened): {job.apply_url}")

    if not job.apply_email and not job.apply_url:
        details.append("No apply_email or apply_url on this listing.")

    return _result(
        match,
        status=status,
        method="+".join(methods) or "packet",
        packet_dir=str(packet_dir),
        detail=" ".join(details),
    )


def _write_packet(job: Job, letter: str, match: JobMatch) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    packet_dir = OUTBOX_DIR / f"{stamp}-{job.slug}"
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "cover_letter.txt").write_text(letter, encoding="utf-8")
    (packet_dir / "job.json").write_text(
        json.dumps(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "apply_email": job.apply_email,
                "apply_url": job.apply_url,
                "score": match.score,
                "reasoning": match.reasoning,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return packet_dir


def _send_email(job: Job, letter: str, resume: str, resume_path: Path | None) -> None:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM") or user
    if not host or not from_addr:
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM."
        )
    if not job.apply_email:
        raise RuntimeError("This job has no apply_email.")

    candidate = extract_candidate(resume)
    msg = EmailMessage()
    msg["Subject"] = f"Application for {job.title} — {candidate.name}"
    msg["From"] = from_addr
    msg["To"] = job.apply_email
    if candidate.email:
        msg["Reply-To"] = candidate.email
    msg.set_content(letter)

    attach_path = resume_path if resume_path and resume_path.exists() else None
    if attach_path:
        data = attach_path.read_bytes()
        maintype, subtype = ("application", "pdf") if attach_path.suffix.lower() == ".pdf" else ("text", "plain")
        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=attach_path.name,
        )

    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)


def _result(
    match: JobMatch,
    status: str,
    method: str,
    packet_dir: str,
    detail: str,
) -> ApplicationResult:
    return ApplicationResult(
        job_title=match.job.title,
        company=match.job.company,
        score=match.score,
        status=status,
        method=method,
        packet_dir=packet_dir,
        apply_email=match.job.apply_email,
        apply_url=match.job.apply_url,
        detail=detail,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _already_applied(log: list[dict], job: Job) -> bool:
    for item in log:
        if item.get("company") == job.company and item.get("job_title") == job.title:
            if item.get("status") in {"sent", "opened_url"}:
                return True
    return False


def _load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def _save_log(entries: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")
