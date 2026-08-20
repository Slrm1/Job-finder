"""Job Finder API + web UI, powered by Affine-S6."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.jobs import fetch_jobs, heuristic_rank, summarize_jobs
from backend.model import AffineS6Client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobfinder")

ROOT = Path(__file__).resolve().parent.parent
settings = get_settings()
model = AffineS6Client(settings)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


class ProfileRequest(BaseModel):
    profile: str = Field(..., min_length=20, max_length=12000)
    search: str = ""
    category: str = ""
    target_role: str = ""


class CoverLetterRequest(BaseModel):
    profile: str = Field(..., min_length=20, max_length=12000)
    job_id: int | None = None
    job_title: str = ""
    company: str = ""
    description: str = ""
    search: str = ""
    category: str = ""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    profile: str = ""


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.app_name,
            "model_id": settings.model_id,
            "model_ready": model.available,
        },
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_id": settings.model_id,
        "model_ready": model.available,
        "model_url": f"https://huggingface.co/{settings.model_id}",
    }


@app.get("/api/jobs")
async def list_jobs(search: str = "", category: str = "") -> dict[str, Any]:
    try:
        jobs = fetch_jobs(settings, search=search, category=category)
    except Exception as exc:  # noqa: BLE001
        logger.exception("job fetch failed")
        raise HTTPException(status_code=502, detail=f"Job source error: {exc}") from exc
    return {"count": len(jobs), "jobs": [j.to_dict() for j in jobs]}


@app.post("/api/match")
async def match(req: ProfileRequest) -> dict[str, Any]:
    try:
        jobs = fetch_jobs(settings, search=req.search or req.target_role, category=req.category)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Job source error: {exc}") from exc

    if model.available:
        try:
            advice = model.match_jobs(req.profile, summarize_jobs(jobs))
            return {
                "mode": "affine-s6",
                "model_id": settings.model_id,
                "jobs": [j.to_dict() for j in jobs[:20]],
                "advice": advice,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Affine-S6 match failed, falling back: %s", exc)

    ranked = heuristic_rank(req.profile, jobs)
    lines = [
        f"- **{r['title']}** @ {r['company']} — fit {r['score']}/100. {r['why']}"
        for r in ranked
    ]
    advice = (
        "Affine-S6 is offline (set `HF_TOKEN` to enable). "
        "Keyword-based ranking instead:\n\n"
        + "\n".join(lines)
        + "\n\nNext actions:\n"
        "- Tighten your profile with role-specific keywords\n"
        "- Open the top matches and tailor one application today\n"
        "- Add a measurable win to your resume summary"
    )
    return {
        "mode": "heuristic",
        "model_id": settings.model_id,
        "jobs": [j.to_dict() for j in jobs[:20]],
        "ranked": ranked,
        "advice": advice,
    }


@app.post("/api/cover-letter")
async def cover_letter(req: CoverLetterRequest) -> dict[str, Any]:
    job_blurb = (
        f"{req.job_title} @ {req.company}\n{req.description}".strip()
        or "General remote software / product role"
    )
    if req.job_id and not req.description:
        try:
            jobs = fetch_jobs(settings, search=req.search, category=req.category)
            match = next((j for j in jobs if j.id == req.job_id), None)
            if match:
                job_blurb = match.blurb()
        except Exception:  # noqa: BLE001
            logger.debug("optional job refresh failed", exc_info=True)

    if not model.available:
        raise HTTPException(
            status_code=503,
            detail="Affine-S6 requires HF_TOKEN. Add a Hugging Face token to .env.",
        )
    try:
        letter = model.cover_letter(req.profile, job_blurb)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"model_id": settings.model_id, "letter": letter}


@app.post("/api/resume-tips")
async def resume_tips(req: ProfileRequest) -> dict[str, Any]:
    if not model.available:
        raise HTTPException(
            status_code=503,
            detail="Affine-S6 requires HF_TOKEN. Add a Hugging Face token to .env.",
        )
    try:
        tips = model.resume_tips(req.profile, req.target_role)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"model_id": settings.model_id, "tips": tips}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    if not model.available:
        raise HTTPException(
            status_code=503,
            detail="Affine-S6 requires HF_TOKEN. Add a Hugging Face token to .env.",
        )
    context = ""
    if req.profile.strip():
        context = f"\n\nCandidate profile for context:\n{req.profile.strip()}"
    try:
        reply = model.chat(req.message + context)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"model_id": settings.model_id, "reply": reply}
