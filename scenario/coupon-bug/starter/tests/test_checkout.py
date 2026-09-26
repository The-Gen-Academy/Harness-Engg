from playwright.sync_api import Page


def total(page: Page) -> str:
    return page.locator("#total").inner_text()


def test_initial_total(checkout_page: Page) -> None:
    assert total(checkout_page) == "$100.00"


def test_two_seats_without_coupon(checkout_page: Page) -> None:
    checkout_page.locator("#quantity").fill("2")
    checkout_page.locator("#quantity").press("Tab")
    assert checkout_page.locator("#subtotal").inner_text() == "$200.00"
    assert total(checkout_page) == "$200.00"


def test_valid_coupon_once(checkout_page: Page) -> None:
    checkout_page.locator("#coupon").fill("BUILD20")
    checkout_page.locator("#apply-coupon").click()
    assert total(checkout_page) == "$80.00"


def test_invalid_coupon_does_not_change_total(checkout_page: Page) -> None:
    checkout_page.locator("#coupon").fill("NOPE")
    checkout_page.locator("#apply-coupon").click()
    assert total(checkout_page) == "$100.00"
