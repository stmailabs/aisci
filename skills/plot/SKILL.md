---
name: plot
description: Aggregate and generate publication-quality figures from experiment results across all BFTS stages.
---


# Plot Aggregation

You are generating publication-quality figures for an AI research paper.

## Arguments

- `--exp-dir <path>`: Experiment directory (required)
- `--no-scientific-skills`: Skip enhanced figure formatting even if plugin is available

Parse from the user's message.

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Load Experiment Context

Read the experiment state and gather all stage summaries:
```bash
uv run python3 -c "
import json
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

cd <exp_dir> && uv run python3 auto_plot_aggregator.py
```

### 5. Review Generated Figures

View each generated figure using the Read tool. Evaluate:
- Are axes properly labeled?
- Are legends clear and complete?
- Do the figures tell a coherent story?
- Are there any visual artifacts or issues?

### Deduplication (v2-style)

After reviewing all figures, identify duplicates or near-duplicates:

1. **Exact duplicates**: Same data plotted the same way (e.g., two training curves from identical runs)
2. **Near-duplicates**: Similar content with minor variations (e.g., same metric on same data with slightly different color schemes)
3. **Redundant aggregations**: A grouped plot that duplicates information already in individual subplots

For each duplicate pair, decide:
- **Keep one, remove the other**: When content is truly identical
- **Merge into one figure**: When the plots complement each other (e.g., train + val curves → combined plot)
- **Keep both**: When each serves a distinct narrative purpose (e.g., per-dataset view + aggregate view)

Delete redundant files from `<exp_dir>/figures/` and update the plot description accordingly. The goal is to minimize figure count while preserving all unique information — critical for page-limited papers (ICBINB = 4 pages).

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

## Enhanced Figures (Optional — claude-scientific-skills)

**Skip if** `--no-scientific-skills` is set, plugin not installed, or config disables it.

First, check if the claude-scientific-skills plugin is actually installed:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('sci-skills' in p['id'] for p in json.load(sys.stdin)) and print('SCIENTIFIC_PLUGIN_OK') or print('SCIENTIFIC_PLUGIN_MISSING')" 2>/dev/null
```
If `SCIENTIFIC_PLUGIN_MISSING`, skip this entire section silently.

Then check config (if experiment config is available):
```bash
uv run python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('<exp_dir>/config.yaml'))
    enabled = str(cfg.get('scientific_skills', {}).get('enabled', 'auto')).lower()
    figures = cfg.get('scientific_skills', {}).get('enhanced_figures', True)
    print(f'enabled={enabled} enhanced_figures={figures}')
except: print('enabled=auto enhanced_figures=True')
" 2>/dev/null
```
If `enabled` is `false` or `enhanced_figures` is `false`, skip this section.

When enabled, apply `/scientific-visualization` principles to the aggregator script for publication-quality output:

1. **Journal-specific formatting**: When the target is known (ICML, NeurIPS, workshop):
   - ICML/NeurIPS: Single column width 3.25", double column 6.75", min font 6pt at final size
   - Workshop: Typically single column, more flexible sizing
   - Use sans-serif fonts (Helvetica/Arial) for figure text

2. **Colorblind-safe palettes**: Use the Okabe-Ito palette or viridis/plasma colormaps:
   ```python
   # Okabe-Ito palette (8 colors, universally distinguishable)
   OKABE_ITO = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
   ```
   Test all figures for grayscale legibility.

3. **Statistical rigor in plots**:
   - Always show error bars (standard error or 95% CI from multi-seed runs)
   - Add significance markers where applicable (*, **, ***)
   - Label sample sizes (n=X) in legends or captions
   - For bar charts, show individual data points when n < 20

4. **Multi-panel layout**: Use matplotlib `GridSpec` for consistent multi-panel figures:
   - Label panels (a), (b), (c) in upper-left corners
   - Share axes where appropriate
   - Use consistent spacing and alignment

5. **Export settings**:
   - Vector PDF for all line/bar plots (infinite resolution)
   - PNG at 600 DPI for scatter/heatmap plots with many points
   - Ensure no text is clipped with `bbox_inches='tight'`

Apply these principles when generating the aggregator script in Step 4, and verify compliance during the review in Step 5.

## Figure Guidelines

- **Minimum 4 figures** for a complete paper
- Each figure should have a clear caption-worthy takeaway
- Use consistent styling across all figures
- Prefer vector formats (PDF) for line plots
- Use raster (PNG 300DPI) for complex plots with many points
- Ensure all data is real (from experiment runs), never synthetic/fake

## Error Handling

- **No figures directory exists** → Report to the user that no experiment figures were found and skip plot aggregation. List which stages completed successfully so the user knows where the pipeline stopped.
- **Matplotlib fails to render** → Check the display backend (`matplotlib.get_backend()`). Switch to the non-interactive `Agg` backend with `matplotlib.use('Agg')` before importing pyplot. Retry rendering.
- **No experiment data available** → Report which stages completed and which have no data. Do not generate empty or placeholder figures.
- **Aggregator script crashes** → Read the error output, fix the specific issue in the script, and retry (up to 3 rounds as specified in the iteration step).
- **Generated figures are empty or all-white** → Check that data was loaded correctly and that plot calls have valid data arrays. Regenerate with explicit data validation before plotting.
- **PDF export fails** → Fall back to PNG-only export at 300 DPI. Warn the user that vector figures are unavailable.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
