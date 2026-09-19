from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.storage.database import SessionLocal


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_settings_dep() -> Settings:
    return get_settings()
