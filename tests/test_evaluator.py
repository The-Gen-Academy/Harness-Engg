import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_demo.browser import ACCEPTANCE_FLOWS, FlowResult
from harness_demo.harness.evaluator import (
    Evaluation,
    _regression_tests_detect_starter_bug,
    evaluate_workspace,
)
from harness_demo.paths import STARTER_ROOT


def test_feedback_reports_passed_checks_the_rollback_discards() -> None:
    evaluation = Evaluation(
        approved=False,
        failures=["No new regression test was added"],
        passed=["Repeated Coupon: $80.00"],
    )

    feedback = evaluation.feedback()

    assert "- No new regression test was added" in feedback
    assert "- Repeated Coupon: $80.00" in feedback
    assert "rollback discarded the work" in feedback


def test_feedback_is_a_single_line_when_approved() -> None:
    evaluation = Evaluation(approved=True, failures=[], passed=["Visible tests passed"])

    assert evaluation.feedback() == "All completion checks passed."


def test_regression_check_requires_failure_on_starter(tmp_path: Path, monkeypatch) -> None:
    new_test = tmp_path / "checkout" / "tests" / "test_regression.py"
    new_test.parent.mkdir(parents=True)
    new_test.write_text("def test_regression():\n    assert True\n", encoding="utf-8")
    observed_targets: list[list[str] | None] = []

    def fake_run(workspace: Path, targets: list[str] | None = None) -> dict[str, object]:
        observed_targets.append(targets)
        return {"ok": False, "output": "expected failure"}

    monkeypatch.setattr("harness_demo.harness.evaluator.run_visible_tests", fake_run)

    assert _regression_tests_detect_starter_bug([new_test]) is True
    assert observed_targets == [["tests/test_regression.py"]]


@pytest.mark.parametrize("quantity_passed", [False, True])
def test_completion_gate_requires_shared_quantity_acceptance(
    tmp_path: Path, monkeypatch, quantity_passed: bool
) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    # Other gates are isolated here; real browser transitions are covered in test_browser.py.
    (workspace / "app.js").write_text("// browser results are supplied by the test\n")
    (workspace / "tests" / "test_regression.py").write_text("def test_regression(): pass\n")
    monkeypatch.setattr(
        "harness_demo.harness.evaluator.run_visible_tests", lambda _: {"ok": True}
    )
    monkeypatch.setattr(
        "harness_demo.harness.evaluator._regression_tests_detect_starter_bug", lambda _: True
    )
    seen_flows: list[str] = []

    def browser_results(path: Path, flows: list[str]) -> list[FlowResult]:
        assert path == workspace
        seen_flows.extend(flows)
        return [
            FlowResult("repeated_coupon", True, "$80.00", "$80.00"),
            FlowResult("remove_coupon", True, "$100.00", "$100.00"),
            FlowResult(
                "quantity_coupon",
                quantity_passed,
                "change quantity to 2 with coupon active: $160.00",
                "change quantity to 2 with coupon active: "
                + ("$160.00" if quantity_passed else "$200.00"),
            ),
        ]

    monkeypatch.setattr("harness_demo.harness.evaluator.run_browser_flows", browser_results)
    recorder = SimpleNamespace(emit=lambda *args, **kwargs: None)

    evaluation = evaluate_workspace(workspace, recorder)

    assert tuple(seen_flows) == ACCEPTANCE_FLOWS
    assert evaluation.approved is quantity_passed
    if not quantity_passed:
        assert len(evaluation.failures) == 1
        assert "Quantity Coupon" in evaluation.failures[0]
        assert "$160.00" in evaluation.failures[0]
        assert "$200.00" in evaluation.failures[0]
