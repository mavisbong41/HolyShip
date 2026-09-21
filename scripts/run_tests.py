"""Run pytest with the isolated test URL loaded from .env."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from database_isolation import require_isolation


def main() -> None:
    _, test_url = require_isolation()
    environment = os.environ | {"HOLYSHIP_TEST_DATABASE_URL": test_url}
    arguments = list(sys.argv[1:])
    if not any(argument.startswith("--basetemp") for argument in arguments):
        arguments.append(f"--basetemp={Path('.pytest_tmp').resolve()}")
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *arguments], env=environment))


if __name__ == "__main__":
    main()
