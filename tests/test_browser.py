import shutil
from pathlib import Path

import pytest

from harness_demo.browser import ACCEPTANCE_FLOWS, FLOWS, run_browser_flows
from harness_demo.paths import STARTER_ROOT


def test_starter_reproduces_coupon_bug(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)

    results = run_browser_flows(workspace, ["single_coupon", "reported_bug", "quantity_coupon"])

    assert results[0].passed is True
    assert results[0].observed == "$80.00"
    assert results[1].passed is False
    assert results[1].observed == "$64.00"
    assert results[2].passed is False
    assert "change quantity to 2 with coupon active: $200.00" in results[2].observed
    assert "reset checkout: $100.00 (quantity 1," in results[2].observed


def _write_derived_state_candidate(workspace: Path) -> None:
    """A known-correct candidate, used only in temporary browser test workspaces."""
    app_path = workspace / "app.js"
    source = app_path.read_text(encoding="utf-8")
    source = source.replace("  totalCents: PRICE_CENTS,\n", "")
    source = source.replace(
        "  const discount = Math.max(0, subtotal - state.totalCents);",
        "  const totalCents = state.activeCoupon === COUPON_CODE\n"
        "    ? Math.round(subtotal * (1 - DISCOUNT_RATE))\n"
        "    : subtotal;\n"
        "  const discount = subtotal - totalCents;",
    )
    source = source.replace("formatMoney(state.totalCents)", "formatMoney(totalCents)")
    source = "\n".join(
        line for line in source.splitlines() if "state.totalCents =" not in line
    ) + "\n"
    app_path.write_text(source, encoding="utf-8")


def test_guard_only_fix_passes_repeated_coupon_but_fails_quantity(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    app_path = workspace / "app.js"
    source = app_path.read_text(encoding="utf-8").replace(
        "  state.activeCoupon = COUPON_CODE;",
        "  if (state.activeCoupon === COUPON_CODE) { return; }\n"
        "  state.activeCoupon = COUPON_CODE;",
    )
    app_path.write_text(source, encoding="utf-8")

    repeated, quantity = run_browser_flows(workspace, ["reported_bug", "quantity_coupon"])

    assert repeated.passed is True
    assert quantity.passed is False
    assert "change quantity to 2 with coupon active: $200.00" in quantity.observed
    assert "apply coupon again at quantity 2: $200.00" in quantity.observed


def test_derived_state_candidate_passes_all_acceptance_flows(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    _write_derived_state_candidate(workspace)

    results = run_browser_flows(workspace, list(ACCEPTANCE_FLOWS))

    assert len(results) == len(ACCEPTANCE_FLOWS)
    assert all(result.passed for result in results), results
    quantity = next(result for result in results if result.name == "quantity_coupon")
    assert quantity.observed == quantity.expected
    assert "remove coupon at quantity 2: $200.00" in quantity.observed
    assert "reset checkout: $100.00 (quantity 1," in quantity.observed
    assert quantity.observed.endswith("coupon input ''; remove button hidden")


def test_later_success_cannot_hide_an_earlier_quantity_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    _write_derived_state_candidate(workspace)
    app_path = workspace / "app.js"
    source = app_path.read_text(encoding="utf-8").replace(
        "function updateQuantity() {",
        "function updateQuantity() {\n  state.activeCoupon = null;",
    )
    app_path.write_text(source, encoding="utf-8")

    result = run_browser_flows(workspace, ["quantity_coupon"])[0]

    assert result.passed is False
    assert "change quantity to 2 with coupon active: $200.00" in result.observed
    assert "apply coupon again at quantity 2: $160.00" in result.observed
    assert "reapply coupon at quantity 2: $160.00" in result.observed
    assert "reset checkout: $100.00 (quantity 1," in result.observed
    assert result.observed.endswith("coupon input ''; remove button hidden")


@pytest.mark.parametrize(
    ("old_text", "new_text", "bad_observation"),
    [
        (
            "subtotalOutput.textContent = formatMoney(subtotal);",
            "subtotalOutput.textContent = formatMoney(PRICE_CENTS);",
            "quantity 2, subtotal $100.00",
        ),
        (
            "discountOutput.textContent = `−${formatMoney(discount)}`;",
            "discountOutput.textContent = `−${formatMoney(0)}`;",
            "subtotal $100.00, discount −$0.00",
        ),
        (
            '  couponInput.value = "";\n',
            "",
            "coupon input 'BUILD20'",
        ),
    ],
)
def test_correct_totals_cannot_hide_inconsistent_display_or_reset(
    tmp_path: Path, old_text: str, new_text: str, bad_observation: str
) -> None:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    _write_derived_state_candidate(workspace)
    app_path = workspace / "app.js"
    app_path.write_text(
        app_path.read_text(encoding="utf-8").replace(old_text, new_text), encoding="utf-8"
    )

    result = run_browser_flows(workspace, ["quantity_coupon"])[0]

    assert result.passed is False
    assert "change quantity to 2 with coupon active: $160.00" in result.observed
    assert "reset checkout: $100.00" in result.observed
    assert bad_observation in result.observed


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
