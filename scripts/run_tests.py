"""Run pytest with the isolated test URL loaded from .env."""
from __future__ import annotations

import os
import subprocess
import sys

from database_isolation import require_isolation


def main() -> None:
    _, test_url = require_isolation()
    environment = os.environ | {"HOLYSHIP_TEST_DATABASE_URL": test_url}
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], env=environment))


if __name__ == "__main__":
    main()
