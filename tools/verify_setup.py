"""Verify all prerequisites for AI Scientist Skills.

Run after cloning to ensure the environment is ready:
    python tools/verify_setup.py
"""

from __future__ import annotations

import importlib
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CHECK = f"{GREEN}\u2713{RESET}"
CROSS = f"{RED}\u2717{RESET}"
WARN = f"{YELLOW}!{RESET}"


# pip name -> import name (only for packages where they differ)
IMPORT_MAP = {
    "PyMuPDF": "fitz",
    "pyyaml": "yaml",
    "pymupdf4llm": "pymupdf4llm",
    "scikit-learn": "sklearn",
    "Pillow": "PIL",
}


def parse_requirements() -> list[tuple[str, str]]:
    """Read requirements.txt and return (pip_name, import_name) pairs."""
    req_file = Path(__file__).resolve().parent.parent / "requirements.txt"
    packages = []
    if not req_file.exists():
        print(f"  {WARN} requirements.txt not found, skipping package check")
        return packages
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # strip version specifiers: torch>=2.0 -> torch
        name = re.split(r"[><=!~\[]", line)[0].strip()
        imp = IMPORT_MAP.get(name, name)
        packages.append((name, imp))
    return packages


def check_python() -> bool:
    v = sys.version_info
    ok = v >= (3, 11)
    status = CHECK if ok else CROSS
    print(f"  {status} Python {v.major}.{v.minor}.{v.micro}", end="")
    if not ok:
        print(f"  (requires 3.11+)", end="")
    print()
    return ok


def check_package(name: str, import_name: str | None = None) -> bool:
    mod = import_name or name
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", "ok")
        print(f"  {CHECK} {name} {ver}")
        return True
    except ImportError:
        print(f"  {CROSS} {name}  (pip install {name})")
        return False


def check_torch_device() -> bool:
    try:
        import torch

        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            print(f"  {CHECK} PyTorch device: cuda ({gpu})")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print(f"  {CHECK} PyTorch device: mps (Apple Silicon)")
        else:
            print(f"  {WARN} PyTorch device: cpu (GPU not detected, experiments will be slower)")
        return True
    except ImportError:
        print(f"  {CROSS} PyTorch not installed")
        return False


def check_latex() -> tuple[bool, bool]:
    pdflatex = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")

    if pdflatex:
        print(f"  {CHECK} pdflatex ({pdflatex})")
    else:
        hint = "brew install --cask basictex" if platform.system() == "Darwin" else "sudo apt install texlive-full"
        print(f"  {CROSS} pdflatex not found  ({hint})")

    if bibtex:
        print(f"  {CHECK} bibtex ({bibtex})")
    else:
        print(f"  {CROSS} bibtex not found")

    return pdflatex is not None, bibtex is not None


def check_s2_api() -> bool:
    """Check Semantic Scholar API availability."""
    has_key = bool(os.environ.get("S2_API_KEY"))
    if has_key:
        print(f"  {CHECK} S2_API_KEY is set")
    else:
        print(f"  {WARN} S2_API_KEY not set — citation search will fall back to WebSearch")
        print(f"      Get a free key at https://www.semanticscholar.org/product/api#api-key")
    return has_key


def check_claude_code() -> bool:
    claude = shutil.which("claude")
    if claude:
        print(f"  {CHECK} Claude Code CLI ({claude})")
        return True
    else:
        print(f"  {CROSS} Claude Code CLI not found  (https://claude.ai/claude-code)")
        return False


def main():
    print()
    print("AI Scientist Skills — Environment Check")
    print("=" * 42)

    errors = 0
    warnings = 0

    # Python version
    print("\n[Python]")
    if not check_python():
        errors += 1

    # Core packages — read from requirements.txt
    print("\n[Python Packages]")
    packages = parse_requirements()
    for name, imp in packages:
        if not check_package(name, imp):
            errors += 1

    # Device
    print("\n[Compute Device]")
    check_torch_device()

    # LaTeX
    print("\n[LaTeX]")
    pdf_ok, bib_ok = check_latex()
    if not pdf_ok or not bib_ok:
        warnings += 1
        print(f"  {WARN} LaTeX is needed for paper writeup (skip with --skip-writeup)")

    # Literature search
    print("\n[Literature Search]")
    if not check_s2_api():
        warnings += 1

    # Claude Code
    print("\n[Claude Code]")
    if not check_claude_code():
        errors += 1

    # Summary
    print("\n" + "=" * 42)
    if errors == 0 and warnings == 0:
        print(f"{CHECK} All checks passed. Ready to go!")
    elif errors == 0:
        print(f"{WARN} {warnings} warning(s) — functional but some features limited.")
    else:
        print(f"{CROSS} {errors} error(s) found. Fix them before running.")
    print()

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
