"""OCR scanned resumes through a Paperless-ngx instance you log into.

Paperless-ngx is not vendored. Job-finder calls its REST API:
https://github.com/paperless-ngx/paperless-ngx
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable

import requests

from jobfinder.config import (
    PAPERLESS_PASSWORD,
    PAPERLESS_TOKEN,
    PAPERLESS_URL,
    PAPERLESS_USER,
    USER_AGENT,
)

GetFn = Callable[..., requests.Response]
PostFn = Callable[..., requests.Response]


class OCRError(RuntimeError):
    pass


def paperless_ready() -> bool:
    return bool(
        PAPERLESS_URL
        and (PAPERLESS_TOKEN or (PAPERLESS_USER and PAPERLESS_PASSWORD))
    )


def ocr_resume(path: str | Path, *, data: bytes | None = None) -> str:
    """Return OCR text. Prefers Paperless-ngx login; ocrmypdf is a local fallback."""
    file_path = Path(path)
    payload = data if data is not None else file_path.read_bytes()
    name = file_path.name or "resume.pdf"
    if paperless_ready():
        return ocr_via_paperless(payload, name)
    local = ocr_via_ocrmypdf(payload, name)
    if local.strip():
        return local
    raise OCRError(
        "Not enough text on that resume. Run Paperless-ngx (docker compose up) "
        "and set PAPERLESS_URL, PAPERLESS_USER, and PAPERLESS_PASSWORD in .env."
    )


def ocr_via_paperless(
    data: bytes,
    filename: str,
    *,
    poster: PostFn | None = None,
    getter: GetFn | None = None,
    sleeper: Callable[[float], None] | None = None,
    timeout: int = 60,
) -> str:
    if not PAPERLESS_URL:
        raise OCRError("PAPERLESS_URL is not set.")
    token = _token(poster)
    headers = {
        "Authorization": f"Token {token}",
        "User-Agent": USER_AGENT,
    }
    post = poster or requests.post
    get = getter or requests.get
    wait = sleeper or time.sleep
    upload = post(
        f"{PAPERLESS_URL}/api/documents/post_document/",
        headers=headers,
        files={"document": (filename, data, "application/octet-stream")},
        data={"title": filename},
        timeout=30,
    )
    if upload.status_code >= 400:
        raise OCRError(f"Paperless upload failed ({upload.status_code}): {upload.text[:300]}")
    task_id = _task_id(upload)
    deadline = time.time() + timeout
    doc_id = ""
    while time.time() < deadline:
        task = get(
            f"{PAPERLESS_URL}/api/tasks/",
            headers=headers,
            params={"task_id": task_id} if task_id else None,
            timeout=20,
        )
        doc_id = _related_document(task, filename)
        if doc_id:
            break
        wait(1)
    if not doc_id:
        raise OCRError("Paperless OCR timed out waiting for the consume task.")
    document = get(
        f"{PAPERLESS_URL}/api/documents/{doc_id}/",
        headers=headers,
        timeout=20,
    )
    if document.status_code >= 400:
        raise OCRError(f"Paperless document fetch failed ({document.status_code}).")
    payload = document.json() if hasattr(document, "json") else {}
    text = str(payload.get("content") or "").strip()
    if len(text) < 40:
        raise OCRError("Paperless returned too little OCR text.")
    return text


def ocr_via_ocrmypdf(data: bytes, filename: str) -> str:
    """Same Tesseract/OCRmyPDF stack Paperless uses, without the Django app."""
    if not shutil.which("ocrmypdf"):
        return ""
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / f"in{suffix}"
        dest = Path(folder) / "out.pdf"
        sidecar = Path(folder) / "out.txt"
        src.write_bytes(data)
        result = subprocess.run(
            ["ocrmypdf", "--sidecar", str(sidecar), str(src), str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            return ""
        if sidecar.is_file():
            return sidecar.read_text(encoding="utf-8", errors="ignore")
    return ""


def _token(poster: PostFn | None = None) -> str:
    if PAPERLESS_TOKEN:
        return PAPERLESS_TOKEN
    if not (PAPERLESS_USER and PAPERLESS_PASSWORD):
        raise OCRError("Set PAPERLESS_USER and PAPERLESS_PASSWORD (or PAPERLESS_TOKEN).")
    post = poster or requests.post
    response = post(
        f"{PAPERLESS_URL}/api/token/",
        json={"username": PAPERLESS_USER, "password": PAPERLESS_PASSWORD},
        timeout=20,
    )
    if response.status_code >= 400:
        raise OCRError("Paperless login failed. Check PAPERLESS_USER / PAPERLESS_PASSWORD.")
    payload = response.json() if hasattr(response, "json") else {}
    token = str(payload.get("token") or "")
    if not token:
        raise OCRError("Paperless /api/token/ did not return a token.")
    return token


def _task_id(response: Any) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = getattr(response, "text", "")
    if isinstance(payload, str):
        return payload.strip().strip('"')
    if isinstance(payload, dict):
        return str(payload.get("task_id") or payload.get("id") or "")
    return str(payload or "")


def _related_document(response: Any, filename: str) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = list(payload.get("results") or payload.get("tasks") or [])
        if payload.get("related_document"):
            return str(payload["related_document"])
        if payload.get("id") and payload.get("content"):
            return str(payload["id"])
    else:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or row.get("state") or "").lower()
        related = row.get("related_document") or row.get("document_id") or ""
        if related and status in {"", "success", "complete", "completed", "done"}:
            return str(related)
        title = str(row.get("title") or row.get("task_file_name") or "")
        if related and filename.split(".")[0].lower() in title.lower():
            return str(related)
    return ""
