# Job-finder

Search public job boards and rank listings against **your resume** using **[Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6)**.

Yes: put a resume in and it will work. Use a text-based `.pdf`, `.txt`, `.md`, or `.docx` (not a scanned image). The app pulls out your name, skills, and experience, then scores public job listings against that. Affine-S6 is optional extra ranking; keyword matching works immediately.

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

## Job sources

Listings come from public JSON APIs (no account required):

- [Remotive](https://remotive.com/)
- [Arbeitnow](https://www.arbeitnow.com/)
- [Remote OK](https://remoteok.com/)

You can still use `profile.yaml` (see `profile.example.yaml`) for extra keywords or things to avoid. If both a resume and a YAML profile exist, they are merged.

## Tests

```bash
pip install -e '.[dev]'
pytest
```
