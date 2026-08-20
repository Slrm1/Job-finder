#!/usr/bin/env python3
"""Job Finder CLI powered by WebScraper991923/Affine-S6."""

import argparse
import json
import sys
from pathlib import Path

from src.config import get_model_id
from src.job_finder import analyze_single_job, find_matching_jobs, load_jobs


def cmd_match(args: argparse.Namespace) -> int:
    resume = args.resume
    if args.resume_file:
        resume = Path(args.resume_file).read_text()

    if not resume.strip():
        print("Error: provide --resume or --resume-file", file=sys.stderr)
        return 1

    jobs = load_jobs(Path(args.jobs)) if args.jobs else None
    matches, response = find_matching_jobs(resume, jobs=jobs, use_api=args.api)

    print(f"Model: {get_model_id()}\n")
    print("=" * 60)
    print("TOP JOB MATCHES")
    print("=" * 60)

    for i, match in enumerate(matches, 1):
        print(f"\n{i}. {match.job.title} at {match.job.company}")
        print(f"   Location: {match.job.location}")
        print(f"   Fit Score: {match.score}/100")
        print(f"   {match.reasoning}")

    if args.verbose and response.thinking:
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
    resume = args.resume
    if args.resume_file:
        resume = Path(args.resume_file).read_text()

    jobs = load_jobs(Path(args.jobs)) if args.jobs else load_jobs()
    job = next((j for j in jobs if j.title.lower() == args.job.lower()), None)
    if not job:
        print(f"Error: job '{args.job}' not found", file=sys.stderr)
        return 1

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
        print(f"- {job.title} ({job.company}, {job.location})")
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
    match.set_defaults(func=cmd_match)

    analyze = sub.add_parser("analyze", help="Analyze fit for a single job")
    analyze.add_argument("--resume", default="", help="Resume or skills text")
    analyze.add_argument("--resume-file", help="Path to resume file")
    analyze.add_argument("--job", required=True, help="Job title to analyze")
    analyze.add_argument("--jobs", help="Path to jobs JSON file")
    analyze.add_argument("--verbose", action="store_true", help="Show model thinking")
    analyze.set_defaults(func=cmd_analyze)

    listing = sub.add_parser("list", help="List available jobs")
    listing.add_argument("--jobs", help="Path to jobs JSON file")
    listing.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
