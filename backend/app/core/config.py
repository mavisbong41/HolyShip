from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
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
    max_attachment_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
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
    ai_review_enabled: bool = True
    ai_review_provider: str = "auto"
    ai_review_model: str = "gemini-2.5-flash"
    ai_review_endpoint: str | None = None
    ai_review_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ai_review_timeout_seconds: float = Field(default=15.0, gt=0.0, le=120.0)
    ai_review_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    ai_review_max_tokens: int = Field(default=2048, ge=1, le=8192)
    ai_review_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    enterprise_privacy_mode: bool = True
    ai_gateway_max_payload_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)
    ocr_tesseract_cmd: str | None = None
    ocr_timeout_seconds: float = Field(default=15.0, gt=0.0, le=120.0)
    ocr_max_calls: int = Field(default=8, ge=1, le=1000)
    ocr_max_concurrent_calls: int = Field(default=2, ge=1, le=16)
    initial_sync_on_startup: bool = False
    continuous_polling_enabled: bool = False
    polling_interval_seconds: float = Field(default=60.0, gt=0.0, le=86400.0)
    polling_backoff_initial_seconds: float = Field(default=1.0, gt=0.0, le=3600.0)
    polling_backoff_max_seconds: float = Field(default=60.0, gt=0.0, le=86400.0)
    polling_source_type: str = "STATIC_BUNDLE"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000,http://localhost:4173,http://127.0.0.1:4173,https://localhost:3200,https://127.0.0.1:3200,https://holyship.onrender.com,https://holyship-backend.onrender.com"
    cors_allow_origin_regex: str | None = None

    @model_validator(mode="after")
    def validate_polling_backoff(self) -> "Settings":
        if self.polling_backoff_max_seconds < self.polling_backoff_initial_seconds:
            raise ValueError("polling_backoff_max_seconds must not be below polling_backoff_initial_seconds")
        return self

    @property
    def resolved_bundle_path(self) -> Path:
        p = self.organizer_bundle_path
        if (p / "inbox").exists():
            return p
        if p.exists() and (p / "inbox").exists():
            return p
        repo_root = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) >= 4 else Path.cwd()
        candidate = repo_root / p
        if (candidate / "inbox").exists():
            return candidate
        app_bundle = Path("/app/data/bundle")
        if (app_bundle / "inbox").exists():
            return app_bundle
        cwd_bundle = Path.cwd() / "data" / "bundle"
        if (cwd_bundle / "inbox").exists():
            return cwd_bundle
        return p

    @property
    def retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=self.retry_max_attempts,
            backoff_seconds=self.retry_backoff_seconds,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]
        if "*" in origins:
            return ["*"]
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        if self.cors_allow_origin_regex and self.cors_allow_origin_regex.strip():
            return self.cors_allow_origin_regex.strip()
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
