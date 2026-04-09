# AI Scientist (aisci)

## Environment

This project uses `uv` with a `.venv` directory.

**CRITICAL RULES:**
1. **ALWAYS** prefix `ai-scientist-*` commands with `uv run`
2. **ALWAYS** use `--config config.yaml` (NOT `templates/bfts_config.yaml`) -- the project config has the user's compute backend and settings
3. **Never** `cd` into the plugin cache directory

CLI commands:

```bash
uv run ai-scientist-verify
uv run ai-scientist-device --info
uv run ai-scientist-config --config config.yaml
uv run ai-scientist-state status <exp_dir>
uv run ai-scientist-search "query" --limit 10
uv run ai-scientist-metrics <file>
uv run ai-scientist-latex compile <dir>
uv run ai-scientist-pdf <file>
uv run ai-scientist-budget --config config.yaml
```

**Never** run `ai-scientist-*` commands without `uv run` -- they are installed in `.venv/bin/` and won't be found otherwise.

**Never** `cd` into the plugin cache directory. Always run commands from this project directory.

## Skills

| Command | Description |
|---------|-------------|
| `/ai-scientist` | Full pipeline: ideation -> experiment -> plot -> writeup -> review |
| `/ai-scientist:ideation` | Generate research ideas with literature search |
| `/ai-scientist:experiment` | 4-stage BFTS experiment pipeline |
| `/ai-scientist:experiment-step` | Single BFTS iteration (internal) |
| `/ai-scientist:experiment-generate` | Code generation only (internal) |
| `/ai-scientist:experiment-execute` | Execution only (internal) |
| `/ai-scientist:plot` | Aggregate publication-quality figures |
| `/ai-scientist:writeup` | Generate LaTeX paper with citations |
| `/ai-scientist:review` | Structured peer review (single + panel + Octopus) |
| `/ai-scientist:lit-search` | Standalone literature search |
| `/ai-scientist:workshop` | Interactive workshop description creator |
| `/ai-scientist:octo-review` | Octopus multi-model panel paper review (optional) |

## Installed Plugins

### Core
- **ai-scientist** -- Full research pipeline (ideation, experiment, writeup, review)
- **octopus** -- Multi-model consensus review via claude-octopus (GPT-4o, Gemini, Claude panel)

### Optional
- **scientific-skills** -- 134 scientific skills (databases, tools, analysis)

### Extras
- **superpowers** -- Planning before BFTS stages, brainstorming during ideation
- **context7** -- Library docs lookup before experiment code generation
- **code-review** -- Code quality review between BFTS stages (complements Octopus ML review)
- **astral** -- ruff lint + format on experiment code before execution
- **claude-hud** -- Status line display

## Octopus Integration

When claude-octopus is installed and configured:
- Multi-model consensus review (GPT-4o, Gemini, Claude -- 3+ models vote)
- Stage-gate code review between BFTS stages
- Panel paper review (3 independent model personas + synthesis)
- Code-methods alignment (verifies paper claims match experiment code)
- Rescue delegation for stuck experiments

Control via config:
```yaml
octopus:
  enabled: auto           # auto | true | false
  stage_gate_review: true
  panel_paper_review: true
  code_alignment: true
  rescue_on_stuck: true
  venue: auto             # auto | neurips | icml | iclr | workshop
```

## Scientific Skills Integration (Optional)

When claude-scientific-skills is installed:
- Multi-database literature search during ideation
- Enhanced scientific writing during writeup
- Publication-quality figure formatting
- Evidence quality assessment during review (GRADE framework)

Control via config:
```yaml
scientific_skills:
  enabled: auto               # auto | true | false
  enhanced_literature: true
  enhanced_writing: true
  enhanced_figures: true
  enhanced_review: true
```

## Review Pipeline

The paper review has 3 independent layers:
1. **Claude single reviewer** -- NeurIPS-style review (always runs)
2. **Claude panel** -- 3 personas (Empiricist, Theorist, Practitioner) + synthesis
3. **Octopus multi-model** -- GPT-4o + Gemini + Claude consensus + code-methods alignment (optional)

Plus cross-review comparison that flags divergences >2 points.

## Install / Update

```bash
curl -fsSL https://raw.githubusercontent.com/stmailabs/aisci/main/scripts/install.sh | bash
```

## Run

```bash
claude '/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md'
claude '/ai-scientist'  # interactive -- guides you through topic creation
```
