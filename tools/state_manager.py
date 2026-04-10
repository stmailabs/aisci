"""Experiment state management — JSON-based journal and tree persistence.

File-based approach suitable for Claude Code skills that run across
multiple invocations.
"""

import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
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


def get_stage_briefing(journal: Dict, stage: str) -> Dict:
    """Generate a rich briefing of a completed stage for handoff to the next stage.

    Unlike journal-summary (counts only), this returns actionable context:
    what worked, what didn't, key findings, and recommendations.
    """
    good = get_good_nodes(journal)
    buggy = get_buggy_nodes(journal)
    best = get_best_node(journal)

    # Collect all unique analyses from good nodes
    findings = []
    for n in good:
        if n.get("analysis"):
            findings.append(n["analysis"])

    # Datasets tested across all good nodes
    datasets = list(set(
        ds for n in good for ds in n.get("datasets_successfully_tested", [])
    ))

    # Collect what approaches failed (from buggy nodes)
    failures = []
    for n in buggy:
        plan = n.get("plan", "")
        exc = n.get("exc_type", "")
        if plan or exc:
            failures.append({"plan": plan, "error": exc})

    briefing = {
        "stage": stage,
        "stage_goal": STAGE_GOALS.get(stage, {}).get("goal", ""),
        "total_iterations": len(journal.get("nodes", [])),
        "successful_iterations": len(good),
        "failed_iterations": len(buggy),
        "datasets_tested": datasets,
        "best_metric": best.get("metric") if best else None,
        "best_plan": best.get("plan", "") if best else "",
        "key_findings": findings[-3:],  # last 3 analyses (most refined)
        "failed_approaches": failures[-3:],  # last 3 failures
    }
    return briefing


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


def save_structured_log(exp_dir: str, stage: str, node: dict) -> str:
    """Save a structured JSON log for a single experiment node."""
    log_dir = Path(exp_dir) / "logs" / "structured"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{stage}_step{node.get('step', 0)}_{node['id'][:8]}.json"

    log_entry = {
        "node_id": node["id"],
        "stage": stage,
        "step": node.get("step", 0),
        "timestamp": node.get("created_at", ""),
        "parent_id": node.get("parent_id"),
        "is_buggy": node.get("is_buggy", False),
        "exec_time": node.get("exec_time", 0),
        "metric": node.get("metric"),
        "datasets": node.get("datasets_successfully_tested", []),
        "error": {
            "type": node.get("exc_type", ""),
            "message": node.get("exc_info", ""),
        } if node.get("is_buggy") else None,
        "plan": node.get("plan", ""),
        "plots": node.get("plot_paths", []),
    }

    with open(log_file, "w") as f:
        json.dump(log_entry, f, indent=2)
    return str(log_file)


def get_code_hash(code: str) -> str:
    """Return SHA-256 hash of code content (whitespace-normalized)."""
    normalized = "\n".join(line.rstrip() for line in code.strip().splitlines())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def find_duplicate_node(journal: dict, code: str) -> Optional[dict]:
    """Check if identical code was already executed in this stage."""
    target_hash = get_code_hash(code)
    for node in journal["nodes"]:
        if get_code_hash(node.get("code", "")) == target_hash:
            return node
    return None


def find_cross_stage_duplicate(exp_dir: str, current_stage: str, code: str) -> Optional[dict]:
    """Check if identical code was already executed in ANY earlier stage."""
    stages_order = ["stage1_initial", "stage2_baseline", "stage3_creative", "stage4_ablation"]
    try:
        current_idx = stages_order.index(current_stage)
    except ValueError:
        return None
    for stage in stages_order[:current_idx]:
        try:
            journal = load_journal(exp_dir, stage)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        dup = find_duplicate_node(journal, code)
        if dup:
            return {**dup, "_source_stage": stage}
    return None


