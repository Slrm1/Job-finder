# Job Finder

AI-powered job matching using [WebScraper991923/Affine-S6](https://huggingface.co/WebScraper991923/Affine-S6), with an offline keyword scorer so you can rank roles without a GPU.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put your resume at `data/resume.pdf` (gitignored) or pass `--resume-file`.

## Usage

```bash
# List target roles
python -m src.cli list

# Match your PDF resume without downloading the 4B model
python -m src.cli match --offline --resume-file data/resume.pdf

# Affine-S6 match (local GPU)
python -m src.cli match --resume-file data/resume.pdf

# Hugging Face Inference API
export HF_TOKEN=hf_your_token
python -m src.cli --api match --resume-file data/resume.pdf
```

## Resume privacy

Do not commit PDFs with phone numbers or emails. `data/resume.pdf` is gitignored.

## Custom jobs

Edit `sample_jobs.json` or pass `--jobs my_jobs.json`. Each listing needs `title`, `company`, `location`, and `description`.
