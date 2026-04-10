---
name: experiment
description: Run the complete 4-stage Best-First Tree Search experiment pipeline — from initial implementation through ablation studies, with multi-agent parallel exploration.
---


# BFTS Experiment Pipeline

You are the experiment orchestrator for the AI Scientist system. This skill manages the complete 4-stage Best-First Tree Search (BFTS) pipeline.

## Arguments

- `--idea <path>`: Path to idea JSON file (required)
- `--config <path>`: Path to config YAML (optional, defaults to `config.yaml`)
- `--exp-dir <path>`: Resume from existing experiment directory (optional)
- `--start-stage <N>`: Start from stage N (1-4, default: 1)
- `--no-octopus`: Disable all Octopus integration (stage-gate review, rescue) even if Octopus is available

Parse these from the user's message.

## Stage Definitions

| Stage | Name | Goal | Max Iters | Key Constraints |
|-------|------|------|-----------|-----------------|
| 1 | Initial Implementation | Working code on simple dataset | 20 | Use simple dataset; if seed code provided, start from it |
| 2 | Baseline Tuning | Optimize hyperparameters | 12 | DO NOT change architecture; add 2+ HF datasets |
| 3 | Creative Research | Novel improvements | 12 | Be creative; use 3 HF datasets total |
| 4 | Ablation Studies | Component analysis | 18 | Same datasets as Stage 3; systematic disable/modify |

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Initialize Experiment

**New experiment** (no `--exp-dir`):
```bash
uv run aisci-state init --idea <idea_path> --config <config_path>
```
This prints the experiment directory path. Use it as `<exp_dir>` in all subsequent commands.

**Resume** (with `--exp-dir`):
```bash
uv run aisci-state status <exp_dir>
```
Read the current stage and completed stages to know where to resume.

### 2. Detect Device
```bash
uv run aisci-device --info
```

### 3. Load Config
```bash
uv run aisci-config --config <config_path>
```

Key values:
- `agent.num_workers`: parallel agents (default 2)
- `agent.stages.stageN_max_iters`: iteration limits
- `agent.search.num_drafts`: initial drafts per stage (default 3)
- `agent.search.max_debug_depth`: max debug retries (default 3)
- `agent.search.debug_prob`: probability of debugging a buggy node (default 0.5)
- `exec.timeout`: execution timeout in seconds (default 3600)

### 4. Build Task Description

Compose from the idea JSON:
```
You are an ambitious AI researcher looking to publish a paper at a top conference.

Title: <idea.Title>
Abstract: <idea.Abstract>
Short Hypothesis: <idea["Short Hypothesis"]>

Current Stage: <stage_name>
Stage Goals: <stage_goals>
```

For Stage 3, also include `Experiments` from the idea.
For Stage 4, also include `Risk Factors and Limitations`.

### 5. Execute Stages (Main Loop)

For each stage (1 through 4):

#### a. Create Initial Draft Nodes

For the FIRST stage only, create `num_drafts` (default 3) draft nodes.
Launch `num_workers` Agent subagents in parallel, each running `/aisci:experiment-step`:

```
Agent 1: /aisci:experiment-step --exp-dir <exp_dir> --stage <stage> --action draft --task-desc "<task_desc>" --stage-goals "<goals>"
Agent 2: /aisci:experiment-step --exp-dir <exp_dir> --stage <stage> --action draft --task-desc "<task_desc>" --stage-goals "<goals>"
```

For stages 2-4, carry the best node from the previous stage as the starting point (no new drafts).

#### a0. Dynamic Sub-stage Planning (new in v0.5)

**Run this at the START of stages 2-4 only** (after stage transition, before iterations begin). Skip for stage 1.

Before starting iterations in this stage, generate 2-3 concrete sub-goals based on the previous stage's findings:

1. Read the stage briefing from the previous stage
2. Identify: (a) what worked, (b) what failed, (c) what's still unknown
3. Generate 2-3 sub-goals for THIS stage that:
   - Address the stage's core goal (baseline tuning / creative research / ablation)
   - Build on the previous stage's strengths
   - Avoid repeating failures
4. Save the sub-goals to `<exp_dir>/state/<stage>/substages.json`:
   ```json
   {
     "sub_goals": [
       {"name": "hyperparameter_sweep", "description": "...", "target_iters": 4},
       {"name": "dataset_expansion", "description": "...", "target_iters": 4},
       {"name": "architectural_refinement", "description": "...", "target_iters": 4}
     ],
     "current_substage": "hyperparameter_sweep"
   }
   ```
5. Allocate iterations across sub-goals (roughly equal by default)
6. Switch sub-goals if the current one stagnates (no improvement for 3+ iterations)

This mirrors v2's AgentManager sub-stage generation but runs in-context.

#### b. Iterative Refinement Loop

