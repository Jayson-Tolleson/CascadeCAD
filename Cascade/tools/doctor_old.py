#!/usr/bin/env python3
"""
Doctor of Truth v0.1
Read-only engineering diagnostics for CascadeCAD.
"""

from pathlib import Path
import re
import sys

# ---------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

JS_DIR = ROOT / "webcad_xbf" / "static" / "js"
HTML_DIR = ROOT / "webcad_xbf" / "templates"
PY_ROOT = ROOT

# ---------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------

FETCH_RE = re.compile(r'fetch\s*\(')
CLICK_RE = re.compile(r'addEventListener\s*\(\s*[\'"]click|onclick\s*=', re.I)
ROUTE_RE = re.compile(r'@.*route\s*\(')

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

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
}


def find_files(root: Path, suffix: str):
    files = []

    if not root.exists():
        return files

    for path in root.rglob(f"*{suffix}"):

        # Skip anything inside excluded directories
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue

        files.append(path)

    return sorted(files)
# ---------------------------------------------------------------------
# JavaScript Scan
# ---------------------------------------------------------------------

def scan_js():

    files = find_files(JS_DIR, ".js")

    listeners = 0
    fetches = 0

    for file in files:

        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue

        listeners += len(CLICK_RE.findall(text))
        fetches += len(FETCH_RE.findall(text))

    return {
        "files": len(files),
        "listeners": listeners,
        "fetches": fetches,
    }

# ---------------------------------------------------------------------
# HTML Scan
# ---------------------------------------------------------------------

def scan_html():

    files = find_files(HTML_DIR, ".html")

    dialogs = 0

    for file in files:

        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue

        dialogs += text.lower().count("<dialog")
        dialogs += text.lower().count("modal")

    return {
        "files": len(files),
        "dialogs": dialogs,
    }

# ---------------------------------------------------------------------
# Python Scan
# ---------------------------------------------------------------------

def scan_python():

    pyfiles = find_files(PY_ROOT, ".py")

    routes = 0

    for file in pyfiles:

        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue

        routes += len(ROUTE_RE.findall(text))

    return {
        "files": len(pyfiles),
        "routes": routes,
    }

# ---------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------

def line(name, value):
    print(f"{name:<24}{value}")

def report():

    print()
    print("=" * 58)
    print("           CascadeCAD Doctor of Truth v0.1")
    print("=" * 58)

    js = scan_js()
    html = scan_html()
    py = scan_python()

    print()
    print("Repository")

    line("JavaScript Files", js["files"])
    line("Python Files", py["files"])
    line("HTML Templates", html["files"])

    print()
    print("Frontend")

    line("Click Listeners", js["listeners"])
    line("fetch() Calls", js["fetches"])
    line("Dialogs", html["dialogs"])

    print()
    print("Backend")

    line("Python Routes", py["routes"])

    print()
    print("=" * 58)
    print("Read-only mode")
    print("Doctor reports facts only.")
    print("=" * 58)

# ---------------------------------------------------------------------

if __name__ == "__main__":

    report()
