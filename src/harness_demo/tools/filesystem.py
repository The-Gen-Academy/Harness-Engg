from __future__ import annotations

from harness_demo.harness.policy import WritePolicy

TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".txt"}
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}


def list_files(policy: WritePolicy, relative_path: str) -> dict[str, object]:
    root = policy.resolve(relative_path)
    if not root.exists():
        return {"ok": False, "error": f"Path does not exist: {relative_path}"}
    if root.is_file():
        return {"ok": True, "files": [root.relative_to(policy.workspace).as_posix()]}

    files = [
        path.relative_to(policy.workspace).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not any(part in IGNORED_PARTS for part in path.parts)
    ]
    return {"ok": True, "files": sorted(files)[:200]}


def read_file(policy: WritePolicy, relative_path: str) -> dict[str, object]:
    target = policy.resolve(relative_path)
    if not target.is_file():
        return {"ok": False, "error": f"File does not exist: {relative_path}"}
    if target.stat().st_size > 100_000:
        return {"ok": False, "error": "File is too large for this demo tool"}
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "error": "Only UTF-8 text files can be read"}
    return {"ok": True, "path": relative_path, "content": content}


def search_code(policy: WritePolicy, query: str, relative_path: str) -> dict[str, object]:
    root = policy.resolve(relative_path)
    if not root.exists():
        return {"ok": False, "error": f"Path does not exist: {relative_path}"}

    candidates = [root] if root.is_file() else list(root.rglob("*"))
    matches: list[str] = []
    needle = query.casefold()
    for path in candidates:
        if (
            not path.is_file()
            or path.suffix not in TEXT_SUFFIXES
            or any(part in IGNORED_PARTS for part in path.parts)
        ):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, start=1):
            if needle in line.casefold():
                relative = path.relative_to(policy.workspace).as_posix()
                matches.append(f"{relative}:{number}: {line.strip()}")
                if len(matches) == 50:
                    return {"ok": True, "matches": matches, "truncated": True}
    return {"ok": True, "matches": matches, "truncated": False}
