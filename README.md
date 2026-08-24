# Job-finder

Search public job boards and rank listings against **your resume** using **[Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6)**.

Yes: put a resume in and it will work. Use a text-based `.pdf`, `.txt`, `.md`, or `.docx` (not a scanned image). The app pulls out your name, skills, and experience, then scores public job listings against that. Affine-S6 is optional extra ranking; keyword matching works immediately. Fit notes and cover text can be rewritten with **[Ai-Humanizer-Llama-3.2-3B-GGUF](https://huggingface.co/mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF)**.

## Put your resume in

Any of these:

1. Upload it on the web UI (`jobfinder serve`).
2. Pass it on the command line:

```bash
jobfinder search "python intern" --resume /path/to/your-resume.pdf
```

3. Save it in this folder as `resume.pdf` (or `resume.txt` / `resume.docx`) and run a search. The file is picked up automatically.

Preview what was parsed:

```bash
jobfinder profile --resume resume.example.txt
```

`resume.example.txt` is a sample you can copy. Scanned/image PDFs will not work unless you export them as text first.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
jobfinder search "python backend intern" --resume resume.example.txt
jobfinder serve
```

Then open http://127.0.0.1:5000 and upload your resume.

Download the local models (Affine-S6 ~8 GB and the humanizer GGUF ~2.1 GB):

```bash
pip install -e '.[ml,humanizer]'
jobfinder download
jobfinder download --status
```

Weights land in `.cache/` (gitignored). Keyword ranking still works without them.

Mailbox login and Paperless OCR (no vendor API keys required):

```
APPLY_FROM=you@example.com
MAIL_HOST=smtp.example.com
MAIL_USER=you@example.com
MAIL_PASSWORD=...
PAPERLESS_URL=http://localhost:8000
PAPERLESS_USER=admin
PAPERLESS_PASSWORD=changeme
```

```bash
cp .env.example .env
docker compose up
jobfinder login
jobfinder run "python intern" --resume resume.example.txt --apply 3
jobfinder run "python intern" --apply 3 --yes
```

`--yes` is required to send. Default is preview. Daily cap is `APPLY_DAILY_CAP` (5).

Re-rank the shortlist with Affine-S6 (needs one of the backends below):

```bash
jobfinder rank "python backend intern" --resume resume.example.txt
```

## Affine-S6

| | |
| --- | --- |
| Model | [`WebScraper991923/Affine-S6`](https://huggingface.co/WebScraper991923/Affine-S6) |
| Base | Qwen3-4B-Thinking-2507 |
| License | Apache-2.0 |
| Size | ~4B parameters, BF16 |

Pick a backend with `AFFINE_BACKEND` (`auto`, `huggingface`, `openai`, or `local`):

1. **Hugging Face Inference** — set `HF_TOKEN` in `.env`.
2. **OpenAI-compatible server** — serve the same repo with vLLM or SGLang and set `AFFINE_API_BASE`.
3. **Local transformers** — install ML extras and download the weights:

```bash
pip install -e '.[ml]'
jobfinder download --skip-humanizer
```

Local CPU inference needs several GB of RAM. A GPU or a remote endpoint is strongly preferred.

Sampling follows the model card: temperature `0.6`, top-p `0.95`, top-k `20`. Thinking text (`</think>`) is stripped before ranking JSON is parsed.

## Humanizer

| | |
| --- | --- |
| Model | [`mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF`](https://huggingface.co/mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF) |
| Base | [`KNipun/Ai-Humanizer-Llama-3.2-3B`](https://huggingface.co/KNipun/Ai-Humanizer-Llama-3.2-3B) |
| Default quant | `Q4_K_M` (~2.1 GB) |

Rewrite AI-sounding fit notes, chat replies, or a cover pitch:

```bash
jobfinder humanize "I am writing to express my strong interest in this robust opportunity."
jobfinder search "python intern" --resume resume.example.txt --humanize
jobfinder pitch "python intern" --resume resume.example.txt
```

On the web UI, check **Humanize fit notes** or paste text into the humanize box.

Without GGUF weights, a small heuristic rewriter still strips common AI phrasing. To run the actual Llama 3.2 3B GGUF locally:

```bash
pip install -e '.[humanizer]'
jobfinder download --skip-affine
HUMANIZER_BACKEND=gguf jobfinder humanize "Paste AI text here."
```

That stores `Ai-Humanizer-Llama-3.2-3B.Q4_K_M.gguf` in `.cache/gguf/`. You can point `HUMANIZER_API_BASE` at any OpenAI-compatible server that hosts the same model.

## Job sources

Listings come from public JSON APIs (no account required):

- [Remotive](https://remotive.com/)
- [Arbeitnow](https://www.arbeitnow.com/)
- [Remote OK](https://remoteok.com/)
- [Greenhouse](https://boards-api.greenhouse.io/) company boards (opt-in)
- [Ashby](https://www.ashbyhq.com/) public boards (opt-in, `ASHBY_BOARDS`)
- [Lever](https://github.com/lever/postings-api) public postings (opt-in, `LEVER_COMPANIES`)
- [USAJobs](https://developer.usajobs.gov/) when `USAJOBS_EMAIL` and `USAJOBS_AUTH_KEY` are set from your developer login
- A pasted listing URL (`--url` or `jobfinder run … --url`)

You can still use `profile.yaml` (see `profile.example.yaml`) for extra keywords or things to avoid. If both a resume and a YAML profile exist, they are merged.

## Login credits instead of API keys

Put **your** mailbox and Paperless logins in `.env`. Job-finder will not store LinkedIn, Indeed, or Greenhouse *candidate* passwords, and it will not browser-login to those sites.

| `.env` | What it is |
| --- | --- |
| `MAIL_HOST` / `MAIL_USER` / `MAIL_PASSWORD` | Your email mailbox (SMTP login) |
| `PAPERLESS_URL` / `PAPERLESS_USER` / `PAPERLESS_PASSWORD` | Your Paperless-ngx admin login for OCR |
| `USAJOBS_EMAIL` / `USAJOBS_AUTH_KEY` | Identity + key issued after you log into developer.usajobs.gov |

`jobfinder login` (alias: `jobfinder keys`) prints set/missing only. `--test` sends a mail through SMTP or an optional vendor API.

Resend/SendGrid/Mailgun keys still work if you prefer them. Mailbox login is used first when `MAIL_HOST` and `MAIL_USER` are set.

## OCR with Paperless-ngx

Scanned resume PDFs are sent to [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) over its REST API (`POST /api/token/` with your username and password, then `post_document/`). The Paperless source code is **not** copied into this repo.

```bash
docker compose up
```

That starts Paperless on port 8000 and Job-finder on port 5000. If Paperless is down, Job-finder tries `ocrmypdf` on PATH (same Tesseract stack Paperless uses).

## Supervisor and subagents

`jobfinder run` is a local supervisor that calls in-process workers: **resume** (parse + OCR) → **search** (boards, URL, hide already-tracked, drop senior titles for intern/new-grad profiles) → **rank** → **writer** (tailored resume + cover letter) → **apply** (only with `--yes`, daily cap) → **followup**.

This is not a hosted multi-agent SaaS. It is the same pipeline the CLI, web UI, and MCP (`run_pipeline`) share.

```bash
jobfinder followup
```

## Apply with a cover letter

Job-finder submits **your** resume over the internet on your behalf when it can:

1. **Mailbox login** — `MAIL_HOST` / `MAIL_USER` / `MAIL_PASSWORD` (or `APPLY_SMTP_*`). This is the default send path.
2. **Optional email APIs** — Resend, SendGrid, or Mailgun if you would rather use a vendor key.
3. **Greenhouse HTTP** — `POST` to the official Job Board applications API when `GREENHOUSE_JOB_BOARD_KEY` is set. That key belongs to the **company’s board**, so it only works for boards you control.
4. **Package** — `.applications/` with `cover-letter.txt`, `resume.pdf`, `application.eml` when nothing can be posted.

```bash
jobfinder search "python intern" --resume resume.example.txt --apply 3
jobfinder apply 1
jobfinder apply --saved --draft-only
```

`--apply` drafts letters. `--yes` (or `--send`) actually submits. `--draft-only` only writes the package. Daily cap: `APPLY_DAILY_CAP`.

Email API key (recommended):

```
APPLY_FROM=you@example.com
RESEND_API_KEY=re_xxxxxxxx
```

or `SENDGRID_API_KEY=SG.xxxxxxxx` or `APPLY_API_KEY=re_xxxxxxxx`.

Check what is configured (secrets are not printed):

```bash
jobfinder keys
jobfinder keys --test
```

`--test` emails you through the API key so you know apply-on-your-behalf works.

SMTP fallback:

```
APPLY_FROM=you@example.com
APPLY_SMTP_HOST=smtp.example.com
APPLY_SMTP_PORT=587
APPLY_SMTP_USER=you@example.com
APPLY_SMTP_PASSWORD=...
```

Greenhouse Job Board API key, only if you have the board's own key:

```
GREENHOUSE_JOB_BOARD_KEY=...
```

`HF_TOKEN` is for Affine-S6 ranking, not for submitting applications. Captcha-gated career pages are not bypassed.

On the web UI, **Submit resume over the internet** on a listing or tracker row. Check **Draft only** to skip sending.

## JobSync-style tracker, dashboard, and MCP

[JobSync](https://github.com/Gsync/jobsync) is a full self-hosted Next.js app. It is **not** a library this Python project can import, so the whole app is not vendored here. Job-finder implements the same local workflow in Python: **save a role, write a cover letter, submit when a hiring email exists, set a status, see pipeline stats, export a resume PDF, and talk to agents over MCP**.

```bash
jobfinder search "python intern" --resume resume.example.txt --save 5
jobfinder apply 1 --mark-applied
jobfinder track list
jobfinder dashboard
jobfinder resume-pdf --resume resume.example.txt -o ada.pdf --template professional
```

On the web UI (`jobfinder serve`):

- **Search** — rank listings, save them, or write a cover letter and apply
- **Dashboard** — pipeline counts, apply/interview/offer rates, recent jobs
- **Tracker** — status, cover letters, email/package submit
- **Resume PDF** — download a simple or professional PDF from your loaded resume

JSON is also available at `/api/jobs` and `/api/dashboard`. Applications are stored in local SQLite (`jobs.db`, or `JOBFINDER_DB`).

Opt into Greenhouse with `--sources remotive,greenhouse` or the Greenhouse checkbox. Default boards are Stripe, Airbnb, Discord, Figma, Notion, Cloudflare, and Databricks (`GREENHOUSE_BOARDS` to change them).

### MCP server

Agents can add and update saved jobs without opening the UI:

```bash
jobfinder mcp
```

That speaks JSON-RPC on stdin/stdout (`initialize`, `tools/list`, `tools/call`). Tools: `add_job`, `list_jobs`, `set_status`, `pipeline_stats`, `draft_cover_letter`, `apply_job`.

Example Claude Desktop config (after `pip install -e .`):

```json
{
  "mcpServers": {
    "jobfinder": {
      "command": "jobfinder",
      "args": ["mcp"]
    }
  }
}
```

Or `python -m jobfinder mcp` if the `jobfinder` script is not on `PATH`.

## Tests

```bash
pip install -e '.[dev]'
pytest
```
