from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_demo.paths import STARTER_ROOT, WORKSPACE_ROOT, WORKSPACES_ROOT


def reset_workspace() -> Path:
    expected = (WORKSPACES_ROOT / "checkout").resolve()
    if WORKSPACE_ROOT.resolve() != expected:
        raise RuntimeError("Refusing to reset an unexpected workspace path")

    WORKSPACES_ROOT.mkdir(parents=True, exist_ok=True)
    if WORKSPACE_ROOT.exists():
        shutil.rmtree(WORKSPACE_ROOT)
    shutil.copytree(STARTER_ROOT, WORKSPACE_ROOT)
    return WORKSPACE_ROOT


def ensure_workspace() -> Path:
    if not WORKSPACE_ROOT.exists():
        return reset_workspace()
    return WORKSPACE_ROOT


class WorkspaceCheckpoint:
    """Keep an attempt transactional until the completion gate approves it."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.snapshot: Path | None = None
        self._committed = False

    def __enter__(self) -> WorkspaceCheckpoint:
        self._temporary = tempfile.TemporaryDirectory(prefix="harness-checkpoint-")
        self.snapshot = Path(self._temporary.name) / "workspace"
        shutil.copytree(self.workspace, self.snapshot)
        return self

    def restore(self) -> None:
        if self.snapshot is None or not self.snapshot.is_dir():
            raise RuntimeError("Workspace checkpoint is not available")
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        shutil.copytree(self.snapshot, self.workspace)

    def commit(self) -> None:
        self._committed = True

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if not self._committed:
            self.restore()
        if self._temporary is not None:
            self._temporary.cleanup()
