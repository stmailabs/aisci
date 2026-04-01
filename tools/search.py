"""Literature search utilities.

Provides two backends:
1. Semantic Scholar API (S2) — requires S2_API_KEY env var for higher rate limits,
   returns structured data with bibtex citations.
2. Fallback mode — when no S2 key is available, the Claude Code skill should use
   the built-in WebSearch tool instead (handled at the skill layer).

Adapted from AI-Scientist-v2/ai_scientist/tools/semantic_scholar.py.
"""

import json
import os
import sys
import time
import warnings
from typing import Dict, List, Optional

import backoff
import requests


# ── Backoff callback ─────────────────────────────────────────────────────────


def _on_backoff(details: Dict) -> None:
    print(
        f"Backing off {details['wait']:0.1f}s after {details['tries']} tries "
        f"calling {details['target'].__name__} at {time.strftime('%X')}",
        file=sys.stderr,
    )


# ── Semantic Scholar API ─────────────────────────────────────────────────────


S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "title,authors,venue,year,abstract,citationCount,citationStyles"
S2_FIELDS_BASIC = "title,authors,venue,year,abstract,citationCount"


def has_s2_api_key() -> bool:
    """Check if a Semantic Scholar API key is configured."""
    return bool(os.getenv("S2_API_KEY"))


@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
    max_tries=5,
    on_backoff=_on_backoff,
)
def search_papers_s2(
    query: str,
    limit: int = 10,
    include_bibtex: bool = True,
) -> Optional[List[Dict]]:
    """Search Semantic Scholar for papers.

    Parameters
    ----------
    query : str
        Search query string.
    limit : int
        Maximum number of results.
    include_bibtex : bool
        Whether to request bibtex citation styles.

    Returns
    -------
    list[dict] | None
        List of paper dicts sorted by citation count (descending),
        or None if no results.
    """
    if not query:
        return None

    headers = {}
    api_key = os.getenv("S2_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key

    fields = S2_FIELDS if include_bibtex else S2_FIELDS_BASIC

    rsp = requests.get(
        f"{S2_API_BASE}/paper/search",
        headers=headers,
        params={"query": query, "limit": limit, "fields": fields},
    )
    rsp.raise_for_status()
    results = rsp.json()

    if not results.get("total", 0):
        return None

    papers = results.get("data", [])
    papers.sort(key=lambda x: x.get("citationCount", 0), reverse=True)

    # Brief rate-limit courtesy pause
    time.sleep(1.0)
    return papers


def get_bibtex(paper: Dict) -> Optional[str]:
    """Extract bibtex string from a paper dict (S2 citationStyles field)."""
    styles = paper.get("citationStyles", {})
    return styles.get("bibtex")


# ── Formatting ───────────────────────────────────────────────────────────────


def format_papers_for_context(papers: List[Dict], max_papers: int = 10) -> str:
    """Format a list of papers into a human-readable string for LLM context."""
    if not papers:
        return "No papers found."

    parts = []
    for i, paper in enumerate(papers[:max_papers]):
        authors = ", ".join(
            a.get("name", "Unknown") for a in paper.get("authors", [])
        )
        bibtex = get_bibtex(paper)
        bibtex_line = f"\nBibTeX: {bibtex}" if bibtex else ""
        parts.append(
            f"{i + 1}. {paper.get('title', 'Unknown Title')}\n"
            f"   Authors: {authors}\n"
            f"   Venue: {paper.get('venue', 'N/A')}, {paper.get('year', 'N/A')}\n"
            f"   Citations: {paper.get('citationCount', 'N/A')}\n"
            f"   Abstract: {paper.get('abstract', 'No abstract available.')}"
            f"{bibtex_line}"
        )
    return "\n\n".join(parts)


def format_papers_json(papers: List[Dict], max_papers: int = 10) -> str:
    """Return papers as a compact JSON string."""
    simplified = []
    for p in papers[:max_papers]:
        simplified.append(
            {
                "title": p.get("title"),
                "authors": [a.get("name") for a in p.get("authors", [])],
                "year": p.get("year"),
                "venue": p.get("venue"),
                "citations": p.get("citationCount"),
                "abstract": p.get("abstract"),
                "bibtex": get_bibtex(p),
            }
        )
    return json.dumps(simplified, indent=2)


# ── Unified search entry point ───────────────────────────────────────────────


def search_papers(query: str, limit: int = 10) -> Optional[List[Dict]]:
    """Search for papers using the best available backend.

    Uses Semantic Scholar if S2_API_KEY is set; otherwise returns None
    (the caller — typically a Claude Code skill — should fall back to WebSearch).
    """
    if has_s2_api_key():
        return search_papers_s2(query, limit=limit, include_bibtex=True)

    # Attempt without key (lower rate limits)
    try:
        return search_papers_s2(query, limit=limit, include_bibtex=True)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            warnings.warn(
                "S2 rate limited and no S2_API_KEY set. "
                "The skill should use WebSearch as fallback."
            )
            return None
        raise


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search academic papers")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Output as JSON"
    )
    args = parser.parse_args()

    papers = search_papers(args.query, limit=args.limit)
    if papers:
        if args.as_json:
            print(format_papers_json(papers, max_papers=args.limit))
        else:
            print(format_papers_for_context(papers, max_papers=args.limit))
    else:
        print("No papers found. Try using WebSearch as fallback.")
