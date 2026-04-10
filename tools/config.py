"""Configuration loading and defaults for AI Scientist experiments."""

from __future__ import annotations

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
class ScientificSkillsConfig:
    enabled: str = "auto"  # "auto" | "true" | "false"
    enhanced_literature: bool = True   # /research-lookup, /database-lookup, /paper-lookup in ideation
    enhanced_writing: bool = True      # /scientific-writing + /citation-management in writeup
    enhanced_figures: bool = True      # /scientific-visualization in plot phase
    enhanced_review: bool = True       # /scientific-critical-thinking in review

    def __post_init__(self):
        # Normalize enabled to string (YAML may parse true/false as bool)
        self.enabled = str(self.enabled).lower()


@dataclass
class OctopusConfig:
    enabled: str = "auto"  # "auto" | "true" | "false"
    stage_gate_review: bool = True          # Multi-model code review between BFTS stages
    multi_model_paper_review: bool = True   # Multi-provider debate on final paper
    claim_verification: bool = True         # Multi-model fact-checking of paper claims
    rescue_on_stuck: bool = True            # Multi-model diagnosis when experiments stuck
    research_intensity: str = "standard"    # "quick" | "standard" | "deep"

    def __post_init__(self):
        self.enabled = str(self.enabled).lower()


@dataclass
class ModalConfig:
    gpu: str = "A100"  # A100 | H100 | T4 | L4
    timeout: int = 3600
    image: str = "python:3.12"


@dataclass
class ComputeConfig:
    backend: str = ""  # "" (unset, will prompt) | "local" | "modal"
    modal: ModalConfig = field(default_factory=ModalConfig)


@dataclass
class RevisionConfig:
    enabled: bool = False
    score_threshold: int = 5       # re-run if Overall < this
    max_passes: int = 2            # max revision cycles
    prompt_before_revision: bool = True  # ask user before each revision


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
    num_cite_rounds: int = 15
    num_writeup_reflections: int = 3

    # Review
    skip_writeup: bool = False
    skip_review: bool = False

    # Octopus multi-model consensus (optional)
    octopus: OctopusConfig = field(default_factory=OctopusConfig)

    # Scientific skills integration (optional)
    scientific_skills: ScientificSkillsConfig = field(default_factory=ScientificSkillsConfig)

    # Compute backend
    compute: ComputeConfig = field(default_factory=ComputeConfig)

    # Revision loop
    revision: RevisionConfig = field(default_factory=RevisionConfig)


# ── Default config path ──────────────────────────────────────────────────────

try:
    from tools import TEMPLATES_DIR
except ImportError:
    TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
# Check project-local config first, fall back to template
_PROJECT_CONFIG = Path("config.yaml")
DEFAULT_CONFIG_PATH = _PROJECT_CONFIG if _PROJECT_CONFIG.exists() else TEMPLATES_DIR / "bfts_config.yaml"


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


def _validate_keys(data: dict, cls, prefix: str = "") -> list[str]:
    """Check for unknown keys in config dict. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        return warnings
    known = {f.name for f in cls.__dataclass_fields__.values()}
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    for key in data:
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in known:
            warnings.append(f"Unknown config key '{full_key}' — will be ignored. Check for typos.")
        elif isinstance(data[key], dict) and key in field_types:
            ft = field_types[key]
            if isinstance(ft, str):
                ft = eval(ft)
            if isinstance(ft, type) and hasattr(ft, "__dataclass_fields__"):
                warnings.extend(_validate_keys(data[key], ft, full_key))
    return warnings


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

    # Validate keys — warn about typos
    warnings = _validate_keys(cfg_dict, Config)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

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
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the result back to the config file (requires --config or writes to templates/bfts_config.yaml)",
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

def main():
    args_parser = argparse.ArgumentParser(description="AI Scientist config loader")
    args_parser.add_argument("--config", type=str, default=None)
    args_parser.add_argument("--set", nargs="*", metavar="KEY=VALUE", default=[])
    args_parser.add_argument("--save", action="store_true")
    args = args_parser.parse_args()

    overrides = {}
    for kv in args.set:
        key, _, val = kv.partition("=")
        try:
            val = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
        parts = key.split(".")
        d = overrides
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val

    cfg = load_config(args.config, overrides)
    output = yaml.dump(asdict(cfg), default_flow_style=False, sort_keys=False)
    print(output)

    if args.save and args.set:
        save_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
        save_config(cfg, str(save_path))
        print(f"Saved to {save_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
