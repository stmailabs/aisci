"""Experiment state management — JSON-based journal and tree persistence.

File-based approach suitable for Claude Code skills that run across
multiple invocations.
"""

import json
import os
import shutil
import sys
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml


# ── Node schema ──────────────────────────────────────────────────────────────

STAGE_NAMES = [
    "stage1_initial",
    "stage2_baseline",
    "stage3_creative",
    "stage4_ablation",
]

STAGE_GOALS = {
    "stage1_initial": {
        "name": "Initial Implementation",
        "goal": "Get a basic working implementation on a simple dataset",
        "stage_number": 1,
    },
    "stage2_baseline": {
        "name": "Baseline Tuning",
        "goal": "Optimize hyperparameters without architecture changes; test on 2+ HuggingFace datasets",
        "stage_number": 2,
    },
    "stage3_creative": {
        "name": "Creative Research",
        "goal": "Novel improvements and insights; test on 3 total HuggingFace datasets",
        "stage_number": 3,
    },
    "stage4_ablation": {
        "name": "Ablation Studies",
        "goal": "Systematic component contribution analysis on same 3 datasets",
        "stage_number": 4,
    },
}


def create_node(
    stage: str,
    plan: str = "",
    code: str = "",
    parent_id: Optional[str] = None,
    overall_plan: str = "",
    plot_code: Optional[str] = None,
    plot_plan: Optional[str] = None,
) -> Dict:
    """Create a new experiment node matching the original Node dataclass schema."""
    return {
        # Identity
        "id": uuid.uuid4().hex,
        "parent_id": parent_id,
        "children_ids": [],
        "step": 0,  # set by add_node
        "stage": stage,
        "created_at": datetime.now().isoformat(),
        "ctime": time.time(),
        # Code & plan
        "plan": plan,
        "overall_plan": overall_plan,
        "code": code,
        "plot_code": plot_code,
        "plot_plan": plot_plan,
        # Execution results
        "term_out": None,
        "exec_time": None,
        "exc_type": None,
        "exc_info": None,
        "exc_stack": None,
        # Parse metrics execution
        "parse_metrics_plan": "",
        "parse_metrics_code": "",
        "parse_term_out": None,
        "parse_exc_type": None,
        "parse_exc_info": None,
        "parse_exc_stack": None,
        # Plot execution
        "plot_term_out": None,
        "plot_exec_time": None,
        "plot_exc_type": None,
        "plot_exc_info": None,
        "plot_exc_stack": None,
        # Evaluation
        "analysis": None,
        "metric": None,  # {"value": ..., "maximize": ..., "name": ..., "description": ...}
        "is_buggy": None,
        "is_buggy_plots": None,
        # Plotting
        "plot_data": {},
        "plots_generated": False,
        "plots": [],
        "plot_paths": [],
        # VLM feedback
        "plot_analyses": [],
        "vlm_feedback_summary": [],
        "datasets_successfully_tested": [],
        # Execution time feedback
        "exec_time_feedback": "",
        # Ablation & hyperparameter
        "ablation_name": None,
        "hyperparam_name": None,
        # Seed flags
        "is_seed_node": False,
        "is_seed_agg_node": False,
        # Experiment results dir
        "exp_results_dir": None,
    }


def node_stage_name(node: Dict, journal: Dict) -> Literal["draft", "debug", "improve"]:
    """Determine node type: draft (root), debug (parent buggy), improve (parent good)."""
    if node["parent_id"] is None:
        return "draft"
    parent = get_node_by_id(journal, node["parent_id"])
    if parent and parent.get("is_buggy"):
        return "debug"
    return "improve"


def node_debug_depth(node: Dict, journal: Dict) -> int:
    """Count consecutive debugging steps from this node up."""
    if node_stage_name(node, journal) != "debug":
        return 0
    parent = get_node_by_id(journal, node["parent_id"])
    if parent is None:
        return 0
    return node_debug_depth(parent, journal) + 1


# ── Journal operations ───────────────────────────────────────────────────────


def create_journal() -> Dict:
    """Create an empty journal."""
    return {"nodes": []}


def get_node_by_id(journal: Dict, node_id: str) -> Optional[Dict]:
    """Find a node by its ID."""
    for node in journal["nodes"]:
        if node["id"] == node_id:
            return node
    return None


