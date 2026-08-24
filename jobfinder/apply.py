"""Turn a ranked job into a cover letter, local package, and optional email send."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
import re
import smtplib
from typing import Callable

from jobfinder.config import (
    APPLY_DIR,
    APPLY_FROM,
    APPLY_SMTP_HOST,
    APPLY_SMTP_PASSWORD,
    APPLY_SMTP_PORT,
    APPLY_SMTP_TLS,
    APPLY_SMTP_USER,
)
from jobfinder.coverletter import generate_cover_letter
from jobfinder.jobs import Job, extract_apply_email
from jobfinder.match import Profile
from jobfinder.submit import (
    discover_apply_target,
    email_api_ready,
    email_backend,
    greenhouse_ready,
    send_application_email,
    submit_greenhouse,
)
from jobfinder.tracker import TrackedJob, get_tracked, record_application, save_job, set_cover_letter

SmtpSender = Callable[[EmailMessage], None]


class ApplyError(RuntimeError):
    pass


@dataclass
class ApplyResult:
    tracked: TrackedJob
    cover_letter: str
    submitted: bool
    method: str
    message: str
    package_dir: Path | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.tracked.id,
            "title": self.tracked.title,
            "company": self.tracked.company,
            "status": self.tracked.status,
            "submitted": self.submitted,
            "method": self.method,
            "message": self.message,
            "apply_email": self.tracked.apply_email,
            "url": self.tracked.url,
            "package_dir": str(self.package_dir) if self.package_dir else "",
            "cover_letter": self.cover_letter,
        }


def smtp_ready(profile: Profile | None = None) -> bool:
    """True if an email API key or SMTP can send applications."""
    backend = email_backend()
    if not backend:
        return False
    if backend in {"resend", "sendgrid", "mailgun"}:
        return True
    return bool(APPLY_SMTP_HOST and _from_address(profile))


def _from_address(profile: Profile | None = None) -> str:
    return APPLY_FROM or (profile.email if profile and profile.email else "")


def job_from_tracked(row: TrackedJob) -> Job:
    return Job(
        id=str(row.id),
        title=row.title,
        company=row.company,
        location=row.location,
        url=row.url,
        description=row.description,
        source=row.source or "tracker",
        apply_email=row.apply_email,
    )


def apply_to_job(
    job: Job,
    profile: Profile,
    *,
    send: bool = False,
    mark_applied: bool = False,
    humanize: bool = True,
    affine: bool = False,
    db_path: Path | None = None,
    apply_dir: Path | None = None,
    smtp_send: SmtpSender | None = None,
    score: float | None = None,
) -> ApplyResult:
    letter = generate_cover_letter(job, profile, humanize=humanize, affine=affine)
    email = job.apply_email or extract_apply_email(job.description, job.url)
    saved = save_job(
        job,
        score=score,
        notes=f"Cover letter drafted for {job.title}",
        cover_letter=letter,
        apply_email=email or None,
        description=job.description or None,
        db_path=db_path,
    )
    return _finish(
        saved,
        profile,
        letter,
        send=send,
        mark_applied=mark_applied,
        db_path=db_path,
        apply_dir=apply_dir,
        smtp_send=smtp_send,
    )


def apply_to_tracked(
    entry_id: int,
    profile: Profile,
    *,
    send: bool = False,
    mark_applied: bool = False,
    humanize: bool = True,
    affine: bool = False,
    db_path: Path | None = None,
    apply_dir: Path | None = None,
    smtp_send: SmtpSender | None = None,
) -> ApplyResult:
    row = get_tracked(entry_id, db_path=db_path)
    job = job_from_tracked(row)
    letter = row.cover_letter.strip() or generate_cover_letter(
        job, profile, humanize=humanize, affine=affine
    )
    if not row.cover_letter.strip():
        row = set_cover_letter(entry_id, letter, db_path=db_path)
        if not row.apply_email:
            email = extract_apply_email(job.description, job.url)
            if email:
                row = save_job(
                    job,
                    apply_email=email,
                    status=row.status,
                    notes=row.notes,
                    db_path=db_path,
                )
    return _finish(
        row,
        profile,
        letter,
        send=send,
        mark_applied=mark_applied,
        db_path=db_path,
        apply_dir=apply_dir,
        smtp_send=smtp_send,
    )


def apply_ranked(
    ranked,
    profile: Profile,
    *,
    limit: int | None = None,
    send: bool = False,
    mark_applied: bool = False,
    humanize: bool = True,
    affine: bool = False,
    db_path: Path | None = None,
    apply_dir: Path | None = None,
    smtp_send: SmtpSender | None = None,
) -> list[ApplyResult]:
    results = []
    for item in ranked[: limit or len(ranked)]:
        results.append(
            apply_to_job(
                item.job,
                profile,
                send=send,
                mark_applied=mark_applied,
                humanize=humanize,
                affine=affine,
                db_path=db_path,
                apply_dir=apply_dir,
                smtp_send=smtp_send,
                score=getattr(item, "score", None),
            )
        )
    return results


def write_package(
    row: TrackedJob,
    profile: Profile,
    letter: str,
    dest: Path,
) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "cover-letter.txt").write_text(letter, encoding="utf-8")
    resume_pdf = dest / "resume.pdf"
    try:
        from jobfinder.pdf import render_resume_pdf

        render_resume_pdf(profile, resume_pdf, template="professional")
    except Exception:
        if profile.resume_text:
            (dest / "resume.txt").write_text(profile.resume_text, encoding="utf-8")
    lines = [
        f"{row.title} — {row.company}",
        f"Listing: {row.url or '(no url)'}",
        f"Apply email: {row.apply_email or '(none found)'}",
        f"Status: {row.status}",
        "",
        "Company career-page forms that need extra questions or a captcha",
        "cannot be finished over HTTP. Greenhouse boards can be submitted when",
        "GREENHOUSE_JOB_BOARD_KEY is set. Otherwise email the .eml file or paste",
        "cover-letter.txt on the listing.",
    ]
    (dest / "HOW_TO_SUBMIT.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if row.apply_email:
        write_eml(row, profile, letter, dest / "application.eml", resume_pdf)
    return dest


def write_eml(
    row: TrackedJob,
    profile: Profile,
    letter: str,
    dest: Path,
    resume_pdf: Path | None = None,
) -> Path:
    message = _build_message(row, profile, letter, resume_pdf)
    dest.write_bytes(bytes(message))
    return dest


def _finish(
    row: TrackedJob,
    profile: Profile,
    letter: str,
    *,
    send: bool,
    mark_applied: bool,
    db_path: Path | None,
    apply_dir: Path | None,
    smtp_send: SmtpSender | None,
) -> ApplyResult:
    folder = (apply_dir or APPLY_DIR) / _package_name(row)
    write_package(row, profile, letter, folder)
    submitted = False
    method = "package"
    message = f"Wrote application package to {folder}"
    resume_pdf = folder / "resume.pdf"

    if send:
        target = discover_apply_target(
            row.url,
            f"{row.apply_email} {row.description}",
        )
        if target.email and target.email != row.apply_email:
            row = save_job(
                job_from_tracked(row),
                apply_email=target.email,
                status=row.status,
                notes=row.notes,
                cover_letter=letter,
                db_path=db_path,
            )
        if row.apply_email and (smtp_send or smtp_ready(profile)):
            if smtp_send:
                smtp_send(_build_message(row, profile, letter, resume_pdf))
                via = "email"
                sent_how = f"Sent cover letter and resume to {row.apply_email} over the internet."
            elif email_api_ready():
                from jobfinder.submit import SubmitError

                try:
                    delivered = send_application_email(
                        to=row.apply_email,
                        from_addr=_from_address(profile) or row.apply_email,
                        subject=f"Application: {row.title} — {profile.name or 'candidate'}",
                        body=letter,
                        resume_pdf=resume_pdf if resume_pdf.is_file() else None,
                    )
                except SubmitError as exc:
                    method = email_backend() or "email"
                    message = str(exc)
                    if mark_applied:
                        row = record_application(row.id, via=method, db_path=db_path)
                    via = ""
                    sent_how = ""
                else:
                    via = delivered.method
                    sent_how = delivered.message
            else:
                _smtp_send(_build_message(row, profile, letter, resume_pdf))
                via = "smtp"
                sent_how = f"Sent cover letter and resume to {row.apply_email} over SMTP."
            if via:
                row = record_application(row.id, via=via, db_path=db_path)
                submitted = True
                method = via
                message = sent_how
        elif target.greenhouse and greenhouse_ready():
            from jobfinder.submit import SubmitError

            try:
                gh = submit_greenhouse(
                    target.greenhouse_board,
                    target.greenhouse_job_id,
                    profile,
                    letter,
                    resume_pdf=resume_pdf if resume_pdf.is_file() else None,
                )
            except SubmitError as exc:
                method = "greenhouse"
                message = str(exc)
            else:
                method = gh.method
                message = gh.message
                if gh.submitted:
                    row = record_application(row.id, via="greenhouse", db_path=db_path)
                    submitted = True
                elif mark_applied:
                    row = record_application(row.id, via="greenhouse", db_path=db_path)
        elif row.apply_email:
            method = "eml"
            message = (
                f"Saved {folder / 'application.eml'} for {row.apply_email}. "
                "Set RESEND_API_KEY, SENDGRID_API_KEY, MAILGUN_API_KEY, "
                "or APPLY_SMTP_HOST in .env to send it over the internet."
            )
            if mark_applied:
                row = record_application(row.id, via="eml", db_path=db_path)
        elif target.greenhouse:
            method = "greenhouse"
            message = (
                "This Greenhouse listing can be submitted over HTTP if you set "
                "GREENHOUSE_JOB_BOARD_KEY (the company's Job Board API key). "
                f"Package: {folder}. Listing: {row.url}"
            )
            if mark_applied:
                row = record_application(row.id, via="greenhouse", db_path=db_path)
        else:
            method = "url" if row.url else "package"
            message = (
                "No hiring email on this listing, so nothing was emailed. "
                f"Package: {folder}"
                + (f" Open and submit at {row.url}" if row.url else "")
            )
            if mark_applied:
                row = record_application(row.id, via=method, db_path=db_path)
    elif mark_applied:
        row = record_application(row.id, via=method, db_path=db_path)
        submitted = True
        message += " Marked as applied."

    if row.status == "applied":
        submitted = True
    return ApplyResult(
        tracked=row,
        cover_letter=letter,
        submitted=submitted,
        method=method,
        message=message,
        package_dir=folder,
    )


def _package_name(row: TrackedJob) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{row.company}-{row.title}".lower()).strip("-")
    return f"{row.id}-{slug[:48] or 'job'}"


def _build_message(
    row: TrackedJob,
    profile: Profile,
    letter: str,
    resume_pdf: Path | None,
) -> EmailMessage:
    from_addr = _from_address(profile)
    if not from_addr:
        from_addr = "jobfinder@localhost"
    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = row.apply_email
    message["Subject"] = f"Application: {row.title} — {profile.name or 'candidate'}"
    message.set_content(letter)
    if resume_pdf and resume_pdf.is_file():
        message.add_attachment(
            resume_pdf.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename="resume.pdf",
        )
    return message


def _smtp_send(message: EmailMessage) -> None:
    if not APPLY_SMTP_HOST:
        raise ApplyError("APPLY_SMTP_HOST is not set.")
    if not message["From"]:
        raise ApplyError("Set APPLY_FROM or put an email on your resume.")
    with smtplib.SMTP(APPLY_SMTP_HOST, APPLY_SMTP_PORT, timeout=30) as smtp:
        if APPLY_SMTP_TLS:
            smtp.starttls()
        if APPLY_SMTP_USER:
            smtp.login(APPLY_SMTP_USER, APPLY_SMTP_PASSWORD)
        smtp.send_message(message)
