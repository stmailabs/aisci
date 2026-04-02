---
name: experiment
description: Run the complete 4-stage Best-First Tree Search experiment pipeline — from initial implementation through ablation studies, with multi-agent parallel exploration.
---


# BFTS Experiment Pipeline

You are the experiment orchestrator for the AI Scientist system. This skill manages the complete 4-stage Best-First Tree Search (BFTS) pipeline.

## Arguments

- `--idea <path>`: Path to idea JSON file (required)
- `--config <path>`: Path to config YAML (optional, defaults to `templates/bfts_config.yaml`)
- `--exp-dir <path>`: Resume from existing experiment directory (optional)
- `--start-stage <N>`: Start from stage N (1-4, default: 1)

Parse these from the user's message.

## Stage Definitions

| Stage | Name | Goal | Max Iters | Key Constraints |
|-------|------|------|-----------|-----------------|
| 1 | Initial Implementation | Working code on simple dataset | 20 | Use simple dataset; if seed code provided, start from it |
| 2 | Baseline Tuning | Optimize hyperparameters | 12 | DO NOT change architecture; add 2+ HF datasets |
| 3 | Creative Research | Novel improvements | 12 | Be creative; use 3 HF datasets total |
| 4 | Ablation Studies | Component analysis | 18 | Same datasets as Stage 3; systematic disable/modify |

## Procedure

### 1. Initialize Experiment

**New experiment** (no `--exp-dir`):
```bash
python3 tools/state_manager.py init --idea <idea_path> --config <config_path>
```
This prints the experiment directory path. Use it as `<exp_dir>` in all subsequent commands.

**Resume** (with `--exp-dir`):
```bash
python3 tools/state_manager.py status <exp_dir>
```
Read the current stage and completed stages to know where to resume.

### 2. Detect Device
```bash
python3 tools/device_utils.py --info
```

### 3. Load Config
```bash
python3 tools/config.py --config <config_path>
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
Launch `num_workers` Agent subagents in parallel, each running `/ai-scientist:experiment-step`:

```
Agent 1: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --action draft --task-desc "<task_desc>" --stage-goals "<goals>"
Agent 2: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --action draft --task-desc "<task_desc>" --stage-goals "<goals>"
```

For stages 2-4, carry the best node from the previous stage as the starting point (no new drafts).

#### b. Iterative Refinement Loop

Repeat until stage completion (max_iters reached or completion criteria met):

1. **Select candidate nodes** for expansion:
   ```bash
   python3 tools/state_manager.py select-nodes <exp_dir> <stage>
   ```
   This returns JSON with candidate node IDs and recommended actions (debug/improve).

2. **Launch parallel agents** for each candidate:
   ```
   Agent 1: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_1> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   Agent 2: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_2> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   ```

3. **Check stage completion** after each batch:
   ```bash
   python3 tools/state_manager.py journal-summary <exp_dir> <stage>
   ```

   **Stage 1 completion**: `good_nodes > 0`
   **Stage 2 completion**: Stable convergence on 2+ datasets; no improvement over several iterations.
   **Stage 3 completion**: Execution time scaling properly (>50% of timeout); tested on 3 datasets.
   **Stage 4 completion**: Max iterations reached (always run to completion).

#### c. Multi-Seed Evaluation

When a stage completes, run the best node's code with multiple random seeds to validate robustness:

1. Get the best node's code:
   ```bash
   python3 tools/state_manager.py best-node <exp_dir> <stage> --show-code
   ```

2. Run it with different seeds (42, 123, 456), modifying the seed line each time:
   ```bash
   for seed in 42 123 456; do
       sed "s/torch.manual_seed(42)/torch.manual_seed($seed)/" <exp_dir>/workspace/runfile.py > <exp_dir>/workspace/runfile_seed_$seed.py
       cd <exp_dir>/workspace && timeout 3600 python3 runfile_seed_$seed.py 2>&1 | tee <exp_dir>/logs/seed_${seed}_output.txt
   done
   ```

3. Collect and compare metrics across seeds.

#### d. Stage Transition

When a stage completes:

1. Record the transition:
   ```bash
   python3 tools/state_manager.py transition <exp_dir> <current_stage> <next_stage>
   ```

2. Generate a stage briefing for the next stage:
   ```bash
   python3 tools/state_manager.py stage-briefing <exp_dir> <current_stage>
   ```
   This returns a JSON summary with: best metrics, datasets tested, key findings, and failed approaches.

3. **Pass the briefing (not the code) to the next stage.** The next stage's agent should:
   - Read the briefing to understand what worked and what didn't
   - Write fresh code informed by the findings — NOT copy-paste previous code
   - Build on the conclusions (e.g., "learning rate 3e-4 worked best on MNIST and FashionMNIST") rather than inheriting implementation details

   The best node's code is still saved (via `save-best`) for reference if needed, but the primary handoff is the briefing.

**Why briefings instead of code?** Each stage has fundamentally different goals. Stage 2 changes hyperparameters, Stage 3 changes architecture, Stage 4 adds ablation logic. Passing code forces the agent to work around existing structure. Passing conclusions lets it write clean code for the new goal.

### 6. Post-Experiment

After all 4 stages complete:

1. Print final summary:
   ```bash
   python3 tools/state_manager.py status <exp_dir>
   python3 tools/state_manager.py journal-summary <exp_dir> stage1_initial
   python3 tools/state_manager.py journal-summary <exp_dir> stage2_baseline
   python3 tools/state_manager.py journal-summary <exp_dir> stage3_creative
   python3 tools/state_manager.py journal-summary <exp_dir> stage4_ablation
   ```

2. Copy best results:
   ```bash
   python3 tools/state_manager.py save-best <exp_dir> stage4_ablation
   cp -r <exp_dir>/workspace/figures/* <exp_dir>/figures/ 2>/dev/null || true
   ```

3. Mark experiment complete:
   ```bash
   python3 tools/state_manager.py update-state <exp_dir> --phase complete --status experiment_done
   ```

## Error Handling

- If Stage 1 exhausts max_iters without a working implementation: **stop the experiment** and report failure.
- If a stage produces no improvement after multiple iterations: proceed to the next stage with the best available node.
- If all agents in a parallel batch fail: retry with different approaches before giving up.

## Progress Reporting

After each iteration batch, report:
- Current stage and iteration number
- Number of good/buggy nodes
- Best metric so far
- Estimated time remaining