def add_node(journal: Dict, node: Dict) -> Dict:
    """Add a node to the journal, setting its step and updating parent's children."""
    node["step"] = len(journal["nodes"])
    journal["nodes"].append(node)
    if node["parent_id"]:
        parent = get_node_by_id(journal, node["parent_id"])
        if parent:
            parent["children_ids"].append(node["id"])
    return node


def get_draft_nodes(journal: Dict) -> List[Dict]:
    """Return root nodes (no parent)."""
    return [n for n in journal["nodes"] if n["parent_id"] is None]


def get_buggy_nodes(journal: Dict) -> List[Dict]:
    """Return nodes marked as buggy."""
    return [n for n in journal["nodes"] if n.get("is_buggy") is True]


def get_good_nodes(journal: Dict) -> List[Dict]:
    """Return nodes that are not buggy (both code and plots)."""
    return [
        n
        for n in journal["nodes"]
        if n.get("is_buggy") is False and n.get("is_buggy_plots") is not True
    ]


def get_best_node(journal: Dict) -> Optional[Dict]:
    """Return the best non-buggy node by metric comparison.

    Falls back to the most recent good node if metrics are not comparable.
    """
    good = get_good_nodes(journal)
    if not good:
        return None
    if len(good) == 1:
        return good[0]

    # Compare by metric
    best = good[0]
    for node in good[1:]:
        if _metric_is_better(node.get("metric"), best.get("metric")):
            best = node
    return best


def _metric_is_better(a: Optional[Dict], b: Optional[Dict]) -> bool:
    """Check if metric *a* is better than metric *b*.

    Supports both simple {value, maximize} and the new {metric_names: [...]} format.
    """
    if a is None:
        return False
    if b is None:
        return True

    a_val = _metric_mean_value(a)
    b_val = _metric_mean_value(b)

    if a_val is None or b_val is None:
        return a_val is not None

    if a_val == b_val:
        return False

    should_maximize = _metric_should_maximize(a)
    comp = a_val > b_val
    return comp if should_maximize else not comp


def _metric_mean_value(m: Optional[Dict]) -> Optional[float]:
    """Extract mean numeric value from a metric dict."""
    if m is None:
        return None
    value = m.get("value")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if "metric_names" in value:
            # New format
            all_vals = []
            for metric in value["metric_names"]:
                for d in metric.get("data", []):
                    v = d.get("final_value")
                    if v is not None:
                        all_vals.append(float(v))
            return sum(all_vals) / len(all_vals) if all_vals else None
        else:
            # Old format: {dataset: value, ...}
            vals = [float(v) for v in value.values() if v is not None]
            return sum(vals) / len(vals) if vals else None
    return None


def _metric_should_maximize(m: Optional[Dict]) -> bool:
    """Determine whether the metric should be maximized."""
    if m is None:
        return True
    value = m.get("value")
    if isinstance(value, dict) and "metric_names" in value:
        try:
            return not value["metric_names"][0]["lower_is_better"]
        except (KeyError, IndexError):
            pass
    return bool(m.get("maximize", True))


def get_nodes_for_expansion(
    journal: Dict,
    strategy: str = "best_first",
    max_debug_depth: int = 3,
    debug_prob: float = 0.5,
) -> List[Dict]:
    """Select candidate parent nodes for expansion.

    Selects candidate parent nodes using the BFTS node selection logic.
    """
    import random

    good = get_good_nodes(journal)
    buggy_leaves = [
        n
        for n in journal["nodes"]
        if n.get("is_buggy") is True
        and not n.get("children_ids")
        and node_debug_depth(n, journal) < max_debug_depth
    ]

    candidates = []

    # Add best good node
    if good:
        best = get_best_node(journal)
        if best:
            candidates.append(best)

    # Optionally add a buggy node for debugging
    if buggy_leaves and random.random() < debug_prob:
        candidates.append(random.choice(buggy_leaves))

    # If no candidates yet, pick any leaf
    if not candidates:
        leaves = [n for n in journal["nodes"] if not n.get("children_ids")]
        if leaves:
            candidates.append(leaves[-1])

    return candidates


def get_journal_summary(journal: Dict) -> Dict:
    """Generate a summary of the journal for status reporting."""
    nodes = journal.get("nodes", [])
    good = get_good_nodes(journal)
    buggy = get_buggy_nodes(journal)
    best = get_best_node(journal)

    return {
        "total_nodes": len(nodes),
        "good_nodes": len(good),
        "buggy_nodes": len(buggy),
        "best_node_id": best["id"] if best else None,
        "best_metric": best.get("metric") if best else None,
        "datasets_tested": list(
            set(
                ds
                for n in good
                for ds in n.get("datasets_successfully_tested", [])
            )
        ),
    }


