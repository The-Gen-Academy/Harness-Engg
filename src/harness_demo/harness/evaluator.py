from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness_demo.browser import ACCEPTANCE_FLOWS, run_browser_flows
from harness_demo.diffing import changed_files
from harness_demo.events import EventRecorder
from harness_demo.paths import STARTER_ROOT
from harness_demo.tools.tests import run_visible_tests


@dataclass(frozen=True)
class Evaluation:
    approved: bool
    failures: list[str]
    passed: list[str]

    def feedback(self) -> str:
        if self.approved:
            return "All completion checks passed."
        lines = ["Failed checks:"]
        lines.extend(f"- {failure}" for failure in self.failures)
        if self.passed:
            lines.append(
                "Checks the rejected candidate passed. The rollback discarded the work behind "
                "them, so every one of these must hold again in the next candidate:"
            )
            lines.extend(f"- {item}" for item in self.passed)
        return "\n".join(lines)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regression_tests_detect_starter_bug(new_tests: list[Path]) -> bool:
    """A real regression test must pass on the candidate and fail on the buggy starter."""
    with tempfile.TemporaryDirectory(prefix="harness-regression-check-") as temporary:
        baseline = Path(temporary) / "checkout"
        shutil.copytree(STARTER_ROOT, baseline)
        relative_tests: list[str] = []
        for source in new_tests:
            relative = source.relative_to(source.parents[1])
            target = baseline / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            relative_tests.append(relative.as_posix())
        result = run_visible_tests(baseline, relative_tests)
        return not bool(result["ok"])


def evaluate_workspace(workspace: Path, recorder: EventRecorder) -> Evaluation:
    failures: list[str] = []
    passed: list[str] = []

    visible = run_visible_tests(workspace)
    if visible["ok"]:
        passed.append("Visible tests passed")
        recorder.emit("eval", "Visible tests passed", status="success")
    else:
        detail = str(visible["output"])[-1_000:]
        failures.append(f"Visible tests failed: {detail}")
        recorder.emit("eval", "Visible tests failed", status="failure")

    for result in run_browser_flows(
        workspace,
        list(ACCEPTANCE_FLOWS),
    ):
        label = result.name.replace("_", " ").title()
        if result.passed:
            passed.append(f"{label}: {result.observed}")
            recorder.emit("eval", f"{label}: {result.observed}", status="success")
        else:
            failure = f"{label}: expected {result.expected}, observed {result.observed}"
            failures.append(failure)
            recorder.emit("eval", failure, status="failure")

    starter_tests = STARTER_ROOT / "tests"
    for original in starter_tests.glob("*.py"):
        candidate = workspace / "tests" / original.name
        if not candidate.exists() or _digest(original) != _digest(candidate):
            failures.append(f"Existing test was modified or removed: tests/{original.name}")
            recorder.emit("guardrail", failures[-1], status="failure")
        else:
            passed.append(f"Protected tests unchanged: tests/{original.name}")

    new_tests = sorted(
        path
        for path in (workspace / "tests").glob("test_*.py")
        if not (starter_tests / path.name).exists()
    )
    if new_tests:
        passed.append("Regression test added")
        recorder.emit("eval", "Regression test added", status="success")
        if visible["ok"] and _regression_tests_detect_starter_bug(new_tests):
            passed.append("Regression test detects the starter bug")
            recorder.emit(
                "eval",
                "Regression test detects the starter bug",
                status="success",
            )
        elif visible["ok"]:
            failure = "New regression tests also pass on the buggy starter"
            failures.append(failure)
            recorder.emit("eval", failure, status="failure")
    else:
        failures.append(
            "No new regression test was added. Existing tests are protected; create a new file "
            "such as tests/test_coupon_regression.py"
        )
        recorder.emit("eval", failures[-1], status="failure")

    app_source = (workspace / "app.js").read_text(encoding="utf-8")
    if "state.totalCents" in app_source:
        failure = (
            "Architecture check failed: app.js must contain zero references to state.totalCents. "
            "Remove totalCents from state; in render(), compute a local totalCents from "
            "PRICE_CENTS * state.quantity and state.activeCoupon. applyCoupon() and "
            "removeCoupon() should change only activeCoupon before rendering. Preserve the "
            "quantity handler so it updates state.quantity and renders; reset must restore "
            "state.quantity and the quantity input to 1, clear the coupon, and render."
        )
        failures.append(failure)
        recorder.emit("eval", failure, status="failure")
    else:
        passed.append("Pricing derived from canonical state")
        recorder.emit("eval", "Pricing derived from canonical state", status="success")

    changes = changed_files(STARTER_ROOT, workspace)
    if len(changes) <= 3:
        passed.append(f"Diff budget satisfied ({len(changes)}/3 files)")
        recorder.emit("guardrail", f"Diff budget satisfied ({len(changes)}/3)", status="success")
    else:
        failures.append(f"Diff exceeds three-file budget: {', '.join(changes)}")
        recorder.emit("guardrail", failures[-1], status="failure")

    return Evaluation(approved=not failures, failures=failures, passed=passed)
