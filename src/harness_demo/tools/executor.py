from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness_demo.browser import FLOWS, run_browser_flows
from harness_demo.diffing import unified_workspace_diff
from harness_demo.events import EventRecorder
from harness_demo.harness.policy import PolicyViolation, WritePolicy
from harness_demo.paths import STARTER_ROOT
from harness_demo.tools.edit import create_file, replace_text, rewrite_file, submit_candidate
from harness_demo.tools.filesystem import list_files, read_file, search_code
from harness_demo.tools.patch import apply_unified_patch
from harness_demo.tools.tests import run_visible_tests

WRITE_TOOLS = {
    "apply_patch",
    "replace_text",
    "rewrite_file",
    "create_file",
    "submit_candidate",
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List files beneath a workspace-relative directory.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative directory or file"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a UTF-8 text file from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_code",
        "description": "Search text files for a case-insensitive literal string.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "description": "Relative search root, usually ."},
            },
            "required": ["query", "path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "replace_text",
        "description": (
            "Replace exactly one occurrence of old_text in an existing workspace file. Include "
            "enough exact surrounding text to make the match unique. Replace a complete function "
            "when changing behavior; avoid a chain of small line edits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "old_text": {"type": "string", "description": "Exact text currently in the file"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "rewrite_file",
        "description": (
            "Replace the complete contents of one existing allowed file. Prefer this when a small "
            "file needs a coherent rewrite. Existing protected tests cannot be rewritten."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "Complete replacement content"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_file",
        "description": (
            "Create a new UTF-8 workspace file without overwriting anything. Use this to add a "
            "new regression test after fixing a bug. The path must not already exist; existing "
            "tests are protected, so choose a new name such as tests/test_coupon_regression.py."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path for the new file"},
                "content": {"type": "string", "description": "Complete file content"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "submit_candidate",
        "description": (
            "Atomically submit one coherent checkout candidate: the complete app.js content and "
            "one regression test. If either write is invalid, neither file changes. Re-submit the "
            "same test_path to revise a candidate. The result includes the actual workspace diff."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "app_js": {
                    "type": "string",
                    "description": "Complete replacement contents for app.js",
                },
                "test_path": {
                    "type": "string",
                    "description": "New test path such as tests/test_coupon_regression.py",
                },
                "test_content": {
                    "type": "string",
                    "description": "Complete Python regression test content",
                },
            },
            "required": ["app_js", "test_path", "test_content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_tests",
        "description": "Run the repository's visible pytest suite using a fixed command.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "check_checkout",
        "description": (
            "Exercise one or more checkout flows in a single browser session. During initial "
            "diagnosis, run only reported_bug; the completion gate checks all acceptance flows."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "flows": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(FLOWS)},
                    "minItems": 1,
                    # uniqueItems is not permitted in strict tool schemas, so duplicates are
                    # dropped in run_browser_flows instead.
                    "description": "Browser flows to exercise together; each one runs once",
                }
            },
            "required": ["flows"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

GENERIC_TOOL_NAMES = {
    "list_files",
    "read_file",
    "search_code",
    "replace_text",
    "rewrite_file",
    "create_file",
    "run_tests",
    "check_checkout",
}
HARNESS_TOOL_NAMES = {"submit_candidate", "run_tests"}


class ToolExecutor:
    def __init__(
        self,
        policy: WritePolicy,
        recorder: EventRecorder,
        *,
        max_calls: int,
        required_reads: set[str] | None = None,
        allowed_tools: set[str] | None = None,
    ) -> None:
        self.policy = policy
        self.recorder = recorder
        self.max_calls = max_calls
        self.call_count = 0
        self.required_reads = {self._normalize_path(path) for path in required_reads or set()}
        self.read_paths: set[str] = set()
        self.read_digests: dict[str, str] = {}
        self.failed_calls: dict[str, int] = {}
        self.allowed_tools = allowed_tools or GENERIC_TOOL_NAMES

    def begin_attempt(self) -> None:
        """Keep reads that still match the file on disk; drop the rest.

        A rollback between attempts can revert a file the model already read, so only
        reads that no longer describe the workspace are discarded. Re-reading unchanged
        files would spend turns the attempt needs for the fix itself.
        """
        current: dict[str, str] = {}
        for path in self.read_paths:
            digest = self._digest(path)
            if digest is not None and digest == self.read_digests.get(path):
                current[path] = digest
        self.read_paths = set(current)
        self.read_digests = current

    def preload_required_reads(self) -> list[tuple[str, str]]:
        """Satisfy the required-read gate from the harness side.

        Reading a file the harness itself demands is not agent work, so the contents
        are handed to the model in its next message rather than costing it one model
        turn per file. Returns the (path, content) pairs that still needed loading.
        """
        loaded: list[tuple[str, str]] = []
        for path in sorted(self.required_reads):
            result = read_file(self.policy, path)
            if not result.get("ok"):
                continue
            self.read_paths.add(path)
            digest = self._digest(path)
            if digest is not None:
                self.read_digests[path] = digest
            loaded.append((path, str(result["content"])))
        return loaded

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [schema for schema in TOOL_SCHEMAS if schema["name"] in self.allowed_tools]

    def call(self, name: str, arguments_json: str) -> str:
        if self.call_count >= self.max_calls:
            result = {"ok": False, "error": f"Tool budget exhausted ({self.max_calls} calls)"}
            self.recorder.emit("guardrail", result["error"], status="failure")
            return json.dumps(result)

        self.call_count += 1
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            result = {"ok": False, "error": f"Invalid tool arguments: {exc}"}
            self.recorder.emit("tool", f"{name}: invalid arguments", status="failure")
            return json.dumps(result)

        description = self._describe(name, arguments)
        self.recorder.emit(
            "agent",
            description,
            data={"tool": name, "arguments": arguments},
        )
        try:
            missing_reads = sorted(self.required_reads - self.read_paths)
            if name in WRITE_TOOLS and missing_reads:
                result = {
                    "ok": False,
                    "error": f"Read required files before writing: {', '.join(missing_reads)}",
                }
            else:
                result = self._dispatch(name, arguments)
        except (OSError, PolicyViolation, RuntimeError, ValueError) as exc:
            result = {"ok": False, "error": str(exc)}
        # Tool failures are deliberately converted into observations for the model.
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        if name == "read_file" and result.get("ok"):
            normalized = self._normalize_path(str(result["path"]))
            self.read_paths.add(normalized)
            digest = self._digest(normalized)
            if digest is not None:
                self.read_digests[normalized] = digest

        if name in WRITE_TOOLS and result.get("ok"):
            result = dict(result)
            patch = unified_workspace_diff(STARTER_ROOT, self.policy.workspace)
            result["workspace_diff"] = patch[-20_000:]
            result["diff_truncated"] = len(patch) > 20_000

        if not result.get("ok") and name in WRITE_TOOLS:
            result = self._escalate_repeat(name, arguments, result)

        if not result.get("ok"):
            status = "failure"
        elif name == "check_checkout" and not result.get("passed"):
            status = "warning"
        else:
            status = "success"
        self.recorder.emit(
            "tool",
            self._outcome(name, result),
            status=status,
            data={"tool": name, "result": result},
        )
        return json.dumps(result, ensure_ascii=False)

    def _escalate_repeat(
        self,
        name: str,
        arguments: dict[str, Any],
        result: dict[str, object],
    ) -> dict[str, object]:
        """Tell the model when it has just re-sent a write that already failed.

        A failed call stays in the conversation history, so a model that cannot see
        why it failed tends to copy the same arguments back out of its own context.
        Naming the repetition is what breaks that loop. Only write tools qualify:
        run_tests and check_checkout re-read the workspace, so repeating one after
        an edit is legitimate.
        """
        signature = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False)
        repeats = self.failed_calls.get(signature, 0)
        self.failed_calls[signature] = repeats + 1
        if not repeats:
            return result

        escalated = dict(result)
        escalated["repeated_call"] = repeats + 1
        escalated["error"] = (
            f"{result.get('error', 'failed')} — this identical {name} call already failed "
            f"{repeats}x, so resending it cannot work. Change approach: rewrite_file "
            "replaces a whole file in one call."
        )
        return escalated

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, object]:
        if name == "list_files":
            return list_files(self.policy, arguments["path"])
        if name == "read_file":
            return read_file(self.policy, arguments["path"])
        if name == "search_code":
            return search_code(self.policy, arguments["query"], arguments["path"])
        if name == "apply_patch":
            return apply_unified_patch(self.policy, arguments["patch"])
        if name == "replace_text":
            return replace_text(
                self.policy,
                arguments["path"],
                arguments["old_text"],
                arguments["new_text"],
            )
        if name == "rewrite_file":
            return rewrite_file(self.policy, arguments["path"], arguments["content"])
        if name == "create_file":
            return create_file(self.policy, arguments["path"], arguments["content"])
        if name == "submit_candidate":
            return submit_candidate(
                self.policy,
                arguments["app_js"],
                arguments["test_path"],
                arguments["test_content"],
            )
        if name == "run_tests":
            return run_visible_tests(self.policy.workspace)
        if name == "check_checkout":
            results = [asdict(result) for result in run_browser_flows(
                self.policy.workspace,
                arguments["flows"],
            )]
            return {
                "ok": True,
                "passed": all(result["passed"] for result in results),
                "results": results,
            }
        return {"ok": False, "error": f"Unknown tool: {name}"}

    @staticmethod
    def _describe(name: str, arguments: dict[str, Any]) -> str:
        if name in {"list_files", "read_file", "replace_text", "rewrite_file", "create_file"}:
            return f"{name} {arguments.get('path', '')}"
        if name == "submit_candidate":
            return f"submit_candidate app.js + {arguments.get('test_path', '')}"
        if name == "search_code":
            return f"search_code {arguments.get('query', '')!r}"
        if name == "apply_patch":
            return "apply_patch"
        if name == "check_checkout":
            return f"check_checkout {', '.join(arguments.get('flows', []))}"
        return name

    @staticmethod
    def _outcome(name: str, result: dict[str, object]) -> str:
        if not result.get("ok"):
            return f"{name}: {result.get('error', 'failed')}"
        if name == "list_files":
            return f"Listed {len(result.get('files', []))} files"
        if name == "search_code":
            return f"Found {len(result.get('matches', []))} matches"
        if name in WRITE_TOOLS:
            return f"Changed {', '.join(result.get('changed_files', []))}"
        if name == "run_tests":
            return "Visible tests passed"
        if name == "check_checkout":
            results = result.get("results", [])
            passed = sum(bool(item.get("passed")) for item in results)
            details = ", ".join(
                f"{item.get('name')}={item.get('observed')}"
                for item in results
            )
            return f"Checkout checks {passed}/{len(results)} passed ({details})"
        return f"{name} completed"

    def _digest(self, path: str) -> str | None:
        try:
            return hashlib.sha256(self.policy.resolve(path).read_bytes()).hexdigest()
        except (OSError, PolicyViolation):
            return None

    @staticmethod
    def _normalize_path(path: str) -> str:
        return Path(path).as_posix().removeprefix("./")
