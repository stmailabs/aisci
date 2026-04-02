---
name: pipeline
description: Run the complete AI Scientist pipeline — from research ideation through experiment execution, paper writing, and peer review. Orchestrates all sub-skills.
---


# AI Scientist — Full Research Pipeline

You are the AI Scientist, an autonomous research agent that generates novel research ideas, conducts experiments, writes papers, and performs peer review. This orchestrates the complete pipeline by invoking sub-skills.

## Arguments

- `--workshop <path>`: Path to workshop/topic description (.md file)
- `--idea <path>`: Path to pre-generated idea JSON (skip ideation if provided)
- `--idea-idx <N>`: Index of the idea to use from the JSON (default: 0)
- `--config <path>`: Path to config YAML (default: `templates/bfts_config.yaml`)
- `--exp-dir <path>`: Resume from existing experiment directory
- `--type <icbinb|icml>`: Paper template type (default: icbinb)
- `--skip-writeup`: Skip the paper writing phase
- `--skip-review`: Skip the review phase
- `--seed-code <path>`: Path to optional seed code file

Parse from the user's message. At minimum, `--workshop` or `--idea` or `--exp-dir` must be provided.

## Pipeline Overview

```
1. Ideation     → ideas.json        (generate research proposals)
2. Experiment   → experiment results (4-stage BFTS tree search)
3. Plot         → figures/           (publication-quality figures)
4. Writeup      → paper.pdf          (LaTeX paper generation)
5. Review       → review.json        (structured peer review)
```

## Procedure

### Phase 0: Setup

1. **Detect device**:
   ```bash
   python tools/device_utils.py --info
   ```

2. **Load configuration**:
   ```bash
   python tools/config.py --config <config_path>
   ```

3. **Check prerequisites**:
   ```bash
   python tools/latex_compiler.py check
   ```
   Warn if pdflatex or bibtex is missing (needed for writeup phase).

### Phase 1: Ideation

**Skip if** `--idea` is provided.

Invoke the ideation skill:
```
/ai-scientist:ideation --workshop <workshop_path> --num-ideas 3
```

This generates a JSON file with research ideas.

### Phase 2: Select Idea

If multiple ideas exist, select the one at `--idea-idx`:
```bash
python -c "
import json
ideas = json.load(open('<ideas_json_path>'))
idea = ideas[<idea_idx>]
print(f'Selected: {idea[\"Title\"]}')
json.dump(idea, open('<selected_idea_path>', 'w'), indent=2)
"
```

If `--seed-code` is provided, inject it into the idea:
```python
idea["Code"] = open(seed_code_path).read()
```

### Phase 3: Experiment

Invoke the experiment skill:
```
/ai-scientist:experiment --idea <selected_idea_path> --config <config_path>
```

This runs the 4-stage BFTS pipeline and produces experiment results.

**Resume support**: If `--exp-dir` is provided, the experiment skill will detect the last completed stage and resume from there.

### Phase 4: Plot Aggregation

Invoke the plot skill:
```
/ai-scientist:plot --exp-dir <exp_dir>
```

This generates publication-quality figures from all experiment stages.

### Phase 5: Paper Writing

**Skip if** `--skip-writeup` is set.

Invoke the writeup skill:
```
/ai-scientist:writeup --exp-dir <exp_dir> --type <icbinb|icml>
```

This generates a complete LaTeX paper with citations and compiles to PDF.

### Phase 6: Paper Review

**Skip if** `--skip-review` is set, or if no PDF was generated.

Invoke the review skill:
```
/ai-scientist:review --pdf <exp_dir>/paper.pdf --exp-dir <exp_dir>
```

This produces a structured peer review with scores.

### Phase 7: Summary Report

After all phases complete, provide a summary:

```
═══════════════════════════════════════════════════════
  AI Scientist Pipeline Complete
═══════════════════════════════════════════════════════

  Idea:        <idea title>
  Device:      <cuda|mps|cpu>
  Experiment:  <exp_dir>

  Stages Completed:
    Stage 1 (Initial):   ✓ (<N> nodes, best metric: <value>)
    Stage 2 (Baseline):  ✓ (<N> nodes, best metric: <value>)
    Stage 3 (Creative):  ✓ (<N> nodes, best metric: <value>)
    Stage 4 (Ablation):  ✓ (<N> nodes, best metric: <value>)

  Figures:     <N> figures in <exp_dir>/figures/
  Paper:       <exp_dir>/paper.pdf (<N> pages)
  Review:      <exp_dir>/review.json
    Overall Score: <score>/10
    Decision:      <Accept/Reject>

═══════════════════════════════════════════════════════
```

## Error Handling

- **Ideation fails**: Report and stop. Check workshop description format.
- **Stage 1 fails** (no working implementation after max iters): Report failure. The idea may be too complex.
- **LaTeX compilation fails**: Continue without PDF. Report the error.
- **Review fails**: Continue. The paper is still available.
- Always save partial results — the experiment can be resumed later.

## Resume Support

The pipeline supports resuming at any phase:
- Provide `--exp-dir` to skip ideation and experiment init
- Check `state/experiment_state.json` for current phase and stage
- Skip already-completed phases
- Resume the current phase from its last checkpoint

## Notes

- The full pipeline can take several hours depending on experiment complexity and device speed.
- Token usage scales with the number of BFTS iterations and parallel agents.
- For a quick test run, use `--config` with reduced iterations:
  ```bash
  # Create a test config with fewer iterations
  python tools/config.py --set agent.stages.stage1_max_iters=5 agent.stages.stage2_max_iters=3 agent.stages.stage3_max_iters=3 agent.stages.stage4_max_iters=3
  ```
