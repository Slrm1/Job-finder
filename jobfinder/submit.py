"""Submit applications over the internet: email, listing fetch, Greenhouse API."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

import requests

from jobfinder.config import (
    APPLY_PHONE,
    GREENHOUSE_JOB_BOARD_KEY,
    MAILGUN_API_BASE,
    MAILGUN_API_KEY,
    MAILGUN_DOMAIN,
    APPLY_EMAIL_BACKEND,
    RESEND_API_KEY,
    SENDGRID_API_KEY,
    USER_AGENT,
)
from jobfinder.jobs import extract_apply_email
from jobfinder.match import Profile

TIMEOUT = 20
MAX_BODY = 400_000
GREENHOUSE_RE = re.compile(
    r"https?://(?:job-)?boards\.greenhouse\.io/([^/?#]+)/jobs/(\d+)",
    re.I,
)
GH_JID_RE = re.compile(r"[?&]gh_jid=(\d+)", re.I)
GetUrl = Callable[[str], tuple[str, str]]
PostJson = Callable[..., requests.Response]


class SubmitError(RuntimeError):
    pass


@dataclass
class ApplyTarget:
    email: str = ""
    greenhouse_board: str = ""
    greenhouse_job_id: str = ""
    url: str = ""

    @property
    def greenhouse(self) -> bool:
        return bool(self.greenhouse_board and self.greenhouse_job_id)


@dataclass
class SubmitResult:
    submitted: bool
    method: str
    message: str
    email: str = ""
    url: str = ""


def split_name(name: str) -> tuple[str, str]:
    parts = [part for part in (name or "Applicant").split() if part]
    if not parts:
        return "Applicant", "Candidate"
    if len(parts) == 1:
        return parts[0], "Candidate"
    return parts[0], " ".join(parts[1:])


def parse_greenhouse(url: str) -> tuple[str, str]:
    if not url:
        return "", ""
    match = GREENHOUSE_RE.search(url)
    if match:
        return match.group(1), match.group(2)
    job_id = ""
    jid = GH_JID_RE.search(url)
    if jid:
        job_id = jid.group(1)
    board = ""
    board_match = re.search(
        r"https?://(?:job-)?boards\.greenhouse\.io/([^/?#]+)", url, re.I
    )
    if board_match:
        board = board_match.group(1)
    return board, job_id


def get_url(url: str) -> tuple[str, str]:
    """GET a listing page. Returns (final_url, body text)."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return url or "", ""
    response = requests.get(
        url,
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
        allow_redirects=True,
    )
    response.raise_for_status()
    text = response.text[:MAX_BODY]
    return str(response.url or url), text


def discover_apply_target(
    url: str,
    extra_text: str = "",
    *,
    getter: GetUrl | None = None,
    fetch: bool = True,
) -> ApplyTarget:
    board, job_id = parse_greenhouse(url)
    email = extract_apply_email(url, extra_text)
    target = ApplyTarget(
        email=email,
        greenhouse_board=board,
        greenhouse_job_id=job_id,
        url=url,
    )
    if (target.email or target.greenhouse) or not fetch or not url:
        return target
    fetch_page = getter or get_url
    try:
        final_url, body = fetch_page(url)
    except Exception:
        return target
    parsed_board, parsed_id = parse_greenhouse(final_url)
    if parsed_board:
        board, job_id = parsed_board, parsed_id
    if not board:
        parsed_board, parsed_id = parse_greenhouse(body)
        if parsed_board:
            board, job_id = parsed_board, parsed_id
    email = email or extract_apply_email(final_url, body)
    return ApplyTarget(
        email=email,
        greenhouse_board=board,
        greenhouse_job_id=job_id,
        url=final_url or url,
    )


def greenhouse_ready() -> bool:
    return bool(GREENHOUSE_JOB_BOARD_KEY)


