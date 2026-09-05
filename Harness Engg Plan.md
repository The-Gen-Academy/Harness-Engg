I’d make the application deliberately tiny: one product, one coupon, and no real payment backend. The complexity should come from how the agent works, not from the checkout itself.

## **The checkout setup**

The page sells an “AI Engineering Workshop” for $100.

It contains:

* Coupon field  
* `Apply coupon` button  
* Subtotal, discount, and total  
* `Reset demo` button

Coupon: `BUILD20` for 20% off.

The bug:

* First application: $100 → $80  
* Second application: $80 → $64  
* Expected: total should remain $80

Underneath, the buggy implementation mutates the current total:

state.total \= state.total \* 0.8;

The correct implementation should store the coupon as state and derive the total from the subtotal each time.

The adjacent case is coupon removal: after applying the discount, removing it must restore the $100 total.

## **The mental model**

You can progressively introduce these pieces:

| Component | Role |
| ----- | ----- |
| Model | Reasons about the problem |
| Loop | Lets the model investigate, act, observe, and revise |
| Tools | Give it the ability to inspect and modify the application |
| Filesystem | Gives it a persistent, bounded environment to work in |
| Skill | Gives it a reusable way of approaching debugging |
| Guardrails | Define what it may change and what counts as completion |
| Tests/evals | Provide evidence that the problem is actually fixed |

Your larger message is:

> The model generates intelligence. The harness turns that intelligence into dependable work.

Use the pinned `gpt-4o-mini-2024-07-18` snapshot for all three stages. Choosing the same small, inexpensive
model makes the comparison more compelling: any improvement comes from the
harness around the model, not from upgrading the model itself.

## **Stage 1: The basic LLM call**

Start by showing the broken webpage. Apply `BUILD20` twice and let the audience see $64.

Then give the model:

* The user complaint  
* The coupon event handler  
* Perhaps one small code snippet

Shared prompt for every stage:

> Fix the coupon bug in this checkout website. The BUILD20 coupon should apply a 20% discount. Users report that the first application changes the total from $100 to $80, but applying it a second time incorrectly changes the total to $64. The total should remain $80.

The model produces a recommendation or code patch. It might:

* Disable the Apply button  
* Add an `isCouponApplied` boolean  
* Check whether the coupon was previously used  
* Rewrite the calculation correctly

The exact answer doesn’t matter. Your point is that it is only a suggestion. The model has not:

* Reproduced the issue  
* Seen the full application  
* Applied the change  
* Checked neighboring behavior  
* Proven that the fix works

Even if the answer is correct, it is unverified.

## **Stage 2: Add tools, filesystem, and a ReAct loop**

Now reset the codebase and give the model a small set of tools:

* `list_files`  
* `read_file`  
* `search_code`  
* `edit_file`  
* `browser_interact`  
* `run_tests`

Give it access to a small repository:

checkout-demo/  
├── index.html  
├── src/  
│   ├── cart.js  
│   ├── coupons.js  
│   └── ui.js  
└── tests/  
    └── cart.test.js

Use the exact same prompt as Stage 1. The difference is not better wording: this
time the environment supplies repository, browser, editing, and test tools.

Now make the ReAct loop visible:

Reason → Act → Observe → Revise

An example trace could be:

1\. Opened checkout page  
2\. Applied BUILD20 twice  
3\. Observed total: $64  
4\. Searched for BUILD20  
5\. Read src/coupons.js  
6\. Found total being mutated  
7\. Edited coupon state logic  
8\. Ran tests  
9\. Opened checkout again  
10\. Verified total remains $80

This is the first major jump:

> The LLM could describe a fix. The agent can now investigate and execute one.

But it still decides its own process. It could stop after testing only the exact reported path.

## **Stage 3: Add a debugging skill**

Introduce a simple `checkout-debugging` skill. Keep it generic enough that it doesn’t reveal the answer.

\# Frontend debugging procedure

1\. Reproduce the reported issue.  
2\. Identify the underlying state transition.  
3\. Fix the root cause, not only the visible symptom.  
4\. Make the smallest reasonable change.  
5\. Add a regression test.  
6\. Test adjacent user flows.  
7\. Report the change and supporting evidence.

Now the agent automatically loads this skill when given a bug-fixing task.

The visible trace becomes:

Loaded skill: frontend-debugging  
Current step: Reproduce the issue  
Current step: Inspect state transition  
Current step: Add regression coverage  
Current step: Verify adjacent flows

This gives you a strong explanation of skills:

> Tools describe what the agent can do. A skill describes how it should approach the work.

The skill could require these four cases:

* Applying the coupon once  
* Applying it twice  
* Removing the coupon

That covers the complete state transition without introducing extra pricing dimensions.

## **Stage 4: Add guardrails**

Keep the guardrails limited and easy to explain.

### **Filesystem boundary**

The agent works in an isolated checkout worktree. It cannot access files outside the repository.

### **Write boundary**

The agent may change:

* `src/cart.js`  
* `src/coupons.js`  
* New regression tests

It may not modify or delete existing tests.

### **Tool boundary**

Allow:

* Reading files  
* Editing approved files  
* Running the test command  
* Interacting with the local webpage

Block:

* Network calls  
* Package installation  
* Shell commands outside an allowlist

### **Completion boundary**

The agent cannot declare success unless:

* Existing tests pass  
* The new regression test passes  
* The browser verification succeeds  
* The final diff stays below a reasonable size

Use at most one revision and a 90-second run budget to demonstrate protection against runaway execution.

## **The best harness moment**

Have the first candidate apply a coherent idempotency guard and add a regression test.

The harness then checks both repeated application and coupon removal in one browser session.

That failure goes back into the loop:

Patch → Test → Failure → Revise → Test → Pass

The agent replaces the mutation-based logic with idempotent coupon state:

state.activeCoupon \= "BUILD20";

The final verification shows:

* Apply once: $80  
* Apply twice: still $80  
* Remove coupon: $100

This is where the harness becomes concrete. It didn’t merely prevent bad behavior. It helped the agent discover that its first fix was incomplete.

## **How to make it visual**

Use one browser page divided into two areas.

**Left: Live checkout**

The real page the agent is fixing. Changes appear immediately.

**Right: Agent run**

Show a clean event stream:

✓ Skill loaded  
✓ Bug reproduced  
✓ 3 files inspected  
✓ Patch applied  
✕ Verification failed  
↻ Revising patch  
✓ 4 tests passed  
✓ Browser verified

Across the top, have three modes:

1. LLM Call  
2. Tool-Using Agent  
3. Harnessed Agent

Reset to the same broken baseline before each mode. That makes the comparison fair and easy to follow.

## **A practical 20-minute flow**

* **0–2 minutes:** Show the webpage and reproduce the bug.  
* **2–6 minutes:** Make the basic LLM call and discuss what it cannot know.  
* **6–11 minutes:** Add tools, filesystem access, and the ReAct loop.  
* **11–16 minutes:** Load the debugging skill and run the structured workflow.  
* **16–18 minutes:** Show the guardrail or test rejecting an incomplete fix.  
* **18–20 minutes:** Show the revised page and summarize the layers.

I would avoid real payment APIs, databases, authentication, package installation, multiple products, or quantity controls. The idempotency regression is enough to demonstrate why harnesses matter without turning the demo into a checkout-system tutorial.
