"""Affine-S6 client via Hugging Face Inference."""

from __future__ import annotations

import logging
import re
from typing import Any

from huggingface_hub import InferenceClient

from backend.config import Settings

logger = logging.getLogger(__name__)

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
TRAILING_THINK_RE = re.compile(r"^.*?</think>", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT = """You are Job Finder's career assistant, powered by Affine-S6.
Help the user match to remote jobs, improve resumes, and write concise cover letters.
Be practical, specific, and honest about fit. Prefer short structured answers with
bullet points when listing matches or actions. Do not invent job postings; only
reason about jobs the user or the system provides."""


def strip_thinking(text: str) -> str:
    """Remove Qwen3 / Affine-S6 thinking blocks from model output."""
    cleaned = THINK_RE.sub("", text)
    cleaned = TRAILING_THINK_RE.sub("", cleaned)
    return cleaned.strip()


class AffineS6Client:
    """Thin wrapper around Hugging Face chat completion for Affine-S6."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_id = settings.model_id
        self._client: InferenceClient | None = None
        if settings.hf_token:
            kwargs: dict[str, Any] = {
                "token": settings.hf_token,
                "model": settings.model_id,
            }
            if settings.hf_provider:
                kwargs["provider"] = settings.hf_provider
            self._client = InferenceClient(**kwargs)

    @property
    def available(self) -> bool:
        return self._client is not None

    def chat(
        self,
        user_message: str,
        *,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        if not self._client:
            raise RuntimeError(
                "HF_TOKEN is not set. Add a Hugging Face token to call Affine-S6."
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system or SYSTEM_PROMPT},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        completion = self._client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            max_tokens=self.settings.model_max_tokens,
            temperature=self.settings.model_temperature,
        )
        raw = completion.choices[0].message.content or ""
        return strip_thinking(raw)

    def match_jobs(self, profile: str, jobs_summary: str) -> str:
        prompt = (
            "Given this candidate profile and these remote job listings, "
            "rank the top 5 best fits. For each: job title, company, fit score "
            "(0-100), and a one-sentence why. Then give 3 concrete next actions.\n\n"
            f"## Candidate profile\n{profile}\n\n"
            f"## Jobs\n{jobs_summary}"
        )
        return self.chat(prompt)

    def cover_letter(self, profile: str, job_blurb: str) -> str:
        prompt = (
            "Write a concise, professional cover letter (180-250 words) tailored "
            "to this role. Use a confident but human tone. No placeholders like "
            "[Your Name] unless the profile truly lacks a name.\n\n"
            f"## Candidate\n{profile}\n\n"
            f"## Job\n{job_blurb}"
        )
        return self.chat(prompt)

    def resume_tips(self, profile: str, target_role: str = "") -> str:
        focus = f" targeting: {target_role}" if target_role.strip() else ""
        prompt = (
            f"Review this resume/profile{focus}. Give:\n"
            "1) Strengths (3 bullets)\n"
            "2) Gaps vs the target market (3 bullets)\n"
            "3) Rewrite suggestions for the summary (one short paragraph)\n"
            "4) Keywords to add\n\n"
            f"## Profile\n{profile}"
        )
        return self.chat(prompt)
