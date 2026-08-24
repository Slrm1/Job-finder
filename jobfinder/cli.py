"""Command-line interface for Job-finder."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from rich.console import Console
from rich.table import Table

from jobfinder.config import AFFINE_S6_MODEL_ID, AFFINE_S6_URL, HUMANIZER_MODEL_ID, HUMANIZER_URL
from jobfinder.jobs import SOURCES, search_jobs
from jobfinder.match import rank_jobs, rank_jobs_with_affine
from jobfinder.resume import resolve_profile

console = Console()


def _load_profile(args: argparse.Namespace):
    return resolve_profile(
        profile_path=getattr(args, "profile", None),
        resume_path=getattr(args, "resume", None),
    )


def _describe_profile(profile) -> None:
    origin = "resume" if profile.resume_text else "profile"
    name = profile.name or "candidate"
    skills = ", ".join(profile.skills[:8]) or "no skills parsed"
    console.print(
        f"[dim]Ranking {name} from {origin} · {len(profile.skills)} skills · {skills}[/dim]"
    )


def _print_jobs(ranked, *, show_summary: bool = True) -> None:
    table = Table(title="Job matches")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Location")
    table.add_column("Source")
    table.add_column("URL", overflow="fold")
    for index, item in enumerate(ranked, start=1):
        table.add_row(
            str(index),
            f"{item.score:.0f}",
            item.job.title,
            item.job.company,
            item.job.location,
            item.job.source,
            item.job.url,
        )
    console.print(table)
    if show_summary:
        for index, item in enumerate(ranked, start=1):
            if not item.summary and not item.reasons:
                continue
            console.print(f"\n[bold]{index}. {item.job.title}[/bold] — {item.job.company}")
            if item.summary:
                console.print(item.summary)
            if item.reasons:
                console.print("  " + "; ".join(item.reasons))


def _add_candidate_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", help="Path to profile.yaml")
    parser.add_argument(
        "--resume",
        help="Path to your resume (.pdf, .txt, .md, .docx). "
        "Also auto-detects resume.pdf in this folder.",
    )


def cmd_search(args: argparse.Namespace) -> int:
    jobs = search_jobs(
        args.query,
        sources=args.sources.split(",") if args.sources else None,
        limit=args.limit,
    )
    profile = _load_profile(args)
    _describe_profile(profile)
    if args.affine:
        ranked = rank_jobs_with_affine(
            jobs, profile, limit=min(args.limit, 8), query=args.query
        )
    else:
        ranked = rank_jobs(jobs, profile, query=args.query)
    if getattr(args, "humanize", False):
        from jobfinder.humanizer import humanize_ranked

        ranked = humanize_ranked(ranked)
    if getattr(args, "save", None):
        from jobfinder.tracker import save_ranked

        stored = save_ranked(ranked, limit=args.save)
        console.print(f"[green]Saved {len(stored)} jobs to the tracker.[/green]")
    if getattr(args, "apply", None):
        from jobfinder.apply import apply_ranked

        applications = apply_ranked(
            ranked,
            profile,
            limit=args.apply,
            send=not getattr(args, "draft_only", False),
            mark_applied=getattr(args, "mark_applied", False),
            affine=args.affine,
        )
        sent = sum(1 for item in applications if item.submitted)
        console.print(
            f"[green]Drafted {len(applications)} cover letters"
            + (f", submitted {sent}." if sent else ".")
            + "[/green]"
        )
        for item in applications:
            console.print(f"  #{item.tracked.id} {item.tracked.title} — {item.message}")
            console.print()
            console.print(item.cover_letter)
    _print_jobs(ranked, show_summary=bool(args.affine or args.verbose or getattr(args, "humanize", False)))
    console.print(f"\n{len(ranked)} jobs from public boards. Model: {AFFINE_S6_MODEL_ID}")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    args.affine = True
    return cmd_search(args)


def cmd_track(args: argparse.Namespace) -> int:
    from jobfinder.tracker import (
        STATUSES,
        counts,
        list_tracked,
        remove_tracked,
        set_notes,
        set_status,
    )

    action = args.track_action
    if action == "list":
        rows = list_tracked(status=args.status)
        if not rows:
            console.print("No saved applications yet. Search with --save 5 to start.")
            return 0
        table = Table(title="Application tracker")
        table.add_column("ID", justify="right")
        table.add_column("Status")
        table.add_column("Score", justify="right")
        table.add_column("Title")
        table.add_column("Company")
        table.add_column("URL", overflow="fold")
        for row in rows:
            table.add_row(
                str(row.id),
                row.status,
                "" if row.score is None else f"{row.score:.0f}",
                row.title,
                row.company,
                row.url,
            )
        console.print(table)
        tally = counts()
        console.print(
            "  ".join(f"{name}={tally[name]}" for name in STATUSES if tally[name])
        )
        return 0
    if action == "status":
        row = set_status(args.id, args.status)
        console.print(f"#{row.id} {row.title} → {row.status}")
        return 0
    if action == "note":
        row = set_notes(args.id, args.note)
        console.print(f"#{row.id} note updated")
        return 0
    if action == "remove":
        remove_tracked(args.id)
        console.print(f"Removed #{args.id}")
        return 0
    return 1


def cmd_profile(args: argparse.Namespace) -> int:
    profile = _load_profile(args)
    _describe_profile(profile)
    console.print(f"Headline: {profile.headline or '—'}")
    console.print(f"Location: {profile.location or '—'}")
    console.print(f"Email:    {profile.email or '—'}")
    console.print(f"Phone:    {profile.phone or '—'}")
    console.print(f"Level:    {profile.experience_level or '—'}")
    console.print("Skills:   " + (", ".join(profile.skills) or "—"))
    console.print("Keywords: " + (", ".join(profile.keywords) or "—"))
    if profile.resume_text:
        console.print(f"Resume:   {len(profile.resume_text)} characters loaded")
    else:
        console.print(
            "[yellow]No resume loaded. Pass --resume PATH or drop resume.pdf here.[/yellow]"
        )
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from jobfinder.affine import generate

    reply = generate(args.prompt)
    if args.thinking and reply.thinking:
        console.print("[dim]thinking[/dim]")
        console.print(reply.thinking)
        console.print()
    text = reply.content
    if getattr(args, "humanize", False):
        from jobfinder.humanizer import humanize_text

        text = humanize_text(text).text()
        console.print(f"[dim]humanized with {HUMANIZER_MODEL_ID}[/dim]")
    console.print(text)
    return 0


def cmd_humanize(args: argparse.Namespace) -> int:
    from jobfinder.humanizer import humanize_text

    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    if not (text or "").strip():
        console.print("[red]Pass text or --file[/red]")
        return 1
    result = humanize_text(text, backend=args.backend)
    if args.original:
        console.print("[dim]original[/dim]")
        console.print(result.original)
        console.print()
    console.print(f"[dim]{result.backend} · {result.model}[/dim]")
    console.print(result.text())
    return 0


def cmd_pitch(args: argparse.Namespace) -> int:
    from jobfinder.humanizer import draft_pitch, humanize_text

    jobs = search_jobs(
        args.query,
        sources=args.sources.split(",") if args.sources else None,
        limit=max(args.limit, 5),
    )
    profile = _load_profile(args)
    ranked = rank_jobs(jobs, profile, query=args.query)
    if not ranked:
        console.print("[red]No jobs found to pitch.[/red]")
        return 1
    top = ranked[0]
    draft = draft_pitch(top.job.title, top.job.company, profile)
    result = humanize_text(draft)
    console.print(f"[bold]{top.job.title}[/bold] — {top.job.company} ({top.score:.0f})")
    if top.job.url:
        console.print(top.job.url)
    console.print()
    console.print(f"[dim]{result.backend} · {HUMANIZER_MODEL_ID}[/dim]")
    console.print(result.text())
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    from jobfinder.apply import apply_to_tracked
    from jobfinder.tracker import list_tracked

    profile = _load_profile(args)
    if not profile.resume_text and not profile.name:
        console.print("[yellow]No resume loaded. Pass --resume PATH for a stronger letter.[/yellow]")
    if args.id is not None:
        ids = [args.id]
    elif args.saved:
        ids = [row.id for row in list_tracked(status="saved")]
    else:
        console.print("[red]Pass a tracker id, or --saved to apply to every saved job.[/red]")
        return 1
    if not ids:
        console.print("No saved jobs to apply to. Search with --apply 3 first.")
        return 1
    failures = 0
    for entry_id in ids:
        try:
            result = apply_to_tracked(
                entry_id,
                profile,
                send=not args.draft_only,
                mark_applied=args.mark_applied,
                affine=args.affine,
            )
        except Exception as exc:
            console.print(f"[red]#{entry_id}: {exc}[/red]")
            failures += 1
            continue
        status = "sent" if result.submitted else result.method
        console.print(
            f"[bold]#{result.tracked.id} {result.tracked.title}[/bold] — "
            f"{result.tracked.company} [{status}]"
        )
        console.print(result.message)
        console.print()
        console.print(result.cover_letter)
    return 1 if failures else 0


def cmd_dashboard(_: argparse.Namespace) -> int:
    from jobfinder.tracker import STATUSES, dashboard_stats

    stats = dashboard_stats()
    table = Table(title="Application dashboard")
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for name in STATUSES:
        table.add_row(name, str(stats["counts"][name]))
    console.print(table)
    console.print(
        f"total={stats['total']}  moved={stats['applied']}  "
        f"interviews={stats['interviews']}  offers={stats['offers']}"
    )
    console.print(
        f"apply {stats['apply_rate']}% · interview {stats['interview_rate']}% · "
        f"offer {stats['offer_rate']}%"
    )
    if stats["recent"]:
        console.print("\n[bold]Recent[/bold]")
        for row in stats["recent"]:
            console.print(f"  #{row.id} {row.title} — {row.company} [{row.status}]")
    else:
        console.print("[dim]Save jobs from search --save or the web tracker.[/dim]")
    return 0


def cmd_resume_pdf(args: argparse.Namespace) -> int:
    from jobfinder.pdf import render_resume_pdf

    profile = _load_profile(args)
    dest = Path(args.output)
    path = render_resume_pdf(profile, dest, template=args.template)
    console.print(f"Wrote {path} ({args.template})")
    if not profile.resume_text and not profile.name:
        console.print("[yellow]No resume loaded; PDF is a sparse template.[/yellow]")
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from jobfinder.mcp_server import serve_stdio

    return serve_stdio()


def cmd_serve(args: argparse.Namespace) -> int:
    from jobfinder.web import create_app

    app = create_app(profile_path=args.profile, resume_path=args.resume)
    console.print(f"Affine-S6 model: {AFFINE_S6_URL}")
    console.print(f"Humanizer:       {HUMANIZER_URL}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_model(_: argparse.Namespace) -> int:
    from jobfinder.affine import available_backend as affine_backend
    from jobfinder.humanizer import available_backend as humanizer_backend

    console.print(f"Ranker:     {AFFINE_S6_MODEL_ID}")
    console.print(f"            {AFFINE_S6_URL}")
    console.print(f"            backend {affine_backend()}")
    console.print(f"Humanizer:  {HUMANIZER_MODEL_ID}")
    console.print(f"            {HUMANIZER_URL}")
    console.print(f"            backend {humanizer_backend()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobfinder",
        description="Search public job boards and rank listings with Affine-S6.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search and rank jobs")
    search.add_argument("query", help="Role or keywords, e.g. 'python backend'")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument(
        "--sources",
        help="Comma-separated sources: " + ",".join(SOURCES),
    )
    _add_candidate_flags(search)
    search.add_argument(
        "--affine",
        action="store_true",
        help="Re-rank the shortlist with Affine-S6 (needs local weights or HF_TOKEN)",
    )
    search.add_argument("--verbose", action="store_true")
    search.add_argument(
        "--humanize",
        action="store_true",
        help="Rewrite fit notes with Ai-Humanizer-Llama-3.2-3B-GGUF",
    )
    search.add_argument(
        "--save",
        type=int,
        metavar="N",
        help="Save the top N matches to the local application tracker",
    )
    search.add_argument(
        "--apply",
        type=int,
        metavar="N",
        help="Write cover letters and submit the top N matches over the internet",
    )
    search.add_argument(
        "--send",
        action="store_true",
        help="(default with --apply) Submit over email or Greenhouse",
    )
    search.add_argument(
        "--draft-only",
        action="store_true",
        help="Write cover letters without sending them",
    )
    search.add_argument(
        "--mark-applied",
        action="store_true",
        help="Mark packaged applications as applied even if email was not sent",
    )
    search.set_defaults(func=cmd_search)

    rank = sub.add_parser("rank", help="Search, then re-rank with Affine-S6")
    rank.add_argument("query")
    rank.add_argument("--limit", type=int, default=10)
    rank.add_argument("--sources")
    _add_candidate_flags(rank)
    rank.add_argument("--verbose", action="store_true")
    rank.add_argument("--humanize", action="store_true")
    rank.add_argument("--save", type=int, metavar="N")
    rank.add_argument("--apply", type=int, metavar="N")
    rank.add_argument("--send", action="store_true")
    rank.add_argument("--draft-only", action="store_true")
    rank.add_argument("--mark-applied", action="store_true")
    rank.set_defaults(func=cmd_rank)

    preview = sub.add_parser("profile", help="Show the profile parsed from your resume")
    _add_candidate_flags(preview)
    preview.set_defaults(func=cmd_profile)

    chat = sub.add_parser("chat", help="Ask Affine-S6 a question")
    chat.add_argument("prompt")
    chat.add_argument("--thinking", action="store_true", help="Show hidden reasoning")
    chat.add_argument("--humanize", action="store_true")
    chat.set_defaults(func=cmd_chat)

    humanize = sub.add_parser(
        "humanize",
        help="Rewrite text with Ai-Humanizer-Llama-3.2-3B-GGUF",
    )
    humanize.add_argument("text", nargs="?", default="", help="Text to rewrite")
    humanize.add_argument("--file", help="Read text from a file")
    humanize.add_argument("--original", action="store_true", help="Also print the input")
    humanize.add_argument(
        "--backend",
        choices=["auto", "gguf", "heuristic", "huggingface", "openai"],
        default=None,
    )
    humanize.set_defaults(func=cmd_humanize)

    pitch = sub.add_parser("pitch", help="Draft a humanized note for the best match")
    pitch.add_argument("query")
    pitch.add_argument("--limit", type=int, default=10)
    pitch.add_argument("--sources")
    _add_candidate_flags(pitch)
    pitch.set_defaults(func=cmd_pitch)

    apply_cmd = sub.add_parser(
        "apply",
        help="Write a cover letter and submit or package the application",
    )
    apply_cmd.add_argument("id", nargs="?", type=int, help="Tracker id from jobfinder track list")
    apply_cmd.add_argument(
        "--saved",
        action="store_true",
        help="Apply to every job still in saved status",
    )
    apply_cmd.add_argument(
        "--send",
        action="store_true",
        help="(default) Submit over the internet via email or Greenhouse",
    )
    apply_cmd.add_argument(
        "--draft-only",
        action="store_true",
        help="Write the cover letter and package without sending",
    )
    apply_cmd.add_argument(
        "--mark-applied",
        action="store_true",
        help="Set status to applied after writing the package",
    )
    apply_cmd.add_argument(
        "--affine",
        action="store_true",
        help="Draft the letter with Affine-S6 when a backend is configured",
    )
    _add_candidate_flags(apply_cmd)
    apply_cmd.set_defaults(func=cmd_apply)

    track = sub.add_parser("track", help="Local application tracker (JobSync-style)")
    from jobfinder.tracker import STATUSES as TRACK_STATUSES

    track_sub = track.add_subparsers(dest="track_action", required=True)
    listed = track_sub.add_parser("list", help="Show saved applications")
    listed.add_argument("--status", choices=TRACK_STATUSES)
    listed.set_defaults(func=cmd_track)
    status = track_sub.add_parser("status", help="Update a saved job's status")
    status.add_argument("id", type=int)
    status.add_argument("status", choices=TRACK_STATUSES)
    status.set_defaults(func=cmd_track)
    note = track_sub.add_parser("note", help="Add a note to a saved job")
    note.add_argument("id", type=int)
    note.add_argument("note")
    note.set_defaults(func=cmd_track)
    remove = track_sub.add_parser("remove", help="Delete a saved job")
    remove.add_argument("id", type=int)
    remove.set_defaults(func=cmd_track)

    dashboard = sub.add_parser("dashboard", help="Show application pipeline stats")
    dashboard.set_defaults(func=cmd_dashboard)

    resume_pdf = sub.add_parser("resume-pdf", help="Export a resume PDF from your profile")
    _add_candidate_flags(resume_pdf)
    resume_pdf.add_argument(
        "-o",
        "--output",
        default="resume-export.pdf",
        help="Output path (default: resume-export.pdf)",
    )
    resume_pdf.add_argument(
        "--template",
        choices=["simple", "professional"],
        default="simple",
    )
    resume_pdf.set_defaults(func=cmd_resume_pdf)

    mcp = sub.add_parser("mcp", help="Run the local MCP server on stdin/stdout")
    mcp.set_defaults(func=cmd_mcp)

    serve = sub.add_parser("serve", help="Run the web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=5000)
    _add_candidate_flags(serve)
    serve.add_argument("--debug", action="store_true")
    serve.set_defaults(func=cmd_serve)

    model = sub.add_parser("model", help="Show the configured Affine-S6 model")
    model.set_defaults(func=cmd_model)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
