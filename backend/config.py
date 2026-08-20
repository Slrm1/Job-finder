"""Application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Job Finder"
    # Affine-S6: Qwen3-4B thinking model from Affine / WebScraper991923
    model_id: str = Field(default="WebScraper991923/Affine-S6", validation_alias="MODEL_ID")
    hf_token: str | None = Field(default=None, validation_alias="HF_TOKEN")
    # Hugging Face Inference provider (e.g. "hf-inference", "together", "fireworks-ai")
    hf_provider: str | None = Field(default=None, validation_alias="HF_PROVIDER")
    remotive_api_url: str = "https://remotive.com/api/remote-jobs"
    max_jobs: int = 40
    model_max_tokens: int = 1024
    model_temperature: float = 0.6


@lru_cache
def get_settings() -> Settings:
    return Settings()
