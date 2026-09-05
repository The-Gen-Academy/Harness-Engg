import shutil
from pathlib import Path

from harness_demo.browser import FLOWS, run_browser_flows
from harness_demo.paths import STARTER_ROOT


def test_starter_reproduces_coupon_bug(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)

    results = run_browser_flows(workspace, ["single_coupon", "reported_bug"])

    assert results[0].passed is True
    assert results[0].observed == "$80.00"
    assert results[1].passed is False
    assert results[1].observed == "$64.00"


def test_browser_flow_converts_ui_errors_into_results(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)

    def broken_flow(page):
        raise RuntimeError("button is unavailable")

    monkeypatch.setitem(FLOWS, "remove_coupon", broken_flow)

    result = run_browser_flows(workspace, ["remove_coupon"])[0]

    assert result.name == "remove_coupon"
    assert result.passed is False
    assert result.expected == "$100.00"
    assert result.observed == "RuntimeError: button is unavailable"
