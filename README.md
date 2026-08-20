# Job-finder

Search public job boards and rank listings with **[Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6)**.

Affine-S6 is a Qwen3-4B thinking model (`WebScraper991923/Affine-S6`) on Hugging Face. This project uses it to score job fit against your profile and write short match notes. Keyword ranking still works if the model is not loaded.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp profile.example.yaml profile.yaml
```

Search without downloading model weights:

```bash
jobfinder search "python backend intern"
jobfinder model
```

Re-rank the shortlist with Affine-S6 (needs one of the backends below):

```bash
jobfinder rank "python backend intern"
```

Web UI:

```bash
jobfinder serve
```

Then open http://127.0.0.1:5000

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

Copy `profile.example.yaml` to `profile.yaml` and fill in skills, keywords, and things to avoid. Keyword matching uses that file immediately; Affine-S6 uses it as the ranking prompt.

## Tests

```bash
pip install -e '.[dev]'
pytest
```
