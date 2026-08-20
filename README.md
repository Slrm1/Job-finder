# Job Finder

Remote job matching powered by **[WebScraper991923/Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6)** — a Qwen3-4B thinking model from the Affine network.

## What it does

- Pulls live remote listings from [Remotive](https://remotive.com/)
- Ranks fits with Affine-S6 (resume / profile → top matches + next actions)
- Generates tailored cover letters and resume tips
- Falls back to keyword ranking when `HF_TOKEN` is not set

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your Hugging Face token
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Affine-S6 setup

1. Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Set `HF_TOKEN` in `.env`
3. Optional: set `HF_PROVIDER` if you route through a specific Inference provider

The app calls Affine-S6 through the Hugging Face Inference API (`huggingface_hub.InferenceClient`). Local GPU loading is not required.

Model id (configurable via `MODEL_ID`):

```
WebScraper991923/Affine-S6
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | App + model status |
| `/api/jobs` | GET | List remote jobs (`search`, `category`) |
| `/api/match` | POST | Rank jobs for a profile |
| `/api/cover-letter` | POST | Write a cover letter |
| `/api/resume-tips` | POST | Resume coaching |
| `/api/chat` | POST | Freeform Affine-S6 chat |

## Project layout

```
backend/          FastAPI app, Affine-S6 client, Remotive adapter
templates/        Web UI
static/           CSS + JS
```
