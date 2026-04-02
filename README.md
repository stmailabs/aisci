<div align="center">

  <img src="assets/banner-en.png" alt="AI Scientist Skills" width="100%"/>

  <p>
    <img src="https://img.shields.io/badge/Claude_Code-Skills-blueviolet?style=flat-square" alt="Claude Code"/>
    <img src="https://img.shields.io/badge/PyTorch-CUDA%20|%20MPS%20|%20CPU-orange?style=flat-square" alt="PyTorch"/>
    <img src="https://img.shields.io/badge/LaTeX-ICML%20|%20ICBINB-blue?style=flat-square" alt="LaTeX"/>
    <img src="https://img.shields.io/badge/Python-3.11+-green?style=flat-square" alt="Python"/>
  </p>

  <strong>Language</strong>: <a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>

</div>

> Re-implements the complete [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) research pipeline as [Claude Code](https://claude.ai/claude-code) skills. Claude Code itself acts as the single research agent — no OpenAI, no Anthropic API keys, no multi-backend orchestration. One agent handles ideation, experiments, plotting, paper writing, and peer review.

## Quick Navigation

| Section | What it helps with |
|---|---|
| [Why This Project](#why-this-project) | Understand the motivation and design philosophy. |
| [Core Pipeline](#core-pipeline) | See the end-to-end flow from idea to reviewed paper. |
| [Quick Start](#quick-start) | Install dependencies and run your first pipeline. |
| [Getting Started Scenarios](#getting-started-scenarios) | Realistic first-use examples after installation. |
| [Skills Reference](#skills-reference) | Browse all available skills and what they do. |
| [Experiment Pipeline](#experiment-pipeline) | Understand the 4-stage BFTS tree search. |
| [Configuration](#configuration) | Tune parallelism, timeouts, and iteration counts. |
| [Comparison with AI-Scientist-v2](#comparison-with-ai-scientist-v2) | See what changed and what improved. |

## Why This Project

[AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) demonstrated that LLMs can autonomously conduct ML research. But it requires orchestrating multiple LLM APIs (OpenAI, Anthropic, etc.), managing complex Python infrastructure, and runs only on CUDA.

This project takes a different approach:

> **Claude Code is the only agent.** It replaces every LLM call, every VLM call, and every backend router in the original system. The Python layer handles only non-LLM concerns: state persistence, code execution, LaTeX compilation, and literature search.

The result is a simpler, more portable system that runs the same research pipeline with a single interface.

## Core Pipeline

```
/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md
```

One command triggers the full lifecycle:

```
 Ideation ───→ Experiment ───→ Plots ───→ Paper ───→ Review
    │              │              │          │          │
    ▼              ▼              ▼          ▼          ▼
 ideas.json    4-stage BFTS    figures/   paper.pdf  review.json
               tree search
```

Each phase can also run independently as a standalone skill.

## Quick Start

### Prerequisites

- [Claude Code](https://claude.ai/claude-code) CLI
- Python 3.11+
- PyTorch 2.0+
- LaTeX (`pdflatex` + `bibtex`)

```bash
# macOS
brew install --cask mactex-no-gui

# Ubuntu / Debian
sudo apt install texlive-full
```

### Install

```bash
git clone https://github.com/x-roocky/ai-scientist-skills.git
cd ai-scientist-skills
pip install -r requirements.txt
```

### Verify

```bash
python tools/verify_setup.py
```

Checks Python version, all dependencies, PyTorch device, LaTeX tools, and Claude Code CLI in one go.

### Run

```bash
# Full pipeline
claude "/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md"
```

## Getting Started Scenarios

After installation, describe your task in natural language. Below are realistic starting points.

### 1. Run the Full Pipeline

**You say:**
> /ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md

**What happens:**
- Claude generates 3 research ideas with literature search,
- selects the first idea and runs a 4-stage experiment (initial impl → tuning → creative → ablation),
- generates publication-quality figures,
- writes a 4-page LaTeX paper with citations,
- performs a structured peer review with NeurIPS-format scoring.

### 2. Just Generate Research Ideas

**You say:**
> /ai-scientist:ideation --workshop examples/ideas/i_cant_believe_its_not_better.md --num-ideas 5

**Typical output:**
- 5 structured research proposals in JSON format,
- each with title, hypothesis, abstract, experiments, and risk factors,
- novelty-checked against Semantic Scholar literature.

### 3. Search Academic Literature

**You say:**
> /ai-scientist:lit-search "vision language models for robotics"

**Typical output:**
- ranked papers with titles, authors, venues, citation counts,
- abstracts and BibTeX entries for the most relevant results.

### 4. Review an Existing Paper

**You say:**
> /ai-scientist:review --pdf path/to/paper.pdf

**Typical output:**
- structured review with strengths, weaknesses, and questions,
- scores for originality, quality, clarity, significance (1-4),
- overall score (1-10) and accept/reject decision,
- per-figure visual quality assessment.

## Skills Reference

8 skills covering the complete research lifecycle.

### Pipeline Orchestration

| Type | Skill | Description |
|------|-------|-------------|
| Orchestrator | `/ai-scientist` | Full pipeline: ideation → experiment → plot → writeup → review. |

### Research & Experimentation

| Type | Skill | Description |
|------|-------|-------------|
| Skill | `/ai-scientist:ideation` | Generate novel research ideas with literature search and novelty checking. |
| Skill | `/ai-scientist:experiment` | 4-stage BFTS experiment orchestrator with parallel agent exploration. |
| Internal | `/ai-scientist:experiment-step` | Single BFTS iteration: generate code, execute, parse metrics, analyze plots. |
| Skill | `/ai-scientist:plot` | Aggregate publication-quality figures from experiment results. |

### Writing & Review

| Type | Skill | Description |
|------|-------|-------------|
| Skill | `/ai-scientist:writeup` | Generate LaTeX paper with automated citation gathering and iterative refinement. |
| Skill | `/ai-scientist:review` | Structured peer review with NeurIPS-format scoring and figure assessment. |

### Utilities

| Type | Skill | Description |
|------|-------|-------------|
| Utility | `/ai-scientist:lit-search` | Standalone academic literature search (Semantic Scholar + WebSearch fallback). |

## Experiment Pipeline

The experiment phase uses a **4-stage Best-First Tree Search (BFTS)**, faithfully adapted from AI-Scientist-v2's `AgentManager`.

| Stage | Name | Goal | Max Iters |
|-------|------|------|-----------|
| 1 | Initial Implementation | Get working code on a simple dataset | 20 |
| 2 | Baseline Tuning | Optimize hyperparameters without architecture changes | 12 |
| 3 | Creative Research | Novel improvements across 3 HuggingFace datasets | 12 |
| 4 | Ablation Studies | Systematic component contribution analysis | 18 |

**How it works**

- Each iteration: Claude generates Python code → executes with timeout → parses metrics from stdout → analyzes generated plots via native vision → updates the search tree.
- Multiple agents explore the tree in parallel (configurable, default 2 workers).
- Nodes branch as `draft` (new root), `debug` (fix buggy parent), or `improve` (enhance good parent).
- Best nodes carry forward between stages. Multi-seed evaluation validates robustness.
- Stage completion criteria mirror the original: Stage 1 needs one working node; Stage 2 needs convergence on 2+ datasets; Stage 3 checks execution time scaling; Stage 4 runs to completion.

## Python Tools

All tools are invoked via `python tools/<module>.py` from the project root.

| Tool | Purpose |
|------|---------|
| `config.py` | Load and merge YAML configuration with CLI overrides. |
| `device_utils.py` | Auto-detect CUDA / MPS / CPU; generate device preamble for experiment code. |
| `search.py` | Semantic Scholar API with bibtex + graceful fallback for WebSearch. |
| `state_manager.py` | JSON-based experiment state: journal, node tree, stage transitions. |
| `metric_parser.py` | Extract metrics from experiment stdout; supports old and new metric formats. |
| `latex_compiler.py` | Cross-platform pdflatex/bibtex compilation with error extraction. |
| `pdf_reader.py` | PDF text extraction via pymupdf4llm / PyMuPDF / pypdf. |

## Project Structure

```
ai-scientist-skills/
├── skills/                   # 8 Claude Code skill prompts (.md)
├── tools/                    # Python utilities
│   ├── config.py             #   Configuration loading
│   ├── device_utils.py       #   CUDA / MPS / CPU detection
│   ├── search.py             #   Literature search (S2 + WebSearch)
│   ├── state_manager.py      #   Experiment state persistence
│   ├── metric_parser.py      #   Metric extraction from stdout
│   ├── latex_compiler.py     #   pdflatex / bibtex wrapper
│   └── pdf_reader.py         #   PDF text extraction
├── templates/
│   ├── latex/icml/            #   8-page ICML 2025 template
│   ├── latex/icbinb/          #   4-page ICBINB workshop template
│   ├── bfts_config.yaml       #   Default BFTS configuration
│   ├── idea_schema.json       #   Research idea JSON schema
│   └── review_fewshot/        #   Few-shot review examples
├── examples/ideas/            # Example workshop descriptions & ideas
├── CLAUDE.md                  # Claude Code project instructions
├── requirements.txt
└── pyproject.toml
```

## Configuration

Edit `templates/bfts_config.yaml` or pass overrides at runtime:

```yaml
agent:
  num_workers: 2           # Parallel BFTS agents
  stages:
    stage1_max_iters: 20   # Reduce for faster test runs
    stage2_max_iters: 12
    stage3_max_iters: 12
    stage4_max_iters: 18
  search:
    num_drafts: 3          # Initial root nodes per stage
    max_debug_depth: 3     # Max consecutive debug retries
    debug_prob: 0.5        # Probability of retrying buggy nodes
exec:
  timeout: 3600            # Per-experiment timeout (seconds)
writeup_type: icbinb       # "icbinb" (4-page) or "icml" (8-page)
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `S2_API_KEY` | No | Semantic Scholar API key for higher rate limits. Falls back to unauthenticated access or WebSearch. |

## Comparison with AI-Scientist-v2

| Aspect | AI-Scientist-v2 | AI Scientist Skills |
|--------|-----------------|---------------------|
| Agent | Multiple LLM APIs (OpenAI, Anthropic, Gemini, etc.) | Claude Code only |
| Interface | Python CLI scripts | Claude Code skills (`/ai-scientist`) |
| Device support | CUDA only | CUDA, MPS (Apple Silicon), CPU |
| State management | In-memory + pickle | JSON files (human-readable, resumable) |
| Vision (VLM) | Separate VLM API calls | Claude's native vision |
| Literature search | Semantic Scholar only | S2 + WebSearch fallback |
| Parallelism | ProcessPoolExecutor | Claude Code Agent subagents |
| Paper templates | ICML + ICBINB | ICML + ICBINB (same) |
| Review format | NeurIPS JSON | NeurIPS JSON (same) |

## License

This project is a derivative work of [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) by Sakana AI, distributed under the [AI Scientist Source Code License](LICENSE). See [LICENSE](LICENSE) for full terms.

## Acknowledgments

Built with [Claude Code](https://claude.ai/claude-code) CLI.

### References

- **[AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist)** by Sakana AI — the original fully autonomous research system whose pipeline design this project faithfully adapts.
