"""Supervisor plus subagents that run the local job-search pipeline.

These are in-process workers (not a hosted agent platform). The supervisor
calls them in order: resume → search → rank → write → apply → follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jobfinder.followup import draft_followup, due_followups
from jobfinder.jobs import Job, fetch_listing, search_jobs
from jobfinder.match import (
    Profile,
    RankedJob,
    drop_mismatched_seniority,
    hide_tracked,
    rank_jobs,
    rank_jobs_with_affine,
)
from jobfinder.resume import resolve_profile


@dataclass
class AgentEvent:
    agent: str
    message: str


@dataclass
class PipelineResult:
    profile: Profile
    jobs: list[Job]
    ranked: list[RankedJob]
    applications: list[Any] = field(default_factory=list)
    followups: list[dict[str, str]] = field(default_factory=list)
    log: list[AgentEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": {
                "name": self.profile.name,
                "skills": self.profile.skills,
                "experience_level": self.profile.experience_level,
            },
            "jobs": len(self.jobs),
            "ranked": [item.to_dict() for item in self.ranked],
            "applications": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.applications
            ],
            "followups": self.followups,
            "log": [{"agent": event.agent, "message": event.message} for event in self.log],
        }


class ResumeAgent:
    name = "resume"

    def run(
        self,
        *,
        profile_path: str | None = None,
        resume_path: str | None = None,
        resume_text: str | None = None,
    ) -> Profile:
        return resolve_profile(
            profile_path=profile_path,
            resume_path=resume_path,
            resume_text=resume_text,
        )


class SearchAgent:
    name = "search"

    def run(
        self,
        query: str,
        profile: Profile,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
        url: str = "",
        include_tracked: bool = False,
        db_path: Path | None = None,
    ) -> list[Job]:
        jobs: list[Job] = []
        if url:
            jobs.append(fetch_listing(url))
        if query and not query.lower().startswith("http"):
            jobs.extend(search_jobs(query, sources=sources, limit=limit))
        elif query.lower().startswith("http") and not url:
            jobs.append(fetch_listing(query))
        jobs = drop_mismatched_seniority(jobs, profile)
        if not include_tracked:
            from jobfinder.tracker import tracked_keys

            jobs = hide_tracked(jobs, tracked_keys(db_path=db_path))
        unique: list[Job] = []
        seen: set[str] = set()
        for job in jobs:
            key = (job.url or f"{job.source}:{job.title}:{job.company}").lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(job)
        return unique[:limit]


class RankAgent:
    name = "rank"

    def run(
        self,
        jobs: list[Job],
        profile: Profile,
        *,
        query: str = "",
        affine: bool = False,
        humanize: bool = False,
        limit: int = 20,
    ) -> list[RankedJob]:
        if affine:
            ranked = rank_jobs_with_affine(jobs, profile, limit=min(limit, 8), query=query)
        else:
            ranked = rank_jobs(jobs, profile, query=query)[:limit]
        if humanize:
            from jobfinder.humanizer import humanize_ranked

            ranked = humanize_ranked(ranked)
        return ranked


class WriterAgent:
    name = "writer"

    def run(
        self,
        ranked: list[RankedJob],
        profile: Profile,
        *,
        affine: bool = False,
        humanize: bool = True,
        db_path: Path | None = None,
        apply_dir: Path | None = None,
        limit: int | None = None,
    ) -> list:
        from jobfinder.apply import apply_ranked

        return apply_ranked(
            ranked,
            profile,
            limit=limit,
            send=False,
            mark_applied=False,
            humanize=humanize,
            affine=affine,
            db_path=db_path,
            apply_dir=apply_dir,
        )


class ApplyAgent:
    name = "apply"

    def run(
        self,
        ranked: list[RankedJob],
        profile: Profile,
        *,
        yes: bool,
        limit: int | None = None,
        affine: bool = False,
        db_path: Path | None = None,
        apply_dir: Path | None = None,
        smtp_send=None,
    ) -> list:
        from jobfinder.apply import apply_ranked

        return apply_ranked(
            ranked,
            profile,
            limit=limit,
            send=yes,
            mark_applied=False,
            affine=affine,
            db_path=db_path,
            apply_dir=apply_dir,
            smtp_send=smtp_send,
        )


class FollowUpAgent:
    name = "followup"

    def run(self, profile: Profile, *, db_path: Path | None = None) -> list[dict[str, str]]:
        notes = []
        for row in due_followups(db_path=db_path):
            notes.append(
                {
                    "id": str(row.id),
                    "title": row.title,
                    "company": row.company,
                    "letter": draft_followup(row, profile),
                }
            )
        return notes


class Supervisor:
    """Run resume → search → rank → write/apply → follow-up."""

    def __init__(self) -> None:
        self.resume = ResumeAgent()
        self.search = SearchAgent()
        self.rank = RankAgent()
        self.writer = WriterAgent()
        self.apply = ApplyAgent()
        self.followup = FollowUpAgent()

    def run(
        self,
        query: str,
        *,
        profile_path: str | None = None,
        resume_path: str | None = None,
        resume_text: str | None = None,
        sources: list[str] | None = None,
        limit: int = 20,
        url: str = "",
        affine: bool = False,
        humanize: bool = True,
        apply_count: int | None = None,
        yes: bool = False,
        include_tracked: bool = False,
        db_path: Path | None = None,
        apply_dir: Path | None = None,
        smtp_send=None,
    ) -> PipelineResult:
        log: list[AgentEvent] = []
        profile = self.resume.run(
            profile_path=profile_path,
            resume_path=resume_path,
            resume_text=resume_text,
        )
        log.append(
            AgentEvent(
                self.resume.name,
                f"Loaded {profile.name or 'candidate'} with {len(profile.skills)} skills"
                + (" (Paperless OCR if the PDF had no text)" if resume_path else ""),
            )
        )
        jobs = self.search.run(
            query,
            profile,
            sources=sources,
            limit=limit,
            url=url,
            include_tracked=include_tracked,
            db_path=db_path,
        )
        log.append(AgentEvent(self.search.name, f"Found {len(jobs)} listings after filters"))
        ranked = self.rank.run(
            jobs,
            profile,
            query=query,
            affine=affine,
            humanize=humanize,
            limit=limit,
        )
        log.append(AgentEvent(self.rank.name, f"Ranked {len(ranked)} jobs"))
        applications = []
        if apply_count:
            if yes:
                applications = self.apply.run(
                    ranked,
                    profile,
                    yes=True,
                    limit=apply_count,
                    affine=affine,
                    db_path=db_path,
                    apply_dir=apply_dir,
                    smtp_send=smtp_send,
                )
                sent = sum(1 for item in applications if item.submitted)
                log.append(
                    AgentEvent(
                        self.apply.name,
                        f"Sent {sent} of {len(applications)} (needs --yes and a mailbox login)",
                    )
                )
            else:
                applications = self.writer.run(
                    ranked,
                    profile,
                    affine=affine,
                    db_path=db_path,
                    apply_dir=apply_dir,
                    limit=apply_count,
                )
                log.append(
                    AgentEvent(
                        self.writer.name,
                        f"Previewed {len(applications)} letters. Pass --yes to send.",
                    )
                )
        followups = self.followup.run(profile, db_path=db_path)
        if followups:
            log.append(
                AgentEvent(self.followup.name, f"{len(followups)} applications due a follow-up")
            )
        return PipelineResult(
            profile=profile,
            jobs=jobs,
            ranked=ranked,
            applications=applications,
            followups=followups,
            log=log,
        )
