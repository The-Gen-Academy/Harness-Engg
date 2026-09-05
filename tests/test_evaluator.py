from pathlib import Path

from harness_demo.harness.evaluator import Evaluation, _regression_tests_detect_starter_bug


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
