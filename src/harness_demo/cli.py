from __future__ import annotations

import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from harness_demo.agent_loop import AgentLoop, AgentSession
from harness_demo.browser import ACCEPTANCE_FLOWS, run_browser_flows
from harness_demo.events import EventRecorder
from harness_demo.harness.completion import decide_completion
from harness_demo.harness.evaluator import evaluate_workspace
from harness_demo.harness.policy import WritePolicy
from harness_demo.harness.skill_loader import load_skill
from harness_demo.model import DEFAULT_MODEL, OpenAIResponsesModel
from harness_demo.paths import SKILLS_ROOT, WORKSPACE_ROOT
from harness_demo.prompt import load_task_prompt
from harness_demo.server import serve_forever
from harness_demo.tools import ToolExecutor
from harness_demo.tools.executor import HARNESS_TOOL_NAMES
from harness_demo.workspace import WorkspaceCheckpoint, ensure_workspace, reset_workspace

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Demonstrate the progression from model to agent to harnessed agent.",
)
console = Console()

BASE_INSTRUCTIONS = """Work on the user's request. Use any tools made available to you.
Be concise and accurately distinguish between recommendations, actions, and verified outcomes.
Do not claim that you performed an action or check unless the environment confirms it. Do not
reveal private chain-of-thought; communicate through actions, outcomes, and a concise summary."""

HARNESS_RUN_TIMEOUT_SECONDS = 90
HARNESS_ATTEMPT_TOOL_CALLS = 8
HARNESS_ATTEMPT_MODEL_TURNS = 8
HARNESS_MAX_REVISIONS = 1


def _preloaded_context(files: list[tuple[str, str]]) -> str:
    """Render harness-supplied file contents for the model's next message."""
    if not files:
        return ""
    sections = [
        (
            "The harness has already read the files it requires before any write, so the "
            "required-read gate is satisfied. Their current contents are below; they are "
            "authoritative, so do not spend turns re-reading them."
        )
    ]
    sections.extend(f"--- {path} ---\n{content.rstrip()}" for path, content in files)
    return "\n\n".join(sections)


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY is not set.[/red] Add it to the repository's .env file.")
        raise typer.Exit(1)


def _show_run_dir(path: Path) -> None:
    console.print(f"\n[dim]Run artifacts: {path.relative_to(Path.cwd())}[/dim]")


