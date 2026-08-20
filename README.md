# Job Finder

Match a resume to roles with [WebScraper991923/Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6), then auto-apply: tailored cover letter, resume attachment, and email send.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your resume at `data/resume.pdf` (gitignored).

## Match

```bash
python -m src.cli list
python -m src.cli match --offline --resume-file data/resume.pdf
```

## Auto-apply

Dry run (default): writes cover letters to `data/outbox/` and **does not send mail**.

```bash
# Apply to every listing at/above the min score (default 60)
python -m src.cli apply --resume-file data/resume.pdf

# One job
python -m src.cli apply --job "NLP" --resume-file data/resume.pdf

python -m src.cli applications --verbose
```

Send for real (email the listing's `apply_email` with your resume attached):

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=app-password
export SMTP_FROM=you@gmail.com

python -m src.cli apply --send --resume-file data/resume.pdf
```

Open apply pages in a browser (does not log into LinkedIn/Indeed):

```bash
python -m src.cli apply --open-urls --resume-file data/resume.pdf
```

## Job listing fields

```json
{
  "title": "Junior AI / NLP Engineer",
  "company": "Applied Language Labs",
  "location": "Remote / Washington, DC",
  "apply_email": "careers@company.com",
  "apply_url": "https://company.com/jobs/123",
  "apply_method": "email",
  "description": "..."
}
```

Replace the sample `.example` addresses with real recruiter emails before `--send`.

## Humanize cover letters

Uses [mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF](https://huggingface.co/mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF) (Q4_K_M, ~2.1GB). First run downloads the GGUF into `models/`. If the weights are missing, a lightweight rewriter is used instead.

```bash
# Rewrite any text
python -m src.cli humanize --text "I am writing to apply for the intern role."

# Rewrite a saved cover letter
python -m src.cli humanize --file data/outbox/<packet>/cover_letter.raw.txt

# Apply with humanized letters (default on)
python -m src.cli apply --job "NLP" --resume-file data/resume.pdf

# Skip rewriting
python -m src.cli apply --no-humanize --resume-file data/resume.pdf
```

Optional: `export HUMANIZER_GGUF=/path/to/Ai-Humanizer-Llama-3.2-3B.Q4_K_M.gguf`

## What this will not do

It will not log into LinkedIn, Indeed, or other job boards, fill Easy Apply forms, or bypass CAPTCHAs. Those sites prohibit that automation. Use `apply_email` on listings you are allowed to email, or `--open-urls` and submit the generated packet yourself.

## Privacy

Do not commit resumes or `data/outbox/`. Both are gitignored.
