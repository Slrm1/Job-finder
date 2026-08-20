import os
from dataclasses import dataclass

from src.config import get_model_id, load_config


@dataclass
class ModelResponse:
    content: str
    thinking: str | None = None


class AffineModel:
    """Wrapper for WebScraper991923/Affine-S6 (Qwen3-4B-Thinking)."""

    def __init__(self, model_id: str | None = None, device: str = "auto"):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model_id or get_model_id()
        self.config = load_config()["inference"]
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype="auto",
            device_map=device,
        )

    def generate(self, messages: list[dict], max_new_tokens: int | None = None) -> ModelResponse:
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens or self.config["max_new_tokens"],
            temperature=self.config["temperature"],
            top_p=self.config["top_p"],
            do_sample=True,
        )
        generated = output_ids[0][inputs["input_ids"].shape[1] :]
        raw = self.tokenizer.decode(generated, skip_special_tokens=True)
        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> ModelResponse:
        open_tag = "<" + "redacted_thinking" + ">"
        close_tag = "</" + "redacted_thinking" + ">"
        thinking = None
        content = raw.strip()

        if close_tag in content:
            before, after = content.split(close_tag, 1)
            thinking = before.replace(open_tag, "").strip()
            content = after.strip()

        return ModelResponse(content=content, thinking=thinking)


class InferenceAPIClient:
    """Lightweight client for Hugging Face Inference API."""

    def __init__(self, model_id: str | None = None):
        from huggingface_hub import InferenceClient

        self.model_id = model_id or get_model_id()
        token = os.environ.get("HF_TOKEN")
        self.client = InferenceClient(model=self.model_id, token=token)

    def generate(self, messages: list[dict], max_new_tokens: int | None = None) -> ModelResponse:
        config = load_config()["inference"]
        response = self.client.chat_completion(
            messages=messages,
            max_tokens=max_new_tokens or config["max_new_tokens"],
            temperature=config["temperature"],
            top_p=config["top_p"],
        )
        raw = response.choices[0].message.content or ""
        return AffineModel._parse_response(raw)


def create_model(use_api: bool = False) -> AffineModel | InferenceAPIClient:
    if use_api or os.environ.get("USE_HF_API", "").lower() in {"1", "true", "yes"}:
        return InferenceAPIClient()
    return AffineModel()
