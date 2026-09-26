# Harness-Engg

## Harness Engineering Demo

A small, presentation-oriented demonstration of the difference between:

1. A model that recommends a fix.
2. A coding agent that can inspect and change a repository.
3. A harnessed agent whose work is bounded and independently verified.

Every stage receives the exact same user prompt and base instructions. The only
differences are the capabilities and controls supplied by the environment.

The deliberately broken checkout sells an AI Engineering Workshop for $100.00 per
seat. The `BUILD20` coupon should apply a 20% discount exactly once, including when
seat quantity changes. The starter compounds the discount on repeated application
and drops the active discount when quantity changes. A duplicate-coupon guard alone
fixes the first symptom but leaves the second visible in the browser.

## Setup

```bash
uv sync
uv run playwright install chromium
cp .env.example .env
```

Then edit `.env`:

```dotenv
OPENAI_API_KEY=your-api-key
HARNESS_DEMO_MODEL=gpt-4o-mini-2024-07-18
HARNESS_DEMO_VISUAL_BROWSER=false
```

The CLI loads this file automatically. Existing shell environment variables
take precedence, so `HARNESS_DEMO_MODEL` can still be overridden for an
individual run.

Every stage intentionally uses the pinned `gpt-4o-mini-2024-07-18` snapshot. Holding the model fixed
across all three stages is what makes the demo's point: the improvement comes
from tools, feedback, skills, guardrails, and verification—not from swapping in
a stronger model. Strict function schemas constrain the shape of tool calls; the
harness still has to help the small model recover from semantically incorrect edits.

To watch the agent's Playwright checks in a visible, slowed-down Chromium window,
set `HARNESS_DEMO_VISUAL_BROWSER=true` in `.env`, or enable it for one run:

```bash
HARNESS_DEMO_VISUAL_BROWSER=true uv run harness-demo agent
```

Visual mode pauses for two seconds after each flow so the observed checkout total
is easy to see. It is disabled by default so automated runs remain fast and headless.

Check the environment:

```bash
uv run harness-demo doctor
```

## Presentation flow

In the first terminal, prepare and serve the checkout:

```bash
uv run harness-demo reset
uv run harness-demo serve
```

Open <http://127.0.0.1:8000>, enter `BUILD20`, and apply it twice. The total
incorrectly changes from $100.00 to $80.00 to $64.00.

Click **Reset demo**, apply the coupon once, then change **Seats** to 2 and leave
the field. The starter shows $200.00 even though the coupon is active; it should
show $160.00. Both stages receive these requirements explicitly:

| Action | Expected total |
| --- | --- |
| Apply BUILD20 to one seat | $80.00 |
| Change to two seats | $160.00 |
| Apply BUILD20 again | $160.00 |
| Remove the coupon | $200.00 |
| Reapply BUILD20 | $160.00 |
| Reset demo | $100.00, one seat, no coupon |

In a second terminal, run the three stages. Reset before each agent stage so
both start from the same code. Run the repair headless, then show the result in
a visible browser with `verify` before resetting. This keeps slow-motion browser
demonstration time out of the harness's 90-second repair budget:

```bash
uv run harness-demo llm

uv run harness-demo reset
HARNESS_DEMO_VISUAL_BROWSER=true uv run harness-demo agent
HARNESS_DEMO_VISUAL_BROWSER=false uv run harness-demo verify

uv run harness-demo reset
HARNESS_DEMO_VISUAL_BROWSER=true uv run harness-demo harness
HARNESS_DEMO_VISUAL_BROWSER=false uv run harness-demo verify
```

