from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from src.config import load_config

SYSTEM_PROMPT = (
    "You rewrite professional writing so it sounds like a real person wrote it. "
    "Keep every fact, name, date, skill, metric, and claim. Do not invent experience. "
    "Use contractions, mixed sentence length, and a natural tone. "
    "Output only the rewritten text."
)


class HumanizerUnavailable(RuntimeError):
    pass


def humanize_text(text: str, *, allow_fallback: bool = True) -> str:
    """Rewrite text with the GGUF humanizer, or a local fallback if the model is missing."""
    if not text.strip():
        return text
    try:
        return _gguf_humanize(text)
    except HumanizerUnavailable:
        if not allow_fallback:
            raise
        return fallback_humanize(text)


def fallback_humanize(text: str) -> str:
    """Lightweight rewrite when the GGUF weights are not downloaded."""
    rewritten = text
    replacements = [
        (r"I am writing to apply for the ", "I'm applying for the "),
        (r"I am writing to apply", "I'm applying"),
        (r"I would welcome the chance to contribute to ([^.]+)\.", r"I'd like to keep working in this space at \1."),
        (r"Thank you for your time\.", "Thanks for reading."),
        (r"Relevant experience:", "A few things that map to this role:"),
        (r"Skills that map to this listing include ", "I've already used "),
        (r"My attached resume has additional project and research detail\.", "The resume has the rest of the project detail."),
        (r"can start from the DC / Maryland area or remotely", "I'm in the DC / Maryland area and can work remote"),
        (r"This opening matches work I have already shipped, especially the overlap with ", "This is close to work I have already shipped, including "),
        (r"seeking an applied role\.", "looking for an applied role."),
    ]
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten)

    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    return rewritten.strip() + "\n"


def _gguf_humanize(text: str) -> str:
    llm = _load_gguf()
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Rewrite this so it sounds human, not AI-generated. "
                    "Keep the same meaning and all facts:\n\n"
                    f"{text}"
                ),
            },
        ],
        temperature=_humanizer_config().get("temperature", 0.6),
        max_tokens=_humanizer_config().get("max_tokens", 768),
    )
    content = response["choices"][0]["message"]["content"] or ""
    return content.strip() + "\n"


@lru_cache(maxsize=1)
def _load_gguf():
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise HumanizerUnavailable(
            "llama-cpp-python is not installed. pip install llama-cpp-python"
        ) from exc

    model_path = _ensure_gguf()
    config = _humanizer_config()
    n_gpu_layers = 0 if os.environ.get("HUMANIZER_CPU", "").lower() in {"1", "true", "yes"} else -1
    return Llama(
        model_path=str(model_path),
        n_ctx=int(config.get("n_ctx", 8192)),
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )


def _ensure_gguf() -> Path:
    config = _humanizer_config()
    repo_id = config["id"]
    filename = config["filename"]
    local = Path(os.environ.get("HUMANIZER_GGUF", ""))
    if local.is_file():
        return local

    cache_dir = Path(__file__).resolve().parent.parent / "models"
    cached = cache_dir / filename
    if cached.is_file():
        return cached

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise HumanizerUnavailable("huggingface_hub is required to download the GGUF model.") from exc

    try:
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(cache_dir),
        )
    except Exception as exc:
        raise HumanizerUnavailable(
            f"Could not download {repo_id}/{filename}. "
            "Place the GGUF at models/ or set HUMANIZER_GGUF."
        ) from exc
    return Path(path)


def _humanizer_config() -> dict:
    return load_config().get("humanizer", {})
