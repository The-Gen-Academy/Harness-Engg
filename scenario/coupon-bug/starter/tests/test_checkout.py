from playwright.sync_api import Page


def total(page: Page) -> str:
    return page.locator("#total").inner_text()


def test_initial_total(checkout_page: Page) -> None:
    assert total(checkout_page) == "$100.00"


def test_valid_coupon_once(checkout_page: Page) -> None:
    checkout_page.locator("#coupon").fill("BUILD20")
    checkout_page.locator("#apply-coupon").click()
    assert total(checkout_page) == "$80.00"


def test_invalid_coupon_does_not_change_total(checkout_page: Page) -> None:
    checkout_page.locator("#coupon").fill("NOPE")
    checkout_page.locator("#apply-coupon").click()
    assert total(checkout_page) == "$100.00"