Run `verify` before resetting so it checks the candidate that stage produced.
See [What `harness-demo verify` does](#what-harness-demo-verify-does) for its checks,
results, and relationship to the harness.

For the live lesson, show the agent's result and its verification, then reset and
show the harness's checks and any revision. Both stages use the same pinned small
model and have at most 16 model turns and 16 tool calls. The harness allocates its
budget across two attempts and also supplies reads and browser feedback outside
those model/tool budgets. The ordinary agent can call the browser checks itself.
The visible starter tests cover the basic flows; they are intentionally incomplete.

Rehearse paired runs before presenting. This scenario exposes a plausible partial
fix; it does not force the agent to fail or guarantee harness success. If both
pass, report that result. Keep a recording of an actual failure-and-recovery pair
as a clearly labeled fallback for a live demonstration.

Run artifacts are written under `.runs/<run-id>/`. The working copy is isolated
under `.workspaces/checkout/`; the checked-in starter is never modified.

## What `harness-demo verify` does

`verify` answers: **Does the current checkout pass the demo's browser checks?**
It uses Playwright to operate the code in `.workspaces/checkout/` and compare the
displayed results with fixed expectations. It makes no model calls and requires
no API key, so the same checks can assess an ordinary agent's fix, a harnessed
agent's fix, or a manual edit.

| Browser flow | What it checks |
| --- | --- |
| `reported_bug` (printed as `repeated_coupon`) | Apply BUILD20 twice to one seat; the total must remain $80.00. |
| `remove_coupon` | Apply then remove BUILD20 from one seat; the total must return to $100.00. |
| `quantity_coupon` | Apply → change to two seats → apply again → remove → reapply → reset. Totals must be $80 → $160 → $160 → $200 → $160 → $100. |

The quantity flow also checks seat count, subtotal, and discount at every step.
After reset, the coupon input must be empty and the Remove coupon button hidden.
Every intermediate result must match; a correct final reset cannot hide an earlier
wrong total. These are specific acceptance flows, not an exhaustive test of every
supported quantity or possible interaction.

Run from the repository root after either repair stage:

```bash
# Run without opening a visible window.
HARNESS_DEMO_VISUAL_BROWSER=false uv run harness-demo verify

# Watch the same checks in a slowed-down Chromium window.
HARNESS_DEMO_VISUAL_BROWSER=true uv run harness-demo verify
```

Playwright's Chromium must be installed (`uv run playwright install chromium`).
The command starts its own temporary local server and opens a fresh page for each
flow; `harness-demo serve` does not need to be running. It checks files on disk,
not the current state of a tab you already have open. Existing checkout files are
preserved. If the workspace is missing, it is initialized from the buggy starter.

The terminal prints a pass or failure with expected and observed values for each
flow. Exit code **0** means all three flows passed; **1** means a check failed.
Failure is expected when checking the untouched buggy starter. Each completed run
saves evidence in `.runs/<timestamp>-verify/`:

- `summary.json`: overall `passed`/`failed` status and individual check results.
- `events.jsonl`: verification events with expected and observed values.
- `patch.diff`: the current workspace's changes relative to the starter; this
  records the candidate being checked and does not apply a patch.

**Verification reports behavior; the harness uses failures to drive another repair.**
Running `verify` does not fix code, roll back changes, or send feedback to an agent.
The harness runs the same browser checks automatically inside its completion gate
and can reject a candidate and request a revision. That gate additionally runs
pytest and checks protected tests, regression-test effectiveness, pricing
architecture, and the changed-file limit. Standalone `verify` does not perform
those extra checks, so passing it is not the same as full harness approval.

## What the harness adds

- A reusable frontend debugging skill.
- A write policy that protects existing tests and project configuration.
- Harness-owned reproduction plus prerequisite reads supplied before model work.
- An atomic candidate tool that writes the app and regression test together and returns its diff.
- Fresh model context, eight model turns, and eight tool calls per attempt; one revision and a
  90-second run budget.
- Batched independent browser acceptance checks for repeated application, removal,
  and the full quantity/coupon sequence. Test implementations remain outside the
  workspace; requirements are shared with both stages.
- Transactional candidates that are saved and rolled back when rejected.
- A completion gate that checks behavior, derived-state architecture, and whether the new test
  fails on the buggy starter, plus persistent evidence (`events.jsonl`, `summary.json`,
  `patch.diff`, and `attempt-N.diff`).

The action log intentionally displays tool calls and outcomes rather than the
model's private reasoning. Its JSONL events retain structured tool arguments,
results, and final work summaries so failed edits can be diagnosed after a run.

The shared user request is stored once in `prompts/task.md`; both `llm` and
`agent`/`harness` load that same file.
