# Job Finder

AI-powered job matching using [WebScraper991923/Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6) — a Qwen3-4B-Thinking model fine-tuned for reasoning and tool use.

## Model

| Property | Value |
|----------|-------|
| **Hugging Face** | [WebScraper991923/Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6) |
| **Architecture** | Qwen3ForCausalLM (4B parameters) |
| **Context** | 262,144 tokens |
| **License** | Apache 2.0 |

The model is configured in `config.yaml` and used for resume-to-job matching and career advice.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Hugging Face Inference API (no local GPU required):

```bash
cp .env.example .env
# Set HF_TOKEN=hf_... in .env
export USE_HF_API=1
```

## Usage

List sample jobs:

```bash
python -m src.cli list
```

Match a resume against all jobs:

```bash
python -m src.cli match --resume "Python developer with PyTorch, transformers, and NLP experience. 2 years building ML pipelines."
```

Analyze fit for a specific job:

```bash
python -m src.cli analyze --job "Machine Learning Engineer" --resume "Python, PyTorch, Hugging Face, LLM fine-tuning"
```

Use the Inference API instead of loading the model locally:

```bash
python -m src.cli --api match --resume "Your skills here"
```

## Project Structure

```
├── config.yaml        # Model ID and inference settings
├── sample_jobs.json   # Sample job listings
├── requirements.txt
└── src/
    ├── cli.py         # Command-line interface
    ├── config.py      # Config loader
    ├── job_finder.py # Matching logic
    └── model.py       # Affine-S6 model wrapper
```

## Custom Jobs

Add your own listings to `sample_jobs.json` or pass a custom file:

```bash
python -m src.cli match --jobs my_jobs.json --resume-file resume.txt
```

Each job entry:

```json
{
  "title": "Job Title",
  "company": "Company Name",
  "location": "City, State",
  "description": "Job description and requirements"
}
```
