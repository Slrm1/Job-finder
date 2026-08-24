"""Rewrite AI-sounding text with Ai-Humanizer-Llama-3.2-3B-GGUF."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from jobfinder.config import (
    HF_TOKEN,
    HUMANIZER_API_BASE,
    HUMANIZER_API_KEY,
    HUMANIZER_BACKEND,
    HUMANIZER_CACHE_DIR,
    HUMANIZER_GGUF_FILE,
    HUMANIZER_MODEL_ID,
    HUMANIZER_URL,
)

SYSTEM_PROMPT = (
    "You are an expert editor. Rewrite the user's text so it sounds like a real "
    "person wrote it: natural, specific, and free of generic AI phrasing. "
    "Keep the same meaning and facts. Do not add new claims. "
    "Output only the rewritten text."
)

_AI_TELLS = (
    (r"\bIt is important to note that\s*", ""),
    (r"\bIt's important to note that\s*", ""),
    (r"\bIt is worth noting that\s*", ""),
    (r"\bIn today's (?:fast-paced|ever-evolving) \w+\s*,\s*", ""),
    (r"\bIn conclusion,\s*", ""),
    (r"\bFurthermore,\s*", "Also, "),
    (r"\bMoreover,\s*", "Also, "),
    (r"\bAdditionally,\s*", "Also, "),
    (r"\bleverage\b", "use"),
    (r"\butiliz(?:e|es|ed|ing)\b", lambda m: {"utilize": "use", "utilizes": "uses", "utilized": "used", "utilizing": "using"}[m.group(0).lower()]),
    (r"\bdelve into\b", "look at"),
    (r"\bembark on\b", "start"),
    (r"\bharness\b", "use"),
    (r"\bfoster\b", "build"),
    (r"\bempower\b", "help"),
    (r"\bstreamline\b", "simplify"),
    (r"\bshowcase(?:s|d|ing)?\b", "show"),
    (r"\bunderscores\b", "shows"),
    (r"\brobust\b", "solid"),
    (r"\bseamless\b", "smooth"),
    (r"\bcutting-edge\b", "modern"),
    (r"\bstate-of-the-art\b", "current"),
    (r"\bcomprehensive\b", "full"),
    (r"\btailored\b", "custom"),
    (r"\blandscape\b", "field"),
    (r"\bplays a (?:vital|crucial|pivotal|key) role in\b", "helps with"),
    (r"\bI am writing to express my (?:strong )?interest in\b", "I'm interested in"),
    (r"\bI am excited to (?:apply|submit my application)\b", "I'd like to apply"),
    (r"—|–", " - "),
    (r"\s{2,}", " "),
)


@dataclass
class HumanizeResult:
    original: str
    humanized: str
    backend: str
    model: str = HUMANIZER_MODEL_ID

    def text(self) -> str:
        return (self.humanized or self.original).strip()


class HumanizerError(RuntimeError):
    pass


def available_backend() -> str:
    requested = HUMANIZER_BACKEND
    if requested in {"gguf", "heuristic", "huggingface", "openai"}:
        return requested
    if HUMANIZER_API_BASE:
        return "openai"
    if _gguf_ready():
        return "gguf"
    return "heuristic"


def humanize_text(text: str, *, backend: str | None = None) -> HumanizeResult:
    original = (text or "").strip()
    if not original:
        return HumanizeResult(original="", humanized="", backend="passthrough")
    if len(original) < 24:
        return HumanizeResult(
            original=original, humanized=original, backend="passthrough"
        )
    chosen = backend or available_backend()
    if chosen == "auto":
        chosen = available_backend()
    if chosen == "gguf":
        rewritten = _humanize_gguf(original)
    elif chosen == "openai":
        rewritten = _humanize_openai(original)
    elif chosen == "huggingface":
        rewritten = _humanize_huggingface(original)
    else:
        rewritten = heuristic_humanize(original)
        chosen = "heuristic"
    rewritten = _cleanup(rewritten) or original
    return HumanizeResult(original=original, humanized=rewritten, backend=chosen)


def heuristic_humanize(text: str) -> str:
    """Lightweight rewrite used when the GGUF weights are not loaded."""
    out = text
    for pattern, replacement in _AI_TELLS:
        out = re.sub(pattern, replacement, out, flags=re.I)
    out = re.sub(r"\s+\.", ".", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = out.strip()
    if out:
        out = out[0].upper() + out[1:]
    return out


def draft_pitch(title: str, company: str, profile) -> str:
    skills = ", ".join(profile.skills[:5]) or "the skills on my resume"
    headline = profile.headline or "I'm looking for a role that fits my background"
    return (
        f"I am writing to express my strong interest in the {title} role at {company}. "
        f"I can leverage my robust experience with {skills} to delve into this "
        f"cutting-edge landscape. {headline}. I am excited to apply and believe "
        f"I can play a vital role in the team."
    )


def humanize_ranked(ranked: list, *, backend: str | None = None) -> list:
    for item in ranked:
        if getattr(item, "summary", ""):
            result = humanize_text(item.summary, backend=backend)
            item.summary = result.text()
            item.humanized = result.backend not in {"passthrough"}
    return ranked


def ensure_gguf(filename: str | None = None) -> Path:
    """Download the Q4_K_M GGUF (or HUMANIZER_GGUF_FILE) into the local cache."""
    from huggingface_hub import hf_hub_download

    name = filename or HUMANIZER_GGUF_FILE
    HUMANIZER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id=HUMANIZER_MODEL_ID,
        filename=name,
        token=HF_TOKEN or None,
        local_dir=str(HUMANIZER_CACHE_DIR),
    )
    return Path(path)


def _gguf_ready() -> bool:
    cached = HUMANIZER_CACHE_DIR / HUMANIZER_GGUF_FILE
    if cached.is_file():
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        return True
    return False


def _cleanup(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'")
    cleaned = re.sub(r"^(here(?:'s| is) (?:a |the )?rewritten version[:\s]*)", "", cleaned, flags=re.I)
    return cleaned.strip()


def _messages(text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Humanize this text:\n\n{text}"},
    ]


@lru_cache(maxsize=1)
def _gguf_llm():
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise HumanizerError(
            "Local GGUF humanizer needs llama-cpp-python:\n"
            "  pip install -e '.[humanizer]'\n"
            f"Then Job-finder will download {HUMANIZER_GGUF_FILE} from {HUMANIZER_URL}"
        ) from exc
    model_path = ensure_gguf()
    return Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_threads=4,
        chat_format="llama-3",
        verbose=False,
    )


def _humanize_gguf(text: str) -> str:
    llm = _gguf_llm()
    response = llm.create_chat_completion(
        messages=_messages(text),
        temperature=0.7,
        top_p=0.9,
        max_tokens=512,
    )
    return response["choices"][0]["message"]["content"] or text


def _humanize_openai(text: str) -> str:
    if not HUMANIZER_API_BASE:
        raise HumanizerError("HUMANIZER_API_BASE is not set.")
    import requests

    url = HUMANIZER_API_BASE.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if HUMANIZER_API_KEY:
        headers["Authorization"] = f"Bearer {HUMANIZER_API_KEY}"
    response = requests.post(
        url,
        headers=headers,
        json={
            "model": HUMANIZER_MODEL_ID,
            "messages": _messages(text),
            "temperature": 0.7,
            "max_tokens": 512,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"] or text


def _humanize_huggingface(text: str) -> str:
    if not HF_TOKEN:
        raise HumanizerError("HF_TOKEN is not set for Hugging Face Inference.")
    from huggingface_hub import InferenceClient

    client = InferenceClient(token=HF_TOKEN)
    response = client.chat.completions.create(
        model=HUMANIZER_MODEL_ID,
        messages=_messages(text),
        temperature=0.7,
        max_tokens=512,
    )
    return response.choices[0].message.content or text
