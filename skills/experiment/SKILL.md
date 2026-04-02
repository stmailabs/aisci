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

If no `--exp-dir` is provided (new experiment):
```bash
python3 -c "
import json, sys
sys.path.insert(0, '.')
from tools.state_manager import init_experiment
from tools.config import load_config, config_to_dict

idea = json.load(open('<idea_path>'))
cfg = load_config('<config_path>')
exp_dir = init_experiment(idea, config_to_dict(cfg))
print(exp_dir)
"
```

If `--exp-dir` is provided (resume):
```bash
python3 -c "
import json, sys
sys.path.insert(0, '.')
from tools.state_manager import load_experiment_state
state = load_experiment_state('<exp_dir>')
print(json.dumps(state, indent=2))
"
```

### 2. Detect Device
```bash
python3 tools/device_utils.py --info
```

### 3. Load Config
```bash
python3 tools/config.py --config <config_path>
```

Read configuration values:
- `agent.num_workers`: parallel agents (default 2)
- `agent.stages.stageN_max_iters`: iteration limits
- `agent.search.num_drafts`: initial drafts per stage (default 3)
- `agent.search.max_debug_depth`: max debug retries (default 3)
- `agent.search.debug_prob`: probability of debugging a buggy node (default 0.5)
- `exec.timeout`: execution timeout in seconds (default 3600)

### 4. Build Task Description

Compose the task description from the idea JSON:
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
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import load_journal, get_nodes_for_expansion
   journal = load_journal('<exp_dir>', '<stage>')
   candidates = get_nodes_for_expansion(journal, max_debug_depth=3, debug_prob=0.5)
   for c in candidates:
       action = 'debug' if c.get('is_buggy') else 'improve'
       print(json.dumps({'id': c['id'], 'action': action, 'metric': c.get('metric')}, indent=2))
   "
   ```

2. **Launch parallel agents** for each candidate:
   Use the Agent tool to launch `num_workers` subagents simultaneously:
   ```
   Agent 1: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_1> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   Agent 2: /ai-scientist:experiment-step --exp-dir <exp_dir> --stage <stage> --parent-id <node_id_2> --action <debug|improve> --task-desc "<task_desc>" --stage-goals "<goals>"
   ```

3. **Check stage completion** after each batch:

   **Stage 1 completion**: At least 1 good (non-buggy) node exists.
   ```bash
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import load_journal, get_good_nodes
   journal = load_journal('<exp_dir>', 'stage1_initial')
   good = get_good_nodes(journal)
   print(json.dumps({'complete': len(good) > 0, 'good_count': len(good)}, indent=2))
   "
   ```

   **Stage 2 completion**: Training curves show stable convergence on 2+ datasets; no improvement over several iterations.

   **Stage 3 completion**: Execution time scaling properly (>50% of timeout); tested on 3 datasets; novel improvements found.

   **Stage 4 completion**: Max iterations reached (always run to completion for thorough ablation).

4. **Save progress** after each batch:
   ```bash
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import load_journal, save_best_solution, get_journal_summary
   journal = load_journal('<exp_dir>', '<stage>')
   save_best_solution('<exp_dir>', '<stage>', journal)
   summary = get_journal_summary(journal)
   print(json.dumps(summary, indent=2))
   "
   ```

#### c. Multi-Seed Evaluation

When a stage completes, run the best node's code with multiple random seeds to validate robustness:

1. Take the best node's code from the completed stage
2. Run it `num_seeds` times (default 3) with different random seeds (42, 123, 456)
3. Collect metrics across all seed runs
4. Select the seed with the best average performance
5. Run plot aggregation across seed results using the best node

This ensures results are not dependent on a specific random initialization.

```bash
# For each seed, modify the seed in runfile.py and re-execute
for seed in 42 123 456; do
    sed "s/torch.manual_seed(42)/torch.manual_seed($seed)/" <exp_dir>/workspace/runfile.py > <exp_dir>/workspace/runfile_seed_$seed.py
    cd <exp_dir>/workspace && timeout 3600 python runfile_seed_$seed.py 2>&1 | tee <exp_dir>/logs/seed_${seed}_output.txt
done
```

#### d. Stage Transition

When a stage completes:

1. Save the best solution:
   ```bash
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import load_journal, get_best_node, save_best_solution, transition_stage
   journal = load_journal('<exp_dir>', '<current_stage>')
   best = get_best_node(journal)
   save_best_solution('<exp_dir>', '<current_stage>', journal)
   if best:
       transition_stage('<exp_dir>', '<current_stage>', '<next_stage>', best['id'], 'Stage completed')
   "
   ```

2. For the next stage, inject the best node as the starting point:
   - Read the best node's code
   - Create a new root node in the next stage's journal with that code
   - This becomes the baseline for the next stage

### 6. Post-Experiment

After all 4 stages complete:

1. Print final summary:
   ```bash
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import load_experiment_state, load_journal, get_journal_summary
   state = load_experiment_state('<exp_dir>')
   for stage in ['stage1_initial', 'stage2_baseline', 'stage3_creative', 'stage4_ablation']:
       journal = load_journal('<exp_dir>', stage)
       summary = get_journal_summary(journal)
       print(f'{stage}: {json.dumps(summary)}')
   "
   ```

2. Copy best results to experiment_results/:
   ```bash
   cp <exp_dir>/state/stage4_ablation/best_solution_*.py <exp_dir>/experiment_results/
   cp -r <exp_dir>/workspace/figures/* <exp_dir>/figures/ 2>/dev/null || true
   ```

3. Update experiment state:
   ```bash
   python3 -c "
   import json, sys
   sys.path.insert(0, '.')
   from tools.state_manager import update_experiment_state
   update_experiment_state('<exp_dir>', phase='complete', status='experiment_done')
   "
   ```

## Error Handling

- If Stage 1 exhausts max_iters without a working implementation: **stop the experiment** and report failure. The idea may be too complex or infeasible.
- If a stage produces no improvement after multiple iterations: proceed to the next stage with the best available node.
- If all agents in a parallel batch fail: retry with different approaches before giving up.

## Progress Reporting

After each iteration batch, report:
- Current stage and iteration number
- Number of good/buggy nodes
- Best metric so far
- Estimated time remaining
