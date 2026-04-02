---
name: plot
description: Aggregate and generate publication-quality figures from experiment results across all BFTS stages.
---


# Plot Aggregation

You are generating publication-quality figures for an AI research paper. This skill replaces `perform_plotting.py` from AI-Scientist-v2.

## Arguments

- `--exp-dir <path>`: Experiment directory (required)

Parse from the user's message.

## Procedure

### 1. Load Experiment Context

Read the experiment state and gather all stage summaries:
```bash
python -c "
import json, sys, os
sys.path.insert(0, '.')
from tools.state_manager import load_experiment_state, load_journal, get_best_node, get_journal_summary
state = load_experiment_state('<exp_dir>')
for stage in ['stage1_initial', 'stage2_baseline', 'stage3_creative', 'stage4_ablation']:
    journal = load_journal('<exp_dir>', stage)
    summary = get_journal_summary(journal)
    best = get_best_node(journal)
    print(f'=== {stage} ===')
    print(json.dumps(summary, indent=2))
    if best and best.get('plot_paths'):
        print(f'Plots: {best[\"plot_paths\"]}')
"
```

### 2. Inventory Existing Plots

List all plots generated across all stages:
```bash
find <exp_dir>/workspace/figures -name "*.png" -o -name "*.pdf" 2>/dev/null | sort
find <exp_dir>/figures -name "*.png" -o -name "*.pdf" 2>/dev/null | sort
```

View each existing plot using the Read tool to understand what's available.

### 3. Read Best Experiment Code

Read the best experiment code from the final stage to understand what data is available:
```bash
ls <exp_dir>/state/stage4_ablation/best_solution_*.py 2>/dev/null || \
ls <exp_dir>/state/stage3_creative/best_solution_*.py 2>/dev/null || \
ls <exp_dir>/state/stage2_baseline/best_solution_*.py 2>/dev/null
```

### 4. Generate Aggregator Script

Create a Python script that produces publication-quality figures. The script should:

1. **Load raw experiment data** from `.npy`, `.json`, or `.csv` files in the workspace
2. **Generate 4-6 key figures** for the paper:
   - **Training curves**: Loss and accuracy over epochs (all datasets overlaid)
   - **Method comparison**: Bar chart comparing baseline vs. proposed method
   - **Ablation results**: Grouped bar chart showing component contributions
   - **Dataset comparison**: Performance across different datasets
   - Any additional figures that illustrate key findings

3. **Follow publication standards**:
   - Use `matplotlib` with `seaborn` style
   - Font size ≥ 10pt for readability
   - Clear legends and axis labels
   - Color-blind friendly palettes
   - Tight layout with no clipping
   - Save as both PNG (300 DPI) and PDF

```bash
cat > <exp_dir>/auto_plot_aggregator.py << 'PYTHON_EOF'
<generated aggregator script>
PYTHON_EOF

cd <exp_dir> && python auto_plot_aggregator.py
```

### 5. Review Generated Figures

View each generated figure using the Read tool. Evaluate:
- Are axes properly labeled?
- Are legends clear and complete?
- Do the figures tell a coherent story?
- Are there any visual artifacts or issues?

### 6. Iterate (up to 3 rounds)

If figures need improvement:
1. Identify specific issues
2. Edit the aggregator script
3. Re-run and re-check

### 7. Finalize

Copy final figures to the experiment's figures directory:
```bash
mkdir -p <exp_dir>/figures
cp <exp_dir>/workspace/figures/*.png <exp_dir>/figures/ 2>/dev/null
cp <exp_dir>/workspace/figures/*.pdf <exp_dir>/figures/ 2>/dev/null
```

List the final figures:
```bash
ls -la <exp_dir>/figures/
```

## Figure Guidelines

- **Minimum 4 figures** for a complete paper
- Each figure should have a clear caption-worthy takeaway
- Use consistent styling across all figures
- Prefer vector formats (PDF) for line plots
- Use raster (PNG 300DPI) for complex plots with many points
- Ensure all data is real (from experiment runs), never synthetic/fake
