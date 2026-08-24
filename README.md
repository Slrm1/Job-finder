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
3. **Local transformers** — install ML extras and let Hugging Face download the weights:

```bash
pip install -e '.[ml]'
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
HUMANIZER_BACKEND=gguf jobfinder humanize "Paste AI text here."
```

That downloads `Ai-Humanizer-Llama-3.2-3B.Q4_K_M.gguf` into `.cache/gguf/` on first use. You can point `HUMANIZER_API_BASE` at any OpenAI-compatible server that hosts the same model.

## Job sources

Listings come from public JSON APIs (no account required):

- [Remotive](https://remotive.com/)
- [Arbeitnow](https://www.arbeitnow.com/)
- [Remote OK](https://remoteok.com/)
- [Greenhouse](https://boards-api.greenhouse.io/) company boards (opt-in)

You can still use `profile.yaml` (see `profile.example.yaml`) for extra keywords or things to avoid. If both a resume and a YAML profile exist, they are merged.

## JobSync-style tracker

[JobSync](https://github.com/Gsync/jobsync) is a full self-hosted Next.js app (Docker, dashboard, MCP, PDF resume export). It is **not** a library this Python project can import, so the whole app is not vendored here.

What *is* helpful from it is the workflow after you find a role: **save it, set a status, keep notes**. Job-finder now has a local SQLite tracker for that, plus Greenhouse company boards (the same public API JobSync uses for discovery):

```bash
jobfinder search "python intern" --resume resume.example.txt --save 5
jobfinder track list
jobfinder track status 1 applied
jobfinder track note 1 "emailed the recruiter"
```

On the web UI, click **Save to tracker** on a listing, then open **Tracker**. Opt into Greenhouse with `--sources remotive,greenhouse` or the Greenhouse checkbox. Default boards are Stripe, Airbnb, Discord, Figma, Notion, Cloudflare, and Databricks (`GREENHOUSE_BOARDS` to change them).

If you want JobSync's full dashboard, resume PDF templates, and MCP server, run that project separately alongside this one.

## Tests

```bash
pip install -e '.[dev]'
pytest
```
