"""Small Flask UI for searching jobs and ranking them with Affine-S6."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template, request

from jobfinder.config import AFFINE_S6_MODEL_ID, AFFINE_S6_URL, DEFAULT_PROFILE_PATH
from jobfinder.jobs import SOURCES, search_jobs
from jobfinder.match import Profile, rank_jobs, rank_jobs_with_affine


def _profile(path: str | None) -> Profile:
    candidate = Path(path) if path else DEFAULT_PROFILE_PATH
    if candidate.exists():
        return Profile.from_yaml(candidate)
    example = candidate.with_name("profile.example.yaml")
    if example.exists():
        return Profile.from_yaml(example)
    return Profile()


def create_app(profile_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["PROFILE_PATH"] = profile_path

    @app.get("/")
    def index():
        profile = _profile(app.config.get("PROFILE_PATH"))
        return render_template(
            "index.html",
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            sources=list(SOURCES),
            profile=profile,
            results=None,
            query="",
            error=None,
            used_affine=False,
        )

    @app.post("/search")
    def search():
        profile = _profile(app.config.get("PROFILE_PATH"))
        query = (request.form.get("query") or "").strip()
        use_affine = request.form.get("affine") == "on"
        selected = request.form.getlist("sources") or list(SOURCES)
        error = None
        ranked = []
        try:
            limit = max(1, min(int(request.form.get("limit") or 20), 50))
        except ValueError:
            limit = 20
        if query:
            try:
                jobs = search_jobs(query, sources=selected, limit=limit)
                if use_affine:
                    ranked = rank_jobs_with_affine(jobs, profile, limit=min(limit, 8))
                else:
                    ranked = rank_jobs(jobs, profile)
            except Exception as exc:
                error = str(exc)
        return render_template(
            "index.html",
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            sources=list(SOURCES),
            profile=profile,
            results=ranked,
            query=query,
            error=error,
            used_affine=use_affine,
            selected_sources=selected,
        )

    return app