def code_similarity(a: str, b: str) -> float:
    """Compute rough similarity between two code strings (0.0 - 1.0).

    Uses normalized line-set Jaccard similarity. Quick and good enough
    to detect "same code with minor tweaks".
    """
    def lines_set(code: str) -> set:
        return set(
            line.strip()
            for line in code.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    a_lines = lines_set(a)
    b_lines = lines_set(b)
    if not a_lines or not b_lines:
        return 0.0
    intersection = a_lines & b_lines
    union = a_lines | b_lines
    return len(intersection) / len(union) if union else 0.0


# ── Checkpointing (atomic per-node state) ────────────────────────────────────


def _safe_node_id(node_id: str) -> str:
    """Sanitize node_id to prevent path traversal. Only allow safe chars."""
    if not node_id or ".." in node_id or "/" in node_id or "\\" in node_id:
        raise ValueError(f"Invalid node_id: {node_id!r}")
    return node_id


def _checkpoint_dir(exp_dir: str, stage: str, node_id: str) -> Path:
    """Get the checkpoint directory for a node."""
    node_id = _safe_node_id(node_id)
    d = Path(exp_dir) / "state" / stage / "checkpoints" / node_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomic write: write to temp file in same directory, then rename.

    Prevents partial/corrupted files from concurrent writers (parallel BFTS workers).
    """
    import tempfile
    # Use same directory so rename is atomic (same filesystem)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_" + path.name)
    try:
        try:
            f = os.fdopen(fd, "w")
        except Exception:
            os.close(fd)  # fdopen failed before taking ownership of fd
            raise
        with f:
            f.write(content)
        os.replace(tmp, path)  # atomic on POSIX + Windows
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_checkpoint(exp_dir: str, stage: str, node_id: str, step: str, data: Any) -> str:
    """Save a checkpoint for a specific step of a node's lifecycle.

    Writes are atomic — safe for concurrent parallel BFTS workers.

    Steps:
      - "code"    → generated code (str)
      - "exec"    → execution output (str, full stdout/stderr)
      - "metrics" → parsed metrics (dict)
      - "plots"   → list of plot file paths (list)
      - "done"    → marker that node is fully processed

    Returns the checkpoint file path.
    """
    d = _checkpoint_dir(exp_dir, stage, node_id)
    if step == "code":
        path = d / "code.py"
        _atomic_write_text(path, data if isinstance(data, str) else json.dumps(data))
    elif step == "exec":
        path = d / "exec.log"
        _atomic_write_text(path, data if isinstance(data, str) else json.dumps(data))
    elif step == "metrics":
        path = d / "metrics.json"
        _atomic_write_text(path, json.dumps(data, indent=2))
    elif step == "plots":
        path = d / "plots.json"
        _atomic_write_text(path, json.dumps(data, indent=2))
    elif step == "done":
        path = d / "done.marker"
        _atomic_write_text(path, datetime.now(timezone.utc).isoformat())
    else:
        raise ValueError(f"Unknown checkpoint step: {step}")
    return str(path)


def load_checkpoint(exp_dir: str, stage: str, node_id: str, step: str) -> Optional[Any]:
    """Load a checkpoint. Returns None if not present."""
    d = _checkpoint_dir(exp_dir, stage, node_id)
    if step == "code":
        path = d / "code.py"
        return path.read_text() if path.exists() else None
    elif step == "exec":
        path = d / "exec.log"
        return path.read_text() if path.exists() else None
    elif step == "metrics":
        path = d / "metrics.json"
        return json.loads(path.read_text()) if path.exists() else None
    elif step == "plots":
        path = d / "plots.json"
        return json.loads(path.read_text()) if path.exists() else None
    elif step == "done":
        path = d / "done.marker"
        return path.read_text() if path.exists() else None
    return None


def checkpoint_status(exp_dir: str, stage: str, node_id: str) -> dict:
    """Report which checkpoints exist for a node, useful for resume logic."""
    d = _checkpoint_dir(exp_dir, stage, node_id)
    return {
        "node_id": node_id,
        "stage": stage,
        "code": (d / "code.py").exists(),
        "exec": (d / "exec.log").exists(),
        "metrics": (d / "metrics.json").exists(),
        "plots": (d / "plots.json").exists(),
        "done": (d / "done.marker").exists(),
        "next_step": _next_step(d),
    }


def _next_step(d: Path) -> str:
    """Determine the next step to execute based on existing checkpoints."""
    if (d / "done.marker").exists():
        return "complete"
    if not (d / "code.py").exists():
        return "generate"
    if not (d / "exec.log").exists():
        return "execute"
    if not (d / "metrics.json").exists():
        return "parse_metrics"
    return "record_node"


def list_incomplete_checkpoints(exp_dir: str, stage: str) -> list[dict]:
    """List all node checkpoints that are not yet 'done'. Useful for resume."""
    checkpoint_root = Path(exp_dir) / "state" / stage / "checkpoints"
    if not checkpoint_root.exists():
        return []
    incomplete = []
    for node_dir in checkpoint_root.iterdir():
        if not node_dir.is_dir():
            continue
        if not (node_dir / "done.marker").exists():
            incomplete.append(checkpoint_status(exp_dir, stage, node_dir.name))
    return incomplete


# ── Error classification (wraps error_classifier) ────────────────────────────


def get_stage_error_analysis(exp_dir: str, stage: str) -> dict:
    """Analyze the error distribution in a stage and return actionable insights."""
    try:
        from tools.error_classifier import analyze_journal
    except ImportError:
        return {"error": "error_classifier module not available"}
    journal = load_journal(exp_dir, stage)
    return analyze_journal(journal)


# ── Smart BFTS: prune dead branches, diversity-aware selection ───────────────


def _node_error_type(node: dict) -> Optional[str]:
    """Get error category for a node (using error_classifier). None if not buggy."""
    if not node.get("is_buggy"):
        return None
    try:
        from tools.error_classifier import classify_node
        return classify_node(node)
    except ImportError:
        return "UNKNOWN"


def _count_siblings_with_same_error(journal: dict, node: dict) -> int:
    """Count how many siblings (same parent) have the same error type."""
    parent_id = node.get("parent_id")
    if parent_id is None:
        # Siblings are all other root drafts
        siblings = [n for n in journal["nodes"] if n.get("parent_id") is None and n["id"] != node["id"]]
    else:
        siblings = [n for n in journal["nodes"] if n.get("parent_id") == parent_id and n["id"] != node["id"]]
    target_error = _node_error_type(node)
    if not target_error:
        return 0
    return sum(1 for s in siblings if _node_error_type(s) == target_error)


def get_nodes_for_expansion_smart(
    journal: Dict,
    max_debug_depth: int = 3,
    debug_prob: float = 0.5,
    prune_sibling_threshold: int = 3,
) -> List[Dict]:
    """Smart node selection for BFTS expansion.

    Improvements over get_nodes_for_expansion:
    - Prunes buggy nodes whose siblings already failed with same error type
      (indicates structural issue, not fixable by debug)
    - Prefers diverse parents over re-expanding same best node
    - Skips nodes that hit max debug depth
    """
    import random

    good = get_good_nodes(journal)
    candidates: List[Dict] = []

    # Filter buggy leaves: skip if too many siblings hit the same error
    buggy_leaves_raw = [
        n for n in journal["nodes"]
        if n.get("is_buggy") is True
        and not n.get("children_ids")
        and node_debug_depth(n, journal) < max_debug_depth
    ]
    buggy_leaves = [
        n for n in buggy_leaves_raw
        if _count_siblings_with_same_error(journal, n) < prune_sibling_threshold
    ]

    # Add best good node
    if good:
        best = get_best_node(journal)
        if best:
            candidates.append(best)

    # Optionally add a buggy node for debugging (but only if not pruned)
    if buggy_leaves and random.random() < debug_prob:
        candidates.append(random.choice(buggy_leaves))

    # Add diversity: if we have multiple good nodes with different approaches, include one
    if len(good) >= 2:
        best_id = candidates[0]["id"] if candidates else None
        diverse_options = [
            n for n in good
            if n["id"] != best_id
            and not n.get("children_ids")  # leaf only
        ]
        if diverse_options and best_id:
            # Pick the one most different from best
            best_code = next((n.get("code", "") for n in good if n["id"] == best_id), "")
            scored = [
                (1 - code_similarity(best_code, n.get("code", "")), n)
                for n in diverse_options
            ]
            scored.sort(key=lambda x: -x[0])  # highest diversity first
            if scored and scored[0][0] > 0.3:  # only include if meaningfully different
                candidates.append(scored[0][1])

    # If no candidates, fall back to any leaf
    if not candidates:
        leaves = [n for n in journal["nodes"] if not n.get("children_ids")]
        if leaves:
            candidates.append(leaves[-1])

    return candidates


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Scientist state manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  uv run python3 tools/state_manager.py init --idea idea.json --config templates/bfts_config.yaml
  uv run python3 tools/state_manager.py status experiments/20260402_idea
  uv run python3 tools/state_manager.py select-nodes experiments/20260402_idea stage1_initial
  uv run python3 tools/state_manager.py add-node experiments/20260402_idea stage1_initial --code runfile.py --plan "First draft" --metric '{"value":0.85,"maximize":false,"name":"val_loss"}'
  uv run python3 tools/state_manager.py best-node experiments/20260402_idea stage1_initial
  uv run python3 tools/state_manager.py save-best experiments/20260402_idea stage1_initial
  uv run python3 tools/state_manager.py transition experiments/20260402_idea stage1_initial stage2_baseline
  uv run python3 tools/state_manager.py update-state experiments/20260402_idea --phase complete --status done
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # init — initialize experiment
    init_p = sub.add_parser("init", help="Initialize experiment directory")
    init_p.add_argument("--idea", required=True, help="Path to idea JSON")
    init_p.add_argument("--config", default=None, help="Path to config YAML")
    init_p.add_argument("--base-dir", default="experiments", help="Base experiments dir")

    # status — show experiment state
    status_p = sub.add_parser("status", help="Show experiment state")
    status_p.add_argument("exp_dir", help="Experiment directory")

    # journal-summary — summarize a stage journal
    summary_p = sub.add_parser("journal-summary", help="Summarize stage journal")
    summary_p.add_argument("exp_dir", help="Experiment directory")
    summary_p.add_argument("stage", help="Stage name")

    # select-nodes — pick candidate parents for next expansion
    sel_p = sub.add_parser("select-nodes", help="Select candidate nodes for expansion")
    sel_p.add_argument("exp_dir", help="Experiment directory")
    sel_p.add_argument("stage", help="Stage name")
    sel_p.add_argument("--max-debug-depth", type=int, default=3)
    sel_p.add_argument("--debug-prob", type=float, default=0.5)

    # add-node — create and add a node to the journal
    add_p = sub.add_parser("add-node", help="Add a node to the stage journal")
    add_p.add_argument("exp_dir", help="Experiment directory")
    add_p.add_argument("stage", help="Stage name")
    add_p.add_argument("--parent-id", default=None, help="Parent node ID")
    add_p.add_argument("--plan", default="", help="Brief plan description")
    add_p.add_argument("--code", default=None, help="Path to code file")
    add_p.add_argument("--output-log", default=None, help="Path to execution output log")
    add_p.add_argument("--exec-time", type=float, default=None, help="Execution time (seconds)")
    add_p.add_argument("--metric", default=None, help="Metric JSON string or @file")
    add_p.add_argument("--buggy", action="store_true", help="Mark node as buggy")
    add_p.add_argument("--analysis", default=None, help="Analysis text or @file")
    add_p.add_argument("--plots", nargs="*", default=[], help="Plot file paths")
    add_p.add_argument("--datasets", nargs="*", default=[], help="Datasets tested")

    # best-node — show the best node in a stage
    best_p = sub.add_parser("best-node", help="Show best node in a stage")
    best_p.add_argument("exp_dir", help="Experiment directory")
    best_p.add_argument("stage", help="Stage name")
    best_p.add_argument("--show-code", action="store_true", help="Print the code too")

    # save-best — save best solution to file
    saveb_p = sub.add_parser("save-best", help="Save best solution code to file")
    saveb_p.add_argument("exp_dir", help="Experiment directory")
    saveb_p.add_argument("stage", help="Stage name")

    # transition — record stage transition
    trans_p = sub.add_parser("transition", help="Transition to next stage")
    trans_p.add_argument("exp_dir", help="Experiment directory")
    trans_p.add_argument("from_stage", help="Current stage")
    trans_p.add_argument("to_stage", help="Next stage")
    trans_p.add_argument("--reason", default="Stage completed", help="Transition reason")

    # update-state — update experiment state fields
    upd_p = sub.add_parser("update-state", help="Update experiment state")
    upd_p.add_argument("exp_dir", help="Experiment directory")
    upd_p.add_argument("--phase", default=None, help="Set current phase")
    upd_p.add_argument("--stage", default=None, help="Set current stage")
    upd_p.add_argument("--status", default=None, help="Set status")

    # node-info — show details of a specific node
    info_p = sub.add_parser("node-info", help="Show details of a specific node")
    info_p.add_argument("exp_dir", help="Experiment directory")
    info_p.add_argument("stage", help="Stage name")
    info_p.add_argument("node_id", help="Node ID")
    info_p.add_argument("--show-code", action="store_true", help="Print the code too")

    # stage-briefing — rich summary for stage handoff
    brief_p = sub.add_parser("stage-briefing", help="Generate stage briefing for handoff to next stage")
    brief_p.add_argument("exp_dir", help="Experiment directory")
    brief_p.add_argument("stage", help="Stage name")

    # dedup-check — check if code already executed in stage
    dedup_p = sub.add_parser("dedup-check", help="Check if code already executed in stage")
    dedup_p.add_argument("exp_dir")
    dedup_p.add_argument("stage")
    dedup_p.add_argument("--code", required=True, help="Path to code file")
    dedup_p.add_argument("--cross-stage", action="store_true",
                         help="Also check earlier stages for duplicates")

    # checkpoint-status — show checkpoint progress for a node
    cp_status_p = sub.add_parser("checkpoint-status",
                                 help="Show checkpoint status for a node (for resume logic)")
    cp_status_p.add_argument("exp_dir")
    cp_status_p.add_argument("stage")
    cp_status_p.add_argument("node_id")

    # list-incomplete — list nodes that haven't completed all checkpoints
    inc_p = sub.add_parser("list-incomplete",
                           help="List nodes with incomplete checkpoints (useful for resume)")
    inc_p.add_argument("exp_dir")
    inc_p.add_argument("stage")

    # save-checkpoint — save a specific checkpoint for a node
    sc_p = sub.add_parser("save-checkpoint",
                          help="Save a checkpoint file for a node")
    sc_p.add_argument("exp_dir")
    sc_p.add_argument("stage")
    sc_p.add_argument("node_id")
    sc_p.add_argument("step", choices=["code", "exec", "metrics", "plots", "done"])
    sc_p.add_argument("--from-file", help="Read data from file (alternative to stdin)")

    # load-checkpoint — load a specific checkpoint for a node
    lc_p = sub.add_parser("load-checkpoint",
                          help="Load a checkpoint file for a node")
    lc_p.add_argument("exp_dir")
    lc_p.add_argument("stage")
    lc_p.add_argument("node_id")
    lc_p.add_argument("step", choices=["code", "exec", "metrics", "plots", "done"])

    # error-analysis — analyze error patterns in a stage
    ea_p = sub.add_parser("error-analysis",
                          help="Classify errors in a stage and recommend fixes")
    ea_p.add_argument("exp_dir")
    ea_p.add_argument("stage")

    # test
    sub.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    def _read_file_or_str(val):
        """If val starts with @, read the file; otherwise return as-is."""
        if val and val.startswith("@"):
            return Path(val[1:]).read_text()
        return val

    if args.command == "init":
        with open(args.idea) as f:
            idea = json.load(f)
        config = {}
        if args.config:
            with open(args.config) as f:
                config = yaml.safe_load(f) or {}
        exp_dir = init_experiment(idea, config, base_dir=args.base_dir)
        print(exp_dir)

    elif args.command == "status":
        state = load_experiment_state(args.exp_dir)
        print(json.dumps(state, indent=2))

    elif args.command == "journal-summary":
        journal = load_journal(args.exp_dir, args.stage)
        summary = get_journal_summary(journal)
        print(json.dumps(summary, indent=2))

    elif args.command == "select-nodes":
        journal = load_journal(args.exp_dir, args.stage)
        # Use smart selection: prunes dead branches, prefers diverse parents
        candidates = get_nodes_for_expansion_smart(
            journal,
            max_debug_depth=args.max_debug_depth,
            debug_prob=args.debug_prob,
        )
        result = []
        for c in candidates:
            action = "debug" if c.get("is_buggy") else "improve"
            if c.get("parent_id") is None and not c.get("is_buggy"):
                action = "improve"  # root good node
            result.append({
                "id": c["id"],
                "action": action,
                "metric": c.get("metric"),
                "is_buggy": c.get("is_buggy"),
                "stage": c.get("stage"),
            })
        print(json.dumps(result, indent=2))

    elif args.command == "add-node":
        journal = load_journal(args.exp_dir, args.stage)
        code = ""
        if args.code:
            code = Path(args.code).read_text()
        node = create_node(
            stage=args.stage,
            plan=args.plan,
            code=code,
            parent_id=args.parent_id,
        )
        # Fill execution results
        if args.output_log:
            log_path = Path(args.output_log)
            if log_path.exists():
                node["term_out"] = log_path.read_text().splitlines()
        if args.exec_time is not None:
            node["exec_time"] = args.exec_time
        if args.metric:
            metric_str = _read_file_or_str(args.metric)
            node["metric"] = json.loads(metric_str)
        node["is_buggy"] = args.buggy
        node["is_buggy_plots"] = False
        if args.analysis:
            node["analysis"] = _read_file_or_str(args.analysis)
        node["plot_paths"] = args.plots
        node["datasets_successfully_tested"] = args.datasets

        add_node(journal, node)
        save_journal(args.exp_dir, args.stage, journal)
        save_structured_log(args.exp_dir, args.stage, node)
        print(json.dumps({
            "node_id": node["id"],
            "step": node["step"],
            "is_buggy": node["is_buggy"],
            "metric": node.get("metric"),
        }, indent=2))

    elif args.command == "best-node":
        journal = load_journal(args.exp_dir, args.stage)
        best = get_best_node(journal)
        if best is None:
            print(json.dumps({"error": "No good nodes found"}))
        else:
            info = {
                "id": best["id"],
                "step": best["step"],
                "metric": best.get("metric"),
                "datasets": best.get("datasets_successfully_tested", []),
                "plan": best.get("plan", ""),
            }
            if args.show_code:
                info["code"] = best.get("code", "")
            print(json.dumps(info, indent=2))

    elif args.command == "save-best":
        journal = load_journal(args.exp_dir, args.stage)
        filepath = save_best_solution(args.exp_dir, args.stage, journal)
        if filepath:
            print(filepath)
        else:
            print("No good nodes to save", file=sys.stderr)
            sys.exit(1)

    elif args.command == "transition":
        journal = load_journal(args.exp_dir, args.from_stage)
        best = get_best_node(journal)
        best_id = best["id"] if best else None
        save_best_solution(args.exp_dir, args.from_stage, journal)
        state = transition_stage(
            args.exp_dir, args.from_stage, args.to_stage,
            best_node_id=best_id, reason=args.reason,
        )
        print(json.dumps({
            "from": args.from_stage,
            "to": args.to_stage,
            "best_node_id": best_id,
            "completed_stages": state["completed_stages"],
        }, indent=2))

    elif args.command == "update-state":
        state = update_experiment_state(
            args.exp_dir,
            phase=args.phase,
            stage=args.stage,
            status=args.status,
        )
        print(json.dumps(state, indent=2))

    elif args.command == "node-info":
        journal = load_journal(args.exp_dir, args.stage)
        node = get_node_by_id(journal, args.node_id)
        if node is None:
            print(json.dumps({"error": f"Node {args.node_id} not found"}))
            sys.exit(1)
        info = {k: v for k, v in node.items() if k != "code" or args.show_code}
        if not args.show_code:
            info.pop("code", None)
            info.pop("term_out", None)  # skip verbose output by default
        print(json.dumps(info, indent=2, default=str))

    elif args.command == "stage-briefing":
        journal = load_journal(args.exp_dir, args.stage)
        briefing = get_stage_briefing(journal, args.stage)
        print(json.dumps(briefing, indent=2, default=str))

    elif args.command == "dedup-check":
        journal = load_journal(args.exp_dir, args.stage)
        code = Path(args.code).read_text()
        dup = find_duplicate_node(journal, code)
        if dup:
            print(json.dumps({"duplicate": True, "stage": args.stage, "node_id": dup["id"],
                              "step": dup.get("step"), "metric": dup.get("metric")}))
        elif getattr(args, "cross_stage", False):
            cross_dup = find_cross_stage_duplicate(args.exp_dir, args.stage, code)
            if cross_dup:
                print(json.dumps({"duplicate": True, "stage": cross_dup.get("_source_stage"),
                                  "node_id": cross_dup["id"], "step": cross_dup.get("step"),
                                  "metric": cross_dup.get("metric"), "cross_stage": True}))
            else:
                print(json.dumps({"duplicate": False}))
        else:
            print(json.dumps({"duplicate": False}))

    elif args.command == "checkpoint-status":
        status = checkpoint_status(args.exp_dir, args.stage, args.node_id)
        print(json.dumps(status, indent=2))

    elif args.command == "list-incomplete":
        incomplete = list_incomplete_checkpoints(args.exp_dir, args.stage)
        print(json.dumps(incomplete, indent=2))

    elif args.command == "save-checkpoint":
        if args.from_file:
            data = Path(args.from_file).read_text()
        else:
            data = sys.stdin.read()
        if args.step == "metrics" or args.step == "plots":
            if not data.strip():
                data = {}
            else:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as e:
                    print(json.dumps({"error": f"Invalid JSON for {args.step}: {e}"}))
                    sys.exit(1)
        path = save_checkpoint(args.exp_dir, args.stage, args.node_id, args.step, data)
        print(json.dumps({"saved": path}))

    elif args.command == "load-checkpoint":
        data = load_checkpoint(args.exp_dir, args.stage, args.node_id, args.step)
        if data is None:
            print(json.dumps({"exists": False}))
            sys.exit(1)
        if args.step in ("metrics", "plots"):
            print(json.dumps(data, indent=2))
        else:
            print(data)

    elif args.command == "error-analysis":
        try:
            from tools.error_classifier import analyze_journal
        except ImportError:
            print(json.dumps({"error": "error_classifier module not available"}))
            sys.exit(1)
        journal = load_journal(args.exp_dir, args.stage)
        analysis = analyze_journal(journal)
        print(json.dumps(analysis, indent=2))

    elif args.command == "test":
        print("Running self-test...")
        import tempfile

        idea = {
            "Name": "test_idea",
            "Title": "Test Research Idea",
            "Short Hypothesis": "Testing the state manager",
            "Abstract": "This is a test.",
            "Experiments": ["Exp 1", "Exp 2"],
            "Risk Factors and Limitations": ["Risk 1"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = init_experiment(idea, {"timeout": 3600}, base_dir=tmpdir)
            print(f"  Created experiment: {exp_dir}")

            journal = load_journal(exp_dir, "stage1_initial")
            node1 = create_node("stage1_initial", plan="First draft", code="print('hello')")
            add_node(journal, node1)
            node1["metric"] = {"value": 0.85, "maximize": False, "name": "val_loss"}
            node1["is_buggy"] = False

            node2 = create_node("stage1_initial", plan="Second draft", code="print('world')", parent_id=node1["id"])
            add_node(journal, node2)
            node2["metric"] = {"value": 0.72, "maximize": False, "name": "val_loss"}
            node2["is_buggy"] = False

            save_journal(exp_dir, "stage1_initial", journal)

            journal2 = load_journal(exp_dir, "stage1_initial")
            assert len(journal2["nodes"]) == 2
            best = get_best_node(journal2)
            assert best["id"] == node2["id"]
            print(f"  Best node: {best['id']} (metric: {best['metric']})")

            transition_stage(exp_dir, "stage1_initial", "stage2_baseline", best["id"])
            state = load_experiment_state(exp_dir)
            assert state["current_stage"] == "stage2_baseline"
            print(f"  Stage transition OK")

            print("Self-test PASSED")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
