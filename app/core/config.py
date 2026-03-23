import os
from typing import List

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings — extended for Gamma-style pipeline."""

    app_name: str = "AI Presentation Generator"
    app_version: str = "2.0.0"
    debug: bool = False

    # ── API ────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: List[str] = ["*"]

    # ── File Upload ────────────────────────────
    max_file_size: int = 10 * 1024 * 1024  # 10 MB
    allowed_file_types: List[str] = [".pdf", ".docx", ".txt", ".md"]

    # ── LLM Providers ─────────────────────────
    openai_api_key: str = ""
    google_api_key: str = ""
    vllm_api_base: str = "http://localhost:8001/v1"

    llm_provider: str = "openai"  # openai | google | vllm
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000

    # ── Redis (state + caching) ───────────────
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False  # Falls back to in-memory when False

    # ── Image Generation ──────────────────────
    image_provider: str = "none"  # none | replicate | stability | dalle
    image_api_key: str = ""
    image_api_base: str = ""
    image_default_model: str = "flux-1-quick"
    image_default_style: str = "Modern, clean, presentation-friendly"
    image_width: int = 1024
    image_height: int = 768

    # ── Pipeline Tuning ───────────────────────
    max_parallel_slides: int = 10  # concurrency cap for asyncio.gather
    max_retries: int = 2  # per-slide retry attempts
    retry_backoff_base: float = 1.0  # seconds, exponential backoff base
    analysis_temperature: float = 0.4
    outline_temperature: float = 0.5
    slide_temperature: float = 0.7
    max_document_chars: int = 12_000  # truncation limit for doc input

    # ── Token Budgets per textAmount ──────────
    token_budget_minimal: int = 80
    token_budget_concise: int = 150
    token_budget_detailed: int = 250
    token_budget_extensive: int = 400

    # ── Templates / Storage ───────────────────
    template_dir: str = "app/static/templates"
    database_url: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
