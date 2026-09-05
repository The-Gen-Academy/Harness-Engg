from __future__ import annotations

import difflib
from pathlib import Path

IGNORED_PARTS = {"__pycache__", ".pytest_cache"}


def _files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not any(part in IGNORED_PARTS for part in path.parts)
    }


def changed_files(before: Path, after: Path) -> list[str]:
    before_files = _files(before)
    after_files = _files(after)
    paths = sorted(before_files.keys() | after_files.keys())
    return [
        path
        for path in paths
        if path not in before_files
        or path not in after_files
        or before_files[path].read_bytes() != after_files[path].read_bytes()
    ]


def unified_workspace_diff(before: Path, after: Path) -> str:
    before_files = _files(before)
    after_files = _files(after)
    chunks: list[str] = []

    for relative in sorted(before_files.keys() | after_files.keys()):
        old_text = (
            before_files[relative].read_text(encoding="utf-8").splitlines(keepends=True)
            if relative in before_files
            else []
        )
        new_text = (
            after_files[relative].read_text(encoding="utf-8").splitlines(keepends=True)
            if relative in after_files
            else []
        )
        if old_text == new_text:
            continue
        chunks.extend(
            difflib.unified_diff(
                old_text,
                new_text,
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )

    return "".join(chunks)
