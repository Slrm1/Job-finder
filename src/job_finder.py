import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.model import ModelResponse, create_model

SAMPLE_JOBS_PATH = Path(__file__).resolve().parent.parent / "sample_jobs.json"


@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str

    def summary(self) -> str:
        return (
            f"- {self.title} at {self.company} ({self.location})\n"
            f"  {self.description}"
        )


@dataclass
class JobMatch:
    job: Job
    score: float
    reasoning: str


def load_jobs(path: Path | None = None) -> list[Job]:
    jobs_path = path or SAMPLE_JOBS_PATH
    with open(jobs_path) as f:
        data = json.load(f)
    return [Job(**item) for item in data]


def _build_match_prompt(resume: str, jobs: list[Job]) -> list[dict]:
    job_list = "\n\n".join(job.summary() for job in jobs)
    system = (
        "You are a job-matching assistant. Analyze the candidate's resume against "
        "each job listing. Rank jobs by fit and explain your reasoning clearly."
    )
    user = (
        f"Candidate resume/skills:\n{resume}\n\n"
        f"Available jobs:\n{job_list}\n\n"
        "For each job, provide:\n"
        "1. A fit score from 0-100\n"
        "2. A brief explanation of strengths and gaps\n\n"
        "Format each job as:\n"
        "## [Job Title]\n"
        "Score: [number]\n"
        "Reasoning: [explanation]"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_matches(response: ModelResponse, jobs: list[Job]) -> list[JobMatch]:
    content = response.content
    matches: list[JobMatch] = []

    for job in jobs:
        pattern = rf"##\s*{re.escape(job.title)}.*?Score:\s*(\d+(?:\.\d+)?).*?Reasoning:\s*(.*?)(?=##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            score = float(match.group(1))
            reasoning = match.group(2).strip()
            matches.append(JobMatch(job=job, score=score, reasoning=reasoning))

    if not matches:
        matches.append(
            JobMatch(
                job=jobs[0],
                score=0.0,
                reasoning=content or "No structured response from model.",
            )
        )

    return sorted(matches, key=lambda m: m.score, reverse=True)


def find_matching_jobs(
    resume: str,
    jobs: list[Job] | None = None,
    use_api: bool = False,
) -> tuple[list[JobMatch], ModelResponse]:
    job_list = jobs or load_jobs()
    model = create_model(use_api=use_api)
    messages = _build_match_prompt(resume, job_list)
    response = model.generate(messages)
    matches = _parse_matches(response, job_list)
    return matches, response


def analyze_single_job(
    resume: str,
    job: Job,
    use_api: bool = False,
) -> ModelResponse:
    model = create_model(use_api=use_api)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a career coach. Analyze how well the candidate fits "
                "this job and suggest concrete improvements to their resume."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Resume/skills:\n{resume}\n\n"
                f"Job:\n{job.title} at {job.company} ({job.location})\n"
                f"{job.description}\n\n"
                "Provide a fit assessment and actionable advice."
            ),
        },
    ]
    return model.generate(messages)
