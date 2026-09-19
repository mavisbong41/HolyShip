from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HolyShip Shipping Document Verification"
    database_url: str = Field(default="postgresql+psycopg://holyship:holyship@localhost:5432/holyship_dev")
    organizer_bundle_path: Path = Field(default=Path("data/bundle"))
    classification_threshold: float = 0.8
    classification_margin_threshold: float = 0.25


@lru_cache
def get_settings() -> Settings:
    return Settings()
