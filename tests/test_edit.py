import shutil
from pathlib import Path

from harness_demo.harness.policy import WritePolicy
from harness_demo.paths import STARTER_ROOT
from harness_demo.tools.edit import create_file, replace_text, rewrite_file, submit_candidate


def copy_starter(tmp_path: Path) -> Path:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    return workspace


def test_replace_text_updates_one_exact_match(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)

    result = replace_text(
        policy,
        "app.js",
        "const PRICE_CENTS = 10_000;",
        "const PRICE_CENTS = 20_000;",
    )

    assert result == {"ok": True, "changed_files": ["app.js"]}
    assert workspace.joinpath("app.js").read_text(encoding="utf-8").startswith(
        "const PRICE_CENTS = 20_000;"
    )


def test_replace_text_rejects_missing_or_ambiguous_match(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)

    missing = replace_text(policy, "app.js", "not in the file", "replacement")
    ambiguous = replace_text(policy, "app.js", "render();", "replacement")

    assert missing["ok"] is False
    assert "exactly match" in str(missing["error"])
    assert ambiguous["ok"] is False
    assert "matched" in str(ambiguous["error"])
    assert "locations" in str(ambiguous["error"])


def test_create_file_adds_test_without_overwriting(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)

    created = create_file(
        policy,
        "tests/test_regression.py",
        "def test_regression():\n    assert True\n",
    )
    duplicate = create_file(policy, "tests/test_regression.py", "overwritten\n")

    assert created == {"ok": True, "changed_files": ["tests/test_regression.py"]}
    assert duplicate["ok"] is False
    assert "tests/test_regression_2.py" in str(duplicate["error"])
    assert workspace.joinpath("tests/test_regression.py").read_text(encoding="utf-8") == (
        "def test_regression():\n    assert True\n"
    )


def test_rewrite_file_replaces_complete_allowed_file(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)

    result = rewrite_file(policy, "app.js", "const rewritten = true;\n")

    assert result == {"ok": True, "changed_files": ["app.js"]}
    assert workspace.joinpath("app.js").read_text(encoding="utf-8") == (
        "const rewritten = true;\n"
    )


def test_replace_text_names_literal_newline_escapes(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    escaped = (
        "state.activeCoupon = COUPON_CODE;\\n"
        "  state.totalCents = Math.round(state.totalCents * (1 - DISCOUNT_RATE));"
    )

    result = replace_text(policy, "app.js", escaped, "// replaced")

    assert result["ok"] is False
    assert "literal backslash-n" in str(result["error"])
    assert "matches exactly one location" in str(result["error"])


def test_writes_reject_content_whose_newlines_are_literal_escapes(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    escaped = "const a = 1;\\nconst b = 2;\\nconst c = 3;"

    rewritten = rewrite_file(policy, "app.js", escaped)
    created = create_file(policy, "tests/test_escaped.py", escaped)

    assert rewritten["ok"] is False
    assert "literal backslash-n" in str(rewritten["error"])
    assert created["ok"] is False
    assert not workspace.joinpath("tests/test_escaped.py").exists()
    assert "const PRICE_CENTS" in workspace.joinpath("app.js").read_text(encoding="utf-8")


def test_submit_candidate_updates_app_and_test_atomically(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)

    result = submit_candidate(
        policy,
        "const candidate = true;\n",
        "tests/test_regression.py",
        "def test_regression():\n    assert True\n",
    )

    assert result == {
        "ok": True,
        "changed_files": ["app.js", "tests/test_regression.py"],
    }
    assert workspace.joinpath("app.js").read_text(encoding="utf-8") == (
        "const candidate = true;\n"
    )
    assert workspace.joinpath("tests/test_regression.py").is_file()


def test_submit_candidate_rolls_back_when_test_is_protected(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    original_app = workspace.joinpath("app.js").read_text(encoding="utf-8")
    policy = WritePolicy.harnessed(workspace)

    result = submit_candidate(
        policy,
        "const candidate = true;\n",
        "tests/test_checkout.py",
        "def test_weakened():\n    assert True\n",
    )

    assert result["ok"] is False
    assert "protected" in str(result["error"])
    assert workspace.joinpath("app.js").read_text(encoding="utf-8") == original_app


def test_submit_candidate_can_revise_its_own_new_test(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    test_path = "tests/test_regression.py"

    submit_candidate(policy, "const first = true;\n", test_path, "def test_first(): pass\n")
    result = submit_candidate(
        policy,
        "const second = true;\n",
        test_path,
        "def test_second(): pass\n",
    )

    assert result["ok"] is True
    assert workspace.joinpath(test_path).read_text(encoding="utf-8") == (
        "def test_second(): pass\n"
    )
