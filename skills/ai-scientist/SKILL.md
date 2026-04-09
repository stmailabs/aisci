---
name: ai-scientist
description: Run the complete AI Scientist pipeline — from research ideation through experiment execution, paper writing, and peer review. Orchestrates all sub-skills.
---


# AI Scientist — Full Research Pipeline

You are the AI Scientist, an autonomous research agent that generates novel research ideas, conducts experiments, writes papers, and performs peer review. This orchestrates the complete pipeline by invoking sub-skills.

> **Runtime**: This project uses `uv` with a `.venv` in the **project directory**. ALL `ai-scientist-*` CLI commands must be called with `uv run` from the project directory, e.g. `uv run ai-scientist-verify`. **Never cd into the plugin cache directory** — always run commands from the user's project working directory.

## Arguments

- `--workshop <path>`: Path to workshop/topic description (.md file)
- `--idea <path>`: Path to pre-generated idea JSON (skip ideation if provided)
- `--idea-idx <N>`: Index of the idea to use from the JSON (default: 0)
- `--config <path>`: Path to config YAML (default: `config.yaml`)
- `--exp-dir <path>`: Resume from existing experiment directory
- `--type <icbinb|icml>`: Paper template type (default: icbinb)
- `--skip-writeup`: Skip the paper writing phase
- `--skip-review`: Skip the review phase
- `--seed-code <path>`: Path to optional seed code file
- `--use-octopus`: Force enable Octopus integration (even if auto-detection fails)
- `--no-octopus`: Force disable Octopus integration (even if Octopus is installed)
- `--no-scientific-skills`: Disable claude-scientific-skills integration (even if installed)
- `--dry-run`: Validate environment and config without running experiments. Reports readiness status and estimated token budget.
- `--revision-passes <N>`: Number of review-revise cycles (overrides config max_passes, 0 = no revision)

Parse from the user's message. If none of `--workshop`, `--idea`, or `--exp-dir` is provided, start with Phase 0.5 (Workshop Creator) to interactively guide the user.

## Pipeline Overview

```
0.5. Workshop    → topic.md          (interactive topic creation, if needed)
1.   Ideation    → ideas.json        (generate research proposals)
2.   Experiment  → experiment results (4-stage BFTS tree search)
3.   Plot        → figures/           (publication-quality figures)
4.   Writeup     → paper.pdf          (LaTeX paper generation)
5.   Review      → review.json        (structured peer review)
```

## Procedure

### Phase 0: Setup

**Important**: This project uses `uv` with a `.venv` in the project directory. All CLI tools (`ai-scientist-verify`, `ai-scientist-state`, etc.) are installed in `.venv/bin/`. Use `uv run` to invoke them, or activate the venv first. If `.venv` doesn't exist or tools are missing, tell the user to run:
```bash
curl -fsSL https://raw.githubusercontent.com/stamate/ai-scientist-skills/main/scripts/install.sh | bash
```

0. **Verify environment and load config**:
   ```bash
   uv run ai-scientist-verify
   uv run ai-scientist-device --info
   uv run ai-scientist-config --config config.yaml
   ```
   If verify fails, **stop and guide the user** through fixing the issues.

1. **Check compute backend**:

   Read `compute.backend` from the config output (step 0). If it says `modal`:
   ```bash
   uv run modal profile current 2>&1
   ```
   If authenticated, report: "Compute: ✓ Modal.com with <gpu> GPU (authenticated)"
   If NOT authenticated, warn: "Compute: ! Modal configured but not authenticated — run 'uv run modal setup'"

   If `compute.backend` is `local`:
   Report: "Compute: ✓ Local (<device from step 0>)"

2. **Check LaTeX** (optional, only needed for writeup):
   ```bash
   uv run ai-scientist-latex check
   ```
   Warn if pdflatex or bibtex is missing — the experiment can still run, paper generation will be skipped.

3. **Detect Octopus** (optional enhancement):

   Check if the claude-octopus plugin is installed and the config toggle:
   ```bash
   claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('octo' in p['id'] for p in json.load(sys.stdin)) and print('OCTOPUS_OK') or print('OCTOPUS_MISSING')" 2>/dev/null
   ```
   Also read the `octopus.enabled` value from the loaded config (step 0 above).

   Determine `OCTOPUS_ENABLED`:
   - If `--no-octopus` is set: `OCTOPUS_ENABLED=false` regardless of anything else
   - If `octopus.enabled` is `"false"` in config: `OCTOPUS_ENABLED=false`
   - If `--use-octopus` is set: `OCTOPUS_ENABLED=true` (warn if plugin missing)
   - If `octopus.enabled` is `"auto"`: `OCTOPUS_ENABLED=true` only if plugin found
   - If `octopus.enabled` is `"true"`: `OCTOPUS_ENABLED=true` (warn if plugin missing)

   Print result:
   - If `OCTOPUS_ENABLED=true`: "Octopus detected — multi-model reviews enabled"
   - If plugin missing: "claude-octopus not installed — install with: claude install gh:stamate/claude-octopus"
   - If `OCTOPUS_ENABLED=false`: "Octopus not enabled — using standard pipeline"

