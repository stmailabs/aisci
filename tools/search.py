"""Literature search utilities.

Provides two backends:
1. Semantic Scholar API (S2) — requires S2_API_KEY env var for higher rate limits,
   returns structured data with bibtex citations.
2. Fallback mode — when no S2 key is available, the Claude Code skill should use
   the built-in WebSearch tool instead (handled at the skill layer).
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


def check_s2_api() -> Dict:
    """Check Semantic Scholar API availability and return status info."""
    result = {"has_key": has_s2_api_key(), "reachable": False, "rate_limited": False}
    try:
        headers = {}
        api_key = os.getenv("S2_API_KEY")
        if api_key:
            headers["X-API-KEY"] = api_key
        rsp = requests.get(
            f"{S2_API_BASE}/paper/search",
            headers=headers,
            params={"query": "test", "limit": 1, "fields": "title"},
            timeout=10,
        )
        if rsp.status_code == 200:
            result["reachable"] = True
        elif rsp.status_code == 429:
            result["reachable"] = True
            result["rate_limited"] = True
        else:
            result["error"] = f"HTTP {rsp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    return result


def search_papers(query: str, limit: int = 10) -> Optional[List[Dict]]:
    """Search for papers using the best available backend.

    Tries Semantic Scholar first. On failure (rate limit, network error,
    no results), returns None so the caller can fall back to WebSearch.
    """
    try:
        papers = search_papers_s2(query, limit=limit, include_bibtex=True)
        if papers:
            return papers
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 429:
            print("S2 rate limited — use WebSearch as fallback.", file=sys.stderr)
        else:
            print(f"S2 error (HTTP {status}) — use WebSearch as fallback.", file=sys.stderr)
    except Exception as e:
        print(f"S2 unavailable ({e}) — use WebSearch as fallback.", file=sys.stderr)
    return None


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search academic papers")
    sub = parser.add_subparsers(dest="command")

    # Default: search (also works without subcommand for backward compat)
    parser.add_argument("query", nargs="?", type=str, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Output as JSON"
    )

    # check: test S2 API connectivity
    sub.add_parser("check", help="Check S2 API availability")

    args = parser.parse_args()

    if args.command == "check":
        status = check_s2_api()
        print(json.dumps(status, indent=2))
        if not status["reachable"]:
            print("\nS2 API is not reachable. Citation search will use WebSearch.", file=sys.stderr)
        elif status["rate_limited"] and not status["has_key"]:
            print("\nS2 API is rate-limited without API key.", file=sys.stderr)
            print("Set S2_API_KEY for reliable citation search, or rely on WebSearch.", file=sys.stderr)
        elif status["has_key"] and status["reachable"]:
            print("\nS2 API is ready with API key.", file=sys.stderr)
        else:
            print("\nS2 API is reachable (no key, lower rate limits).", file=sys.stderr)
    elif args.query:
        papers = search_papers(args.query, limit=args.limit)
        if papers:
            if args.as_json:
                print(format_papers_json(papers, max_papers=args.limit))
            else:
                print(format_papers_for_context(papers, max_papers=args.limit))
        else:
            print("No results from S2. Use WebSearch as fallback.", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
