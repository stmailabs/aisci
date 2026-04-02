"""LaTeX compilation utilities.

Wraps pdflatex + bibtex for paper generation.
Cross-platform: works on Mac (BasicTeX/MacTeX) and Linux (texlive).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def find_pdflatex() -> Optional[str]:
    """Find the pdflatex binary."""
    return shutil.which("pdflatex")


def find_bibtex() -> Optional[str]:
    """Find the bibtex binary."""
    return shutil.which("bibtex")


def check_latex_installed() -> Dict[str, bool]:
    """Check which LaTeX tools are installed."""
    return {
        "pdflatex": find_pdflatex() is not None,
        "bibtex": find_bibtex() is not None,
        "chktex": shutil.which("chktex") is not None,
    }


def compile_latex(
    latex_dir: str,
    main_file: str = "template.tex",
    timeout: int = 60,
    num_passes: int = 4,
) -> Tuple[bool, Optional[str], List[str]]:
    """Compile a LaTeX document to PDF.

    Runs pdflatex multiple times (for cross-references) and bibtex.

    Parameters
    ----------
    latex_dir : str
        Directory containing the .tex file.
    main_file : str
        Name of the main .tex file.
    timeout : int
        Timeout for each compilation pass in seconds.
    num_passes : int
        Number of pdflatex passes (default 4 for proper cross-refs).

    Returns
    -------
    (success, pdf_path, errors)
        success : bool
        pdf_path : str | None — path to the generated PDF
        errors : list[str] — list of error messages
    """
    latex_path = Path(latex_dir).resolve()
    tex_path = latex_path / main_file
    errors = []

    if not tex_path.exists():
        return False, None, [f"TeX file not found: {tex_path}"]

    pdflatex = find_pdflatex()
    bibtex = find_bibtex()

    if not pdflatex:
        return False, None, ["pdflatex not found. Install MacTeX/texlive."]

    base_name = main_file.rsplit(".", 1)[0]
    pdf_path = latex_path / f"{base_name}.pdf"

    common_args = [
        pdflatex,
        "-interaction=nonstopmode",
        "-file-line-error",
        main_file,
    ]

    # Pass 1: initial compilation
    for pass_num in range(1, num_passes + 1):
        try:
            result = subprocess.run(
                common_args,
                cwd=str(latex_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                # Extract error lines
                for line in result.stdout.splitlines():
                    if line.startswith("!") or "Error" in line:
                        errors.append(f"Pass {pass_num}: {line.strip()}")
        except subprocess.TimeoutExpired:
            errors.append(f"Pass {pass_num}: pdflatex timed out after {timeout}s")
            return False, None, errors

        # Run bibtex after first pass
        if pass_num == 1 and bibtex:
            bib_file = latex_path / f"{base_name}.aux"
            if bib_file.exists():
                try:
                    subprocess.run(
                        [bibtex, base_name],
                        cwd=str(latex_path),
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                except subprocess.TimeoutExpired:
                    errors.append("bibtex timed out")

    success = pdf_path.exists()
    return success, str(pdf_path) if success else None, errors


def check_page_count(pdf_path: str) -> Optional[int]:
    """Count pages in a PDF file."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except ImportError:
        # Fallback: use pdfinfo if available
        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            try:
                result = subprocess.run(
                    [pdfinfo, pdf_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.splitlines():
                    if line.startswith("Pages:"):
                        return int(line.split(":")[1].strip())
            except Exception:
                pass
    return None


def check_latex_errors(latex_dir: str, main_file: str = "template.tex") -> List[str]:
    """Run chktex on a LaTeX file and return warnings/errors."""
    chktex = shutil.which("chktex")
    if not chktex:
        return []

    latex_path = Path(latex_dir).resolve()
    tex_path = latex_path / main_file

    if not tex_path.exists():
        return [f"File not found: {tex_path}"]

    try:
        result = subprocess.run(
            [chktex, "-q", str(tex_path)],
            cwd=str(latex_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        issues = []
        for line in result.stderr.splitlines() + result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("ChkTeX"):
                issues.append(line)
        return issues
    except Exception as e:
        return [f"chktex error: {e}"]


def setup_latex_dir(
    target_dir: str,
    template_type: str = "icbinb",
    templates_base: Optional[str] = None,
) -> str:
    """Copy a LaTeX template to the target directory.

    Parameters
    ----------
    target_dir : str
        Destination directory for the LaTeX files.
    template_type : str
        "icbinb" (4-page) or "icml" (8-page).
    templates_base : str | None
        Base directory containing templates. Defaults to templates/latex/.

    Returns
    -------
    str
        Path to the target LaTeX directory.
    """
    if templates_base is None:
        templates_base = str(Path(__file__).parent.parent / "templates" / "latex")

    src = Path(templates_base) / template_type
    dst = Path(target_dir)

    if not src.exists():
        raise FileNotFoundError(f"Template not found: {src}")

    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        dest_item = dst / item.name
        if item.is_file():
            shutil.copy2(str(item), str(dest_item))
        elif item.is_dir():
            if dest_item.exists():
                shutil.rmtree(str(dest_item))
            shutil.copytree(str(item), str(dest_item))

    return str(dst)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="LaTeX compilation utilities")
    sub = parser.add_subparsers(dest="command")

    # compile
    compile_p = sub.add_parser("compile", help="Compile LaTeX to PDF")
    compile_p.add_argument("latex_dir", help="Directory with .tex files")
    compile_p.add_argument("--main", default="template.tex", help="Main .tex file")
    compile_p.add_argument("--timeout", type=int, default=60)

    # check
    check_p = sub.add_parser("check", help="Check LaTeX installation")

    # setup
    setup_p = sub.add_parser("setup", help="Copy template to target directory")
    setup_p.add_argument("target_dir", help="Target directory")
    setup_p.add_argument("--type", default="icbinb", choices=["icbinb", "icml"])

    # pages
    pages_p = sub.add_parser("pages", help="Count PDF pages")
    pages_p.add_argument("pdf_path", help="Path to PDF")

    args = parser.parse_args()

    if args.command == "compile":
        success, pdf_path, errors = compile_latex(
            args.latex_dir, args.main, args.timeout
        )
        result = {"success": success, "pdf_path": pdf_path, "errors": errors}
        print(json.dumps(result, indent=2))

    elif args.command == "check":
        info = check_latex_installed()
        print(json.dumps(info, indent=2))

    elif args.command == "setup":
        path = setup_latex_dir(args.target_dir, args.type)
        print(f"Template copied to: {path}")

    elif args.command == "pages":
        count = check_page_count(args.pdf_path)
        print(f"Pages: {count}")

    else:
        parser.print_help()
