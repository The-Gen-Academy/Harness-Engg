from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from harness_demo.paths import STARTER_ROOT


class PolicyViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class WritePolicy:
    workspace: Path
    strict: bool = False
    max_changed_files: int = 3

    @classmethod
    def basic(cls, workspace: Path) -> WritePolicy:
        return cls(workspace=workspace, strict=False, max_changed_files=20)

    @classmethod
    def harnessed(cls, workspace: Path) -> WritePolicy:
        return cls(workspace=workspace, strict=True, max_changed_files=3)

    def resolve(self, relative_path: str) -> Path:
        if not relative_path or relative_path in {".", "./"}:
            return self.workspace.resolve()
        candidate = (self.workspace / relative_path).resolve()
        try:
            candidate.relative_to(self.workspace.resolve())
        except ValueError as exc:
            raise PolicyViolation(f"Path escapes the workspace: {relative_path}") from exc
        if ".git" in Path(relative_path).parts:
            raise PolicyViolation("Git internals are outside the tool boundary")
        return candidate

    def validate_write(self, relative_path: str, *, creating: bool) -> Path:
        target = self.resolve(relative_path)
        normalized = Path(relative_path).as_posix().removeprefix("./")
        if not self.strict:
            return target

        if normalized in {"app.js", "index.html", "styles.css"}:
            return target
        if fnmatch.fnmatch(normalized, "tests/test_*.py"):
            if (STARTER_ROOT / normalized).exists():
                raise PolicyViolation(f"Existing tests are protected: {normalized}")
            return target
        if fnmatch.fnmatch(normalized, "tests/*.py"):
            raise PolicyViolation(f"Only new test_*.py files may be written: {normalized}")
        raise PolicyViolation(f"Harness policy does not allow writing {normalized}")
