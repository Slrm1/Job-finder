"""Shared configuration for Job-finder and Affine-S6."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Hugging Face model added at the user's request:
# https://huggingface.co/WebScraper991923/Affine-S6
AFFINE_S6_MODEL_ID = "WebScraper991923/Affine-S6"
AFFINE_S6_REVISION = "b3e23b1895ad43fa48437d3d126f89aa17e53698"
AFFINE_S6_URL = "https://huggingface.co/WebScraper991923/Affine-S6"

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = ROOT_DIR / "profile.yaml"
DEFAULT_RESUME_PATH = ROOT_DIR / "resume.pdf"

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
AFFINE_API_BASE = os.getenv("AFFINE_API_BASE") or os.getenv("OPENAI_BASE_URL")
AFFINE_API_KEY = os.getenv("AFFINE_API_KEY") or os.getenv("OPENAI_API_KEY") or HF_TOKEN
AFFINE_BACKEND = os.getenv("AFFINE_BACKEND", "auto").strip().lower()
AFFINE_MODEL = os.getenv("AFFINE_MODEL", AFFINE_S6_MODEL_ID)

USER_AGENT = "Job-finder/0.1 (+https://github.com/Slrm1/Job-finder)"

THINK_END_TOKEN = "</think>"
# Qwen3 tokenizer id for </think>
THINK_END_TOKEN_ID = 151668

DEFAULT_GENERATION = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "max_new_tokens": 1024,
}
