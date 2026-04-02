"""Metric parsing utilities.

Extracts performance metrics from experiment stdout/stderr output.
Supports both the simple {value, maximize, name} format and the new
structured {metric_names: [{metric_name, lower_is_better, data: [...]}]} format.
"""

import json
import re
import sys
from typing import Dict, List, Optional, Tuple


# ── Metric direction detection ───────────────────────────────────────────────

# Metrics where lower is better
MINIMIZE_METRICS = {
    "loss",
    "val_loss",
    "validation_loss",
    "test_loss",
    "train_loss",
    "mse",
    "rmse",
    "mae",
    "error",
    "error_rate",
    "perplexity",
    "ppl",
    "cer",
    "wer",
    "bpc",
    "nll",
    "cross_entropy",
    "ce_loss",
    "fid",
}

# Metrics where higher is better
MAXIMIZE_METRICS = {
    "accuracy",
    "acc",
    "val_accuracy",
    "test_accuracy",
    "train_accuracy",
    "f1",
    "f1_score",
    "precision",
    "recall",
    "auc",
    "auroc",
    "auprc",
    "ap",
    "map",
    "bleu",
    "rouge",
    "meteor",
    "iou",
    "dice",
    "r2",
    "r_squared",
    "spearman",
    "pearson",
    "correlation",
    "ssim",
    "psnr",
    "top1",
    "top5",
    "ndcg",
    "mrr",
    "hit_rate",
}


def detect_metric_direction(name: str) -> str:
    """Determine if a metric should be maximized or minimized.

    Returns "maximize" or "minimize".
    """
    name_lower = name.lower().strip().replace("-", "_").replace(" ", "_")

    if name_lower in MINIMIZE_METRICS:
        return "minimize"
    if name_lower in MAXIMIZE_METRICS:
        return "maximize"

    # Heuristics
    if "loss" in name_lower or "error" in name_lower:
        return "minimize"
    if "acc" in name_lower or "score" in name_lower:
        return "maximize"

    # Default: minimize (loss-like metrics are more common in training output)
    return "minimize"


# ── Output parsing ───────────────────────────────────────────────────────────

# Common patterns for metric output
METRIC_PATTERNS = [
    # key: value (with optional whitespace, colons, equals)
    r"(?P<name>[\w\s\-/]+?)\s*[:=]\s*(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*%?",
    # Epoch N, key: value
    r"(?:epoch|step|iter)\s*\d+.*?(?P<name>[\w\s\-/]+?)\s*[:=]\s*(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
    # [key] value or (key) value
    r"[\[\(](?P<name>[\w\s\-/]+?)[\]\)]\s*[:=]?\s*(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
]

# Lines to skip (not real metrics)
SKIP_PATTERNS = [
    r"^\s*$",
    r"^=+$",
    r"^-+$",
    r"^using device",
    r"^downloading",
    r"^loading",
    r"^\d+/\d+\s*\[",  # progress bars
    r"^Files already downloaded",
]


def parse_metrics_from_output(
    stdout_text: str,
    metric_names: Optional[List[str]] = None,
) -> List[Dict]:
    """Parse metrics from experiment stdout/stderr.

    Parameters
    ----------
    stdout_text : str
        Raw output from experiment execution.
    metric_names : list[str] | None
        If provided, only extract these specific metric names.

    Returns
    -------
    list[dict]
        List of metric dicts, each with:
        - name: str
        - value: float
        - maximize: bool
        - line: str (the source line)
    """
    metrics = []
    seen_keys = {}  # Track last value per metric name

    for line in stdout_text.splitlines():
        # Skip non-metric lines
        if any(re.match(pat, line.strip(), re.IGNORECASE) for pat in SKIP_PATTERNS):
            continue

        for pattern in METRIC_PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                name = match.group("name").strip()
                try:
                    value = float(match.group("value"))
                except ValueError:
                    continue

                # Filter by requested names
                if metric_names:
                    name_lower = name.lower().replace("-", "_").replace(" ", "_")
                    if not any(
                        m.lower().replace("-", "_").replace(" ", "_") == name_lower
                        for m in metric_names
                    ):
                        continue

                direction = detect_metric_direction(name)
                entry = {
                    "name": name,
                    "value": value,
                    "maximize": direction == "maximize",
                    "line": line.strip(),
                }

                # Keep the last occurrence of each metric (final epoch value)
                seen_keys[name.lower()] = len(metrics)
                metrics.append(entry)

    # Return only the last occurrence of each metric
    final_metrics = {}
    for m in metrics:
        key = m["name"].lower()
        final_metrics[key] = m

    return list(final_metrics.values())


