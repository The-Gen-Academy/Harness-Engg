from __future__ import annotations

from pathlib import Path

from harness_demo.diffing import changed_files
from harness_demo.harness.policy import PolicyViolation, WritePolicy
from harness_demo.paths import STARTER_ROOT
from harness_demo.workspace import WorkspaceCheckpoint

# Weak models routinely emit "\\n" in tool-call JSON, so the decoded argument carries a
# literal backslash and "n" where the file has a real line break. The text then never
# matches and the model cannot see why, because its own rendering of the two looks the
# same. These helpers name that failure instead of reporting a generic mismatch.
LITERAL_ESCAPES = (("\\r\\n", "\r\n"), ("\\n", "\n"), ("\\r", "\r"), ("\\t", "\t"))
ESCAPING_HINT = (
    "In the tool-call JSON a line break is the two-character escape \\n; \\\\n sends a "
    "literal backslash instead."
)


def _decode_literal_escapes(text: str) -> str:
    for literal, actual in LITERAL_ESCAPES:
        text = text.replace(literal, actual)
    return text


def _looks_escaped(text: str) -> bool:
    """True when text carries literal escape sequences and no real line breaks."""
    return "\n" not in text and _decode_literal_escapes(text) != text


def _mismatch_error(content: str, old_text: str) -> dict[str, object]:
    decoded = _decode_literal_escapes(old_text)
    if decoded != old_text and content.count(decoded) == 1:
        return {
            "ok": False,
            "error": (
                "old_text did not match because its line breaks are literal backslash-n "
                "sequences rather than real newlines; the same text with real newlines "
                f"matches exactly one location. {ESCAPING_HINT} Resend old_text with real "
                "newlines, or use rewrite_file."
            ),
        }
    return {
        "ok": False,
        "error": "old_text did not exactly match the current file; read the file and retry",
    }


def _escaped_content_error(content: str) -> dict[str, object] | None:
    """Reject content whose only line breaks are literal escapes.

    Writing it would silently produce a single-line file full of backslash-n, which
    passes the write and then fails every downstream check for no visible reason.
    """
    if not _looks_escaped(content) or content.count("\\n") < 2:
        return None
    return {
        "ok": False,
        "error": (
            "content has no real line breaks but contains literal backslash-n sequences, "
            f"so writing it would produce a single corrupted line. {ESCAPING_HINT} Resend "
            "content with real newlines."
        ),
    }


def _check_change_budget(policy: WritePolicy, relative_path: str) -> dict[str, object] | None:
    prospective = set(changed_files(STARTER_ROOT, policy.workspace)) | {relative_path}
    if len(prospective) <= policy.max_changed_files:
        return None
    return {
        "ok": False,
        "error": (
            f"Edit would exceed the {policy.max_changed_files}-file change budget: "
            f"{', '.join(sorted(prospective))}"
        ),
    }


def replace_text(
    policy: WritePolicy,
    relative_path: str,
    old_text: str,
    new_text: str,
) -> dict[str, object]:
    """Replace one exact occurrence in an existing UTF-8 file."""
    if not old_text:
        return {"ok": False, "error": "old_text must not be empty"}

    target = policy.resolve(relative_path)
    if not target.is_file():
        return {"ok": False, "error": f"File does not exist: {relative_path}"}
    target = policy.validate_write(relative_path, creating=False)
    normalized_path = target.relative_to(policy.workspace.resolve()).as_posix()
    if target.stat().st_size > 100_000:
        return {"ok": False, "error": "File is too large for this demo tool"}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "Only UTF-8 text files can be edited"}

    occurrences = content.count(old_text)
    if occurrences == 0:
        return _mismatch_error(content, old_text)
    if occurrences > 1:
        return {
            "ok": False,
            "error": f"old_text matched {occurrences} locations; include more surrounding context",
        }

    escaped_error = _escaped_content_error(new_text)
    if escaped_error:
        return escaped_error

    updated = content.replace(old_text, new_text, 1)
    if len(updated) > 100_000:
        return {"ok": False, "error": "Edited file would exceed the 100 KB demo limit"}

    budget_error = _check_change_budget(policy, normalized_path)
    if budget_error:
        return budget_error

    target.write_text(updated, encoding="utf-8")
    return {"ok": True, "changed_files": [normalized_path]}


def create_file(policy: WritePolicy, relative_path: str, content: str) -> dict[str, object]:
    """Create one new UTF-8 file without overwriting an existing file."""
    if len(content) > 100_000:
        return {"ok": False, "error": "Content exceeds the 100 KB demo limit"}
    escaped_error = _escaped_content_error(content)
    if escaped_error:
        return escaped_error

    target = policy.resolve(relative_path)
    normalized_path = target.relative_to(policy.workspace.resolve()).as_posix()
    if target.exists():
        path = Path(normalized_path)
        suggestion = path.with_name(f"{path.stem}_2{path.suffix}").as_posix()
        return {
            "ok": False,
            "error": (
                f"File already exists: {normalized_path}. create_file never overwrites files; "
                f"choose another new path such as {suggestion}. Existing tests are protected."
            ),
        }
    target = policy.validate_write(relative_path, creating=True)

    budget_error = _check_change_budget(policy, normalized_path)
    if budget_error:
        return budget_error

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "changed_files": [normalized_path]}


def rewrite_file(policy: WritePolicy, relative_path: str, content: str) -> dict[str, object]:
    """Replace the complete contents of one existing allowed UTF-8 file."""
    if len(content) > 100_000:
        return {"ok": False, "error": "Content exceeds the 100 KB demo limit"}
    escaped_error = _escaped_content_error(content)
    if escaped_error:
        return escaped_error

    target = policy.resolve(relative_path)
    if not target.is_file():
        return {"ok": False, "error": f"File does not exist: {relative_path}"}
    target = policy.validate_write(relative_path, creating=False)
    normalized_path = target.relative_to(policy.workspace.resolve()).as_posix()

    try:
        target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "Only UTF-8 text files can be edited"}

    budget_error = _check_change_budget(policy, normalized_path)
    if budget_error:
        return budget_error

    target.write_text(content, encoding="utf-8")
    return {"ok": True, "changed_files": [normalized_path]}


def submit_candidate(
    policy: WritePolicy,
    app_js: str,
    test_path: str,
    test_content: str,
) -> dict[str, object]:
    """Atomically install a complete app implementation and one regression test.

    A weak model is much more reliable when it can submit one coherent candidate than
    when it must maintain an exact mental copy across a chain of substring edits. The
    workspace checkpoint ensures a rejected half-submission never leaks into the next
    tool observation.
    """
    normalized_test_path = Path(test_path).as_posix().removeprefix("./")
    if not normalized_test_path.startswith("tests/test_") or not normalized_test_path.endswith(
        ".py"
    ):
        return {
            "ok": False,
            "error": "test_path must be a new Python test such as tests/test_coupon_regression.py",
        }

    try:
        with WorkspaceCheckpoint(policy.workspace) as checkpoint:
            app_result = rewrite_file(policy, "app.js", app_js)
            if not app_result.get("ok"):
                return {"ok": False, "error": f"app.js was not changed: {app_result['error']}"}

            test_target = policy.resolve(normalized_test_path)
            if test_target.exists():
                test_result = rewrite_file(policy, normalized_test_path, test_content)
            else:
                test_result = create_file(policy, normalized_test_path, test_content)
            if not test_result.get("ok"):
                return {
                    "ok": False,
                    "error": f"Regression test was not changed: {test_result['error']}",
                }

            checkpoint.commit()
    except (OSError, PolicyViolation, RuntimeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "changed_files": ["app.js", normalized_test_path],
    }
