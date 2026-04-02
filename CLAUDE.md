# AI Scientist Skills for Claude Code

This project provides a complete AI research automation pipeline as Claude Code skills. It reimplements the [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) workflow using Claude Code as the central agent.

## Skills

| Command | Description |
|---------|-------------|
| `/ai-scientist` | Full pipeline: ideation → experiment → plot → writeup → review |
| `/ai-scientist:ideation` | Generate research ideas with literature search |
| `/ai-scientist:experiment` | 4-stage BFTS experiment pipeline |
| `/ai-scientist:experiment-step` | Single BFTS iteration (internal) |
| `/ai-scientist:plot` | Aggregate publication-quality figures |
| `/ai-scientist:writeup` | Generate LaTeX paper with citations |
| `/ai-scientist:review` | Structured peer review (NeurIPS format) |
| `/ai-scientist:lit-search` | Standalone literature search |

## Project Layout

- `skills/` — Skill directories, each containing a `SKILL.md` (Agent Skills standard)
- `tools/` — Python utilities (search, state management, device detection, metrics, LaTeX, PDF)
- `templates/` — LaTeX templates (ICML, ICBINB), config, schema, review examples
- `examples/` — Example workshop descriptions and research ideas
- `experiments/` — Generated experiment outputs (gitignored)

## Tool Usage

All tools are invoked via `python3 tools/<module>.py` from the project root:

```bash
python3 tools/verify_setup.py              # Verify all prerequisites
python3 tools/device_utils.py              # Detect CUDA/MPS/CPU
python3 tools/search.py "query"            # Search papers (S2 API)
python3 tools/state_manager.py status DIR  # Check experiment state
python3 tools/metric_parser.py FILE        # Parse metrics from output
python3 tools/latex_compiler.py compile DIR # Compile LaTeX to PDF
python3 tools/pdf_reader.py FILE           # Extract PDF text
python3 tools/config.py --config FILE      # Load/display config
```

## Environment

- **Python**: 3.11+
- **PyTorch**: 2.0+ (CUDA, MPS, or CPU)
- **LaTeX**: pdflatex + bibtex (MacTeX on macOS, texlive on Linux)
- **Optional**: `S2_API_KEY` env var for Semantic Scholar API (higher rate limits)

## Experiment Code Conventions

All generated experiment code must:
1. Auto-detect device (CUDA/MPS/CPU) — never hardcode `cuda`
2. Print metrics as `metric_name: value` for parsing
3. Save plots to `figures/` directory
4. Set random seeds for reproducibility
5. Keep execution under 60 minutes
