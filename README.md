# Harness-Engg

## Harness Engineering Demo

A small, presentation-oriented demonstration of the difference between:

1. A model that recommends a fix.
2. A coding agent that can inspect and change a repository.
3. A harnessed agent whose work is bounded and independently verified.

Every stage receives the exact same user prompt and base instructions. The only
differences are the capabilities and controls supplied by the environment.

The deliberately broken checkout sells an AI Engineering Workshop for $100.00.
The `BUILD20` coupon should apply a 20% discount exactly once, but the starter
application mutates the current total and compounds the discount.

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

In a second terminal, run the three stages. Reset before each agent stage so
both start from the same code:

```bash
uv run harness-demo llm

uv run harness-demo reset
uv run harness-demo agent

uv run harness-demo reset
uv run harness-demo harness
```

Run artifacts are written under `.runs/<run-id>/`. The working copy is isolated
under `.workspaces/checkout/`; the checked-in starter is never modified.

## What the harness adds

- A reusable frontend debugging skill.
- A write policy that protects existing tests and project configuration.
- Harness-owned reproduction plus prerequisite reads supplied before model work.
- An atomic candidate tool that writes the app and regression test together and returns its diff.
- Fresh model context, eight model turns, and eight tool calls per attempt; one revision and a
  90-second run budget.
- Batched independent browser acceptance checks hidden from the worker agent.
- Transactional candidates that are saved and rolled back when rejected.
- A completion gate that checks behavior, derived-state architecture, and whether the new test
  fails on the buggy starter, plus persistent evidence (`events.jsonl`, `summary.json`,
  `patch.diff`, and `attempt-N.diff`).

The action log intentionally displays tool calls and outcomes rather than the
model's private reasoning. Its JSONL events retain structured tool arguments,
results, and final work summaries so failed edits can be diagnosed after a run.

The shared user request is stored once in `prompts/task.md`; both `llm` and
`agent`/`harness` load that same file.
