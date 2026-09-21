"""Print non-secret database isolation and row-survival evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from database_isolation import database_identity, require_eval_isolation


TRACKED_TABLES = (
    "email_messages",
    "attachments",
    "classification_results",
    "documents",
    "document_extractions",
    "extracted_fields",
    "comparison_results",
    "human_review_cases",
    "human_review_field_overrides",
    "human_review_events",
)


def snapshot(url: str) -> dict[str, object]:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            revision = (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                if "alembic_version" in tables
                else None
            )
            rows: dict[str, object] = {}
            for table in TRACKED_TABLES:
                if table not in tables:
                    continue
                count, identity_hash = connection.execute(
                    text(
                        f"SELECT count(*), "
                        f"md5(coalesce(string_agg(id::text, ',' ORDER BY id), '')) FROM {table}"
                    )
                ).one()
                rows[table] = {"count": int(count), "identity_hash": identity_hash}
            status_counts = {}
            if "email_messages" in tables:
                status_counts = {
                    status: int(count)
                    for status, count in connection.execute(
                        text(
                            "SELECT processing_status, count(*) FROM email_messages "
                            "GROUP BY processing_status ORDER BY processing_status"
                        )
                    )
                }
            review_counts = {}
            if "human_review_cases" in tables and "case_origin" in {
                column["name"] for column in inspect(connection).get_columns("human_review_cases")
            }:
                review_counts = {
                    f"{origin}:{status}": int(count)
                    for origin, status, count in connection.execute(
                        text(
                            "SELECT case_origin, status, count(*) FROM human_review_cases "
                            "GROUP BY case_origin, status ORDER BY case_origin, status"
                        )
                    )
                }
            return {
                "database": database_identity(url)[3],
                "revision": revision,
                "rows": rows,
                "processing_status_counts": status_counts,
                "review_counts": review_counts,
            }
    finally:
        engine.dispose()


def main() -> None:
    dev_url, test_url, eval_url = require_eval_isolation()
    print(
        json.dumps(
            {
                "dev": snapshot(dev_url),
                "test": snapshot(test_url),
                "eval": snapshot(eval_url),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