def email_backend() -> str:
    """Pick resend, sendgrid, mailgun, or smtp from API keys / env."""
    requested = APPLY_EMAIL_BACKEND
    if requested == "resend":
        return "resend" if RESEND_API_KEY else ""
    if requested == "sendgrid":
        return "sendgrid" if SENDGRID_API_KEY else ""
    if requested == "mailgun":
        return "mailgun" if (MAILGUN_API_KEY and MAILGUN_DOMAIN) else ""
    if requested == "smtp":
        from jobfinder.config import APPLY_SMTP_HOST

        return "smtp" if APPLY_SMTP_HOST else ""
    if RESEND_API_KEY:
        return "resend"
    if SENDGRID_API_KEY:
        return "sendgrid"
    if MAILGUN_API_KEY and MAILGUN_DOMAIN:
        return "mailgun"
    from jobfinder.config import APPLY_SMTP_HOST

    if APPLY_SMTP_HOST:
        return "smtp"
    return ""


def email_api_ready() -> bool:
    return email_backend() in {"resend", "sendgrid", "mailgun"}


def key_status() -> dict[str, str]:
    """Which apply credentials are present (no secret values)."""
    from jobfinder.config import (
        APPLY_API_KEY,
        APPLY_FROM,
        APPLY_SMTP_HOST,
        GREENHOUSE_JOB_BOARD_KEY,
        MAILGUN_API_KEY,
        MAILGUN_DOMAIN,
        RESEND_API_KEY,
        SENDGRID_API_KEY,
    )

    def flag(ok: bool) -> str:
        return "set" if ok else "missing"

    return {
        "email_backend": email_backend() or "none",
        "APPLY_FROM": flag(bool(APPLY_FROM)),
        "APPLY_API_KEY": flag(bool(APPLY_API_KEY)),
        "RESEND_API_KEY": flag(bool(RESEND_API_KEY)),
        "SENDGRID_API_KEY": flag(bool(SENDGRID_API_KEY)),
        "MAILGUN_API_KEY": flag(bool(MAILGUN_API_KEY)),
        "MAILGUN_DOMAIN": flag(bool(MAILGUN_DOMAIN)),
        "APPLY_SMTP_HOST": flag(bool(APPLY_SMTP_HOST)),
        "GREENHOUSE_JOB_BOARD_KEY": flag(bool(GREENHOUSE_JOB_BOARD_KEY)),
    }


def send_application_email(
    *,
    to: str,
    from_addr: str,
    subject: str,
    body: str,
    resume_pdf: Path | None = None,
    poster: PostJson | None = None,
) -> SubmitResult:
    if not from_addr:
        raise SubmitError("Set APPLY_FROM or put an email on your resume.")
    backend = email_backend()
    if backend == "resend":
        _send_resend(to, from_addr, subject, body, resume_pdf, poster)
    elif backend == "sendgrid":
        _send_sendgrid(to, from_addr, subject, body, resume_pdf, poster)
    elif backend == "mailgun":
        _send_mailgun(to, from_addr, subject, body, resume_pdf, poster)
    else:
        raise SubmitError(
            "No email API key found. Set RESEND_API_KEY, SENDGRID_API_KEY, "
            "MAILGUN_API_KEY+MAILGUN_DOMAIN, or APPLY_API_KEY (re_... / SG....)."
        )
    return SubmitResult(
        submitted=True,
        method=backend,
        message=f"Sent cover letter and resume to {to} via {backend} API.",
        email=to,
    )


def _resume_b64(resume_pdf: Path | None) -> tuple[str, str]:
    if not resume_pdf or not resume_pdf.is_file():
        return "", ""
    return base64.b64encode(resume_pdf.read_bytes()).decode("ascii"), "resume.pdf"


def _send_resend(to, from_addr, subject, body, resume_pdf, poster) -> None:
    if not RESEND_API_KEY:
        raise SubmitError("RESEND_API_KEY is not set.")
    payload: dict[str, Any] = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    encoded, filename = _resume_b64(resume_pdf)
    if encoded:
        payload["attachments"] = [{"filename": filename, "content": encoded}]
    send = poster or requests.post
    response = send(
        "https://api.resend.com/emails",
        json=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        timeout=TIMEOUT,
    )
    if getattr(response, "status_code", 0) >= 400:
        raise SubmitError(f"Resend returned HTTP {response.status_code}: {response.text[:300]}")


