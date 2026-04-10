"""Statistical analysis for experiment results — multi-seed aggregation, significance tests."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Optional


# ── Aggregation ──────────────────────────────────────────────────────────────


def aggregate_seeds(values: list[float]) -> dict:
    """Aggregate metric values across multiple seeds.

    Returns mean, std, 95% CI, min/max, stability flag.
    A metric is 'unstable' if std > 5% of |mean| (or std > 0.1 when mean near 0).
    """
    n = len(values)
    if n == 0:
        return {"n": 0, "error": "no values"}
    if n == 1:
        return {
            "n": 1,
            "mean": values[0],
            "std": 0.0,
            "ci_95_low": values[0],
            "ci_95_high": values[0],
            "min": values[0],
            "max": values[0],
            "values": values,
            "stable": None,  # Can't determine with 1 sample
            "warning": "Single sample — run with more seeds for statistical validity",
        }

    mean = statistics.mean(values)
    std = statistics.stdev(values) if n >= 2 else 0.0

    # 95% CI using t-distribution approximation (good enough for our purposes)
    # For n=3: t_0.975 ≈ 4.303; n=5: 2.776; n=10: 2.262; n>=30: 1.96
    t_critical = _t_critical_95(n)
    margin = t_critical * (std / math.sqrt(n)) if n >= 2 else 0.0

    # Stability: std should be < 5% of |mean|, or < 0.1 if mean near zero
    mean_abs = abs(mean)
    if mean_abs > 0.1:
        stable = (std / mean_abs) < 0.05
    else:
        stable = std < 0.1

    result = {
        "n": n,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "ci_95_low": round(mean - margin, 6),
        "ci_95_high": round(mean + margin, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "values": [round(v, 6) for v in values],
        "stable": stable,
    }
    if not stable:
        cv = (std / mean_abs * 100) if mean_abs > 0 else float("inf")
        result["warning"] = f"Unstable: std/mean = {cv:.1f}% (target <5%). Run more seeds or fix variance."
    return result


def _t_critical_95(n: int) -> float:
    """Approximate t-critical value for 95% CI, two-tailed."""
    if n >= 30:
        return 1.96
    table = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447,
             8: 2.365, 9: 2.306, 10: 2.262, 15: 2.131, 20: 2.086, 25: 2.060}
    return table.get(n, 2.0)


# ── Significance Testing (for ablations) ─────────────────────────────────────


def paired_t_test(group_a: list[float], group_b: list[float]) -> dict:
    """Paired t-test for ablation comparisons.

    E.g., baseline vs no-component-X on same seeds.
    Returns t-statistic, degrees of freedom, p-value, effect size (Cohen's d).
    """
    if len(group_a) != len(group_b):
        return {"error": f"Unequal groups: {len(group_a)} vs {len(group_b)}"}
    if len(group_a) < 2:
        return {"error": "Need at least 2 paired samples"}

    diffs = [a - b for a, b in zip(group_a, group_b)]
    n = len(diffs)
    mean_diff = statistics.mean(diffs)
    std_diff = statistics.stdev(diffs) if n >= 2 else 0.0

    if std_diff == 0:
        return {
            "n": n,
            "mean_a": statistics.mean(group_a),
            "mean_b": statistics.mean(group_b),
            "mean_diff": mean_diff,
            "t_stat": float("inf") if mean_diff != 0 else 0.0,
            "df": n - 1,
            "p_value": 0.0 if mean_diff != 0 else 1.0,
            "effect_size": float("inf") if mean_diff != 0 else 0.0,
            "significant": mean_diff != 0,
            "interpretation": "Zero variance in differences",
        }

    se_diff = std_diff / math.sqrt(n)
    t_stat = mean_diff / se_diff
    df = n - 1
    p_value = _t_p_value(abs(t_stat), df)

    # Cohen's d for paired samples
    cohens_d = mean_diff / std_diff

    significant = p_value < 0.05

    if abs(cohens_d) < 0.2:
        effect_interp = "negligible"
    elif abs(cohens_d) < 0.5:
        effect_interp = "small"
    elif abs(cohens_d) < 0.8:
        effect_interp = "medium"
    else:
        effect_interp = "large"

    return {
        "n": n,
        "mean_a": round(statistics.mean(group_a), 6),
        "mean_b": round(statistics.mean(group_b), 6),
        "mean_diff": round(mean_diff, 6),
        "std_diff": round(std_diff, 6),
        "t_stat": round(t_stat, 4),
        "df": df,
        "p_value": round(p_value, 6),
        "effect_size": round(cohens_d, 4),
        "effect_interpretation": effect_interp,
        "significant": significant,
        "interpretation": _interpret_ablation(mean_diff, p_value, cohens_d),
    }


def _t_p_value(t_abs: float, df: int) -> float:
    """Approximate two-tailed p-value for a t-statistic.

    Uses the Wilson-Hilferty approximation — accurate to ~3 decimal places for p < 0.1.
    Good enough for deciding significance at 0.05 level.
    """
    if df < 1:
        return 1.0
    # Convert t to approximate z using Wilson-Hilferty
    # For large df, t ≈ z. For small df, use approximation:
    if df >= 30:
        z = t_abs
    else:
        # Cornish-Fisher approximation
        z = t_abs * (1 - 1 / (4 * df))
    # Standard normal survival function (2-tailed)
    # Using erfc approximation: P(|Z| > z) = erfc(z/sqrt(2))
    p = math.erfc(z / math.sqrt(2))
    return max(0.0, min(1.0, p))


def _interpret_ablation(mean_diff: float, p_value: float, cohens_d: float) -> str:
    """Plain-English interpretation of ablation result."""
    if p_value >= 0.05:
        return "Not significant — cannot claim this component contributes meaningfully"
    direction = "improves" if mean_diff < 0 else "worsens"  # assumes lower-is-better metric
    size = "slightly" if abs(cohens_d) < 0.5 else "meaningfully" if abs(cohens_d) < 0.8 else "substantially"
    return f"Significant: removing this component {size} {direction} the metric (p={p_value:.4f})"


# ── Node-level metric aggregation ────────────────────────────────────────────


def aggregate_node_metrics(nodes: list[dict], metric_name: Optional[str] = None) -> dict:
    """Aggregate metrics across multiple nodes (e.g., multi-seed runs).

    Each node should have a `metric` dict with `value` and optional `name`.
    Returns aggregated statistics + per-node breakdown.
    """
    values = []
    names = set()
    for node in nodes:
        m = node.get("metric") or {}
        if m.get("value") is not None:
            if metric_name and m.get("name") != metric_name:
                continue
            values.append(float(m["value"]))
            if m.get("name"):
                names.add(m["name"])

    if not values:
        return {"error": "No valid metric values found"}

    result = aggregate_seeds(values)
    result["metric_name"] = list(names)[0] if len(names) == 1 else "mixed"
    result["n_nodes"] = len(nodes)
    return result


def compare_ablation(baseline_nodes: list[dict], ablation_nodes: list[dict],
                     metric_name: Optional[str] = None) -> dict:
    """Compare baseline vs ablation across nodes. Nodes should use same seeds."""
    baseline_values = []
    ablation_values = []

    for node in baseline_nodes:
        m = node.get("metric") or {}
        if m.get("value") is not None:
            baseline_values.append(float(m["value"]))

    for node in ablation_nodes:
        m = node.get("metric") or {}
        if m.get("value") is not None:
            ablation_values.append(float(m["value"]))

    if len(baseline_values) != len(ablation_values):
        return {"error": f"Group sizes differ: {len(baseline_values)} vs {len(ablation_values)}"}

    return paired_t_test(baseline_values, ablation_values)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Statistical analysis for experiment results")
    sub = parser.add_subparsers(dest="command")

    # aggregate: compute mean/std/CI across a list of values
    a_parser = sub.add_parser("aggregate", help="Aggregate metric values (mean, std, CI)")
    a_parser.add_argument("values", nargs="+", type=float, help="Metric values from multiple seeds")

    # paired: paired t-test between two groups
    p_parser = sub.add_parser("paired", help="Paired t-test between two groups")
    p_parser.add_argument("--a", nargs="+", type=float, required=True, help="Group A values (baseline)")
    p_parser.add_argument("--b", nargs="+", type=float, required=True, help="Group B values (ablation)")

    # journal: aggregate metrics from a stage journal
    j_parser = sub.add_parser("journal", help="Aggregate all metrics from a stage journal")
    j_parser.add_argument("exp_dir", help="Experiment directory")
    j_parser.add_argument("stage", help="Stage name")

    args = parser.parse_args()

    if args.command == "aggregate":
        result = aggregate_seeds(args.values)
        print(json.dumps(result, indent=2))

    elif args.command == "paired":
        result = paired_t_test(args.a, args.b)
        print(json.dumps(result, indent=2))

    elif args.command == "journal":
        from tools.state_manager import load_journal
        journal = load_journal(args.exp_dir, args.stage)
        nodes = journal.get("nodes", [])
        good_nodes = [n for n in nodes if not n.get("is_buggy")]
        result = aggregate_node_metrics(good_nodes)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
