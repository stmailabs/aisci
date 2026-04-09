"""AI Scientist tools for Claude Code skills package."""

from pathlib import Path

# Templates live inside the tools package (works for both pip install and local dev)
PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"

# Fallback: if templates aren't inside tools/ (e.g. running from cloned repo root)
if not TEMPLATES_DIR.exists():
    TEMPLATES_DIR = PACKAGE_ROOT.parent / "templates"
