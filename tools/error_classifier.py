"""Classify experiment failures into categories for pattern detection and auto-diagnosis."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


# Error category patterns — order matters (first match wins)
ERROR_PATTERNS = [
    ("CUDA_OOM", [
        r"CUDA out of memory",
        r"RuntimeError:.*out of memory",
        r"torch\.cuda\.OutOfMemoryError",
        r"CUDA error: out of memory",
    ]),
    ("MPS_OOM", [
        r"MPS backend out of memory",
        r"MPSNDArray.*out of memory",
    ]),
    ("SYSTEM_OOM", [
        r"Killed\s*$",
        r"MemoryError",
        r"Cannot allocate memory",
    ]),
    ("IMPORT_ERROR", [
        r"ModuleNotFoundError: No module named",
        r"ImportError: cannot import name",
        r"ImportError: No module named",
    ]),
    ("MISSING_DATA", [
        r"FileNotFoundError:.*\.(csv|json|jsonl|parquet|arrow|npy|npz|pt|pth|bin|safetensors)",
        r"DatasetNotFoundError",
        r"Dataset.*not found",
        r"No such file or directory.*data",
    ]),
    ("HF_DATASET_ERROR", [
        r"datasets\.exceptions",
        r"Could not find dataset.*on the Hub",
        r"DatasetGenerationError",
    ]),
    ("NETWORK_ERROR", [
        r"ConnectionError",
        r"requests\.exceptions\.ConnectionError",
        r"URLError",
        r"TimeoutError.*connection",
        r"Failed to establish a new connection",
    ]),
    ("TIMEOUT", [
        r"Timeout after \d+s",
        r"TimeoutExpired",
        r"subprocess\.TimeoutExpired",
    ]),
    ("SHAPE_MISMATCH", [
        r"shape.*must match|shape.*mismatch",
        r"size mismatch",
        r"The size of tensor .* must match",
        r"RuntimeError:.*shape",
        r"mat1 and mat2 shapes cannot be multiplied",
        r"Expected.*but got.*shape",
    ]),
    ("DEVICE_MISMATCH", [
        r"Expected all tensors to be on the same device",
        r"Expected.*device.*but got",
        r"RuntimeError:.*cuda.*cpu",
    ]),
    ("DTYPE_MISMATCH", [
        r"expected.*got.*dtype",
        r"Expected.*type.*but got",
        r"RuntimeError:.*dtype",
    ]),
    ("NAN_INF", [
        r"NaN|nan",
        r"Inf|inf",
        r"RuntimeError:.*nan",
        r"loss.*nan",
    ]),
    ("DIVIDE_BY_ZERO", [
        r"ZeroDivisionError",
        r"divide by zero",
    ]),
    ("INDEX_ERROR", [
        r"IndexError: .*out of range",
        r"IndexError: .*out of bounds",
        r"list index out of range",
    ]),
    ("KEY_ERROR", [
        r"KeyError:",
    ]),
    ("TYPE_ERROR", [
        r"TypeError:",
    ]),
    ("SYNTAX_ERROR", [
        r"SyntaxError:",
        r"IndentationError:",
    ]),
    ("API_AUTH_ERROR", [
        r"401.*Unauthorized",
        r"Invalid API key",
        r"Authentication failed",
        r"API token.*invalid",
    ]),
    ("RATE_LIMIT", [
        r"429.*Too Many Requests",
        r"RateLimitError",
        r"rate limit exceeded",
    ]),
    ("ASSERTION_ERROR", [
        r"AssertionError:",
    ]),
    ("ATTRIBUTE_ERROR", [
        r"AttributeError:.*has no attribute",
    ]),
    ("FILE_NOT_FOUND", [
        r"FileNotFoundError:",
        r"No such file or directory",
    ]),
    ("PERMISSION_ERROR", [
        r"PermissionError:",
        r"Permission denied",
    ]),
]


# Recommendations per error type
ERROR_RECOMMENDATIONS = {
    "CUDA_OOM": "Reduce batch_size, use gradient accumulation, enable mixed precision (fp16/bf16), or use a smaller model",
    "MPS_OOM": "Reduce batch_size or use smaller model. MPS has less memory than typical CUDA GPUs",
    "SYSTEM_OOM": "Reduce batch size or memory footprint. Consider processing data in chunks",
    "IMPORT_ERROR": "Install the missing package with: uv pip install <package>",
    "MISSING_DATA": "Verify dataset path. Check if dataset was downloaded or if path is relative vs absolute",
    "HF_DATASET_ERROR": "Check HuggingFace dataset name and availability. Try: datasets.load_dataset() with cache_dir",
    "NETWORK_ERROR": "Check internet connection. HuggingFace or S2 API may be unreachable. Retry or use cached data",
    "TIMEOUT": "Reduce dataset size, use fewer epochs, or increase timeout in config (exec.timeout)",
    "SHAPE_MISMATCH": "Check tensor dimensions. Add .shape prints before the failing operation. Verify model input/output dimensions match data",
    "DEVICE_MISMATCH": "Move all tensors to same device (e.g., .to(device)). Use device variable consistently throughout code",
    "DTYPE_MISMATCH": "Cast tensors to same dtype with .to(torch.float32) or .float(). Check model precision settings",
    "NAN_INF": "Check learning rate (often too high), loss function (check log/div by zero), input normalization, gradient clipping",
    "DIVIDE_BY_ZERO": "Add epsilon to denominators. Check for empty batches or zero-variance statistics",
    "INDEX_ERROR": "Check array/tensor bounds. Verify dataset size matches expected length. Check off-by-one errors",
    "KEY_ERROR": "Verify dictionary keys exist before access. Use .get() with defaults for optional keys",
    "TYPE_ERROR": "Check argument types. Verify input data types match function signatures",
    "SYNTAX_ERROR": "Code generation produced invalid Python. Retry with simpler approach",
    "API_AUTH_ERROR": "Check API key is set. For S2, set S2_API_KEY env var",
    "RATE_LIMIT": "Reduce request frequency. Wait and retry. Consider caching results",
    "ASSERTION_ERROR": "Generated code has failing assertion. Check assumption about data or model state",
    "ATTRIBUTE_ERROR": "Method/attribute does not exist on object. Check API version or typo in attribute name",
    "FILE_NOT_FOUND": "Verify file path. Check current working directory. File may need to be downloaded first",
    "PERMISSION_ERROR": "Check file/directory permissions. May need to run in user-writable directory",
    "UNKNOWN": "Manual investigation needed. Check the full execution log",
}


def classify_error(error_text: str) -> str:
    """Classify an error message into a category.

    Args:
        error_text: Full error message or traceback (can include exc_type + exc_info + stdout tail)

    Returns:
        Error category string (e.g., "CUDA_OOM", "SHAPE_MISMATCH", "UNKNOWN")
    """
    if not error_text:
        return "UNKNOWN"

    for category, patterns in ERROR_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, error_text, re.IGNORECASE):
                return category
    return "UNKNOWN"


def classify_node(node: dict) -> str:
    """Classify a buggy node's error.

    Combines exc_type, exc_info, and term_out (last N lines) into one search text.
    """
    if not node.get("is_buggy"):
        return "NOT_BUGGY"

    parts = []
    if node.get("exc_type"):
        parts.append(str(node["exc_type"]))
    if node.get("exc_info"):
        parts.append(str(node["exc_info"])[:1000])

    term_out = node.get("term_out", [])
    if isinstance(term_out, list):
        parts.extend(term_out[-30:])  # last 30 lines
    elif isinstance(term_out, str):
        parts.append("\n".join(term_out.strip().split("\n")[-30:]))

    analysis = node.get("analysis", "")
    if analysis:
        parts.append(str(analysis)[:500])

    text = "\n".join(parts)
    return classify_error(text)


def analyze_journal(journal: dict) -> dict:
    """Analyze a stage journal and return error distribution + recommendation.

    Returns:
        {
            "total_nodes": int,
            "buggy_nodes": int,
            "good_nodes": int,
            "error_distribution": {"CUDA_OOM": 12, "SHAPE_MISMATCH": 5, ...},
            "dominant_error": "CUDA_OOM" or None,
            "dominant_pct": float (0-1),
            "recommendation": str,
            "nodes_by_error": {"CUDA_OOM": ["node1", "node2"], ...}
        }
    """
    nodes = journal.get("nodes", [])
    error_counts = Counter()
    nodes_by_error = {}

    buggy = 0
    good = 0
    for node in nodes:
        if node.get("is_buggy"):
            buggy += 1
            category = classify_node(node)
            error_counts[category] += 1
            nodes_by_error.setdefault(category, []).append(node.get("id", "unknown"))
        else:
            good += 1

    total = len(nodes)
    dominant_error = None
    dominant_pct = 0.0
    recommendation = ""

    if error_counts:
        dominant_error, dominant_count = error_counts.most_common(1)[0]
        dominant_pct = dominant_count / total if total > 0 else 0
        recommendation = ERROR_RECOMMENDATIONS.get(dominant_error, "Manual investigation needed")

    return {
        "total_nodes": total,
        "buggy_nodes": buggy,
        "good_nodes": good,
        "error_distribution": dict(error_counts),
        "dominant_error": dominant_error,
        "dominant_pct": round(dominant_pct, 3),
        "recommendation": recommendation,
        "nodes_by_error": nodes_by_error,
    }


def should_auto_rescue(analysis: dict, threshold: float = 0.5) -> bool:
    """Decide if experiment should trigger automatic Octopus rescue.

    Rescue if:
    - >= threshold fraction of nodes have same error type
    - AND at least 3 nodes total (avoid rescue on 1-2 random failures)
    """
    if analysis["total_nodes"] < 3:
        return False
    return analysis["dominant_pct"] >= threshold


def main():
    parser = argparse.ArgumentParser(description="Classify experiment errors and analyze failure patterns")
    sub = parser.add_subparsers(dest="command")

    # classify: classify a single error message
    c_parser = sub.add_parser("classify", help="Classify a single error message")
    c_parser.add_argument("--text", help="Error text (or read from stdin)")
    c_parser.add_argument("--file", help="File containing error text")

    # analyze: analyze a journal file
    a_parser = sub.add_parser("analyze", help="Analyze a stage journal for error patterns")
    a_parser.add_argument("exp_dir", help="Experiment directory")
    a_parser.add_argument("stage", help="Stage name")

    args = parser.parse_args()

    if args.command == "classify":
        text = args.text
        if not text and args.file:
            text = Path(args.file).read_text()
        if not text:
            text = sys.stdin.read()
        category = classify_error(text)
        print(json.dumps({
            "category": category,
            "recommendation": ERROR_RECOMMENDATIONS.get(category, "")
        }, indent=2))

    elif args.command == "analyze":
        from tools.state_manager import load_journal
        journal = load_journal(args.exp_dir, args.stage)
        analysis = analyze_journal(journal)
        print(json.dumps(analysis, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
