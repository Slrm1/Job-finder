"""Command-line interface for Job-finder."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from rich.console import Console
from rich.table import Table

from jobfinder.config import AFFINE_S6_MODEL_ID, AFFINE_S6_URL, DEFAULT_PROFILE_PATH
from jobfinder.jobs import SOURCES, search_jobs
from jobfinder.match import Profile, rank_jobs, rank_jobs_with_affine

console = Console()


def _load_profile(path: str | None) -> Profile:
    candidate = Path(path) if path else DEFAULT_PROFILE_PATH
    if not candidate.exists():
        example = candidate.with_name("profile.example.yaml")
        if path:
            raise FileNotFoundError(f"Profile not found: {candidate}")
        if example.exists():
            console.print(
                f"[yellow]No profile.yaml found; using {example.name}[/yellow]"
            )
            return Profile.from_yaml(example)
        return Profile()
    return Profile.from_yaml(candidate)


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


def cmd_search(args: argparse.Namespace) -> int:
    jobs = search_jobs(
        args.query,
        sources=args.sources.split(",") if args.sources else None,
        limit=args.limit,
    )
    profile = _load_profile(args.profile)
    if args.affine:
        ranked = rank_jobs_with_affine(jobs, profile, limit=min(args.limit, 8))
    else:
        ranked = rank_jobs(jobs, profile)
    _print_jobs(ranked, show_summary=bool(args.affine or args.verbose))
    console.print(f"\n{len(ranked)} jobs from public boards. Model: {AFFINE_S6_MODEL_ID}")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    args.affine = True
    return cmd_search(args)


def cmd_chat(args: argparse.Namespace) -> int:
    from jobfinder.affine import generate

    reply = generate(args.prompt)
    if args.thinking and reply.thinking:
        console.print("[dim]thinking[/dim]")
        console.print(reply.thinking)
        console.print()
    console.print(reply.content)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from jobfinder.web import create_app

    app = create_app(profile_path=args.profile)
    console.print(f"Affine-S6 model: {AFFINE_S6_URL}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_model(_: argparse.Namespace) -> int:
    from jobfinder.affine import available_backend

    console.print(f"Model:    {AFFINE_S6_MODEL_ID}")
    console.print(f"URL:      {AFFINE_S6_URL}")
    console.print(f"Backend:  {available_backend()}")
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
    search.add_argument("--profile", help="Path to profile.yaml")
    search.add_argument(
        "--affine",
        action="store_true",
        help="Re-rank the shortlist with Affine-S6 (needs local weights or HF_TOKEN)",
    )
    search.add_argument("--verbose", action="store_true")
    search.set_defaults(func=cmd_search)

    rank = sub.add_parser("rank", help="Search, then re-rank with Affine-S6")
    rank.add_argument("query")
    rank.add_argument("--limit", type=int, default=10)
    rank.add_argument("--sources")
    rank.add_argument("--profile")
    rank.add_argument("--verbose", action="store_true")
    rank.set_defaults(func=cmd_rank)

    chat = sub.add_parser("chat", help="Ask Affine-S6 a question")
    chat.add_argument("prompt")
    chat.add_argument("--thinking", action="store_true", help="Show hidden reasoning")
    chat.set_defaults(func=cmd_chat)

    serve = sub.add_parser("serve", help="Run the web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=5000)
    serve.add_argument("--profile")
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
