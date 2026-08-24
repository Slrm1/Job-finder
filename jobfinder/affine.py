"""Inference client for WebScraper991923/Affine-S6."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from jobfinder.config import (
    AFFINE_API_BASE,
    AFFINE_API_KEY,
    AFFINE_BACKEND,
    AFFINE_MODEL,
    AFFINE_S6_MODEL_ID,
    DEFAULT_GENERATION,
    HF_TOKEN,
    THINK_END_TOKEN,
    THINK_END_TOKEN_ID,
)

SYSTEM_PROMPT = (
    "You are Affine-S6, a careful job-search assistant. "
    "Think through the candidate fit, then answer clearly. "
    "Prefer concrete evidence from the job text over generic advice."
)


@dataclass
class AffineReply:
    content: str
    thinking: str = ""
    backend: str = ""
    model: str = AFFINE_S6_MODEL_ID

    def text(self) -> str:
        return self.content.strip()


class AffineError(RuntimeError):
    pass


def split_thinking(text: str) -> tuple[str, str]:
    """Split Qwen3 thinking output into (thinking, visible content)."""
    if not text:
        return "", ""
    if THINK_END_TOKEN in text:
        thinking, _, content = text.partition(THINK_END_TOKEN)
        thinking = thinking.replace("<think>", "").strip()
        return thinking, content.strip()
    return "", text.strip()


def available_backend() -> str:
    """Pick an inference backend without loading weights."""
    requested = AFFINE_BACKEND
    if requested in {"local", "huggingface", "openai"}:
        return requested
    if AFFINE_API_BASE:
        return "openai"
    if HF_TOKEN:
        return "huggingface"
    return "local"


def generate(
    prompt: str,
    *,
    system: str = SYSTEM_PROMPT,
    max_new_tokens: int | None = None,
) -> AffineReply:
    backend = available_backend()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    if backend == "openai":
        return _generate_openai(messages, max_new_tokens)
    if backend == "huggingface":
        return _generate_huggingface(messages, max_new_tokens)
    if backend == "local":
        return _generate_local(messages, max_new_tokens)
    raise AffineError(f"Unknown Affine-S6 backend: {backend}")


def generate_json(prompt: str, **kwargs: Any) -> dict[str, Any]:
    reply = generate(prompt, **kwargs)
    payload = _extract_json(reply.content)
    if payload is None:
        raise AffineError(f"Affine-S6 did not return JSON: {reply.content[:400]}")
    payload["_thinking"] = reply.thinking
    payload["_backend"] = reply.backend
    return payload


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = _JSON_RE.search(cleaned)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None


def _gen_kwargs(max_new_tokens: int | None) -> dict[str, Any]:
    params = dict(DEFAULT_GENERATION)
    if max_new_tokens is not None:
        params["max_new_tokens"] = max_new_tokens
    return params


def _generate_openai(
    messages: list[dict[str, str]], max_new_tokens: int | None
) -> AffineReply:
    if not AFFINE_API_BASE:
        raise AffineError(
            "AFFINE_API_BASE is not set. Point it at a vLLM/SGLang/Featherless "
            f"endpoint serving {AFFINE_S6_MODEL_ID}."
        )
    try:
        from openai import OpenAI
    except ImportError:
        # huggingface_hub is already a dependency; fall back to raw HTTP
        return _generate_openai_http(messages, max_new_tokens)

    client = OpenAI(base_url=AFFINE_API_BASE, api_key=AFFINE_API_KEY or "EMPTY")
    params = _gen_kwargs(max_new_tokens)
    response = client.chat.completions.create(
        model=AFFINE_MODEL,
        messages=messages,
        temperature=params["temperature"],
        top_p=params["top_p"],
        max_tokens=params["max_new_tokens"],
    )
    raw = response.choices[0].message.content or ""
    thinking, content = split_thinking(raw)
    extra = getattr(response.choices[0].message, "reasoning_content", None)
    if extra and not thinking:
        thinking = str(extra)
    return AffineReply(content=content, thinking=thinking, backend="openai")


def _generate_openai_http(
    messages: list[dict[str, str]], max_new_tokens: int | None
) -> AffineReply:
    import requests

    params = _gen_kwargs(max_new_tokens)
    url = AFFINE_API_BASE.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if AFFINE_API_KEY:
        headers["Authorization"] = f"Bearer {AFFINE_API_KEY}"
    response = requests.post(
        url,
        headers=headers,
        json={
            "model": AFFINE_MODEL,
            "messages": messages,
            "temperature": params["temperature"],
            "top_p": params["top_p"],
            "max_tokens": params["max_new_tokens"],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    message = data["choices"][0]["message"]
    raw = message.get("content") or ""
    thinking, content = split_thinking(raw)
    if message.get("reasoning_content") and not thinking:
        thinking = message["reasoning_content"]
    return AffineReply(content=content, thinking=thinking, backend="openai")


def _generate_huggingface(
    messages: list[dict[str, str]], max_new_tokens: int | None
) -> AffineReply:
    if not HF_TOKEN:
        raise AffineError(
            "HF_TOKEN is not set. Create one at https://huggingface.co/settings/tokens "
            f"to call {AFFINE_S6_MODEL_ID} remotely."
        )
    from huggingface_hub import InferenceClient

    params = _gen_kwargs(max_new_tokens)
    client = InferenceClient(token=HF_TOKEN)
    response = client.chat.completions.create(
        model=AFFINE_MODEL,
        messages=messages,
        temperature=params["temperature"],
        top_p=params["top_p"],
        max_tokens=params["max_new_tokens"],
    )
    raw = response.choices[0].message.content or ""
    thinking, content = split_thinking(raw)
    return AffineReply(content=content, thinking=thinking, backend="huggingface")


_LOCAL_MODEL = None
_LOCAL_TOKENIZER = None


def _generate_local(
    messages: list[dict[str, str]], max_new_tokens: int | None
) -> AffineReply:
    global _LOCAL_MODEL, _LOCAL_TOKENIZER
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise AffineError(
            "Local Affine-S6 inference needs the ML extra:\n"
            "  pip install -e '.[ml]'\n"
            "Or set HF_TOKEN / AFFINE_API_BASE for remote inference."
        ) from exc

    if _LOCAL_TOKENIZER is None or _LOCAL_MODEL is None:
        from jobfinder.download import affine_model_source

        model_id, revision = affine_model_source()
        tok_kwargs: dict[str, Any] = {}
        model_kwargs: dict[str, Any] = {
            "torch_dtype": torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            "device_map": "auto",
        }
        if revision:
            tok_kwargs["revision"] = revision
            model_kwargs["revision"] = revision
        _LOCAL_TOKENIZER = AutoTokenizer.from_pretrained(model_id, **tok_kwargs)
        _LOCAL_MODEL = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)

    tokenizer = _LOCAL_TOKENIZER
    model = _LOCAL_MODEL
    params = _gen_kwargs(max_new_tokens)
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    output_ids = model.generate(
        **inputs,
        max_new_tokens=params["max_new_tokens"],
        temperature=params["temperature"],
        top_p=params["top_p"],
        top_k=params["top_k"],
        do_sample=True,
    )
    new_ids = output_ids[0][inputs.input_ids.shape[-1] :].tolist()
    try:
        index = len(new_ids) - new_ids[::-1].index(THINK_END_TOKEN_ID)
    except ValueError:
        index = 0
    thinking = tokenizer.decode(new_ids[:index], skip_special_tokens=True).strip("\n")
    content = tokenizer.decode(new_ids[index:], skip_special_tokens=True).strip("\n")
    return AffineReply(content=content, thinking=thinking, backend="local")
