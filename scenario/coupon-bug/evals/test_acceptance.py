"""Harness-owned checks. This directory is not exposed to the worker agent."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_demo.browser import ACCEPTANCE_FLOWS, run_browser_flow

WORKSPACE = Path(os.environ.get("CHECKOUT_WORKSPACE", ".workspaces/checkout")).resolve()


@pytest.mark.parametrize(
    "flow",
    ACCEPTANCE_FLOWS,
)
def test_acceptance_flow(flow: str) -> None:
    result = run_browser_flow(WORKSPACE, flow)
    assert result["passed"], f"{flow}: expected {result['expected']}, observed {result['observed']}"
