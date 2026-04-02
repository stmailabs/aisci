---
name: experiment-step
description: Execute a single Best-First Tree Search iteration — select parent node, generate experiment code, execute it, parse metrics, analyze plots, and update the journal.
---


# BFTS Experiment Step

You are an AI researcher executing a single iteration of the Best-First Tree Search (BFTS) experiment pipeline. This is the **innermost loop** of the AI Scientist system — the core that generates code, runs experiments, and evaluates results.

## Arguments (provided by the calling skill)

- `--exp-dir <path>`: Experiment directory
- `--stage <name>`: Current stage (stage1_initial, stage2_baseline, stage3_creative, stage4_ablation)
- `--parent-id <id>`: Parent node ID to branch from (null for draft nodes)
- `--action <type>`: One of: `draft` (new root), `debug` (fix buggy parent), `improve` (enhance good parent)
- `--task-desc <text>`: Task/idea description for context
- `--stage-goals <text>`: Current stage goals

Parse these from the user's message or arguments.

## Procedure

### 1. Load Context

Check the current journal state:
```bash
python3 tools/state_manager.py journal-summary <exp_dir> <stage>
```

If a parent node ID is provided, read the parent node's details:
```bash
python3 tools/state_manager.py node-info <exp_dir> <stage> <parent_id> --show-code
```

### 2. Detect Device

```bash
python3 tools/device_utils.py --preamble
```

### 3. Generate Experiment Code

Based on the action type, generate a complete Python experiment script:

#### For `draft` (new root node):
- Generate a fresh implementation from the task description
- Include the device preamble
- Include dataset loading (prefer HuggingFace `datasets` library)
- Include a training loop with proper metric reporting
- Include plotting code (loss curves, accuracy, etc.)

#### For `debug` (fix buggy parent):
- Read the parent's code and error output from node-info
- Identify the bug from the exception type and stack trace
- Fix the issue while preserving the approach
- Do NOT completely rewrite — make targeted fixes

#### For `improve` (enhance good parent):
- Read the parent's metrics and analysis from node-info
- If this is the **first node of a new stage** (parent from previous stage):
  - Read the stage briefing: `python3 tools/state_manager.py stage-briefing <exp_dir> <previous_stage>`
  - Write fresh code informed by the briefing's findings and metrics
  - Do NOT copy the parent's code — the goals have changed
- If this is a **within-stage improvement**:
  - Read the parent's code from node-info and make targeted improvements
- Stage-specific goals:
  - **Stage 1**: Get it working with basic correctness
  - **Stage 2**: Tune hyperparameters (LR, epochs, batch size), add datasets. Do NOT change architecture.
  - **Stage 3**: Creative novel improvements, new architectures, 3 HF datasets
  - **Stage 4**: Ablation studies — systematically disable/modify components

#### Code Requirements (ALL stages):

The generated code MUST:
1. Start with the device preamble (CUDA/MPS/CPU auto-detection)
2. Print metrics in a parseable format: `metric_name: value`
   - Always print `val_loss: <value>` or `accuracy: <value>`
   - Print metrics after each epoch AND at the end
3. Save plots to `figures/` directory relative to the workspace
4. Handle errors gracefully (try/except around training)
5. Use `torch.no_grad()` for evaluation
6. Set random seeds for reproducibility
7. Print dataset names when loaded: `Dataset: <name>`
8. Keep execution time under 60 minutes

Example metric output:
```
Epoch 1/10, train_loss: 0.5234, val_loss: 0.4891, accuracy: 0.7523
...
Final Results:
val_loss: 0.2100
accuracy: 0.8900
```

### 4. Write and Execute Code

Determine step number from journal-summary total_nodes.

Write the code:
```bash
cat > <exp_dir>/workspace/runfile.py << 'PYTHON_EOF'
<generated code>
PYTHON_EOF
mkdir -p <exp_dir>/workspace/figures
```

Execute and capture output:
```bash
cd <exp_dir>/workspace && timeout 3600 python3 runfile.py 2>&1 | tee <exp_dir>/logs/step_<N>_output.txt
```

### 5. Parse Metrics

```bash
python3 tools/metric_parser.py <exp_dir>/logs/step_<N>_output.txt --json
```

### 6. Analyze Plots

If plots were generated in `<exp_dir>/workspace/figures/`:
- Use the Read tool to view each generated PNG file
- Analyze: convergence, overfitting, consistency across datasets, ablation clarity

### 7. Determine Bug Status

**Buggy** if ANY of: exception raised, no valid metrics, timeout, NaN/Inf in metrics.
**Not buggy** if: execution completed + at least one valid metric.

### 8. Save Node to Journal

```bash
python3 tools/state_manager.py add-node <exp_dir> <stage> \
    --plan "<brief plan description>" \
    --code <exp_dir>/workspace/runfile.py \
    --output-log <exp_dir>/logs/step_<N>_output.txt \
    --exec-time <seconds> \
    --metric '<metric_json>' \
    --datasets <dataset1> <dataset2> \
    --plots <exp_dir>/workspace/figures/plot1.png <exp_dir>/workspace/figures/plot2.png \
    [--parent-id <parent_id>] \
    [--buggy] \
    [--analysis "<analysis text>"]
```

This command prints the new node's ID, step number, buggy status, and metric.

### 9. Report Results

Provide a concise summary:
- Node ID and action type (draft/debug/improve)
- Whether the code executed successfully
- Key metrics (if any)
- Brief analysis of results
- Recommendation for next step (debug, improve, or move on)

## Stage-Specific Guidelines

### Stage 1: Initial Implementation
- Keep it simple — MNIST, Fashion-MNIST, or a small HF dataset
- Basic model (MLP, small CNN, small pretrained model)
- Goal: working code that produces valid metrics
- If given seed code, use it as starting point

### Stage 2: Baseline Tuning
- DO NOT change model architecture from Stage 1's best
- Tune: learning rate, batch size, epochs, optimizer, scheduler
- Add 2 more HuggingFace datasets
- Goal: best performance through hyperparameter optimization

### Stage 3: Creative Research
- Try novel architectures, loss functions, training strategies
- Use 3 HuggingFace datasets total
- Generate insightful plots showing the novel contributions
- Goal: publishable improvements and insights

### Stage 4: Ablation Studies
- Use same 3 datasets from Stage 3
- Systematically disable/modify each component
- Generate comparison plots (with/without each component)
- Goal: understand contribution of each part
