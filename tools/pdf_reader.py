"""PDF text extraction for paper review.

Uses pymupdf4llm and pypdf for text extraction.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def extract_text(pdf_path: str, max_pages: Optional[int] = None) -> str:
    """Extract text from a PDF file.

    Tries pymupdf4llm first (better formatting), falls back to PyMuPDF plain text.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Try pymupdf4llm (Markdown-formatted output)
    try:
        import pymupdf4llm

        text = pymupdf4llm.to_markdown(str(path))
        if max_pages:
            # Rough page splitting by form feed or page markers
            pages = _split_pages(text)
            text = "\n\n".join(pages[:max_pages])
        return text
    except ImportError:
        pass

    # Fall back to PyMuPDF plain text
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        texts = []
        page_limit = max_pages or len(doc)
        for i in range(min(page_limit, len(doc))):
            texts.append(doc[i].get_text())
        doc.close()
        return "\n\n".join(texts)
    except ImportError:
        pass

    # Last resort: pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        texts = []
        page_limit = max_pages or len(reader.pages)
        for i in range(min(page_limit, len(reader.pages))):
            text = reader.pages[i].extract_text()
            if text:
                texts.append(text)
        return "\n\n".join(texts)
    except ImportError:
        raise ImportError(
            "No PDF library found. Install one of: pymupdf4llm, PyMuPDF, pypdf"
        )


def extract_sections(pdf_path: str) -> Dict[str, str]:
    """Extract and split a paper into sections.

    Returns a dict mapping section names to their content.
    """
    text = extract_text(pdf_path)
    sections = {}
    current_section = "preamble"
    current_content = []

    # Common section headers in academic papers
    section_patterns = [
        "abstract",
        "introduction",
        "related work",
        "background",
        "method",
        "methodology",
        "approach",
        "experimental setup",
        "experiments",
        "results",
        "discussion",
        "ablation",
        "conclusion",
        "references",
        "appendix",
    ]

    for line in text.splitlines():
        stripped = line.strip().lower()
        # Check if this line is a section header
        matched = False
        for pattern in section_patterns:
            if stripped == pattern or stripped.startswith(f"{pattern}:"):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = pattern
                current_content = []
                matched = True
                break
            # Also match numbered sections like "1 Introduction" or "## Introduction"
            cleaned = stripped.lstrip("#0123456789. ")
            if cleaned == pattern or cleaned.startswith(f"{pattern}:"):
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = pattern
                current_content = []
                matched = True
                break
        if not matched:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def get_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    try:
        import fitz

        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except ImportError:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except ImportError:
        pass

    return 0


def _split_pages(text: str) -> List[str]:
    """Split text by page boundaries (form feeds or markers)."""
    # Try form feed split
    pages = text.split("\f")
    if len(pages) > 1:
        return pages

    # Try common page markers
    import re

    pages = re.split(r"\n---+\s*Page\s+\d+\s*---+\n", text)
    if len(pages) > 1:
        return pages

    # Fall back to rough page estimate (~3000 chars per page)
    chunk_size = 3000
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="PDF text extraction")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--sections", action="store_true", help="Split into sections")
    parser.add_argument("--pages", type=int, default=None, help="Max pages to extract")
    parser.add_argument("--count", action="store_true", help="Just count pages")
    args = parser.parse_args()

    if args.count:
        print(get_page_count(args.pdf_path))
    elif args.sections:
        sections = extract_sections(args.pdf_path)
        for name, content in sections.items():
            print(f"\n{'='*60}")
            print(f"SECTION: {name}")
            print(f"{'='*60}")
            print(content[:500] + ("..." if len(content) > 500 else ""))
    else:
        text = extract_text(args.pdf_path, max_pages=args.pages)
        print(text)


if __name__ == "__main__":
    main()
