"""Configuration — all settings from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    api_title: str = "SketchyAPI — Satire-as-a-Service"
    api_version: str = "0.1.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Auth
    api_keys: str = ""  # Comma-separated "key:tier" pairs

    # Paths (all explicit, no project_root magic)
    output_dir: str = "/data/output"
    sqlite_path: str = "/data/jobs.db"

    # ComfyUI
    comfyui_url: str = "http://localhost:8188"
    comfyui_checkpoint: str = "flux1-dev-fp8.safetensors"
    comfyui_steps: int = 20

    # Queue
    queue_backend: str = "sqlite"  # "sqlite" | "redis" (future)
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_backend: str = "local"  # "local" | "s3" (future)
    s3_bucket: str = ""
    s3_prefix: str = "comics/"

    # Worker
    worker_poll_interval: int = 5
    worker_max_concurrent: int = 1

    # Script writer
    script_writer_backend: str = "stub"  # "stub" | "prompt_only" | "openai" | "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_base_url: str = ""  # For custom LLM endpoints

    # Rate limiting (requests per hour)
    rate_limit_free: int = 5
    rate_limit_pro: int = 50
    rate_limit_enterprise: int = 500

    # Webhook
    webhook_timeout: int = 10
    webhook_max_retries: int = 3

    # Public base URL
    base_url: str = "http://localhost:8000"

    class Config:
        env_prefix = "SKETCHY_"
        env_file = ".env"

    @property
    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir)

    @property
    def resolved_sqlite_path(self) -> Path:
        return Path(self.sqlite_path)

    def parse_api_keys(self) -> dict[str, str]:
        if not self.api_keys:
            return {}
        result = {}
        for entry in self.api_keys.split(","):
            entry = entry.strip()
            if ":" in entry:
                key, tier = entry.rsplit(":", 1)
                result[key] = tier
            else:
                result[entry] = "free"
        return result

    def rate_limit_for_tier(self, tier: str) -> int:
        return {
            "free": self.rate_limit_free,
            "pro": self.rate_limit_pro,
            "enterprise": self.rate_limit_enterprise,
        }.get(tier, self.rate_limit_free)


settings = Settings()
