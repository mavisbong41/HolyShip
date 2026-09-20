from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.core.reliability import RetryPolicy


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HolyShip Shipping Document Verification"
    database_url: str = Field(default="postgresql+psycopg://holyship:holyship@localhost:5432/holyship_dev")
    organizer_bundle_path: Path = Field(default=Path("data/bundle"))
    classification_threshold: float = 0.8
    classification_margin_threshold: float = 0.25
    sync_max_workers: int = Field(default=4, ge=1, le=32)
    extraction_max_workers: int = Field(default=2, ge=1, le=2)
    organizer_http_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    retry_max_attempts: int = Field(default=3, ge=1, le=8)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0, le=10.0)
    semantic_resolver_timeout_seconds: float = Field(default=5.0, gt=0.0, le=120.0)
    ai_escalation_enabled: bool = False
    ai_provider: str = "disabled"
    ai_model: str = "none"
    ai_endpoint: str | None = None
    ai_api_key: SecretStr | None = None
    ai_confidence_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    ai_timeout_seconds: float = Field(default=5.0, gt=0.0, le=120.0)
    ai_max_calls_per_case: int = Field(default=2, ge=1, le=14)
    ai_max_concurrent_calls: int = Field(default=2, ge=1, le=16)
    ai_resolver_version: str = "phase6-resolver-v1"
    ai_prompt_schema_version: str = "phase6-schema-v1"
    ocr_timeout_seconds: float = Field(default=15.0, gt=0.0, le=120.0)
    ocr_max_calls: int = Field(default=8, ge=1, le=1000)
    ocr_max_concurrent_calls: int = Field(default=2, ge=1, le=16)

    @property
    def retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=self.retry_max_attempts,
            backoff_seconds=self.retry_backoff_seconds,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
