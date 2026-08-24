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

# AI humanizer (GGUF): https://huggingface.co/mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF
HUMANIZER_MODEL_ID = "mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF"
HUMANIZER_BASE_MODEL = "KNipun/Ai-Humanizer-Llama-3.2-3B"
HUMANIZER_URL = "https://huggingface.co/mradermacher/Ai-Humanizer-Llama-3.2-3B-GGUF"
HUMANIZER_GGUF_FILE = os.getenv(
    "HUMANIZER_GGUF_FILE", "Ai-Humanizer-Llama-3.2-3B.Q4_K_M.gguf"
)
HUMANIZER_BACKEND = os.getenv("HUMANIZER_BACKEND", "auto").strip().lower()
HUMANIZER_API_BASE = os.getenv("HUMANIZER_API_BASE")
HUMANIZER_API_KEY = os.getenv("HUMANIZER_API_KEY") or os.getenv("HF_TOKEN")

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = ROOT_DIR / "profile.yaml"
DEFAULT_RESUME_PATH = ROOT_DIR / "resume.pdf"

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
AFFINE_API_BASE = os.getenv("AFFINE_API_BASE") or os.getenv("OPENAI_BASE_URL")
AFFINE_API_KEY = os.getenv("AFFINE_API_KEY") or os.getenv("OPENAI_API_KEY") or HF_TOKEN
AFFINE_BACKEND = os.getenv("AFFINE_BACKEND", "auto").strip().lower()
AFFINE_MODEL = os.getenv("AFFINE_MODEL", AFFINE_S6_MODEL_ID)

USER_AGENT = "Job-finder/0.1 (+https://github.com/Slrm1/Job-finder)"

JOBFINDER_DB = Path(os.getenv("JOBFINDER_DB", str(ROOT_DIR / "jobs.db")))
APPLY_DIR = Path(os.getenv("APPLY_DIR", str(ROOT_DIR / ".applications")))
APPLY_FROM = os.getenv("APPLY_FROM", "").strip()
APPLY_SMTP_HOST = os.getenv("APPLY_SMTP_HOST", "").strip()
APPLY_SMTP_PORT = int(os.getenv("APPLY_SMTP_PORT", "587"))
APPLY_SMTP_USER = os.getenv("APPLY_SMTP_USER", "").strip()
APPLY_SMTP_PASSWORD = os.getenv("APPLY_SMTP_PASSWORD", "")
APPLY_SMTP_TLS = os.getenv("APPLY_SMTP_TLS", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
GREENHOUSE_BOARDS = [
    token.strip()
    for token in os.getenv(
        "GREENHOUSE_BOARDS",
        "stripe,airbnb,discord,figma,notion,cloudflare,databricks",
    ).split(",")
    if token.strip()
]

THINK_END_TOKEN = "</think>"
# Qwen3 tokenizer id for </think>
THINK_END_TOKEN_ID = 151668

DEFAULT_GENERATION = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "max_new_tokens": 1024,
}
