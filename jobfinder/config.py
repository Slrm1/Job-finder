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
CACHE_DIR = Path(os.getenv("JOBFINDER_CACHE", str(ROOT_DIR / ".cache")))
AFFINE_CACHE_DIR = CACHE_DIR / "affine-s6"
HUMANIZER_CACHE_DIR = CACHE_DIR / "gguf"

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
AFFINE_API_BASE = os.getenv("AFFINE_API_BASE") or os.getenv("OPENAI_BASE_URL")
AFFINE_API_KEY = os.getenv("AFFINE_API_KEY") or os.getenv("OPENAI_API_KEY") or HF_TOKEN
AFFINE_BACKEND = os.getenv("AFFINE_BACKEND", "auto").strip().lower()
AFFINE_MODEL = os.getenv("AFFINE_MODEL", AFFINE_S6_MODEL_ID)

USER_AGENT = "Job-finder/0.1 (+https://github.com/Slrm1/Job-finder)"

JOBFINDER_DB = Path(os.getenv("JOBFINDER_DB", str(ROOT_DIR / "jobs.db")))
APPLY_DIR = Path(os.getenv("APPLY_DIR", str(ROOT_DIR / ".applications")))
APPLY_FROM = os.getenv("APPLY_FROM", "").strip()
APPLY_SMTP_HOST = (
    os.getenv("APPLY_SMTP_HOST") or os.getenv("MAIL_HOST") or os.getenv("SMTP_HOST") or ""
).strip()
APPLY_SMTP_PORT = int(os.getenv("APPLY_SMTP_PORT") or os.getenv("MAIL_PORT") or "587")
APPLY_SMTP_USER = (
    os.getenv("APPLY_SMTP_USER") or os.getenv("MAIL_USER") or os.getenv("SMTP_USER") or ""
).strip()
APPLY_SMTP_PASSWORD = (
    os.getenv("APPLY_SMTP_PASSWORD")
    or os.getenv("MAIL_PASSWORD")
    or os.getenv("SMTP_PASSWORD")
    or ""
)
APPLY_SMTP_TLS = os.getenv("APPLY_SMTP_TLS", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
APPLY_PHONE = os.getenv("APPLY_PHONE", "").strip()
APPLY_EMAIL_BACKEND = os.getenv("APPLY_EMAIL_BACKEND", "auto").strip().lower()
APPLY_DAILY_CAP = int(os.getenv("APPLY_DAILY_CAP", "5"))
FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "10"))
APPLY_API_KEY = os.getenv("APPLY_API_KEY", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip() or (
    APPLY_API_KEY if APPLY_API_KEY.startswith("re_") else ""
)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "").strip() or (
    APPLY_API_KEY if APPLY_API_KEY.startswith("SG.") else ""
)
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "").strip()
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "").strip()
MAILGUN_API_BASE = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net").rstrip("/")

# Paperless-ngx login (OCR). Token is optional; username/password hits /api/token/.
PAPERLESS_URL = os.getenv("PAPERLESS_URL", "").strip().rstrip("/")
PAPERLESS_USER = os.getenv("PAPERLESS_USER", "").strip()
PAPERLESS_PASSWORD = os.getenv("PAPERLESS_PASSWORD", "")
PAPERLESS_TOKEN = os.getenv("PAPERLESS_TOKEN", "").strip()


def _csv(name: str, default: str) -> list[str]:
    return [
        token.strip()
        for token in os.getenv(name, default).split(",")
        if token.strip()
    ]


GREENHOUSE_JOB_BOARD_KEY = os.getenv("GREENHOUSE_JOB_BOARD_KEY", "").strip()
GREENHOUSE_BOARDS = _csv(
    "GREENHOUSE_BOARDS",
    "stripe,airbnb,discord,figma,notion,cloudflare,databricks",
)
ASHBY_BOARDS = _csv("ASHBY_BOARDS", "openai,anthropic,notion,linear")
LEVER_COMPANIES = _csv("LEVER_COMPANIES", "netflix,spotify,duolingo")
USAJOBS_EMAIL = os.getenv("USAJOBS_EMAIL", "").strip() or APPLY_FROM
USAJOBS_AUTH_KEY = (
    os.getenv("USAJOBS_AUTH_KEY") or os.getenv("USAJOBS_API_KEY") or ""
).strip()

THINK_END_TOKEN = "</think>"
# Qwen3 tokenizer id for </think>
THINK_END_TOKEN_ID = 151668

DEFAULT_GENERATION = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "max_new_tokens": 1024,
}