4. **Detect claude-scientific-skills** (optional enhancement):

   Check if the claude-scientific-skills plugin is installed:
   ```bash
   # Check both global and project-local plugin paths for the research-lookup skill
   claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('sci-skills' in p['id'] for p in json.load(sys.stdin)) and print('SCIENTIFIC_SKILLS_OK') or print('SCIENTIFIC_SKILLS_MISSING')" 2>/dev/null
   ```
   This checks for the `/research-lookup` skill which is present in claude-scientific-skills and claude-scientific-writer plugins.
   Also read the `scientific_skills.enabled` value from the loaded config (step 0).

   Determine `SCIENTIFIC_SKILLS_ENABLED`:
   - If `--no-scientific-skills` is set: `SCIENTIFIC_SKILLS_ENABLED=false`
   - If `scientific_skills.enabled` is `"false"` in config: `SCIENTIFIC_SKILLS_ENABLED=false`
   - If `scientific_skills.enabled` is `"auto"`: `SCIENTIFIC_SKILLS_ENABLED=true` only if plugin found
   - If `scientific_skills.enabled` is `"true"`: `SCIENTIFIC_SKILLS_ENABLED=true` (warn if missing)

   Print result:
   - If `SCIENTIFIC_SKILLS_ENABLED=true`: "Scientific skills detected — enhanced literature, writing, and review enabled"
   - If not found: "claude-scientific-skills not found — using standard pipeline (install for 78+ database access, DOI verification, and IMRAD writing)"

### Phase 0 Summary

After all checks, print a summary that MUST include ALL of these lines:
```
  Python:      ✓ <version>
  Device:      ✓ <device>
  Compute:     ✓ <local or Modal.com with GPU type>
  Config:      ✓ <stages/iters/workers>
  LaTeX:       ✓ or ! <status>
  S2 API:      ✓ or ! <status>
  Octopus:     ✓ or ✗ <status>
  Scientific:  ✓ or ✗ <status>
```

Read `compute.backend` and `compute.modal.gpu` from the config output to fill the Compute line. If `backend` is `modal`, show "Modal.com with <gpu> GPU". If `local`, show "Local (<device>)".

### Dry-Run Check

**Only if** `--dry-run` is set. After Phase 0 completes, perform extended validation and stop:

1. Report all Phase 0 results (environment, device, compute backend, config, LaTeX, Octopus, scientific skills)
2. If `--workshop` provided, validate the workshop file has required sections (Title, Keywords, TL;DR, Abstract)
3. If `--idea` provided, validate the idea JSON has required fields per `templates/idea_schema.json`
4. Test S2 API connectivity:
   ```bash
   uv run ai-scientist-search check
   ```
5. Test LaTeX compilation with a minimal document:
   ```bash
   uv run ai-scientist-latex check
   ```
6. Report estimated token budget (if budget_estimator.py exists):
   ```bash
   uv run ai-scientist-budget --config <config_path> 2>/dev/null || echo "Budget estimator not available"
   ```
7. Print summary:
   ```
   ═══════════════════════════════════════════════════════
     AI Scientist Dry Run — Validation Complete
   ═══════════════════════════════════════════════════════
     Environment:    ✓ Ready
     Workshop:       ✓ Valid (or N/A)
     Config:         ✓ Loaded (<N> stages, <N> max iters)
     LaTeX:          ✓ Available (or ✗ Missing)
     S2 API:         ✓ Connected (or ! Fallback to WebSearch)
     Octopus:        ✓ Enabled (or — Disabled)
     Scientific:     ✓ Enabled (or — Disabled)
   ═══════════════════════════════════════════════════════
   ```
8. **Stop here.** Do not proceed to Phase 0.5 or beyond.

### Phase 0.5: Workshop Creator

**Skip if** `--workshop`, `--idea`, or `--exp-dir` is already provided.

If the user didn't specify a research topic, invoke the workshop skill to guide them interactively:
```
/ai-scientist:workshop
```

This will ask the user about their research interests and generate a workshop description `.md` file. Use the output path as `--workshop` for the next phase.

### Phase 1: Ideation

**Skip if** `--idea` is provided.

Invoke the ideation skill. Pass the config path so it can read feature toggles, and `--no-scientific-skills` if disabled:
```
/ai-scientist:ideation --workshop <workshop_path> --num-ideas 3 --config <config_path>
```
Add `--no-scientific-skills` if `SCIENTIFIC_SKILLS_ENABLED` is false.

This generates a JSON file with research ideas.

### Phase 2: Select Idea

