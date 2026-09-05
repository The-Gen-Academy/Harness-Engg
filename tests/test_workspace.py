from pathlib import Path

from harness_demo.workspace import WorkspaceCheckpoint


def test_checkpoint_restores_uncommitted_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    workspace.mkdir()
    app = workspace / "app.js"
    app.write_text("before\n", encoding="utf-8")

    with WorkspaceCheckpoint(workspace):
        app.write_text("after\n", encoding="utf-8")
        (workspace / "new.txt").write_text("candidate\n", encoding="utf-8")

    assert app.read_text(encoding="utf-8") == "before\n"
    assert not workspace.joinpath("new.txt").exists()


def test_checkpoint_keeps_committed_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    workspace.mkdir()
    app = workspace / "app.js"
    app.write_text("before\n", encoding="utf-8")

    with WorkspaceCheckpoint(workspace) as checkpoint:
        app.write_text("after\n", encoding="utf-8")
        checkpoint.commit()

    assert app.read_text(encoding="utf-8") == "after\n"