# ── Experiment state ─────────────────────────────────────────────────────────


def init_experiment(
    idea: Dict,
    config: Dict,
    base_dir: str = "experiments",
) -> str:
    """Initialize a new experiment directory structure.

    Returns the path to the experiment directory.
    """
    idea_name = idea.get("Name", "unnamed")
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_name = f"{date_str}_{idea_name}"
    exp_dir = Path(base_dir) / exp_name

    # Create directory structure
    for subdir in [
        "state/stage1_initial",
        "state/stage2_baseline",
        "state/stage3_creative",
        "state/stage4_ablation",
        "workspace",
        "figures",
        "latex",
        "logs",
        "experiment_results",
    ]:
        (exp_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Save idea
    with open(exp_dir / "idea.json", "w") as f:
        json.dump(idea, f, indent=2)

    # Generate idea markdown
    idea_md = _idea_to_markdown(idea)
    with open(exp_dir / "idea.md", "w") as f:
        f.write(idea_md)

    # Save config
    with open(exp_dir / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Initialize experiment state
    state = {
        "experiment_id": exp_name,
        "idea_name": idea_name,
        "created_at": datetime.now().isoformat(),
        "current_phase": "experiment",
        "current_stage": "stage1_initial",
        "completed_stages": [],
        "stage_transitions": [],
        "config": config,
    }
    with open(exp_dir / "state" / "experiment_state.json", "w") as f:
        json.dump(state, f, indent=2)

    # Initialize empty journals for each stage
    for stage in STAGE_NAMES:
        save_journal(str(exp_dir), stage, create_journal())

    return str(exp_dir)


def _idea_to_markdown(idea: Dict) -> str:
    """Convert an idea dict to a Markdown description."""
    lines = [f"# {idea.get('Title', 'Untitled Research Idea')}", ""]
    if idea.get("Short Hypothesis"):
        lines.extend(["## Hypothesis", idea["Short Hypothesis"], ""])
    if idea.get("Abstract"):
        lines.extend(["## Abstract", idea["Abstract"], ""])
    if idea.get("Experiments"):
        lines.append("## Experiments")
        exps = idea["Experiments"]
        if isinstance(exps, list):
            for i, exp in enumerate(exps, 1):
                lines.append(f"{i}. {exp}")
        else:
            lines.append(str(exps))
        lines.append("")
    if idea.get("Related Work"):
        lines.extend(["## Related Work", idea["Related Work"], ""])
    if idea.get("Risk Factors and Limitations"):
        lines.append("## Risk Factors and Limitations")
        risks = idea["Risk Factors and Limitations"]
        if isinstance(risks, list):
            for r in risks:
                lines.append(f"- {r}")
        else:
            lines.append(str(risks))
        lines.append("")
    return "\n".join(lines)


def load_experiment_state(exp_dir: str) -> Dict:
    """Load the global experiment state."""
    path = Path(exp_dir) / "state" / "experiment_state.json"
    with open(path) as f:
        return json.load(f)


def save_experiment_state(exp_dir: str, state: Dict) -> None:
    """Save the global experiment state."""
    path = Path(exp_dir) / "state" / "experiment_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def update_experiment_state(
    exp_dir: str,
    phase: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict:
    """Update specific fields in the experiment state."""
    state = load_experiment_state(exp_dir)
    if phase is not None:
        state["current_phase"] = phase
    if stage is not None:
        state["current_stage"] = stage
    if status is not None:
        state["status"] = status
    save_experiment_state(exp_dir, state)
    return state


def transition_stage(
    exp_dir: str,
    from_stage: str,
    to_stage: str,
    best_node_id: Optional[str] = None,
    reason: str = "",
) -> Dict:
    """Record a stage transition."""
    state = load_experiment_state(exp_dir)
    state["completed_stages"].append(from_stage)
    state["current_stage"] = to_stage
    state["stage_transitions"].append(
        {
            "from": from_stage,
            "to": to_stage,
            "best_node_id": best_node_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
    )
    save_experiment_state(exp_dir, state)
    return state


def can_resume(exp_dir: str) -> bool:
    """Check if an experiment can be resumed."""
    state_path = Path(exp_dir) / "state" / "experiment_state.json"
    return state_path.exists()


# ── Journal persistence ──────────────────────────────────────────────────────


def load_journal(exp_dir: str, stage: str) -> Dict:
    """Load a stage journal from disk."""
    path = Path(exp_dir) / "state" / stage / "journal.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return create_journal()


def save_journal(exp_dir: str, stage: str, journal: Dict) -> None:
    """Save a stage journal to disk."""
    path = Path(exp_dir) / "state" / stage / "journal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(journal, f, indent=2)


def save_best_solution(exp_dir: str, stage: str, journal: Dict) -> Optional[str]:
    """Save the best solution code from a stage journal. Returns the file path."""
    best = get_best_node(journal)
    if best is None:
        return None
    stage_dir = Path(exp_dir) / "state" / stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous best solutions
    for f in stage_dir.glob("best_solution_*.py"):
        f.unlink()

    filename = f"best_solution_{best['id']}.py"
    filepath = stage_dir / filename
    with open(filepath, "w") as f:
        f.write(best.get("code", ""))

    with open(stage_dir / "best_node_id.txt", "w") as f:
        f.write(best["id"])

    return str(filepath)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Scientist state manager")
    sub = parser.add_subparsers(dest="command")

    # init
    init_p = sub.add_parser("init", help="Initialize experiment")
    init_p.add_argument("--idea", required=True, help="Path to idea JSON")
    init_p.add_argument("--config", default=None, help="Path to config YAML")
    init_p.add_argument("--base-dir", default="experiments", help="Base experiments dir")

    # status
    status_p = sub.add_parser("status", help="Show experiment status")
    status_p.add_argument("exp_dir", help="Experiment directory")

    # journal-summary
    summary_p = sub.add_parser("journal-summary", help="Show journal summary")
    summary_p.add_argument("exp_dir", help="Experiment directory")
    summary_p.add_argument("stage", help="Stage name")

    # test
    sub.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    if args.command == "init":
        with open(args.idea) as f:
            idea = json.load(f)
        config = {}
        if args.config:
            with open(args.config) as f:
                config = yaml.safe_load(f) or {}
        exp_dir = init_experiment(idea, config, base_dir=args.base_dir)
        print(f"Experiment initialized: {exp_dir}")

    elif args.command == "status":
        state = load_experiment_state(args.exp_dir)
        print(json.dumps(state, indent=2))

    elif args.command == "journal-summary":
        journal = load_journal(args.exp_dir, args.stage)
        summary = get_journal_summary(journal)
        print(json.dumps(summary, indent=2))

    elif args.command == "test":
        # Self-test
        print("Running self-test...")
        idea = {
            "Name": "test_idea",
            "Title": "Test Research Idea",
            "Short Hypothesis": "Testing the state manager",
            "Abstract": "This is a test.",
            "Experiments": ["Exp 1", "Exp 2"],
            "Risk Factors and Limitations": ["Risk 1"],
        }
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = init_experiment(idea, {"timeout": 3600}, base_dir=tmpdir)
            print(f"  Created experiment: {exp_dir}")

            # Add nodes
            journal = load_journal(exp_dir, "stage1_initial")
            node1 = create_node("stage1_initial", plan="First draft", code="print('hello')")
            add_node(journal, node1)
            node1["metric"] = {"value": 0.85, "maximize": False, "name": "val_loss"}
            node1["is_buggy"] = False
            node1["is_buggy_plots"] = False

            node2 = create_node(
                "stage1_initial",
                plan="Second draft",
                code="print('world')",
                parent_id=node1["id"],
            )
            add_node(journal, node2)
            node2["metric"] = {"value": 0.72, "maximize": False, "name": "val_loss"}
            node2["is_buggy"] = False
            node2["is_buggy_plots"] = False

            save_journal(exp_dir, "stage1_initial", journal)

            # Reload and verify
            journal2 = load_journal(exp_dir, "stage1_initial")
            assert len(journal2["nodes"]) == 2
            best = get_best_node(journal2)
            assert best["id"] == node2["id"]  # 0.72 < 0.85, minimize → node2 is better
            print(f"  Best node: {best['id']} (metric: {best['metric']})")

            summary = get_journal_summary(journal2)
            print(f"  Summary: {json.dumps(summary, indent=2)}")

            # Test stage transition
            transition_stage(exp_dir, "stage1_initial", "stage2_baseline", best["id"])
            state = load_experiment_state(exp_dir)
            assert state["current_stage"] == "stage2_baseline"
            print(f"  Stage transition OK: {state['current_stage']}")

            print("Self-test PASSED ✓")
    else:
        parser.print_help()
