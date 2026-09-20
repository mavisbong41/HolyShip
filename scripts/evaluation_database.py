"""Destructive cleanup confined to the dedicated evaluation database."""
from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import get_settings
from database_isolation import database_identity, require_eval_isolation


ROOT = Path(__file__).resolve().parents[1]


def reset_and_migrate(eval_url: str) -> None:
    """Reset only the eval schema, then build it exclusively through Alembic."""
    _dev_url, _test_url, configured_eval_url = require_eval_isolation()
    if database_identity(eval_url) != database_identity(configured_eval_url):
        raise SystemExit("Refusing evaluation reset for an unconfigured database.")
    engine = create_engine(eval_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    os.environ["DATABASE_URL"] = eval_url
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    verification_engine = create_engine(eval_url, pool_pre_ping=True)
    try:
        tables = set(inspect(verification_engine).get_table_names())
        if "email_messages" not in tables or "comparison_results" not in tables:
            raise SystemExit("Evaluation migrations did not create the current application schema.")
    finally:
        verification_engine.dispose()
