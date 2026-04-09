"""Progress dashboard for AI Scientist experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.state_manager import load_experiment_state, load_journal, get_best_node, get_journal_summary


STAGES = ["stage1_initial", "stage2_baseline", "stage3_creative", "stage4_ablation"]
STAGE_LABELS = {
    "stage1_initial": "Stage 1: Initial Implementation",
    "stage2_baseline": "Stage 2: Baseline Tuning",
    "stage3_creative": "Stage 3: Creative Exploration",
    "stage4_ablation": "Stage 4: Ablation Studies",
}


def get_dashboard(exp_dir: str) -> dict:
    """Build a progress summary for the experiment."""
    exp_path = Path(exp_dir)
    if not exp_path.exists():
        return {"error": f"Experiment directory not found: {exp_dir}"}

    state = load_experiment_state(exp_dir)
    current_stage = state.get("current_stage", "unknown")
    current_phase = state.get("current_phase", "unknown")
    status = state.get("status", "unknown")

    stages_summary = []
    for stage in STAGES:
        try:
            journal = load_journal(exp_dir, stage)
            summary = get_journal_summary(journal)
            best = get_best_node(journal)
            best_metric = best.get("metric", {}).get("value") if best else None
            stages_summary.append({
                "stage": stage,
                "label": STAGE_LABELS.get(stage, stage),
                "total_nodes": summary.get("total_nodes", 0),
                "good_nodes": summary.get("good_nodes", 0),
                "buggy_nodes": summary.get("buggy_nodes", 0),
                "best_metric": best_metric,
                "best_node_id": best["id"] if best else None,
            })
        except (FileNotFoundError, json.JSONDecodeError):
            stages_summary.append({
                "stage": stage,
                "label": STAGE_LABELS.get(stage, stage),
                "total_nodes": 0,
                "good_nodes": 0,
                "buggy_nodes": 0,
                "best_metric": None,
                "best_node_id": None,
            })

    return {
        "exp_dir": str(exp_path),
        "current_phase": current_phase,
        "current_stage": current_stage,
        "status": status,
        "stages": stages_summary,
    }


def print_dashboard(data: dict) -> None:
    """Pretty-print the dashboard."""
    if "error" in data:
        print(data["error"], file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 60)
    print("  AI Scientist — Experiment Progress")
    print("=" * 60)
    print(f"  Directory: {data['exp_dir']}")
    print(f"  Phase:     {data['current_phase']}")
    print(f"  Stage:     {data['current_stage']}")
    print(f"  Status:    {data['status']}")
    print()

    for s in data["stages"]:
        total = s["total_nodes"]
        good = s["good_nodes"]
        buggy = s["buggy_nodes"]
        is_current = (s["stage"] == data["current_stage"])
        marker = " ◀ current" if is_current else ""

        if total == 0:
            bar = "  [ not started ]"
        else:
            pct = good / total * 100 if total > 0 else 0
            filled = int(pct / 5)
            bar = f"  [{'█' * filled}{'░' * (20 - filled)}] {good}/{total} good ({pct:.0f}%)"

        metric_str = f"  Best: {s['best_metric']:.6f}" if s['best_metric'] is not None else ""

        print(f"  {s['label']}{marker}")
        print(f"{bar}{metric_str}")
        if buggy > 0:
            print(f"  ⚠ {buggy} buggy nodes")
        print()

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="AI Scientist experiment progress dashboard")
    parser.add_argument("exp_dir", help="Experiment directory")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()

    data = get_dashboard(args.exp_dir)

    if args.as_json:
        print(json.dumps(data, indent=2))
    else:
        print_dashboard(data)


if __name__ == "__main__":
    main()
