"""Typed application settings loaded from environment / .env."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tunables for extraction, LLM calls, and filesystem paths."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    vlm_model_name: str = "gemini-2.0-flash"
    text_model_name: str = "gemini-2.0-flash"

    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    vlm_timeout_seconds: float = Field(default=120.0, gt=0.0)
    text_timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_retries: int = Field(default=3, ge=0)

    extraction_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    fuzzy_match_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    scenarios_dir: Path = Path("scenarios")
    extraction_cache_dir: Path = Path(".cache/extraction")
    extraction_prompt_version: str = "1"
    database_path: Path = Path("pnid_recon.db")


settings = Settings()
