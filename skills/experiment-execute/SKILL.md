---
name: experiment-execute
description: Execute previously generated experiment code, parse metrics, analyze plots, and record the node. Pairs with experiment-generate.
---


# Experiment Execution

You execute a previously generated experiment script, parse its output, and record the result as a BFTS node.

## Arguments

- `--exp-dir <path>`: Experiment directory
- `--stage <name>`: Current stage
- `--parent-id <id>`: Parent node ID (optional)
- `--plan <text>`: Brief plan description for this node

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Execute Code

Determine step number from journal:
```bash
uv run ai-scientist-state journal-summary <exp_dir> <stage>
```

Lint and format before running (if astral plugin available — skip silently if not):
```bash
ruff format <exp_dir>/workspace/runfile.py 2>/dev/null || true
ruff check <exp_dir>/workspace/runfile.py --fix --silent 2>/dev/null || true
```

Run the previously generated code:

**If `compute.backend` is `local`** (default):
```bash
cd <exp_dir>/workspace && timeout 3600 uv run python3 runfile.py 2>&1 | tee <exp_dir>/logs/step_<N>_output.txt
```

**If `compute.backend` is `modal`**: Run on Modal cloud GPU:
```bash
uv run ai-scientist-modal-run <exp_dir>/workspace/runfile.py --gpu <compute.modal.gpu from config> --output-log <exp_dir>/logs/step_<N>_output.txt
```
If Modal fails, fall back to local and warn the user.

### 2. Parse Metrics

```bash
uv run ai-scientist-metrics <exp_dir>/logs/step_<N>_output.txt --json
```

### 3. Analyze Plots

If plots exist in `<exp_dir>/workspace/figures/`, view each PNG with the Read tool. Assess convergence, overfitting, dataset consistency.

### 4. Determine Bug Status

Buggy if: exception raised, no valid metrics, timeout, NaN/Inf in metrics.

### 5. Save Node

```bash
uv run ai-scientist-state add-node <exp_dir> <stage> \
    --plan "<plan>" \
    --code <exp_dir>/workspace/runfile.py \
    --output-log <exp_dir>/logs/step_<N>_output.txt \
    --exec-time <seconds> \
    --metric '<metric_json>' \
    --datasets <dataset1> <dataset2> \
    --plots <plot_paths> \
    [--parent-id <parent_id>] \
    [--buggy] \
    [--analysis "<analysis>"]
```

### 6. Report

Node ID, bug status, metrics, recommendation for next step.

## Error Handling

- **Timeout during execution (>3600s)** → Save whatever partial output exists to the log file, mark the node as buggy with analysis noting "execution timeout", and recommend reducing model size or dataset scope.
- **Out of memory (OOM) error** → Catch OOM in the output log, mark the node as buggy, and suggest reducing batch size, using gradient accumulation, or switching to a smaller model variant.
- **Metrics not found in output** → Mark the node as buggy with analysis noting "no metrics parsed from output". Check whether the script ran to completion or crashed before the metric-printing stage.
- **Script raises an unhandled exception** → Capture the full traceback in the log, mark the node as buggy, and include the exception type and message in the analysis field.
- **Runfile does not exist** → Report that `experiment-generate` must be run first. Do not attempt execution without a generated script.
- **NaN or Inf in parsed metrics** → Mark the node as buggy with analysis noting "NaN/Inf in metrics", and recommend checking learning rate, loss function, or data preprocessing.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
