from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from rich.console import Console

from harness_demo.diffing import changed_files, unified_workspace_diff
from harness_demo.paths import RUNS_ROOT, STARTER_ROOT, WORKSPACE_ROOT


@dataclass(frozen=True)
class Event:
    timestamp: str
    actor: str
    message: str
    status: str
    data: dict[str, Any]


class EventRecorder:
    """Prints a presentation-friendly trace and stores machine-readable evidence."""

    _styles: ClassVar[dict[str, str]] = {
        "info": "cyan",
        "success": "green",
        "failure": "red",
        "warning": "yellow",
    }
    _symbols: ClassVar[dict[str, str]] = {
        "info": "→",
        "success": "✓",
        "failure": "✕",
        "warning": "!",
    }

    def __init__(self, stage: str, console: Console | None = None) -> None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        self.run_id = f"{timestamp}-{stage}"
        self.stage = stage
        self.run_dir = RUNS_ROOT / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_dir / "events.jsonl"
        self.console = console or Console()
        self.events: list[Event] = []

    def emit(
        self,
        actor: str,
        message: str,
        *,
        status: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        event = Event(
            timestamp=datetime.now(UTC).isoformat(),
            actor=actor.upper(),
            message=message,
            status=status,
            data=data or {},
        )
        self.events.append(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

        style = self._styles.get(status, "white")
        symbol = self._symbols.get(status, "•")
        self.console.print(
            f"[{style}]{symbol} {event.actor:<9}[/{style}] {message}",
            highlight=False,
        )

    def finalize(self, summary: dict[str, Any]) -> Path:
        if WORKSPACE_ROOT.exists():
            patch = unified_workspace_diff(STARTER_ROOT, WORKSPACE_ROOT)
            (self.run_dir / "patch.diff").write_text(patch, encoding="utf-8")
            summary.setdefault("changed_files", changed_files(STARTER_ROOT, WORKSPACE_ROOT))

        summary.update({"run_id": self.run_id, "stage": self.stage})
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self.run_dir

    def capture_attempt_patch(self, attempt: int, before: Path, after: Path) -> Path:
        """Persist a rejected or accepted candidate before any rollback."""
        path = self.run_dir / f"attempt-{attempt}.diff"
        path.write_text(unified_workspace_diff(before, after), encoding="utf-8")
        return path
