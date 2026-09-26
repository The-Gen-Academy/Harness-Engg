import json

import pytest
from typer.testing import CliRunner

from harness_demo import cli
from harness_demo.browser import ACCEPTANCE_FLOWS, FlowResult


@pytest.mark.parametrize("passed", [False, True])
def test_verify_reports_behavior_without_model_calls(tmp_path, monkeypatch, passed) -> None:
    workspace = tmp_path / "checkout"
    workspace.mkdir()
    app_js = workspace / "app.js"
    app_js.write_text("// preserve the agent's candidate\n", encoding="utf-8")
    runs = tmp_path / "runs"
    flows_seen = []

    def check_flows(path, flows):
        assert path == workspace
        flows_seen.extend(flows)
        return [
            FlowResult("repeated_coupon", True, "$80.00", "$80.00"),
            FlowResult("remove_coupon", True, "$100.00", "$100.00"),
            FlowResult("quantity_coupon", passed, "$160.00", "$160.00" if passed else "$200.00"),
        ]

    def unexpected_model(*args, **kwargs):
        raise AssertionError("Verification must not call a model")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "ensure_workspace", lambda: workspace)
    monkeypatch.setattr(cli, "run_browser_flows", check_flows)
    monkeypatch.setattr(cli, "OpenAIResponsesModel", unexpected_model)
    monkeypatch.setattr(cli, "_show_run_dir", lambda path: None)
    monkeypatch.setattr("harness_demo.events.RUNS_ROOT", runs)
    monkeypatch.setattr("harness_demo.events.WORKSPACE_ROOT", workspace)

    result = CliRunner().invoke(cli.app, ["verify"])

    assert result.exit_code == (0 if passed else 1), result.output
    assert flows_seen == list(ACCEPTANCE_FLOWS)
    assert "quantity_coupon" in result.output
    assert app_js.read_text(encoding="utf-8") == "// preserve the agent's candidate\n"
    summary = json.loads(next(runs.glob("*/summary.json")).read_text(encoding="utf-8"))
    assert summary["status"] == ("passed" if passed else "failed")
    assert summary["checks"][-1]["passed"] is passed
