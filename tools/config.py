"""Configuration loading and defaults for AI Scientist experiments.

Adapted from AI-Scientist-v2/ai_scientist/treesearch/utils/config.py
to work standalone with Claude Code skills.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml


# ── Data classes mirroring the original Config hierarchy ──────────────────────


@dataclass
class SearchConfig:
    max_debug_depth: int = 3
    debug_prob: float = 0.5
    num_drafts: int = 3


@dataclass
class StageIterations:
    stage1_max_iters: int = 20
    stage2_max_iters: int = 12
    stage3_max_iters: int = 12
    stage4_max_iters: int = 18


@dataclass
class ExecConfig:
    timeout: int = 3600
    agent_file_name: str = "runfile.py"


@dataclass
class AgentConfig:
    type: str = "parallel"
    num_workers: int = 2
    stages: StageIterations = field(default_factory=StageIterations)
    search: SearchConfig = field(default_factory=SearchConfig)
    k_fold_validation: int = 1
    data_preview: bool = False
    expose_prediction: bool = False


@dataclass
class ExperimentConfig:
    num_syn_datasets: int = 1


@dataclass
class Config:
    """Top-level configuration for an AI Scientist experiment run."""

    # Directories
    data_dir: str = "data"
    log_dir: str = "logs"
    workspace_dir: str = "workspaces"

    # Task description
    desc_file: Optional[str] = None
    goal: Optional[str] = None
    eval: Optional[str] = None

    # Data handling
    preprocess_data: bool = False
    copy_data: bool = True

    # Experiment naming
    exp_name: str = "run"

    # Execution
    exec: ExecConfig = field(default_factory=ExecConfig)

    # Agent
    agent: AgentConfig = field(default_factory=AgentConfig)

    # Experiment
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)

    # Report
    generate_report: bool = True

    # Paper writeup
    writeup_type: str = "icbinb"  # "icbinb" (4-page) or "icml" (8-page)
    num_cite_rounds: int = 20
    num_writeup_reflections: int = 3

    # Review
    skip_writeup: bool = False
    skip_review: bool = False


# ── Default config path ──────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
DEFAULT_CONFIG_PATH = TEMPLATES_DIR / "bfts_config.yaml"


# ── Loading / merging ────────────────────────────────────────────────────────


def _nested_dataclass_from_dict(cls, data: dict):
    """Recursively instantiate nested dataclasses from a dict."""
    if not isinstance(data, dict):
        return data
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key in field_types:
            ft = field_types[key]
            # Resolve string type annotations
            if isinstance(ft, str):
                ft = eval(ft)
            if isinstance(ft, type) and hasattr(ft, "__dataclass_fields__") and isinstance(value, dict):
                kwargs[key] = _nested_dataclass_from_dict(ft, value)
            else:
                kwargs[key] = value
    return cls(**kwargs)


def load_config(path: Optional[str] = None, overrides: Optional[dict] = None) -> Config:
    """Load configuration from a YAML file and apply optional overrides.

    Parameters
    ----------
    path : str | None
        Path to YAML config file.  Falls back to templates/bfts_config.yaml.
    overrides : dict | None
        Key-value pairs that override loaded values (flat or nested).
    """
    cfg_dict: dict = {}
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path) as f:
            cfg_dict = yaml.safe_load(f) or {}

    # Apply overrides
    if overrides:
        _deep_merge(cfg_dict, overrides)

    cfg = _nested_dataclass_from_dict(Config, cfg_dict)
    return cfg


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def save_config(cfg: Config, path: str) -> None:
    """Persist a Config to YAML."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        yaml.dump(asdict(cfg), f, default_flow_style=False, sort_keys=False)


def config_to_dict(cfg: Config) -> dict:
    """Convert Config to a plain dict."""
    return asdict(cfg)


# ── CLI helper ───────────────────────────────────────────────────────────────


def parse_config_args(argv=None) -> Config:
    """Quick CLI wrapper for loading config with --config and --set overrides."""
    parser = argparse.ArgumentParser(description="AI Scientist config loader")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config")
    parser.add_argument(
        "--set",
        nargs="*",
        metavar="KEY=VALUE",
        default=[],
        help="Override config values (e.g. --set agent.num_workers=4 exec.timeout=1800)",
    )
    args = parser.parse_args(argv)

    overrides = {}
    for kv in args.set:
        key, _, val = kv.partition("=")
        # Try to parse as JSON for booleans / numbers
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
        # Support dotted keys → nested dict
        parts = key.split(".")
        d = overrides
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val

    return load_config(args.config, overrides)


# ── Main (self-test) ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = parse_config_args()
    print(yaml.dump(asdict(cfg), default_flow_style=False, sort_keys=False))
