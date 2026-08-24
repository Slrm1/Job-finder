"""Small Flask UI for searching jobs and ranking them with Affine-S6."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from jobfinder.config import (
    AFFINE_S6_MODEL_ID,
    AFFINE_S6_URL,
    HUMANIZER_MODEL_ID,
    HUMANIZER_URL,
)
from jobfinder.jobs import DEFAULT_SOURCES, SOURCES, Job, extract_apply_email, search_jobs
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


def _job_from_form() -> Job:
    description = request.form.get("description") or ""
    url = request.form.get("url") or ""
    return Job(
        id=request.form.get("job_id") or "web",
        title=request.form.get("title") or "Untitled",
        company=request.form.get("company") or "Unknown",
        location=request.form.get("location") or "",
        url=url,
        description=description,
        source=request.form.get("source") or "web",
        apply_email=extract_apply_email(description, url),
    )


def create_app(
    profile_path: str | None = None, resume_path: str | None = None
) -> Flask:
    app = Flask(__name__)
    app.config["PROFILE_PATH"] = profile_path
    app.config["RESUME_PATH"] = resume_path
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    def _smtp_ready() -> bool:
        from jobfinder.apply import smtp_ready

        return smtp_ready()

    def _template(**extra):
        profile = extra.get("profile") or _base_profile(profile_path, resume_path)
        payload = dict(
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            humanizer_id=HUMANIZER_MODEL_ID,
            humanizer_url=HUMANIZER_URL,
            sources=list(SOURCES),
            default_sources=list(DEFAULT_SOURCES),
            profile=profile,
            results=None,
            query="",
            error=None,
            used_affine=False,
            used_humanize=False,
            humanize_input="",
            humanize_output="",
            humanize_backend="",
            smtp_ready=_smtp_ready(),
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
        use_humanize = request.form.get("humanize") == "on"
        selected = request.form.getlist("sources") or list(DEFAULT_SOURCES)
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
                used_humanize=use_humanize,
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
                if use_humanize:
                    from jobfinder.humanizer import humanize_ranked

                    ranked = humanize_ranked(ranked)
            except Exception as exc:
                error = str(exc)
        return _template(
            profile=profile,
            results=ranked,
            query=query,
            error=error,
            used_affine=use_affine,
            used_humanize=use_humanize,
            selected_sources=selected,
        )

    @app.post("/track")
    def track_save():
        from jobfinder.tracker import TrackerError, save_job

        job = _job_from_form()
        try:
            score = float(request.form["score"]) if request.form.get("score") else None
        except ValueError:
            score = None
        try:
            save_job(
                job,
                status=request.form.get("status") or "saved",
                score=score,
                notes=request.form.get("notes") or "",
            )
        except TrackerError as exc:
            return _template(error=str(exc), results=[])
        return redirect(url_for("tracker"))

    @app.post("/apply")
    def apply_from_search():
        from jobfinder.apply import apply_to_job

        job = _job_from_form()
        try:
            score = float(request.form["score"]) if request.form.get("score") else None
        except ValueError:
            score = None
        try:
            profile = _profile_from_request(profile_path, resume_path)
            apply_to_job(
                job,
                profile,
                send=request.form.get("send") == "on",
                mark_applied=request.form.get("mark_applied") == "on",
                score=score,
            )
        except Exception as exc:
            return _template(error=str(exc), results=[])
        return redirect(url_for("tracker"))

    @app.get("/tracker")
    def tracker():
        from jobfinder.tracker import STATUSES, counts, list_tracked

        status = request.args.get("status") or None
        try:
            rows = list_tracked(status=status)
        except Exception as exc:
            return _template(error=str(exc), results=[])
        return render_template(
            "tracker.html",
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            humanizer_id=HUMANIZER_MODEL_ID,
            humanizer_url=HUMANIZER_URL,
            rows=rows,
            statuses=STATUSES,
            counts=counts(),
            filter_status=status,
            smtp_ready=_smtp_ready(),
        )

    @app.get("/dashboard")
    def dashboard():
        from jobfinder.tracker import dashboard_stats

        return render_template(
            "dashboard.html",
            model_id=AFFINE_S6_MODEL_ID,
            model_url=AFFINE_S6_URL,
            humanizer_id=HUMANIZER_MODEL_ID,
            humanizer_url=HUMANIZER_URL,
            stats=dashboard_stats(),
        )

    @app.get("/resume.pdf")
    def resume_pdf():
        from jobfinder.pdf import TEMPLATES, render_resume_pdf

        template = request.args.get("template") or "simple"
        if template not in TEMPLATES:
            return _template(error=f"Unknown template {template}", results=[]), 400
        profile = _base_profile(profile_path, resume_path)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "resume.pdf"
            render_resume_pdf(profile, path, template=template)
            data = path.read_bytes()
        return send_file(
            BytesIO(data),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="resume.pdf",
        )

    @app.get("/api/jobs")
    def api_jobs():
        from jobfinder.tracker import list_tracked

        status = request.args.get("status") or None
        rows = [row.to_dict() for row in list_tracked(status=status)]
        return jsonify(rows)

    @app.get("/api/dashboard")
    def api_dashboard():
        from jobfinder.tracker import dashboard_stats

        stats = dashboard_stats()
        payload = dict(stats)
        payload["recent"] = [row.to_dict() for row in stats["recent"]]
        return jsonify(payload)

    @app.post("/tracker/<int:entry_id>/apply")
    def tracker_apply(entry_id: int):
        from jobfinder.apply import apply_to_tracked

        try:
            profile = _base_profile(profile_path, resume_path)
            apply_to_tracked(
                entry_id,
                profile,
                send=request.form.get("send") == "on",
                mark_applied=request.form.get("mark_applied") == "on",
            )
        except Exception as exc:
            return _template(error=str(exc), results=[])
        return redirect(url_for("tracker"))

    @app.get("/tracker/<int:entry_id>/cover-letter.txt")
    def tracker_cover_letter(entry_id: int):
        from jobfinder.tracker import TrackerError, get_tracked

        try:
            row = get_tracked(entry_id)
        except TrackerError as exc:
            return _template(error=str(exc), results=[]), 404
        data = (row.cover_letter or "No cover letter drafted yet.\n").encode("utf-8")
        return send_file(
            BytesIO(data),
            mimetype="text/plain",
            as_attachment=True,
            download_name=f"cover-letter-{entry_id}.txt",
        )

    @app.post("/tracker/<int:entry_id>/status")
    def tracker_status(entry_id: int):
        from jobfinder.tracker import TrackerError, set_status

        try:
            set_status(entry_id, request.form.get("status") or "saved")
        except TrackerError as exc:
            return _template(error=str(exc), results=[])
        return redirect(url_for("tracker"))

    @app.post("/tracker/<int:entry_id>/remove")
    def tracker_remove(entry_id: int):
        from jobfinder.tracker import TrackerError, remove_tracked

        try:
            remove_tracked(entry_id)
        except TrackerError as exc:
            return _template(error=str(exc), results=[])
        return redirect(url_for("tracker"))

    @app.post("/humanize")
    def humanize():
        from jobfinder.humanizer import humanize_text

        text = (request.form.get("text") or "").strip()
        error = None
        output = ""
        backend = ""
        if text:
            try:
                result = humanize_text(text)
                output = result.text()
                backend = result.backend
            except Exception as exc:
                error = str(exc)
        return _template(
            humanize_input=text,
            humanize_output=output,
            humanize_backend=backend,
            error=error,
        )

    return app
