# Troubleshooting

## Installation

### `uv: command not found`
Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### `claude: command not found`
Install Claude Code: `npm install -g @anthropic-ai/claude-code`

### Plugin install says "already on disk" but skills don't work
The marketplace cache is stale. Force update:
```bash
claude plugin marketplace update aisci
claude plugin uninstall aisci@aisci --scope project
claude plugin install aisci@aisci --scope project
```

### `aisci-verify: command not found`
The CLI tools are in `.venv/bin/`. Always use `uv run`:
```bash
uv run aisci-verify
```

## Experiments

### CUDA Out of Memory
Experiment code uses too much GPU memory.
- Add to config: `exec.timeout: 3600`
- In the experiment, Claude will auto-reduce batch size after OOM errors
- Force CPU: set device to `cpu` in experiment code preamble
- Reduce model size or dataset in the workshop description

### All Stage 1 Nodes Are Failing
After 20 iterations, no working code.
- Check the error patterns: `uv run aisci-state journal-summary <exp_dir> stage1_initial`
- Common causes: missing dataset, wrong import, incompatible library versions
- Provide seed code: `claude '/aisci --idea idea.json --seed-code starter.py'`
- Enable Octopus rescue: `octopus.rescue_on_stuck: true` in config

### Experiment Takes Too Long
- Reduce iterations: `--set agent.stages.stage1_max_iters=5 agent.stages.stage2_max_iters=3`
- Reduce workers: `--set agent.num_workers=1`
- Skip later stages: let the experiment run stage 1 only, then review

### Metrics Not Found in Output
The experiment code doesn't print metrics in the expected format.
- Metrics must be printed as: `metric_name: value` (e.g., `val_loss: 0.342`)
- Check the output log: `cat <exp_dir>/logs/step_*_output.txt | tail -20`

## Paper Writing

### LaTeX Compilation Fails
```bash
# Check if LaTeX is installed
uv run aisci-latex check

# macOS — install BasicTeX + required packages
brew install --cask basictex
sudo tlmgr update --self
sudo tlmgr install subfigure multirow cleveref xspace natbib algorithm algorithmic

# Ubuntu/Debian
sudo apt install texlive-full
```

### BibTeX Errors
- Missing `.bib` entries cause warnings but usually don't break compilation
- Check the generated `.bib` file in the experiment's latex directory
- If bibliography is broken, the paper still compiles without citations

### Paper Exceeds Page Limit
- icbinb template: 4 pages (workshop)
- icml template: 8 pages (conference)
- If the paper is too long, Claude will trim during writeup reflections

## Review

### S2 API Returns 403
Rate limited without API key. Get a free key:
1. Visit https://www.semanticscholar.org/product/api#api-key-form
2. Set: `export S2_API_KEY="your-key-here"`
3. Add to shell profile: `echo 'export S2_API_KEY="your-key"' >> ~/.zshrc`

The pipeline falls back to WebSearch if S2 is unavailable.

### Octopus Review Fails
- Check Octopus plugin is installed: `claude plugin list --scope project | grep octo`
- Verify API keys are set for multi-model providers (GPT-4o, Gemini)
- If Octopus is unavailable, the Claude review (steps 1-8) still runs independently
- Check config: `octopus.enabled` should be `auto` or `true`

### Octopus Models Disagree (Low Consensus)
- This is expected for borderline papers — disagreement highlights areas needing revision
- Check the per-model breakdown in the review output
- Focus on claims where all models agree there are issues
- Re-run with `octopus.venue: workshop` for more lenient review thresholds

### Octopus Authentication Errors
- Each model provider needs its own API key
- Set `OPENAI_API_KEY` for GPT-4o access
- Set `GOOGLE_API_KEY` or `GEMINI_API_KEY` for Gemini access
- Claude uses your existing Anthropic credentials automatically
- Test with: `claude '/aisci:octo-review --test'`

## Progress Monitoring

Check experiment progress mid-run:
```bash
uv run aisci-dashboard <exp_dir>
uv run aisci-state status <exp_dir>
uv run aisci-state journal-summary <exp_dir> stage1_initial
```