If multiple ideas exist, select the one at `--idea-idx`:
```bash
uv run python3 -c "
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

Invoke the experiment skill. If Octopus is disabled, pass `--no-octopus` so experiment-level Octopus hooks are also skipped:

**If `OCTOPUS_ENABLED`**:
```
/ai-scientist:experiment --idea <selected_idea_path> --config <config_path>
```

**If NOT `OCTOPUS_ENABLED`**:
```
/ai-scientist:experiment --idea <selected_idea_path> --config <config_path> --no-octopus
```

This runs the 4-stage BFTS pipeline and produces experiment results.

**Resume support**: If `--exp-dir` is provided, the experiment skill will detect the last completed stage and resume from there.

### Phase 4: Plot Aggregation

Invoke the plot skill. If scientific skills are disabled, pass `--no-scientific-skills`:
```
/ai-scientist:plot --exp-dir <exp_dir>
```
Add `--no-scientific-skills` if `SCIENTIFIC_SKILLS_ENABLED` is false.

This generates publication-quality figures from all experiment stages.

### Phase 5: Paper Writing

**Skip if** `--skip-writeup` is set.

Invoke the writeup skill. If scientific skills are disabled, pass `--no-scientific-skills`:
```
/ai-scientist:writeup --exp-dir <exp_dir> --type <icbinb|icml>
```
Add `--no-scientific-skills` if `SCIENTIFIC_SKILLS_ENABLED` is false.

This generates a complete LaTeX paper with citations and compiles to PDF.

### Phase 6: Paper Review

**Skip if** `--skip-review` is set, or if no PDF was generated.

Run the review skill. Forward `--no-octopus` if Octopus is disabled so the review skill skips the multi-model review step:

**If `OCTOPUS_ENABLED`**:
```
/ai-scientist:review --pdf <exp_dir>/paper.pdf --exp-dir <exp_dir>
```
The review skill's Step 11 automatically invokes `/octo:debate` for multi-model paper review with code-methods alignment.

**If NOT `OCTOPUS_ENABLED`**:
```
/ai-scientist:review --pdf <exp_dir>/paper.pdf --exp-dir <exp_dir> --no-octopus
```

Also forward `--no-scientific-skills` if `SCIENTIFIC_SKILLS_ENABLED` is false, to skip Step 9 (evidence assessment) in the review skill.

The `/ai-scientist:octo-review` skill exists for standalone use when the user wants multi-model review without the Claude review.

### Phase 6.5: Revision Loop (Optional)

**Skip if** `revision.enabled` is `false` in config AND `--revision-passes` is not set or is 0.

If `--revision-passes <N>` is provided, use that as max passes (overrides config). Otherwise use `revision.max_passes` from config.

For each revision pass (up to max_passes):

1. **Check score**: Read the review from `<exp_dir>/review.json`. Extract the `Overall` score (1-10).
   - If `Overall >= revision.score_threshold`: print "Review score <score>/10 meets threshold (<threshold>). No revision needed." and **break the loop**.

2. **Prompt user** (if `revision.prompt_before_revision` is `true`):
   Ask the user:
   > "Review score is <score>/10 (threshold: <threshold>). Revision pass <N>/<max>. Options:"
   > 1. "Revise and re-review (recommended)"
   > 2. "Accept current paper and stop"

   If user chooses to stop, break the loop.

3. **Extract actionable feedback**: From the review JSON, collect:
   - All items in `Weaknesses` array
   - All items in `Questions` array
   - If Octopus review exists (`octopus_review.md`), extract its weaknesses too
   - If evidence assessment exists (`evidence_assessment.md`), extract concerns

4. **Map feedback to phases**: Categorize each weakness:
   - "missing baselines", "insufficient experiments", "more datasets" -> re-run relevant experiment stage
   - "unclear writing", "poor organization", "grammar" -> re-run writeup
   - "missing citations", "uncited claims" -> re-run citation gathering in writeup
   - "figure quality", "unclear plots" -> re-run plot aggregation
   - Everything else -> re-run writeup (default)

5. **Re-run affected phases**:
   - If experiments need re-running: invoke `/ai-scientist:experiment --exp-dir <exp_dir> --start-stage <N>` where N is the stage number (1=initial, 2=baseline, 3=creative, 4=ablation)
   - If plots need re-running: invoke `/ai-scientist:plot --exp-dir <exp_dir>`
   - If writeup needs re-running: invoke `/ai-scientist:writeup --exp-dir <exp_dir> --type <type>` with the review feedback injected into the task context
   - Always re-run writeup after any experiment/plot changes

6. **Re-review**:
   - First, preserve the current review: `cp <exp_dir>/review.json <exp_dir>/review_pass<N>.json`
   - Then re-run: invoke `/ai-scientist:review --pdf <exp_dir>/paper.pdf --exp-dir <exp_dir>`
   - The review skill writes the new review to `review.json`, which is checked in the next loop iteration check

7. **Report revision**: "Revision pass <N> complete. New score: <new_score>/10 (was: <old_score>/10)"

After all passes complete (or threshold met), proceed to Phase 7.

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
  Evidence:    <exp_dir>/evidence_assessment.md (if scientific-skills available)
    Quality:     <High/Moderate/Low> (GRADE framework)
  Octopus Review: <exp_dir>/octopus_review.md (if Octopus available)
    Panel:         <recommendation> (multi-model consensus)
    Alignment:     <aligned/minor-discrepancies/major-discrepancies>
  Revisions:   <N> pass(es) (score: <initial> -> <final>)

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
  uv run ai-scientist-config --set agent.stages.stage1_max_iters=5 agent.stages.stage2_max_iters=3 agent.stages.stage3_max_iters=3 agent.stages.stage4_max_iters=3
  ```
