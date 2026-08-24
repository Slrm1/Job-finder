"""Small Flask UI for searching jobs and ranking them with Affine-S6."""

from __future__ import annotations

from flask import Flask, render_template, request

from jobfinder.config import AFFINE_S6_MODEL_ID, AFFINE_S6_URL
from jobfinder.jobs import SOURCES, search_jobs
from jobfinder.match import rank_jobs, rank_jobs_with_affine
from jobfinder.resume import ResumeError, read_resume_bytes, resolve_profile


def _base_profile(profile_path: str | None, resume_path: str | None):
    return resolve_profile(profile_path=profile_path, resume_path=resume_path)


def _profile_from_request(profile_path: str | None, resume_path: str | None):
    upload = request.files.get("resume")
    if upload and upload.filename:
        text = read_resume_bytes(upload.read(), upload.filename)
        return resolve_profile(
            profile_path=profile_path,
            resume_path=resume_path,
            resume_text=text,
        )
    return _base_profile(profile_path, resume_path)


def create_app(
    profile_path: str | None = None, resume_path: str | None = None
) -> Flask:
    app = Flask(__name__)
    app.config["PROFILE_PATH"] = profile_path
    app.config["RESUME_PATH"] = resume_path
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    def _template(**extra):
        profile = extra.get("profile") or _base_profile(profile_path, resume_path)
        payload = dict(
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            sources=list(SOURCES),
            profile=profile,
            results=None,
            query="",
            error=None,
            used_affine=False,
        )
        payload.update(extra)
        return render_template("index.html", **payload)

    @app.get("/")
    def index():
        return _template()

    @app.post("/search")
    def search():
        query = (request.form.get("query") or "").strip()
        use_affine = request.form.get("affine") == "on"
        selected = request.form.getlist("sources") or list(SOURCES)
        error = None
        ranked = []
        try:
            limit = max(1, min(int(request.form.get("limit") or 20), 50))
        except ValueError:
            limit = 20
        try:
            profile = _profile_from_request(profile_path, resume_path)
        except ResumeError as exc:
            return _template(
                error=str(exc),
                query=query,
                used_affine=use_affine,
                selected_sources=selected,
                results=[],
            )
        if query:
            try:
                jobs = search_jobs(query, sources=selected, limit=limit)
                if use_affine:
                    ranked = rank_jobs_with_affine(
                        jobs, profile, limit=min(limit, 8), query=query
                    )
                else:
                    ranked = rank_jobs(jobs, profile, query=query)
            except Exception as exc:
                error = str(exc)
        return _template(
            profile=profile,
            results=ranked,
            query=query,
            error=error,
            used_affine=use_affine,
            selected_sources=selected,
        )

    return app
