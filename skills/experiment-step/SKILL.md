---
name: experiment-step
description: Execute a single Best-First Tree Search iteration — select parent node, generate experiment code, execute it, parse metrics, analyze plots, and update the journal.
---


# BFTS Experiment Step

You are an AI researcher executing a single iteration of the Best-First Tree Search (BFTS) experiment pipeline. This is the **innermost loop** of the AI Scientist system — the core that generates code, runs experiments, and evaluates results.

This skill replaces `ParallelAgent.step()` + `Interpreter` from AI-Scientist-v2.

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

```bash
# Load experiment state and journal
python -c "
import json, sys
sys.path.insert(0, '.')
from tools.state_manager import load_journal, get_node_by_id
journal = load_journal('<exp_dir>', '<stage>')
print(json.dumps({'total_nodes': len(journal['nodes']), 'stage': '<stage>'}, indent=2))
"
```

If a parent node ID is provided, read the parent node's code, metrics, analysis, and execution output from the journal.

### 2. Detect Device

```bash
python tools/device_utils.py
```

Read the detected device and get the device preamble:
```bash
python tools/device_utils.py --preamble
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
- Read the parent's code and error output
- Identify the bug from the exception type and stack trace
- Fix the issue while preserving the approach
- Do NOT completely rewrite — make targeted fixes

#### For `improve` (enhance good parent):
- Read the parent's code, metrics, and analysis
- Make specific improvements based on the stage goals:
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
8. Keep execution time under 60 minutes (scale model/data appropriately)

Example metric output format:
```
Epoch 1/10, train_loss: 0.5234, val_loss: 0.4891, accuracy: 0.7523
Epoch 2/10, train_loss: 0.3456, val_loss: 0.3210, accuracy: 0.8234
...
Final Results:
val_loss: 0.2100
accuracy: 0.8900
```

### 4. Write and Execute Code

Write the generated code to the workspace:
```bash
cat > <exp_dir>/workspace/runfile.py << 'PYTHON_EOF'
<generated code>
PYTHON_EOF
```

Create the figures directory:
```bash
mkdir -p <exp_dir>/workspace/figures
```

Execute with timeout:
```bash
cd <exp_dir>/workspace && timeout 3600 python runfile.py 2>&1
```

**Important**: Capture the full output (stdout + stderr). This is needed for metric parsing.

### 5. Parse Metrics

```bash
cd <exp_dir>/workspace && timeout 3600 python runfile.py 2>&1 | tee <exp_dir>/logs/step_<N>_output.txt
```

Then parse metrics:
```bash
python tools/metric_parser.py <exp_dir>/logs/step_<N>_output.txt --json
```

### 6. Analyze Plots

If plots were generated in `<exp_dir>/workspace/figures/`:
- Use the Read tool to view each generated PNG file
- Analyze the plots:
  - Are training curves converging?
  - Is there overfitting (train vs val divergence)?
  - Are results consistent across datasets?
  - Do ablation results show clear component contributions?

### 7. Determine Bug Status

A node is **buggy** if ANY of:
- The execution raised an exception (non-zero exit code)
- No valid metrics were parsed from the output
- Execution timed out
- The code produced NaN/Inf values in metrics

A node is **not buggy** if:
- Execution completed successfully
- At least one valid metric was parsed
- Plots were generated (optional but preferred)

### 8. Save Node to Journal

```bash
python -c "
import json, sys, time
sys.path.insert(0, '.')
from tools.state_manager import load_journal, create_node, add_node, save_journal

journal = load_journal('<exp_dir>', '<stage>')
node = create_node(
    stage='<stage>',
    plan='<brief plan description>',
    code=open('<exp_dir>/workspace/runfile.py').read(),
    parent_id=<parent_id_or_None>,
    plot_code=None,
)

# Fill execution results
node['term_out'] = open('<exp_dir>/logs/step_<N>_output.txt').read().splitlines()
node['exec_time'] = <execution_time_seconds>
node['exc_type'] = <exception_type_or_None>
node['is_buggy'] = <True_or_False>
node['is_buggy_plots'] = <True_or_False>
node['analysis'] = '''<your analysis of the results>'''
node['metric'] = <parsed_metric_dict_or_None>
node['plot_paths'] = <list_of_plot_paths>
node['vlm_feedback_summary'] = ['''<your plot analysis>''']
node['datasets_successfully_tested'] = <list_of_dataset_names>

add_node(journal, node)
save_journal('<exp_dir>', '<stage>', journal)
print(json.dumps({'node_id': node['id'], 'is_buggy': node['is_buggy'], 'metric': node['metric']}, indent=2))
"
```

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