def parse_final_metrics(stdout_text: str) -> Optional[Dict]:
    """Parse metrics and return a single best metric dict for node evaluation.

    Returns a metric dict compatible with the state_manager node format:
    {"value": ..., "maximize": ..., "name": ..., "description": ...}
    """
    metrics = parse_metrics_from_output(stdout_text)
    if not metrics:
        return None

    # Prioritize validation metrics over training metrics
    priority_prefixes = ["val_", "validation_", "test_", "eval_"]
    for prefix in priority_prefixes:
        for m in metrics:
            if m["name"].lower().startswith(prefix):
                return {
                    "value": m["value"],
                    "maximize": m["maximize"],
                    "name": m["name"],
                    "description": f"Parsed from output: {m['line']}",
                }

    # Fall back to last reported metric
    best = metrics[-1]
    return {
        "value": best["value"],
        "maximize": best["maximize"],
        "name": best["name"],
        "description": f"Parsed from output: {best['line']}",
    }


def parse_structured_metrics(stdout_text: str) -> Optional[Dict]:
    """Parse the new structured metric format from output.

    Looks for JSON blocks containing the metric_names structure.

    Returns the metric dict in the new format:
    {"value": {"metric_names": [...]}, "maximize": None}
    """
    # Try to find JSON metric blocks in output
    json_pattern = r"\{[^{}]*\"metric_names\"[^{}]*\}"
    # More permissive: look for multiline JSON
    lines = stdout_text.splitlines()
    json_buffer = ""
    in_json = False
    brace_count = 0

    for line in lines:
        stripped = line.strip()
        if not in_json and "{" in stripped and "metric_names" in stripped:
            in_json = True
            json_buffer = ""

        if in_json:
            json_buffer += line + "\n"
            brace_count += stripped.count("{") - stripped.count("}")
            if brace_count <= 0:
                in_json = False
                try:
                    parsed = json.loads(json_buffer)
                    if "metric_names" in parsed:
                        return {"value": parsed, "maximize": None}
                except json.JSONDecodeError:
                    continue

    return None


def compare_metrics(a: Optional[Dict], b: Optional[Dict]) -> int:
    """Compare two metric dicts.

    Returns:
        1 if a is better than b
        -1 if b is better than a
        0 if equal or incomparable
    """
    if a is None and b is None:
        return 0
    if a is None:
        return -1
    if b is None:
        return 1

    a_val = _get_mean_value(a)
    b_val = _get_mean_value(b)

    if a_val is None or b_val is None:
        return 0
    if a_val == b_val:
        return 0

    maximize = a.get("maximize", True)
    if isinstance(a.get("value"), dict) and "metric_names" in a["value"]:
        try:
            maximize = not a["value"]["metric_names"][0]["lower_is_better"]
        except (KeyError, IndexError):
            pass

    if maximize:
        return 1 if a_val > b_val else -1
    else:
        return 1 if a_val < b_val else -1


def _get_mean_value(m: Dict) -> Optional[float]:
    """Extract mean value from a metric dict."""
    value = m.get("value")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if "metric_names" in value:
            vals = []
            for metric in value["metric_names"]:
                for d in metric.get("data", []):
                    v = d.get("final_value")
                    if v is not None:
                        vals.append(float(v))
            return sum(vals) / len(vals) if vals else None
        else:
            vals = [float(v) for v in value.values() if v is not None]
            return sum(vals) / len(vals) if vals else None
    return None


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse metrics from experiment output")
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="File with experiment output (- for stdin)",
    )
    parser.add_argument("--names", nargs="*", help="Filter to specific metric names")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()

    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file) as f:
            text = f.read()

    # Try structured format first
    structured = parse_structured_metrics(text)
    if structured:
        print(json.dumps(structured, indent=2))
    else:
        metrics = parse_metrics_from_output(text, metric_names=args.names)
        if args.as_json:
            print(json.dumps(metrics, indent=2))
        else:
            if not metrics:
                print("No metrics found in output.")
            else:
                for m in metrics:
                    direction = "↑" if m["maximize"] else "↓"
                    print(f"  {m['name']}{direction}: {m['value']:.6f}")
                final = parse_final_metrics(text)
                if final:
                    print(f"\nBest metric: {final['name']} = {final['value']:.6f}")
