# Frontend debugging procedure

Use this procedure for bug-fixing work in a browser-based application.

1. Reproduce the reported behavior before changing code.
2. Identify the underlying state transition that produces the behavior.
3. Fix the root cause rather than only hiding the visible symptom.
4. Make the smallest reasonable change.
5. Add a regression test without weakening or deleting existing tests.
6. Test adjacent user flows that depend on the same state.
7. Report the change and the evidence supporting completion.

For this coupon scenario, the harness reproduces the `reported_bug` browser flow
before model work and supplies the current contents of `app.js`,
`tests/test_checkout.py`, and `tests/conftest.py`. Treat that evidence as
authoritative and do not spend turns repeating those reads or checks.

Applying an already-active coupon must be idempotent, and removing it must restore
the $100.00 base price. Derived display values must be calculated from canonical
inputs and state rather than stored as a second mutable source of truth. Submit a
coherent application and regression-test candidate instead of a sequence of small
line substitutions.

Add the regression test under a new descriptive filename such as
`tests/test_coupon_regression.py`. Follow the existing Playwright test style: use
the `checkout_page` fixture, `locator(...)`, and `inner_text()` or
`text_content()`. The regression must fail against the buggy starter and pass
against the candidate. A failed write tool call means no change occurred and must
not be reported as completed.
