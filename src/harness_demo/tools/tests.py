from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_visible_tests(
    workspace: Path,
    test_paths: list[str] | None = None,
) -> dict[str, object]:
    targets = test_paths or ["tests"]
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": output[-8_000:],
    }
