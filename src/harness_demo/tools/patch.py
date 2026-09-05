from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unidiff import PatchSet

from harness_demo.diffing import changed_files
from harness_demo.harness.policy import PolicyViolation, WritePolicy
from harness_demo.paths import STARTER_ROOT


@dataclass(frozen=True)
class PendingWrite:
    path: Path
    content: str


def _apply_file_patch(source: str, patched_file: object) -> str:
    source_lines = source.splitlines(keepends=True)
    output: list[str] = []
    source_index = 0

    for hunk in patched_file:  # type: ignore[union-attr]
        hunk_start = max(hunk.source_start - 1, 0)
        if hunk_start < source_index:
            raise ValueError("Patch hunks overlap or are out of order")
        output.extend(source_lines[source_index:hunk_start])
        source_index = hunk_start

        for line in hunk:
            if line.is_context:
                if source_index >= len(source_lines) or source_lines[source_index] != line.value:
                    raise ValueError("Patch context does not match the current file")
                output.append(source_lines[source_index])
                source_index += 1
            elif line.is_removed:
                if source_index >= len(source_lines) or source_lines[source_index] != line.value:
                    raise ValueError("Patch removal does not match the current file")
                source_index += 1
            elif line.is_added:
                output.append(line.value)

    output.extend(source_lines[source_index:])
    return "".join(output)


def apply_unified_patch(policy: WritePolicy, patch_text: str) -> dict[str, object]:
    if len(patch_text) > 100_000:
        return {"ok": False, "error": "Patch exceeds the 100 KB demo limit"}

    try:
        patch_set = PatchSet(patch_text.splitlines(keepends=True))
    # Parser errors vary by unidiff version; all become a safe tool observation.
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Invalid unified diff: {exc}"}
    if not patch_set:
        return {"ok": False, "error": "Patch contained no file changes"}

    writes: list[PendingWrite] = []
    touched: list[str] = []
    try:
        for patched_file in patch_set:
            if patched_file.is_removed_file:
                raise PolicyViolation("Deleting files is not allowed in this demo")
            relative = patched_file.path.removeprefix("a/").removeprefix("b/")
            target = policy.resolve(relative)
            creating = not target.exists()
            target = policy.validate_write(relative, creating=creating)
            source = "" if creating else target.read_text(encoding="utf-8")
            writes.append(PendingWrite(target, _apply_file_patch(source, patched_file)))
            touched.append(relative)
    except (OSError, PolicyViolation, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    prospective = set(changed_files(STARTER_ROOT, policy.workspace)) | set(touched)
    if len(prospective) > policy.max_changed_files:
        return {
            "ok": False,
            "error": (
                f"Patch would exceed the {policy.max_changed_files}-file change budget: "
                f"{', '.join(sorted(prospective))}"
            ),
        }

    for write in writes:
        write.path.parent.mkdir(parents=True, exist_ok=True)
        write.path.write_text(write.content, encoding="utf-8")
    return {"ok": True, "changed_files": sorted(set(touched))}
