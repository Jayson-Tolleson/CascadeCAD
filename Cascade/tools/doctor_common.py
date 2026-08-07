from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    "venv",
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".cache",
    "tools",
}

def find_files(root: Path, suffix: str):
    files = []

    if not root.exists():
        return files

    for path in root.rglob(f"*{suffix}"):

        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue

        files.append(path)

    return sorted(files)