def _send_sendgrid(to, from_addr, subject, body, resume_pdf, poster) -> None:
    if not SENDGRID_API_KEY:
        raise SubmitError("SENDGRID_API_KEY is not set.")
    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    encoded, filename = _resume_b64(resume_pdf)
    if encoded:
        payload["attachments"] = [
            {
                "content": encoded,
                "filename": filename,
                "type": "application/pdf",
                "disposition": "attachment",
            }
        ]
    send = poster or requests.post
    response = send(
        "https://api.sendgrid.com/v3/mail/send",
        json=payload,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        timeout=TIMEOUT,
    )
    if getattr(response, "status_code", 0) >= 400:
        raise SubmitError(
            f"SendGrid returned HTTP {response.status_code}: {getattr(response, 'text', '')[:300]}"
        )


def _send_mailgun(to, from_addr, subject, body, resume_pdf, poster) -> None:
    if not (MAILGUN_API_KEY and MAILGUN_DOMAIN):
        raise SubmitError("MAILGUN_API_KEY and MAILGUN_DOMAIN are required.")
    url = f"{MAILGUN_API_BASE}/v3/{MAILGUN_DOMAIN}/messages"
    data = {"from": from_addr, "to": to, "subject": subject, "text": body}
    files = None
    if resume_pdf and resume_pdf.is_file():
        files = {"attachment": ("resume.pdf", resume_pdf.read_bytes(), "application/pdf")}
    send = poster or requests.post
    try:
        response = send(
            url,
            data=data,
            files=files,
            auth=("api", MAILGUN_API_KEY),
            timeout=TIMEOUT,
        )
    except TypeError:
        response = send(url, json={"data": data}, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if getattr(response, "status_code", 0) >= 400:
        raise SubmitError(
            f"Mailgun returned HTTP {response.status_code}: {getattr(response, 'text', '')[:300]}"
        )


def greenhouse_payload(profile: Profile, letter: str) -> dict[str, Any]:
    first, last = split_name(profile.name)
    email = profile.email
    if not email:
        raise SubmitError("Greenhouse submit needs an email on your resume or APPLY_FROM.")
    payload: dict[str, Any] = {
        "first_name": first[:255],
        "last_name": last[:255],
        "email": email[:255],
        "resume_text": (profile.resume_text or letter)[:20000],
        "cover_letter_text": letter[:15000],
        "data_compliance": {
            "gdpr_consent_given": True,
            "gdpr_processing_consent_given": True,
        },
    }
    if profile.phone or APPLY_PHONE:
        payload["phone"] = (profile.phone or APPLY_PHONE)[:40]
    if profile.location:
        payload["location"] = profile.location[:255]
    return payload


def submit_greenhouse(
    board: str,
    job_id: str,
    profile: Profile,
    letter: str,
    *,
    resume_pdf: Path | None = None,
    api_key: str | None = None,
    poster: PostJson | None = None,
) -> SubmitResult:
    key = api_key if api_key is not None else GREENHOUSE_JOB_BOARD_KEY
    if not key:
        return SubmitResult(
            submitted=False,
            method="greenhouse",
            message=(
                "This is a Greenhouse listing. HTTP submit needs that company's "
                "Job Board API key (GREENHOUSE_JOB_BOARD_KEY). Without it, Job-finder "
                "can still email the application if a hiring address is found."
            ),
            url=f"https://boards.greenhouse.io/{board}/jobs/{job_id}",
        )
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    token = base64.b64encode(f"{key}:".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = attach_resume_files(greenhouse_payload(profile, letter), resume_pdf)
    send = poster or requests.post
    response = send(url, json=payload, headers=headers, timeout=TIMEOUT)
    if response.status_code >= 400:
        detail = (response.text or "")[:300]
        raise SubmitError(
            f"Greenhouse returned HTTP {response.status_code} for {board} job {job_id}. {detail}"
        )
    return SubmitResult(
        submitted=True,
        method="greenhouse",
        message=f"Submitted resume and cover letter to Greenhouse board {board} job {job_id}.",
        url=f"https://boards.greenhouse.io/{board}/jobs/{job_id}",
    )


def attach_resume_files(payload: dict[str, Any], resume_pdf: Path | None) -> dict[str, Any]:
    if resume_pdf and resume_pdf.is_file():
        payload["resume_content"] = base64.b64encode(resume_pdf.read_bytes()).decode("ascii")
        payload["resume_content_filename"] = "resume.pdf"
    return payload
