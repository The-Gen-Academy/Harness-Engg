from pathlib import Path

import pytest

from harness_demo.harness.policy import PolicyViolation, WritePolicy


def test_policy_blocks_workspace_escape(tmp_path: Path) -> None:
    policy = WritePolicy.basic(tmp_path)
    with pytest.raises(PolicyViolation, match="escapes"):
        policy.resolve("../outside.txt")


def test_harness_policy_allows_app_and_new_regression_test(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text("", encoding="utf-8")
    policy = WritePolicy.harnessed(tmp_path)

    assert policy.validate_write("app.js", creating=False) == tmp_path / "app.js"
    assert policy.validate_write("tests/test_regression.py", creating=True) == (
        tmp_path / "tests" / "test_regression.py"
    )


def test_harness_policy_protects_existing_tests(tmp_path: Path) -> None:
    test_path = tmp_path / "tests" / "test_checkout.py"
    test_path.parent.mkdir()
    test_path.write_text("", encoding="utf-8")
    policy = WritePolicy.harnessed(tmp_path)

    with pytest.raises(PolicyViolation, match="protected"):
        policy.validate_write("tests/test_checkout.py", creating=False)


def test_harness_policy_allows_revising_an_agent_created_test(tmp_path: Path) -> None:
    test_path = tmp_path / "tests" / "test_regression.py"
    test_path.parent.mkdir()
    test_path.write_text("def test_new(): pass\n", encoding="utf-8")
    policy = WritePolicy.harnessed(tmp_path)

    assert policy.validate_write("tests/test_regression.py", creating=False) == test_path
