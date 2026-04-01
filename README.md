# AI Scientist Skills

**Fully autonomous AI research — from idea to paper — powered by Claude Code.**

This project re-implements the complete [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) pipeline as a set of [Claude Code](https://claude.ai/claude-code) skills. Instead of orchestrating multiple LLM APIs, Claude Code itself acts as the single research agent — generating ideas, writing experiment code, analyzing results, authoring LaTeX papers, and performing peer review.

> [中文说明](#中文说明)

---

## How It Works

```
/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md
```

One command triggers the full pipeline:

```
 Ideation ──→ Experiment ──→ Plots ──→ Paper ──→ Review
   │              │            │         │          │
   ▼              ▼            ▼         ▼          ▼
ideas.json    4-stage BFTS   figures/  paper.pdf  review.json
              tree search
```

Each phase can also run independently as a standalone skill.

## Key Features

- **Single agent** — Claude Code replaces all LLM/VLM backends; no OpenAI or Anthropic API keys needed
- **Cross-platform** — auto-detects CUDA, Apple MPS, or CPU for PyTorch experiments
- **Parallel BFTS** — multi-agent tree search with configurable parallelism (default 2 workers)
- **Full paper pipeline** — LaTeX generation with citation gathering, figure analysis, and iterative refinement
- **Structured review** — NeurIPS-format scoring with vision-based figure assessment
- **Resumable** — JSON-based state allows interrupting and resuming at any point

## Quick Start

### 1. Prerequisites

- [Claude Code](https://claude.ai/claude-code) CLI installed
- Python 3.11+
- PyTorch 2.0+
- LaTeX (`pdflatex` + `bibtex`)

```bash
# macOS
brew install --cask mactex-no-gui

# Ubuntu/Debian
sudo apt install texlive-full
```

### 2. Install

```bash
git clone <this-repo>
cd ai-scientist-skills
pip install -r requirements.txt
```

### 3. Run

```bash
# Full pipeline
claude "/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md"

# Or run individual phases
claude "/ai-scientist:ideation --workshop examples/ideas/i_cant_believe_its_not_better.md"
claude "/ai-scientist:experiment --idea experiments/<dir>/idea.json"
claude "/ai-scientist:writeup --exp-dir experiments/<dir> --type icbinb"
claude "/ai-scientist:review --pdf experiments/<dir>/paper.pdf"
claude "/ai-scientist:lit-search 'vision language models'"
```

## Skills Reference

| Skill | Description |
|-------|-------------|
| `/ai-scientist` | Full pipeline orchestrator |
| `/ai-scientist:ideation` | Generate research ideas with literature search and novelty checking |
| `/ai-scientist:experiment` | 4-stage Best-First Tree Search: initial impl → tuning → creative research → ablation |
| `/ai-scientist:experiment-step` | Single BFTS iteration (used internally by experiment) |
| `/ai-scientist:plot` | Aggregate publication-quality figures from experiment results |
| `/ai-scientist:writeup` | Generate LaTeX paper with automated citation gathering |
| `/ai-scientist:review` | Structured peer review with NeurIPS-format scoring |
| `/ai-scientist:lit-search` | Standalone academic literature search |

## Experiment Pipeline

The experiment phase uses a **4-stage Best-First Tree Search (BFTS)**, faithfully adapted from AI-Scientist-v2:

| Stage | Goal | Max Iterations |
|-------|------|----------------|
| 1. Initial Implementation | Get working code on a simple dataset | 20 |
| 2. Baseline Tuning | Optimize hyperparameters (no architecture changes) | 12 |
| 3. Creative Research | Novel improvements across 3 HuggingFace datasets | 12 |
| 4. Ablation Studies | Systematic component contribution analysis | 18 |

Each iteration generates code, executes it with timeout, parses metrics, analyzes plots via Claude's vision, and updates the search tree. Multiple agents explore the tree in parallel.

## Project Structure

```
ai-scientist-skills/
├── skills/              # 8 Claude Code skill prompts
├── tools/               # Python utilities
│   ├── config.py        #   Configuration loading
│   ├── device_utils.py  #   CUDA/MPS/CPU detection
│   ├── search.py        #   Literature search (S2 API + WebSearch)
│   ├── state_manager.py #   Experiment state persistence
│   ├── metric_parser.py #   Metric extraction from stdout
│   ├── latex_compiler.py#   pdflatex/bibtex wrapper
│   └── pdf_reader.py    #   PDF text extraction
├── templates/
│   ├── latex/icml/       #   8-page ICML 2025 template
│   ├── latex/icbinb/     #   4-page ICBINB workshop template
│   ├── bfts_config.yaml  #   Default BFTS configuration
│   └── review_fewshot/   #   Few-shot review examples
├── examples/ideas/       # Example workshop descriptions
├── CLAUDE.md             # Claude Code project instructions
├── requirements.txt
└── pyproject.toml
```

## Configuration

Edit `templates/bfts_config.yaml` or pass overrides:

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
    max_debug_depth: 3     # Max debug retries
    debug_prob: 0.5        # Probability of retrying buggy nodes
exec:
  timeout: 3600            # Per-experiment timeout (seconds)
writeup_type: icbinb       # "icbinb" (4-page) or "icml" (8-page)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `S2_API_KEY` | No | Semantic Scholar API key for higher rate limits |

## Comparison with AI-Scientist-v2

| Aspect | AI-Scientist-v2 | This Project |
|--------|-----------------|--------------|
| Agent | Multiple LLM APIs (OpenAI, Anthropic, etc.) | Claude Code only |
| Interface | Python CLI scripts | Claude Code skills (`/ai-scientist`) |
| Device | CUDA only | CUDA, MPS (Apple Silicon), CPU |
| State | In-memory + pickle | JSON files (human-readable, resumable) |
| VLM | Separate API calls | Claude's native vision |
| Lit search | Semantic Scholar only | S2 + WebSearch fallback |
| Parallelism | ProcessPoolExecutor | Claude Code Agent subagents |

## License

This project adapts the research pipeline design from [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) by Sakana AI. Refer to the original repository for its license terms.

---

## 中文说明

# AI Scientist Skills

**完全自主的 AI 科研流程 —— 从创意到论文 —— 由 Claude Code 驱动。**

本项目将 [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) 的完整科研流程重新实现为 [Claude Code](https://claude.ai/claude-code) 技能包。Claude Code 本身作为唯一的研究代理，完成创意生成、实验代码编写、结果分析、LaTeX 论文撰写和同行评审的全流程。

### 核心特性

- **单一代理** — Claude Code 替代所有 LLM/VLM 后端，无需 OpenAI 或 Anthropic API 密钥
- **跨平台** — 自动检测 CUDA、Apple MPS 或 CPU 作为 PyTorch 后端
- **并行树搜索** — 多代理 Best-First Tree Search，可配置并发度（默认 2）
- **完整论文流程** — LaTeX 生成、自动引文采集、图表分析、迭代优化
- **结构化评审** — NeurIPS 格式评分，含视觉图表评估
- **可恢复** — JSON 状态存储，支持任意阶段中断和恢复

### 快速上手

```bash
# 安装依赖
pip install -r requirements.txt

# 运行完整流程
claude "/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md"

# 单独运行各阶段
claude "/ai-scientist:ideation --workshop <workshop文件>"
claude "/ai-scientist:experiment --idea <idea.json>"
claude "/ai-scientist:writeup --exp-dir <实验目录> --type icbinb"
claude "/ai-scientist:review --pdf <论文.pdf>"
claude "/ai-scientist:lit-search '大语言模型'"
```

### 环境要求

- [Claude Code](https://claude.ai/claude-code) CLI
- Python 3.11+
- PyTorch 2.0+（CUDA / MPS / CPU）
- LaTeX（macOS: `brew install --cask mactex-no-gui`）
- 可选：`S2_API_KEY` 环境变量（Semantic Scholar API，提高速率限制）

### 实验流程

实验阶段使用 **4 阶段 Best-First Tree Search (BFTS)**，忠实复现 AI-Scientist-v2 的设计：

| 阶段 | 目标 | 最大迭代 |
|------|------|----------|
| 1. 初始实现 | 在简单数据集上获得可运行的代码 | 20 |
| 2. 基线调优 | 优化超参数（不改架构） | 12 |
| 3. 创新研究 | 在 3 个 HuggingFace 数据集上探索新方法 | 12 |
| 4. 消融实验 | 系统分析各组件贡献 | 18 |

### 与 AI-Scientist-v2 对比

| 方面 | AI-Scientist-v2 | 本项目 |
|------|-----------------|--------|
| 代理 | 多个 LLM API | 仅 Claude Code |
| 界面 | Python 脚本 | Claude Code 技能 (`/ai-scientist`) |
| 设备 | 仅 CUDA | CUDA、MPS（Apple Silicon）、CPU |
| 状态 | 内存 + pickle | JSON 文件（可读、可恢复） |
| 视觉 | 单独 VLM API | Claude 原生视觉能力 |
| 文献搜索 | 仅 Semantic Scholar | S2 + WebSearch 备选 |
| 并行 | ProcessPoolExecutor | Claude Code Agent 子代理 |
