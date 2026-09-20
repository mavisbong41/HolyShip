"""Shared Phase-0 database isolation guard for local developer commands."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def resolved_urls() -> tuple[str, str]:
    dotenv = load_dotenv()
    dev = os.environ.get("DATABASE_URL", dotenv.get("DATABASE_URL", ""))
    test = os.environ.get("HOLYSHIP_TEST_DATABASE_URL", dotenv.get("HOLYSHIP_TEST_DATABASE_URL", ""))
    if not dev or not test:
        raise SystemExit("DATABASE_URL and HOLYSHIP_TEST_DATABASE_URL must both be configured.")
    return dev, test


def resolved_eval_url() -> str:
    dotenv = load_dotenv()
    eval_url = os.environ.get(
        "HOLYSHIP_EVAL_DATABASE_URL",
        dotenv.get("HOLYSHIP_EVAL_DATABASE_URL", ""),
    )
    if not eval_url:
        raise SystemExit("HOLYSHIP_EVAL_DATABASE_URL must be configured.")
    return eval_url


def database_identity(url: str) -> tuple[str, str, int | None, str]:
    parsed = urlsplit(url)
    return (parsed.hostname or "", parsed.username or "", parsed.port, parsed.path.lstrip("/"))


def require_isolation() -> tuple[str, str]:
    dev, test = resolved_urls()
    if database_identity(dev) == database_identity(test):
        raise SystemExit("Refusing to run: DATABASE_URL and HOLYSHIP_TEST_DATABASE_URL resolve to the same database.")
    return dev, test


def require_eval_isolation() -> tuple[str, str, str]:
    """Return dev/test/eval URLs only when destructive eval cleanup is safe."""
    dev, test = require_isolation()
    eval_url = resolved_eval_url()
    eval_identity = database_identity(eval_url)
    if eval_identity == database_identity(dev):
        raise SystemExit(
            "Refusing evaluation reset: HOLYSHIP_EVAL_DATABASE_URL resolves to DATABASE_URL."
        )
    if eval_identity == database_identity(test):
        raise SystemExit(
            "Refusing evaluation reset: HOLYSHIP_EVAL_DATABASE_URL resolves to "
            "HOLYSHIP_TEST_DATABASE_URL."
        )
    if eval_identity[3].lower() in {"", "postgres", "template0", "template1"}:
        raise SystemExit(
            "Refusing evaluation reset: use a dedicated non-maintenance database."
        )
    return dev, test, eval_url
