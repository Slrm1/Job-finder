#!/usr/bin/env python3
"""Job Finder CLI powered by WebScraper991923/Affine-S6."""

import argparse
import json
import sys
from pathlib import Path

from src.apply import apply_to_jobs, apply_to_named_jobs, list_applications
from src.config import get_model_id
from src.job_finder import analyze_single_job, find_jobs, find_matching_jobs, load_jobs, match_jobs_offline
from src.resume import load_resume

DEFAULT_RESUME = Path(__file__).resolve().parent.parent / "data" / "resume.pdf"


def _resume_path(args: argparse.Namespace) -> Path | None:
    if args.resume_file:
        return Path(args.resume_file)
    if DEFAULT_RESUME.exists() and not getattr(args, "resume", "").strip():
        return DEFAULT_RESUME
    return None


def _read_resume(args: argparse.Namespace) -> str:
    if args.resume_file:
        return load_resume(args.resume_file)
    if args.resume.strip():
        return args.resume
    if DEFAULT_RESUME.exists():
        return load_resume(DEFAULT_RESUME)
    raise SystemExit("Error: provide --resume, --resume-file, or place a PDF at data/resume.pdf")


def cmd_match(args: argparse.Namespace) -> int:
    resume = _read_resume(args)
    jobs = load_jobs(Path(args.jobs)) if args.jobs else None
    matches, response = find_matching_jobs(
        resume, jobs=jobs, use_api=args.api, offline=args.offline
    )

    scorer = "offline keyword overlap" if args.offline else get_model_id()
    print(f"Scorer: {scorer}\n")
    print("=" * 60)
    print("TOP JOB MATCHES")
    print("=" * 60)

    for i, match in enumerate(matches, 1):
        print(f"\n{i}. {match.job.title} at {match.job.company}")
        print(f"   Location: {match.job.location}")
        print(f"   Fit Score: {match.score}/100")
        print(f"   {match.reasoning}")

    if args.verbose and response and response.thinking:
        print("\n" + "=" * 60)
        print("MODEL REASONING")
        print("=" * 60)
        print(response.thinking)

    if args.json:
        output = [
            {
                "title": m.job.title,
                "company": m.job.company,
                "location": m.job.location,
                "score": m.score,
                "reasoning": m.reasoning,
            }
            for m in matches
        ]
        print(json.dumps(output, indent=2))

    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    resume = _read_resume(args)

    jobs = load_jobs(Path(args.jobs)) if args.jobs else load_jobs()
    matches = find_jobs(args.job, jobs)
    if not matches:
        print(f"Error: job '{args.job}' not found", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print("Matched multiple jobs; using the first:")
        for job in matches:
            print(f"- {job.title} ({job.company})")
    job = matches[0]

    if args.offline:
        match = match_jobs_offline(resume, [job])[0]
        print("Scorer: offline keyword overlap\n")
        print(f"Analysis for: {job.title} at {job.company}")
        print(f"Fit Score: {match.score}/100")
        print(match.reasoning)
        return 0

    response = analyze_single_job(resume, job, use_api=args.api)
    print(f"Model: {get_model_id()}\n")
    print(f"Analysis for: {job.title} at {job.company}\n")
    print(response.content)

    if args.verbose and response.thinking:
        print("\n--- Model reasoning ---")
        print(response.thinking)

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    jobs = load_jobs(Path(args.jobs)) if args.jobs else load_jobs()
    for job in jobs:
        target = job.apply_email or job.apply_url or "no apply target"
        print(f"- {job.title} ({job.company}, {job.location}) → {target}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    resume = _read_resume(args)
    resume_path = _resume_path(args)
    jobs = load_jobs(Path(args.jobs)) if args.jobs else load_jobs()

    if args.job:
        targets = find_jobs(args.job, jobs)
        if not targets:
            print(f"Error: job '{args.job}' not found", file=sys.stderr)
            return 1
        if len(targets) > 1:
            print(f"Matched {len(targets)} jobs for '{args.job}':")
            for job in targets:
                print(f"- {job.title} ({job.company})")
            print()
        results = apply_to_named_jobs(
            resume,
            resume_path,
            targets,
            send=args.send,
            open_urls=args.open_urls,
            offline=args.offline,
            use_api=args.api,
            force=args.force,
        )
    else:
        results = apply_to_jobs(
            resume,
            resume_path,
            jobs,
            min_score=args.min_score,
            limit=args.limit,
            send=args.send,
            open_urls=args.open_urls,
            offline=args.offline,
            use_api=args.api,
            force=args.force,
        )

    mode = "SEND" if args.send else "DRY RUN"
    print(f"Auto-apply ({mode}) — {len(results)} job(s)\n")
    if not results:
        print("No jobs met the score cutoff. Lower --min-score or pass --job.")
        return 0
    for item in results:
        print(f"- [{item.status}] {item.job_title} at {item.company} ({item.score}/100)")
        print(f"  {item.detail}")
    if not args.send:
        print("\nNo emails were sent. Re-run with --send after setting SMTP_* env vars.")
    return 0 if all(item.status != "error" for item in results) else 1


def cmd_applications(args: argparse.Namespace) -> int:
    entries = list_applications()
    if not entries:
        print("No applications yet. Run: python -m src.cli apply --offline")
        return 0
    for item in entries:
        print(
            f"- [{item.get('status')}] {item.get('job_title')} at {item.get('company')} "
            f"({item.get('score')}/100) {item.get('created_at')}"
        )
        if args.verbose:
            print(f"  {item.get('detail')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Job Finder using WebScraper991923/Affine-S6"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Use Hugging Face Inference API instead of loading locally",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    match = sub.add_parser("match", help="Match resume against job listings")
    match.add_argument("--resume", default="", help="Resume or skills text")
    match.add_argument("--resume-file", help="Path to resume file")
    match.add_argument("--jobs", help="Path to jobs JSON file")
    match.add_argument("--json", action="store_true", help="Output JSON")
    match.add_argument("--verbose", action="store_true", help="Show model thinking")
    match.add_argument(
        "--offline",
        action="store_true",
        help="Score jobs with keyword overlap (no model download)",
    )
    match.set_defaults(func=cmd_match)

    analyze = sub.add_parser("analyze", help="Analyze fit for a single job")
    analyze.add_argument("--resume", default="", help="Resume or skills text")
    analyze.add_argument("--resume-file", help="Path to resume file")
    analyze.add_argument("--job", required=True, help="Job title to analyze")
    analyze.add_argument("--jobs", help="Path to jobs JSON file")
    analyze.add_argument("--verbose", action="store_true", help="Show model thinking")
    analyze.add_argument(
        "--offline",
        action="store_true",
        help="Score this job with keyword overlap (no model download)",
    )
    analyze.set_defaults(func=cmd_analyze)

    listing = sub.add_parser("list", help="List available jobs")
    listing.add_argument("--jobs", help="Path to jobs JSON file")
    listing.set_defaults(func=cmd_list)

    apply = sub.add_parser("apply", help="Auto-apply to matching jobs (dry-run by default)")
    apply.add_argument("--resume", default="", help="Resume or skills text")
    apply.add_argument("--resume-file", help="Path to resume file")
    apply.add_argument("--jobs", help="Path to jobs JSON file")
    apply.add_argument("--job", help="Apply to one job title (or company) instead of the batch")
    apply.add_argument("--min-score", type=float, default=None, help="Minimum match score for --all")
    apply.add_argument("--limit", type=int, default=None, help="Max applications this run")
    apply.add_argument(
        "--offline",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use keyword matching and template cover letters (default). --no-offline uses Affine-S6.",
    )
    apply.add_argument(
        "--send",
        action="store_true",
        help="Actually email applications (requires SMTP_* env vars)",
    )
    apply.add_argument(
        "--open-urls",
        action="store_true",
        help="Open apply_url pages in your browser",
    )
    apply.add_argument("--force", action="store_true", help="Re-apply even if already sent")
    apply.set_defaults(func=cmd_apply)

    history = sub.add_parser("applications", help="Show application history")
    history.add_argument("--verbose", action="store_true", help="Show packet paths and send details")
    history.set_defaults(func=cmd_applications)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
