import shutil
from pathlib import Path

from harness_demo.harness.policy import WritePolicy
from harness_demo.paths import STARTER_ROOT
from harness_demo.tools.patch import apply_unified_patch


def copy_starter(tmp_path: Path) -> Path:
    workspace = tmp_path / "checkout"
    shutil.copytree(STARTER_ROOT, workspace)
    return workspace


def test_patch_updates_allowed_app_file(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    patch = """--- a/app.js
+++ b/app.js
@@ -1,4 +1,4 @@
-const PRICE_CENTS = 10_000;
+const PRICE_CENTS = 20_000;
 const COUPON_CODE = "BUILD20";
 const DISCOUNT_RATE = 0.2;
 
"""

    result = apply_unified_patch(policy, patch)

    assert result["ok"] is True
    assert (
        workspace.joinpath("app.js")
        .read_text(encoding="utf-8")
        .startswith("const PRICE_CENTS = 20_000;")
    )


def test_patch_cannot_modify_protected_test(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    patch = """--- a/tests/test_checkout.py
+++ b/tests/test_checkout.py
@@ -1,1 +1,1 @@
-from playwright.sync_api import Page
+# weakened
"""

    result = apply_unified_patch(policy, patch)

    assert result["ok"] is False
    assert "protected" in str(result["error"])


def test_patch_can_create_new_regression_test(tmp_path: Path) -> None:
    workspace = copy_starter(tmp_path)
    policy = WritePolicy.harnessed(workspace)
    patch = """--- /dev/null
+++ b/tests/test_regression.py
@@ -0,0 +1,2 @@
+def test_regression():
+    assert True
"""

    result = apply_unified_patch(policy, patch)

    assert result["ok"] is True
    assert workspace.joinpath("tests/test_regression.py").read_text(encoding="utf-8") == (
        "def test_regression():\n    assert True\n"
    )
