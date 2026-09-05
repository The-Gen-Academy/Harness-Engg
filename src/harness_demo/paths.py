from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = PROJECT_ROOT / "scenario" / "coupon-bug"
STARTER_ROOT = SCENARIO_ROOT / "starter"
WORKSPACES_ROOT = PROJECT_ROOT / ".workspaces"
WORKSPACE_ROOT = WORKSPACES_ROOT / "checkout"
RUNS_ROOT = PROJECT_ROOT / ".runs"
PROMPTS_ROOT = PROJECT_ROOT / "prompts"
SKILLS_ROOT = PROJECT_ROOT / "skills"