@app.command()
def doctor() -> None:
    """Check prerequisites without making an API request."""
    checks: list[tuple[str, bool, str]] = []
    checks.append(("uv", shutil.which("uv") is not None, shutil.which("uv") or "not found"))
    checks.append(
        (
            "OpenAI key",
            bool(os.getenv("OPENAI_API_KEY")),
            (
                "loaded from the environment or .env"
                if os.getenv("OPENAI_API_KEY")
                else "missing in the environment and .env"
            ),
        )
    )
    checks.append(
        (
            "Model",
            True,
            os.getenv("HARNESS_DEMO_MODEL", DEFAULT_MODEL),
        )
    )

    browser_ok = False
    browser_detail = "not installed"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        browser_ok = True
        browser_detail = "Chromium launches"
    except Exception as exc:  # noqa: BLE001 - doctor must report optional browser failures.
        browser_detail = str(exc).splitlines()[0]
    checks.append(("Playwright", browser_ok, browser_detail))

    checks.append(
        (
            "Workspace",
            WORKSPACE_ROOT.exists(),
            "ready" if WORKSPACE_ROOT.exists() else "run: uv run harness-demo reset",
        )
    )

    table = Table(title="Harness demo doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in checks:
        table.add_row(name, "[green]ready[/green]" if ok else "[yellow]attention[/yellow]", detail)
    console.print(table)

    required = {"uv", "Playwright"}
    if any(not ok and name in required for name, ok, _ in checks):
        raise typer.Exit(1)


@app.command()
def reset() -> None:
    """Replace the generated checkout workspace with the known buggy starter."""
    workspace = reset_workspace()
    console.print(f"[green]✓[/green] Reset workspace: {workspace.relative_to(Path.cwd())}")


@app.command()
def serve(
    host: Annotated[
        str, typer.Option(help="Interface on which to serve the checkout")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port on which to serve the checkout")] = 8000,
) -> None:
    """Serve the current checkout workspace until interrupted."""
    workspace = ensure_workspace()
    console.print(f"Serving [bold]{workspace.relative_to(Path.cwd())}[/bold]")
    console.print(f"Open [link=http://{host}:{port}]http://{host}:{port}[/link] (Ctrl-C to stop)")
    serve_forever(workspace, host, port)


@app.command()
def verify() -> None:
    """Check the current checkout against the same browser requirements after either stage."""
    workspace = ensure_workspace()
    recorder = EventRecorder("verify", console)
    results = run_browser_flows(workspace, list(ACCEPTANCE_FLOWS))
    for result in results:
        recorder.emit(
            "verify",
            f"{result.name}: expected {result.expected}, observed {result.observed}",
            status="success" if result.passed else "failure",
            data=asdict(result),
        )
    passed = all(result.passed for result in results)
    run_dir = recorder.finalize(
        {
            "status": "passed" if passed else "failed",
            "checks": [asdict(result) for result in results],
        }
    )
    _show_run_dir(run_dir)
    if not passed:
        raise typer.Exit(1)


@app.command()
def llm() -> None:
    """Stage 1: ask a model for advice without tools or repository access."""
    _require_api_key()
    recorder = EventRecorder("llm", console)
    model = OpenAIResponsesModel()
    recorder.emit("model", f"Calling {model.model} with zero tools")
    try:
        response = model.respond(
            input_items=[{"role": "user", "content": load_task_prompt()}],
            instructions=BASE_INSTRUCTIONS,
        )
        answer = (response.output_text or "No text response returned.").strip()
        recorder.emit("model", "Returned a recommendation", status="success")
        console.print(Panel(Markdown(answer), title="Vanilla LLM response", border_style="cyan"))
        run_dir = recorder.finalize(
            {
                "status": "completed",
                "model": model.model,
                "tools_available": 0,
                "files_inspected": 0,
                "files_changed": 0,
                "verification": "none",
            }
        )
    except Exception as exc:
        recorder.emit("model", f"API call failed: {exc}", status="failure")
        run_dir = recorder.finalize({"status": "failed", "error": str(exc)})
        _show_run_dir(run_dir)
        raise typer.Exit(1) from exc
    _show_run_dir(run_dir)


def _run_agent_stage(*, harnessed: bool) -> None:
    _require_api_key()
    workspace = ensure_workspace()
    stage = "harness" if harnessed else "agent"
    recorder = EventRecorder(stage, console)
    model = OpenAIResponsesModel()
    policy = WritePolicy.harnessed(workspace) if harnessed else WritePolicy.basic(workspace)
    required_reads = (
        {"app.js", "tests/test_checkout.py", "tests/conftest.py"} if harnessed else None
    )

    instructions = BASE_INSTRUCTIONS
    if harnessed:
        skill_path = SKILLS_ROOT / "frontend-debugging" / "SKILL.md"
        skill = load_skill(skill_path)
        recorder.emit("harness", "Loaded skill: frontend-debugging", status="success")
        recorder.emit(
            "guardrail",
            "Writes limited to app files and new tests; existing tests protected",
            status="success",
        )
        instructions += f"\n\nFollow this required skill:\n\n{skill}"

    task = load_task_prompt()

    try:
        if not harnessed:
            tools = ToolExecutor(
                policy,
                recorder,
                max_calls=HARNESS_ATTEMPT_TOOL_CALLS * (HARNESS_MAX_REVISIONS + 1),
            )
            recorder.emit("model", f"Using {model.model} with {len(tools.schemas)} tools")
            loop = AgentLoop(
                model,
                tools,
                recorder,
                instructions=instructions,
                max_model_turns=HARNESS_ATTEMPT_MODEL_TURNS * (HARNESS_MAX_REVISIONS + 1),
            )
            session = AgentSession()
            session = loop.run(task, session)
            console.print(
                Panel(Markdown(session.final_text), title="Agent summary", border_style="cyan")
            )
            run_dir = recorder.finalize(
                {
                    "status": "completed",
                    "model": model.model,
                    "tool_calls": tools.call_count,
                    "model_turns": session.model_turns,
                    "completion_authority": "agent",
                }
            )
            _show_run_dir(run_dir)
            return

        max_revisions = HARNESS_MAX_REVISIONS
        evaluation = None
        deadline = time.monotonic() + HARNESS_RUN_TIMEOUT_SECONDS
        total_tool_calls = 0
        total_model_turns = 0
        session = AgentSession()
        rejected_patch = ""

        reproductions = run_browser_flows(workspace, ["reported_bug", "quantity_coupon"])
        reproduction_details = []
        for result in reproductions:
            detail = f"{result.name}: expected {result.expected}, observed {result.observed}"
            reproduction_details.append(detail)
            recorder.emit(
                "harness",
                f"Checked reported behavior before model work: {detail}",
                status="success" if not result.passed else "warning",
                data=asdict(result),
            )
        reproduction_context = (
            "The harness already checked both reported browser flows before this attempt:\n"
            + "\n".join(reproduction_details)
            + "\nDo not spend a turn reproducing them again."
        )

        with WorkspaceCheckpoint(workspace) as checkpoint:
            assert checkpoint.snapshot is not None
            for revision in range(max_revisions + 1):
                if time.monotonic() >= deadline:
                    recorder.emit(
                        "complete",
                        f"Not approved: {HARNESS_RUN_TIMEOUT_SECONDS}-second time budget exhausted",
                        status="warning",
                    )
                    break

                tools = ToolExecutor(
                    policy,
                    recorder,
                    max_calls=HARNESS_ATTEMPT_TOOL_CALLS,
                    required_reads=required_reads,
                    allowed_tools=HARNESS_TOOL_NAMES,
                )
                recorder.emit(
                    "model",
                    (
                        f"Attempt {revision + 1}: using {model.model} with "
                        f"{len(tools.schemas)} tools and {HARNESS_ATTEMPT_TOOL_CALLS} tool calls"
                    ),
                )
                preloaded = tools.preload_required_reads()
                if preloaded:
                    recorder.emit(
                        "harness",
                        "Pre-loaded required reads off the turn budget: "
                        f"{', '.join(path for path, _ in preloaded)}",
                        status="success",
                    )
                if revision == 0:
                    message = f"{task}\n\n{reproduction_context}"
                else:
                    assert evaluation is not None
                    message = (
                        f"{task}\n\n{reproduction_context}\n\n"
                        "The previous candidate was rejected and the workspace was rolled back "
                        "to the clean checkpoint. This is a fresh model session: the rejected "
                        "candidate below is evidence, not the current workspace. Build a new "
                        "candidate that satisfies the whole checklist, then verify again:\n"
                        f"{evaluation.feedback()}\n"
                        "A failed tool call made no change; report only confirmed actions.\n\n"
                        "Rejected candidate diff:\n"
                        f"{rejected_patch or '(candidate made no file changes)'}"
                    )
                context = _preloaded_context(preloaded)
                if context:
                    message = f"{message}\n\n{context}"
                loop = AgentLoop(
                    model,
                    tools,
                    recorder,
                    instructions=instructions,
                    max_model_turns=HARNESS_ATTEMPT_MODEL_TURNS,
                )
                session = loop.run(
                    message,
                    AgentSession(),
                    deadline=deadline,
                    required_first_tool="submit_candidate",
                )
                total_tool_calls += tools.call_count
                total_model_turns += session.model_turns

                recorder.emit("harness", "Running independent completion checks")
                evaluation = evaluate_workspace(workspace, recorder)
                attempt = revision + 1
                patch_path = recorder.capture_attempt_patch(attempt, checkpoint.snapshot, workspace)
                rejected_patch = patch_path.read_text(encoding="utf-8")[-20_000:]
                recorder.emit("harness", f"Saved candidate patch: attempt-{attempt}.diff")

                decision = decide_completion(evaluation, revision, max_revisions)
                recorder.emit(
                    "complete",
                    decision.message,
                    status="success" if decision.approved else "warning",
                )
                if decision.approved:
                    checkpoint.commit()
                    console.print(
                        Panel(
                            Markdown(session.final_text),
                            title="Harnessed agent summary",
                            border_style="green",
                        )
                    )
                    run_dir = recorder.finalize(
                        {
                            "status": "approved",
                            "model": model.model,
                            "tool_calls": total_tool_calls,
                            "model_turns": total_model_turns,
                            "revisions": revision,
                            "checks_passed": evaluation.passed,
                        }
                    )
                    _show_run_dir(run_dir)
                    return

                checkpoint.restore()
                recorder.emit(
                    "harness",
                    "Rejected candidate rolled back to the clean checkpoint",
                    status="warning",
                )

        failures = (
            evaluation.failures
            if evaluation is not None
            else [f"{HARNESS_RUN_TIMEOUT_SECONDS}-second time budget exhausted"]
        )
        run_dir = recorder.finalize(
            {
                "status": "not-approved",
                "model": model.model,
                "tool_calls": total_tool_calls,
                "model_turns": total_model_turns,
                "revisions": max_revisions,
                "failures": failures,
            }
        )
        _show_run_dir(run_dir)
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        recorder.emit(stage, f"Run failed: {type(exc).__name__}: {exc}", status="failure")
        run_dir = recorder.finalize({"status": "failed", "error": str(exc)})
        _show_run_dir(run_dir)
        raise typer.Exit(1) from exc


@app.command()
def agent() -> None:
    """Stage 2: run a basic tool-using coding agent."""
    _run_agent_stage(harnessed=False)


@app.command("harness")
def harness_command() -> None:
    """Stage 3: add a skill, policies, evaluation, and a completion gate."""
    _run_agent_stage(harnessed=True)


if __name__ == "__main__":
    app()
