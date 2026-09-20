"""Read-only Phase-2 development schema verification."""
from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import get_settings


def main() -> None:
    engine = create_engine(get_settings().database_url)
    inspector = inspect(engine)
    with engine.connect() as connection:
        print("revision=", connection.scalar(text("select version_num from alembic_version")))
        print(
            "dev_tables=",
            {
                table: connection.scalar(text("select to_regclass(:name)"), {"name": f"public.{table}"})
                for table in ("email_messages", "attachments", "documents", "processing_events")
            },
        )
    selected = {
        "content_sha256",
        "retrieval_status",
        "retrieval_reason_code",
        "routing_outcome",
        "role_confidence",
        "role_evidence",
        "validation_outcome",
        "parse_duration_ms",
    }
    for table in ("attachments", "documents"):
        print(
            f"{table}_columns=",
            [(column["name"], column["nullable"]) for column in inspector.get_columns(table) if column["name"] in selected],
        )
        print(
            f"{table}_checks=",
            [(constraint["name"], constraint["sqltext"]) for constraint in inspector.get_check_constraints(table)],
        )
        print(f"{table}_indexes=", [index["name"] for index in inspector.get_indexes(table)])


if __name__ == "__main__":
    main()