If the superpowers plugin is available, use `/superpowers:writing-plans` at the start of each stage to create a brief plan for what this stage should achieve and how to approach the iterations. This helps maintain focus across many iterations.

Repeat until stage completion (max_iters reached or completion criteria met):

1. **Select candidate nodes** for expansion:

   **LLM-guided node evaluation** (Claude-native, better than rule-based selection):

   Before calling `select-nodes`, read the current journal and pick candidates holistically:

   1. Run `aisci-state journal-summary <exp_dir> <stage>` to see progress
   2. For the top 3 candidate nodes (by metric), read each node's full state including:
      - Metric value and trend
      - VLM score (from vlm_score field)
      - Datasets successfully tested
      - Error pattern (if any)
   3. Use your judgment to select 1-2 parents to expand, considering:
      - Which has the strongest overall progress (not just metric)?
      - Which explores a different direction (diversity)?
      - Are any trapped in local optima (high metric but poor plot quality)?
   4. Fall back to `aisci-state select-nodes` if the journal has <5 nodes (not enough context yet)

   This gives you v2's LLM-guided selection without needing a separate API call.

   ```bash
   uv run aisci-state select-nodes <exp_dir> <stage>
   ```
   This returns JSON with candidate node IDs and recommended actions (debug/improve).

2. **Launch parallel agents** for each candidate:
   ```
   Agent 1: /aisci:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_1> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   Agent 2: /aisci:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_2> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   ```

3. **Check stage completion** after each batch:
   ```bash
   uv run aisci-state journal-summary <exp_dir> <stage>
   ```

   **Stage 1 completion**: `good_nodes > 0`
   **Stage 2 completion**: Stable convergence on 2+ datasets; no improvement over several iterations.
   **Stage 3 completion**: Execution time scaling properly (>50% of timeout); tested on 3 datasets.
   **Stage 4 completion**: Max iterations reached (always run to completion).

   **HALT condition**: If `max_iters` is reached and `good_nodes == 0` for any stage, the pipeline MUST halt with an error. Do not proceed to multi-seed evaluation or stage transition — there is no code to promote. Report the error analysis (via `uv run aisci-state error-analysis <exp_dir> <stage>`) and suggest the user fix the root cause before resuming.

#### c. Multi-Seed Evaluation (parallel)

Use the parallel multi-seed runner to validate robustness:
```bash
uv run aisci-multi-seed <exp_dir>/workspace/runfile.py \
    --seeds 42 123 456 \
    --workdir <exp_dir>/workspace \
    --log-dir <exp_dir>/logs \
    --aggregate \
    --output-file <exp_dir>/state/<stage>/seed_aggregate.json
```

This runs all seeds concurrently with GPU queue management. Each seed gets its own GPU (CUDA_VISIBLE_DEVICES set automatically). On Apple Silicon (MPS), seeds run sequentially but still use the aggregator.

After aggregation, mark the multi-seed result as a seed-agg node:
```bash
uv run aisci-state add-node <exp_dir> <stage> \
    --plan "Multi-seed validation of best node" \
    --code <exp_dir>/state/<stage>/best_solution_*.py \
    --metric "@<exp_dir>/state/<stage>/seed_aggregate.json" \
    --is-seed-agg-node \
    --datasets <datasets>
```

The seed-agg node becomes the "official" best node for stage transition (more statistically robust than single-run best).

The aggregate output includes: mean, std, 95% CI, min/max, and a `stable` flag. **If `stable` is false** (std/mean > 5%), the result is unreliable — warn the user and consider running 2 more seeds (789, 101) for a total of 5.

The writeup will read `seed_aggregate.json` and report metrics with error bars (e.g., "89.1% ± 1.2%"), not single-point estimates.

#### d. Stage Transition

When a stage completes:

1. Record the transition:
   ```bash
   uv run aisci-state transition <exp_dir> <current_stage> <next_stage>
   ```

2. Generate a stage briefing for the next stage:
   ```bash
   uv run aisci-state stage-briefing <exp_dir> <current_stage>
   ```
   This returns a JSON summary with: best metrics, datasets tested, key findings, and failed approaches.

3. **Pass the briefing (not the code) to the next stage.** The next stage's agent should:
   - Read the briefing to understand what worked and what didn't
   - Write fresh code informed by the findings — NOT copy-paste previous code
   - Build on the conclusions (e.g., "learning rate 3e-4 worked best on MNIST and FashionMNIST") rather than inheriting implementation details

   The best node's code is still saved (via `save-best`) for reference if needed, but the primary handoff is the briefing.

**Why briefings instead of code?** Each stage has fundamentally different goals. Stage 2 changes hyperparameters, Stage 3 changes architecture, Stage 4 adds ablation logic. Passing code forces the agent to work around existing structure. Passing conclusions lets it write clean code for the new goal.

#### e. Stage-Gate Code Review (Octopus primary, code-review fallback)

