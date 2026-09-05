from pathlib import Path


def load_skill(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required skill not found: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Required skill is empty: {path}")
    return content
