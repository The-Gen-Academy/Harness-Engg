from harness_demo.paths import PROMPTS_ROOT


def load_task_prompt() -> str:
    """Return the identical user prompt supplied to every demo stage."""
    return (PROMPTS_ROOT / "task.md").read_text(encoding="utf-8").strip()
