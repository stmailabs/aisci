"""Estimate token usage and cost for an AI Scientist pipeline run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


# Token estimates per operation
TOKENS_PER_IDEA_REFLECTION = 4_000
TOKENS_PER_LIT_SEARCH = 3_000
TOKENS_PER_EXPERIMENT_STEP = 12_000
TOKENS_PER_MULTI_SEED_RUN = 2_000
TOKENS_PER_STAGE_TRANSITION = 5_000
TOKENS_PER_CITE_ROUND = 6_000
TOKENS_PER_WRITEUP_REFLECTION = 10_000
TOKENS_PER_REVIEW = 15_000
TOKENS_PER_OCTOPUS_REVIEW = 25_000  # Higher: dispatches to multiple models
TOKENS_PER_SCIENTIFIC_REVIEW = 10_000

# Cost per million tokens (approximate)
CLAUDE_COST_PER_M_INPUT = 3.0
CLAUDE_COST_PER_M_OUTPUT = 15.0
OCTOPUS_COST_PER_M = 3.0  # Blended across providers


def estimate(config: dict, num_ideas: int = 3) -> dict:
    stages = config.get("agent", {}).get("stages", {})
    s1 = stages.get("stage1_max_iters", 20)
    s2 = stages.get("stage2_max_iters", 12)
    s3 = stages.get("stage3_max_iters", 12)
    s4 = stages.get("stage4_max_iters", 18)
    total_iters = s1 + s2 + s3 + s4
    num_reflections = 5
    cite_rounds = config.get("num_cite_rounds", 5)
    writeup_reflections = config.get("num_writeup_reflections", 3)

    octo_cfg = config.get("octopus", {})
    sci_cfg = config.get("scientific_skills", {})
    octo_enabled = str(octo_cfg.get("enabled", "auto")).lower() != "false"
    sci_enabled = str(sci_cfg.get("enabled", "auto")).lower() != "false"

    ideation = num_ideas * (
        TOKENS_PER_IDEA_REFLECTION * num_reflections + TOKENS_PER_LIT_SEARCH * 2
    )
    experiments = total_iters * TOKENS_PER_EXPERIMENT_STEP
    multi_seed = 4 * 3 * TOKENS_PER_MULTI_SEED_RUN
    transitions = 3 * TOKENS_PER_STAGE_TRANSITION
    writeup = cite_rounds * TOKENS_PER_CITE_ROUND + writeup_reflections * TOKENS_PER_WRITEUP_REFLECTION
    review = TOKENS_PER_REVIEW

    claude_total = ideation + experiments + multi_seed + transitions + writeup + review

    octopus_total = 0
    if octo_enabled:
        if octo_cfg.get("stage_gate_review", True):
            octopus_total += 3 * TOKENS_PER_OCTOPUS_REVIEW
        if octo_cfg.get("multi_model_paper_review", True):
            octopus_total += TOKENS_PER_OCTOPUS_REVIEW
        if octo_cfg.get("claim_verification", True):
            octopus_total += TOKENS_PER_OCTOPUS_REVIEW // 2
        if octo_cfg.get("rescue_on_stuck", True):
            octopus_total += TOKENS_PER_OCTOPUS_REVIEW

    if sci_enabled:
        if sci_cfg.get("enhanced_literature", True):
            claude_total += num_ideas * TOKENS_PER_LIT_SEARCH * 3
        if sci_cfg.get("enhanced_writing", True):
            claude_total += TOKENS_PER_CITE_ROUND * 2
        if sci_cfg.get("enhanced_figures", True):
            claude_total += 5_000
        if sci_cfg.get("enhanced_review", True):
            claude_total += TOKENS_PER_SCIENTIFIC_REVIEW

    revision_cfg = config.get("revision", {})
    revision_enabled = revision_cfg.get("enabled", False)
    revision_passes = revision_cfg.get("max_passes", 0) if revision_enabled else 0
    revision_total = 0
    if revision_passes > 0:
        revision_total = revision_passes * (writeup + review)
        claude_total += revision_total

    return {
        "ideation": ideation,
        "experiments": experiments,
        "multi_seed": multi_seed,
        "transitions": transitions,
        "writeup": writeup,
        "review": review,
        "revision": revision_total,
        "claude_total": claude_total,
        "octopus_total": octopus_total,
        "octopus_enabled": octo_enabled,
        "scientific_skills_enabled": sci_enabled,
        "revision_passes": revision_passes,
    }


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1_000:.0f}K"


def main():
    parser = argparse.ArgumentParser(description="Estimate token usage for AI Scientist pipeline")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--ideas", type=int, default=3, help="Number of ideas to generate")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    est = estimate(config, args.ideas)

    if args.json:
        print(json.dumps(est, indent=2))
        return

    print()
    print("Estimated token usage:")
    print(f"  Ideation ({args.ideas} ideas, 5 reflections):  {format_tokens(est['ideation']):>8}")
    print(f"  Experiments (4 stages):                {format_tokens(est['experiments']):>8}")
    print(f"  Multi-seed validation:                 {format_tokens(est['multi_seed']):>8}")
    print(f"  Stage transitions:                     {format_tokens(est['transitions']):>8}")
    print(f"  Writeup (citations + reflections):     {format_tokens(est['writeup']):>8}")
    print(f"  Review:                                {format_tokens(est['review']):>8}")
    if est["revision_passes"] > 0:
        print(f"  Revision ({est['revision_passes']} passes):              {format_tokens(est['revision']):>8}")
    print(f"  {'─' * 48}")
    print(f"  Total Claude:    {format_tokens(est['claude_total']):>8}")
    if est["octopus_enabled"]:
        print(f"  Total Octopus:   {format_tokens(est['octopus_total']):>8}")
    print()

    claude_cost = est["claude_total"] / 1_000_000 * (CLAUDE_COST_PER_M_INPUT + CLAUDE_COST_PER_M_OUTPUT) / 2
    octo_cost = est["octopus_total"] / 1_000_000 * OCTOPUS_COST_PER_M
    print(f"  Estimated cost: ~${claude_cost:.2f} (Claude)", end="")
    if est["octopus_enabled"]:
        print(f" + ~${octo_cost:.2f} (Octopus)", end="")
    print()
    print()


if __name__ == "__main__":
    main()
