from __future__ import annotations

import argparse
import json

from backend.app.core.config import get_settings
from backend.app.data_lifecycle.service import DataLifecyclePolicy, DataLifecycleService
from backend.app.storage.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HolyShip Data Lifecycle retention cleanup.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview cleanup without mutating data.")
    mode.add_argument("--apply", action="store_true", help="Apply cleanup actions.")
    args = parser.parse_args()

    settings = get_settings()
    dry_run = True
    if args.apply:
        dry_run = False
    elif args.dry_run:
        dry_run = True
    else:
        dry_run = settings.data_lifecycle_dry_run

    with SessionLocal() as session:
        run = DataLifecycleService(
            session,
            DataLifecyclePolicy.from_settings(settings),
        ).run(dry_run=dry_run, source="COMMAND")

    print(
        json.dumps(
            {
                "run_id": str(run.id),
                "status": run.status,
                "dry_run": run.dry_run,
                "policy": run.policy,
                "summary": run.summary,
                "error_message": run.error_message,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
