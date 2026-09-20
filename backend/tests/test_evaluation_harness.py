from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import database_isolation
import evaluation_database


DEV = "postgresql+psycopg://holyship:holyship@localhost:5432/holyship_dev"
TEST = "postgresql+psycopg://holyship:holyship@localhost:5432/holyship_test"
EVAL = "postgresql+psycopg://holyship:holyship@localhost:5432/holyship_eval"


def _configure(monkeypatch, *, dev=DEV, test=TEST, eval_url=EVAL):
    monkeypatch.setattr(
        database_isolation,
        "load_dotenv",
        lambda: {
            "DATABASE_URL": dev,
            "HOLYSHIP_TEST_DATABASE_URL": test,
            "HOLYSHIP_EVAL_DATABASE_URL": eval_url,
        },
    )
    for key in (
        "DATABASE_URL",
        "HOLYSHIP_TEST_DATABASE_URL",
        "HOLYSHIP_EVAL_DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_evaluation_database_must_be_distinct_from_dev_and_test(monkeypatch):
    _configure(monkeypatch)
    assert database_isolation.require_eval_isolation() == (DEV, TEST, EVAL)

    _configure(monkeypatch, eval_url=DEV)
    with pytest.raises(SystemExit, match="resolves to DATABASE_URL"):
        database_isolation.require_eval_isolation()

    _configure(monkeypatch, eval_url=TEST)
    with pytest.raises(SystemExit, match="HOLYSHIP_TEST_DATABASE_URL"):
        database_isolation.require_eval_isolation()


@pytest.mark.parametrize("database_name", ["", "postgres", "template0", "template1"])
def test_evaluation_database_rejects_maintenance_databases(monkeypatch, database_name):
    eval_url = f"postgresql+psycopg://holyship:holyship@localhost:5432/{database_name}"
    _configure(monkeypatch, eval_url=eval_url)
    with pytest.raises(SystemExit, match="dedicated non-maintenance database"):
        database_isolation.require_eval_isolation()


def test_reset_rejects_a_url_other_than_the_configured_eval_database(monkeypatch):
    monkeypatch.setattr(
        evaluation_database,
        "require_eval_isolation",
        lambda: (DEV, TEST, EVAL),
    )
    with pytest.raises(SystemExit, match="unconfigured database"):
        evaluation_database.reset_and_migrate(
            "postgresql+psycopg://holyship:holyship@localhost:5432/another_database"
        )
