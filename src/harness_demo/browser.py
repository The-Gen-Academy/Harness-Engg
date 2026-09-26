from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from harness_demo.server import temporary_server

VISUAL_BROWSER_ENV = "HARNESS_DEMO_VISUAL_BROWSER"
FLOW_TIMEOUT_MS = 5_000
ACCEPTANCE_FLOWS = ("reported_bug", "remove_coupon", "quantity_coupon")

QUANTITY_COUPON_EXPECTATIONS = (
    ("apply coupon at quantity 1", "$80.00 (quantity 1, subtotal $100.00, discount −$20.00)"),
    (
        "change quantity to 2 with coupon active",
        "$160.00 (quantity 2, subtotal $200.00, discount −$40.00)",
    ),
    ("apply coupon again at quantity 2", "$160.00 (quantity 2, subtotal $200.00, discount −$40.00)"),
    ("remove coupon at quantity 2", "$200.00 (quantity 2, subtotal $200.00, discount −$0.00)"),
    ("reapply coupon at quantity 2", "$160.00 (quantity 2, subtotal $200.00, discount −$40.00)"),
    (
        "reset checkout",
        (
            "$100.00 (quantity 1, subtotal $100.00, discount −$0.00); "
            "coupon input ''; remove button hidden"
        ),
    ),
)


def _sequence_summary(steps: list[tuple[str, str]] | tuple[tuple[str, str], ...]) -> str:
    return " → ".join(f"{label}: {value}" for label, value in steps)


def _visual_browser_enabled() -> bool:
    return os.getenv(VISUAL_BROWSER_ENV, "").strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FlowResult:
    name: str
    passed: bool
    expected: str
    observed: str


def _total(page: Page) -> str:
    return page.locator("#total").inner_text()


def _apply_coupon(page: Page, times: int = 1) -> None:
    page.locator("#coupon").fill("BUILD20")
    for _ in range(times):
        page.locator("#apply-coupon").click()


def _initial(page: Page) -> FlowResult:
    observed = _total(page)
    return FlowResult("initial_total", observed == "$100.00", "$100.00", observed)


def _single_coupon(page: Page) -> FlowResult:
    _apply_coupon(page)
    observed = _total(page)
    return FlowResult("single_coupon", observed == "$80.00", "$80.00", observed)


def _reported_bug(page: Page) -> FlowResult:
    _apply_coupon(page, times=2)
    observed = _total(page)
    return FlowResult("repeated_coupon", observed == "$80.00", "$80.00", observed)


def _remove_coupon(page: Page) -> FlowResult:
    _apply_coupon(page)
    page.locator("#remove-coupon").click()
    observed = _total(page)
    return FlowResult("remove_coupon", observed == "$100.00", "$100.00", observed)


def _quantity_coupon(page: Page) -> FlowResult:
    observations: list[tuple[str, str]] = []

    def observe() -> None:
        label = QUANTITY_COUPON_EXPECTATIONS[len(observations)][0]
        value = (
            f"{_total(page)} (quantity {page.locator('#quantity').input_value()}, "
            f"subtotal {page.locator('#subtotal').inner_text()}, "
            f"discount {page.locator('#discount').inner_text()})"
        )
        if label == "reset checkout":
            remove_visibility = "visible" if page.locator("#remove-coupon").is_visible() else "hidden"
            value += (
                f"; coupon input {page.locator('#coupon').input_value()!r}; "
                f"remove button {remove_visibility}"
            )
        observations.append((label, value))
        if _visual_browser_enabled():
            page.wait_for_timeout(1_000)

    try:
        _apply_coupon(page)
        observe()
        page.locator("#quantity").fill("2")
        page.locator("#quantity").blur()
        observe()
        _apply_coupon(page)
        observe()
        page.locator("#remove-coupon").click()
        observe()
        _apply_coupon(page)
        observe()
        page.locator("#reset-demo").click()
        observe()
    except Exception as exc:
        label = QUANTITY_COUPON_EXPECTATIONS[len(observations)][0]
        raise RuntimeError(f"{label}: {str(exc).splitlines()[0]}") from exc

    return FlowResult(
        "quantity_coupon",
        tuple(observations) == QUANTITY_COUPON_EXPECTATIONS,
        _sequence_summary(QUANTITY_COUPON_EXPECTATIONS),
        _sequence_summary(observations),
    )


FLOWS: dict[str, Callable[[Page], FlowResult]] = {
    "initial_total": _initial,
    "single_coupon": _single_coupon,
    "reported_bug": _reported_bug,
    "remove_coupon": _remove_coupon,
    "quantity_coupon": _quantity_coupon,
}

FLOW_EXPECTATIONS: dict[str, tuple[str, str]] = {
    "initial_total": ("initial_total", "$100.00"),
    "single_coupon": ("single_coupon", "$80.00"),
    "reported_bug": ("repeated_coupon", "$80.00"),
    "remove_coupon": ("remove_coupon", "$100.00"),
    "quantity_coupon": ("quantity_coupon", _sequence_summary(QUANTITY_COUPON_EXPECTATIONS)),
}


def run_browser_flows(workspace: Path, flow_names: list[str]) -> list[FlowResult]:
    unknown = sorted(set(flow_names) - FLOWS.keys())
    if unknown:
        raise ValueError(f"Unknown browser flow: {', '.join(unknown)}")

    # Each flow gets its own page, so running a repeated name twice only costs time.
    flow_names = list(dict.fromkeys(flow_names))
    if not flow_names:
        raise ValueError("At least one browser flow is required")

    results: list[FlowResult] = []
    visual_browser = _visual_browser_enabled()
    with temporary_server(workspace) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not visual_browser,
            slow_mo=700 if visual_browser else 0,
        )
        try:
            for flow_name in flow_names:
                page = browser.new_page()
                page.set_default_timeout(FLOW_TIMEOUT_MS)
                try:
                    page.goto(url, wait_until="networkidle")
                    results.append(FLOWS[flow_name](page))
                    if visual_browser:
                        page.wait_for_timeout(2_000)
                except Exception as exc:  # noqa: BLE001 - a broken UI is a failed flow.
                    result_name, expected = FLOW_EXPECTATIONS[flow_name]
                    detail = str(exc).splitlines()[0] or type(exc).__name__
                    results.append(
                        FlowResult(
                            result_name,
                            False,
                            expected,
                            f"{type(exc).__name__}: {detail}",
                        )
                    )
                finally:
                    page.close()
        finally:
            browser.close()
    return results


def run_browser_flow(workspace: Path, flow_name: str) -> dict[str, object]:
    return asdict(run_browser_flows(workspace, [flow_name])[0])
