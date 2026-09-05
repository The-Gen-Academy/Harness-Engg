import json

from rich.console import Console

from harness_demo.browser import FlowResult
from harness_demo.events import EventRecorder
from harness_demo.harness.policy import WritePolicy
from harness_demo.tools.executor import ToolExecutor


def test_checkout_tool_separates_execution_from_check_result(tmp_path, monkeypatch) -> None:
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=2)
    results = iter([
        [FlowResult("initial_total", True, "$100.00", "$100.00")],
        [FlowResult("repeated_coupon", False, "$80.00", "$64.00")],
    ])
    monkeypatch.setattr(
        "harness_demo.tools.executor.run_browser_flows",
        lambda workspace, flows: next(results),
    )

    passing = json.loads(executor.call("check_checkout", '{"flows":["initial_total"]}'))
    passing_event = recorder.events[-1]
    failing = json.loads(executor.call("check_checkout", '{"flows":["reported_bug"]}'))
    failing_event = recorder.events[-1]

    assert passing["ok"] is True
    assert passing_event.status == "success"
    assert "1/1 passed" in passing_event.message
    assert failing["ok"] is True
    assert failing["passed"] is False
    assert failing_event.status == "warning"
    assert "0/1 passed" in failing_event.message


def test_tool_events_retain_arguments_and_results(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=1)
    patch = "not a unified diff"

    result = json.loads(executor.call("apply_patch", json.dumps({"patch": patch})))

    assert result["ok"] is False
    assert recorder.events[-2].data == {
        "tool": "apply_patch",
        "arguments": {"patch": patch},
    }
    assert recorder.events[-1].data == {"tool": "apply_patch", "result": result}


def test_writes_require_fresh_reads(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    test_path = tmp_path / "tests" / "test_checkout.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(
        WritePolicy.basic(tmp_path),
        recorder,
        max_calls=4,
        required_reads={"app.js", "tests/test_checkout.py"},
    )
    rewrite_arguments = json.dumps({"path": "app.js", "content": "const ok = false;\n"})

    blocked = json.loads(executor.call("rewrite_file", rewrite_arguments))
    executor.call("read_file", '{"path":"app.js"}')
    executor.call("read_file", '{"path":"tests/test_checkout.py"}')
    changed = json.loads(executor.call("rewrite_file", rewrite_arguments))

    assert blocked["ok"] is False
    assert "Read required files" in blocked["error"]
    assert changed["ok"] is True
    assert changed["changed_files"] == ["app.js"]
    assert "const ok = false;" in changed["workspace_diff"]


def test_attempt_boundary_keeps_reads_of_unchanged_files(tmp_path) -> None:
    app = tmp_path / "app.js"
    app.write_text("const ok = true;\n", encoding="utf-8")
    reverted = tmp_path / "index.html"
    reverted.write_text("<p>clean</p>\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(
        WritePolicy.basic(tmp_path),
        recorder,
        max_calls=4,
        required_reads={"app.js"},
    )

    executor.call("read_file", '{"path":"app.js"}')
    executor.call("read_file", '{"path":"index.html"}')
    reverted.write_text("<p>rolled back</p>\n", encoding="utf-8")
    executor.begin_attempt()
    written = json.loads(
        executor.call(
            "rewrite_file",
            json.dumps({"path": "app.js", "content": "const ok = false;\n"}),
        )
    )

    assert executor.read_paths == {"app.js"}
    assert written["ok"] is True
    assert written["changed_files"] == ["app.js"]


def test_attempt_boundary_drops_reads_of_reverted_files(tmp_path) -> None:
    app = tmp_path / "app.js"
    app.write_text("const ok = false;\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(
        WritePolicy.basic(tmp_path),
        recorder,
        max_calls=2,
        required_reads={"app.js"},
    )

    executor.call("read_file", '{"path":"app.js"}')
    app.write_text("const ok = true;\n", encoding="utf-8")
    executor.begin_attempt()
    blocked = json.loads(
        executor.call(
            "rewrite_file",
            json.dumps({"path": "app.js", "content": "const ok = null;\n"}),
        )
    )

    assert executor.read_paths == set()
    assert blocked["ok"] is False
    assert "Read required files before writing: app.js" in blocked["error"]


def test_repeated_identical_failure_escalates_to_a_different_approach(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=3)
    arguments = json.dumps(
        {"path": "app.js", "old_text": "not in the file", "new_text": "x"}
    )

    first = json.loads(executor.call("replace_text", arguments))
    second = json.loads(executor.call("replace_text", arguments))
    third = json.loads(executor.call("replace_text", arguments))

    assert "already failed" not in str(first["error"])
    assert "identical replace_text call already failed 1x" in str(second["error"])
    assert second["repeated_call"] == 2
    assert "rewrite_file" in str(second["error"])
    assert third["repeated_call"] == 3


def test_preloaded_required_reads_satisfy_the_gate_without_tool_calls(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    test_path = tmp_path / "tests" / "test_checkout.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(
        WritePolicy.basic(tmp_path),
        recorder,
        max_calls=1,
        required_reads={"app.js", "tests/test_checkout.py"},
    )

    loaded = executor.preload_required_reads()
    written = json.loads(
        executor.call(
            "rewrite_file",
            json.dumps({"path": "app.js", "content": "const ok = false;\n"}),
        )
    )

    assert [path for path, _ in loaded] == ["app.js", "tests/test_checkout.py"]
    assert loaded[0][1] == "const ok = true;\n"
    assert executor.call_count == 1
    assert written["ok"] is True
    assert written["changed_files"] == ["app.js"]


def test_harness_tool_surface_is_small_and_atomic(tmp_path) -> None:
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(
        WritePolicy.harnessed(tmp_path),
        recorder,
        max_calls=8,
        allowed_tools={"submit_candidate", "run_tests"},
    )

    assert [schema["name"] for schema in executor.schemas] == [
        "submit_candidate",
        "run_tests",
    ]


def test_repeat_escalation_exempts_workspace_dependent_checks(tmp_path, monkeypatch) -> None:
    recorder = EventRecorder("executor-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=2)
    monkeypatch.setattr(
        "harness_demo.tools.executor.run_visible_tests",
        lambda workspace: {"ok": False, "error": "tests failed", "output": ""},
    )

    executor.call("run_tests", "{}")
    second = json.loads(executor.call("run_tests", "{}"))

    assert "already failed" not in str(second["error"])
    assert "repeated_call" not in second