When a stage completes, run code review on the best node before transitioning.

**PREREQUISITE: Best solution file must exist.** Run `uv run aisci-state save-best <exp_dir> <stage>` first. If it prints "No good nodes to save" or exits with an error, SKIP this entire section (there's nothing to review) and log a warning. This is a normal state for stages that completed with all-buggy nodes (which should have already halted the pipeline — see HALT condition above).

**Never run both Octopus review and `/code-review`** — they overlap significantly and waste tokens. Octopus already includes code-focused providers that subsume most of what `/code-review` catches. Pick one based on availability.

**Primary: Octopus multi-model review** (default when `octopus.enabled` is not `"false"` and the plugin is installed):
```
/octo:review "<exp_dir>/state/<current_stage>/best_solution_*.py"
```
This dispatches to multiple providers for adversarial code review. Catches ML-specific issues (data leakage, incorrect metrics, device handling, numerical instability) as well as general code quality. Quote the path in case `<exp_dir>` contains spaces.

**Fallback: `/code-review` plugin** (only if Octopus is unavailable):
If the claude-octopus plugin is not installed, or `octopus.enabled` is `"false"`, or `--no-octopus` was passed, use the general `/code-review` plugin for code quality review. This is less thorough for ML issues but catches basic code quality problems.

**Run this BEFORE the stage transition** (step d), not after — because `transition` updates `current_stage` to the next stage. Review the just-completed stage's best code.

1. **Check Octopus availability** (respect global config and plugin presence):
   ```bash
   claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('octo' in p['id'] for p in json.load(sys.stdin)) and print('OCTOPUS_OK') or print('OCTOPUS_MISSING')" 2>/dev/null
   ```
   The plugin must be present. Also check the loaded config's `octopus.enabled` value. If it is `"false"`, or `--no-octopus` was passed, skip this step.

2. **If available**, get the promoted best solution from the just-completed stage:
   ```bash
   uv run aisci-state save-best <exp_dir> <completed_stage>
   ```
   Where `<completed_stage>` is the stage that just finished (e.g., `stage1_initial`), NOT the next stage.
   This writes the best node's code to `<exp_dir>/state/<current_stage>/best_solution_<id>.py`. Use that file path for the review:
   ```
   /octo:review "<exp_dir>/state/<current_stage>/best_solution_<id>.py"
   ```

3. **Parse the review output**. Octopus review returns prose (Markdown), not structured JSON. Read the output and identify any critical issues mentioned (data leakage, incorrect metrics, statistical errors, device bugs).

4. **Persist findings** to a file that the next stage can read:
   ```bash
   cat > <exp_dir>/state/<current_stage>/octopus_code_review.md << 'MD_EOF'
   <octopus review output — Markdown prose>
   MD_EOF
   ```

5. **If critical issues found** (data leakage, incorrect metrics, statistical errors):
   - When building the task description for the next stage (step 4 of the main loop), read `octopus_code_review.md` and append a summary of critical findings directly into the `task_desc` string:
     ```
     Code Review Issues (from Octopus — address these as a priority):
     <summarize critical findings from octopus_code_review.md>
     ```
   - This ensures the next stage's experiment-step agents see the issues in their `--task-desc` argument
   - Print warning: "Octopus found critical code issues — included in next stage's task description"

6. **If no issues or only minor issues**:
   - Proceed normally — no changes to the next stage's task description

Note: The `stage-briefing` command does not automatically include `octopus_code_review.md`. The findings must be injected into the task description manually as described above.

This step typically adds 1-3 minutes per stage transition but can prevent wasted iterations in subsequent stages.

#### f. Rescue for Stuck Experiments (Optional — Octopus)

**Skip if** any of these conditions are true:
- The global `octopus.enabled` config value is `"false"`
- The `--no-octopus` flag was passed to the orchestrator
- `octopus.rescue_on_stuck` is `false` in config
- The claude-octopus plugin is not installed (check same as stage-gate step e.1)

**Auto-rescue trigger**: After every iteration batch (not just at 80%), run error pattern analysis. Rescue if **≥50% of nodes have the same error type** AND at least 3 buggy nodes exist. This catches patterns early instead of waiting for the pipeline to waste 80% of iterations.

```bash
uv run aisci-state error-analysis <exp_dir> <current_stage>
```

This returns JSON with:
- `error_distribution`: count per error category (CUDA_OOM, SHAPE_MISMATCH, etc.)
- `dominant_error`: the most common error type
- `dominant_pct`: fraction of nodes hitting it (0.0-1.0)
- `recommendation`: a concrete fix suggestion

**Trigger rescue if**: `dominant_pct >= 0.5` AND `total_nodes >= 3`. The legacy 80% threshold still applies as a backstop (rescue even if errors are scattered).

1. **Collect recent error information**:
   ```bash
   uv run aisci-state journal-summary <exp_dir> <current_stage>
   uv run aisci-state error-analysis <exp_dir> <current_stage>
   ```
   Note the total nodes, buggy count, and error classification.

   Then get error details from recent buggy nodes. Read the stage journal to find node IDs:
   ```bash
   uv run python3 -c "
   import json
   from tools.state_manager import load_journal, get_buggy_nodes
   j = load_journal('<exp_dir>', 'stage1_initial')
   buggy = get_buggy_nodes(j)[-3:]  # last 3 buggy nodes
   for n in buggy:
       print(f'Node {n[\"id\"]}: exc_type={n.get(\"exc_type\",\"?\")} exc_info={str(n.get(\"exc_info\",\"\"))[:200]}')
       term = n.get('term_out', [])
       # term_out may be a list (from splitlines) or a string
       if isinstance(term, list):
           lines = term
       elif isinstance(term, str):
           lines = term.strip().split('\\n')
       else:
           lines = []
       if lines:
           print('Last output:', '\\n'.join(lines[-15:]))
       print('---')
   "
   ```
   Use the printed exc_type, exc_info, and last output lines to build a concrete error summary for the debug prompt.

2. **Invoke Octopus debug** with the collected error details:
   ```
   /octo:debug "ML experiment is failing repeatedly. After <N> iterations, zero experiments produce valid metrics. Error details from recent attempts: <paste exc_type and exc_info from 2-3 buggy nodes>. The research goal is: <task_desc>. Experiment code is at: <exp_dir>/workspace/runfile.py. Diagnose the root cause and suggest a concrete fix approach."
   ```

3. **Use the diagnosis** to inform the next draft/debug action. Include Octopus's recommendations in the task description for the next experiment-step agent.

This is a last-resort mechanism — it only triggers when the BFTS tree is failing to produce any working code.

### 6. Post-Experiment

After all 4 stages complete:

1. Print final summary:
   ```bash
   uv run aisci-state status <exp_dir>
   uv run aisci-state journal-summary <exp_dir> stage1_initial
   uv run aisci-state journal-summary <exp_dir> stage2_baseline
   uv run aisci-state journal-summary <exp_dir> stage3_creative
   uv run aisci-state journal-summary <exp_dir> stage4_ablation
   ```

2. Copy best results:
   ```bash
   uv run aisci-state save-best <exp_dir> stage4_ablation
   cp -r <exp_dir>/workspace/figures/* <exp_dir>/figures/ 2>/dev/null || true
   ```

3. Mark experiment complete:
   ```bash
   uv run aisci-state update-state <exp_dir> --phase complete --status experiment_done
   ```

## Error Handling

- If Stage 1 exhausts max_iters without a working implementation: **stop the experiment** and report failure.
- If a stage produces no improvement after multiple iterations: proceed to the next stage with the best available node.
- If all agents in a parallel batch fail: retry with different approaches before giving up.

### All Nodes in a Stage Are Buggy

If after 80%+ of max_iters, every node has errors:

1. **Report to user**: "Stage X: All N attempts produced errors. Common patterns:" — list the most common error types (e.g., "OOM: 5 nodes", "Shape mismatch: 3 nodes")
2. **Invoke Octopus debug** if available (see step f above)
3. **If Octopus debug succeeds**: apply its suggestions and retry with fresh code
4. **If Octopus debug also fails or is unavailable**: mark stage as FAILED, skip remaining stages, report to user with diagnostic summary

### Execution Timeout

If experiment code exceeds the 3600s timeout:
- The process is killed automatically
- Save whatever output was captured to the log file
- Mark the node as buggy with note "timeout after 3600s"
- Continue to next iteration — do NOT retry the same code
- If timeouts are frequent (>50% of nodes), suggest reducing model size or dataset in the next iteration's task description

### Out of Memory

If code fails with OOM (CUDA or system):
- Mark node as buggy with note "out of memory"
- In the next iteration, explicitly add to the task description: "Previous attempt failed with OOM. Use smaller batch size, gradient accumulation, or mixed precision."
- If 3+ consecutive OOM failures, suggest switching to CPU or reducing model size

### Parallel Worker Imbalance

If one worker finishes all tasks but another is still running:
- Don't wait — proceed with available results
- The slow worker's results will be recorded when they complete
- Next iteration can use all available nodes for selection

### Experiment Resumption

If the pipeline crashes mid-stage:
- Use `uv run aisci-state status <exp_dir>` to check current state
- Use `uv run aisci-state journal-summary <exp_dir> <stage>` to see completed iterations
- Resume by re-running the experiment skill with `--exp-dir <exp_dir>` — it will detect the current stage and continue from where it left off

## Progress Reporting

After each iteration batch, report:
- Current stage and iteration number
- Number of good/buggy nodes
- Best metric so far
- Estimated time remaining
