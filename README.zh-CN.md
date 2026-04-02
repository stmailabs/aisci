<div align="center">

  <img src="assets/banner-zh.png" alt="AI Scientist Skills" width="100%"/>

  <p>
    <img src="https://img.shields.io/badge/Claude_Code-Skills-blueviolet?style=flat-square" alt="Claude Code"/>
    <img src="https://img.shields.io/badge/PyTorch-CUDA%20|%20MPS%20|%20CPU-orange?style=flat-square" alt="PyTorch"/>
    <img src="https://img.shields.io/badge/LaTeX-ICML%20|%20ICBINB-blue?style=flat-square" alt="LaTeX"/>
    <img src="https://img.shields.io/badge/Python-3.11+-green?style=flat-square" alt="Python"/>
  </p>

  <strong>语言</strong>：<a href="README.md">English</a> | <a href="README.zh-CN.md">中文</a>

</div>

> 将 [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) 的完整科研流程重新实现为 [Claude Code](https://claude.ai/claude-code) 技能包。Claude Code 本身作为唯一的研究代理 —— 无需 OpenAI、无需 Anthropic API 密钥、无需多后端编排。一个代理完成创意生成、实验执行、图表绘制、论文撰写和同行评审。

## 快速导航

| 章节 | 内容 |
|------|------|
| [为什么做这个项目](#为什么做这个项目) | 项目动机与设计理念 |
| [核心流程](#核心流程) | 从创意到论文评审的端到端流程 |
| [快速上手](#快速上手) | 安装依赖并运行第一次实验 |
| [使用场景](#使用场景) | 安装后的典型使用示例 |
| [技能一览](#技能一览) | 所有可用技能及其功能 |
| [实验流程](#实验流程) | 4 阶段 BFTS 树搜索详解 |
| [配置说明](#配置说明) | 调整并发度、超时和迭代次数 |
| [与 AI-Scientist-v2 对比](#与-ai-scientist-v2-对比) | 变化与改进 |

## 为什么做这个项目

[AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) 证明了 LLM 可以自主开展 ML 研究。但它需要编排多个 LLM API（OpenAI、Anthropic 等）、管理复杂的 Python 基础设施，且仅支持 CUDA。

本项目采用不同的方法：

> **Claude Code 是唯一的代理。** 它替代了原系统中的每一次 LLM 调用、每一次 VLM 调用和每一个后端路由。Python 层仅处理非 LLM 事务：状态持久化、代码执行、LaTeX 编译和文献搜索。

最终结果：一个更简洁、更便携的系统，用单一界面运行相同的科研流程。

## 核心流程

```
/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md
```

一条命令触发完整流程：

```
 创意生成 ───→ 实验执行 ───→ 图表 ───→ 论文 ───→ 评审
    │              │           │        │         │
    ▼              ▼           ▼        ▼         ▼
 ideas.json    4阶段 BFTS   figures/  paper.pdf  review.json
               树搜索
```

每个阶段也可作为独立技能单独运行。

## 快速上手

### 环境要求

- [Claude Code](https://claude.ai/claude-code) CLI
- Python 3.11+
- PyTorch 2.0+
- LaTeX（`pdflatex` + `bibtex`）

```bash
# macOS
brew install --cask mactex-no-gui

# Ubuntu / Debian
sudo apt install texlive-full
```

### 安装

**方式 A — 克隆后作为项目使用**（推荐首次使用）：
```bash
git clone https://github.com/x-roocky/ai-scientist-skills.git
cd ai-scientist-skills
pip install -r requirements.txt
```

**方式 B — 作为 Claude Code 插件安装**：
```bash
git clone https://github.com/x-roocky/ai-scientist-skills.git
pip install -r ai-scientist-skills/requirements.txt
claude --plugin-dir ./ai-scientist-skills
```

### 验证环境

```bash
python tools/verify_setup.py
```

一键检查 Python 版本、全部依赖、PyTorch 设备、LaTeX 工具和 Claude Code CLI。

### 运行

```bash
# 完整流程
claude "/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md"
```

## 使用场景

安装完成后，用自然语言描述你的任务即可。以下是典型的使用场景。

### 1. 运行完整流程

**你说：**
> /ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md

**执行过程：**
- Claude 生成 3 个研究创意并进行文献检索，
- 选择第一个创意，运行 4 阶段实验（初始实现 → 调优 → 创新 → 消融），
- 生成发表级质量的图表，
- 撰写带引文的 4 页 LaTeX 论文，
- 进行 NeurIPS 格式的结构化同行评审。

### 2. 仅生成研究创意

**你说：**
> /ai-scientist:ideation --workshop examples/ideas/i_cant_believe_its_not_better.md --num-ideas 5

**典型输出：**
- 5 个结构化的研究提案（JSON 格式），
- 每个包含标题、假设、摘要、实验计划和风险因素，
- 通过 Semantic Scholar 进行新颖性检查。

### 3. 搜索学术文献

**你说：**
> /ai-scientist:lit-search "视觉语言模型在机器人中的应用"

**典型输出：**
- 按引用数排序的论文列表，含标题、作者、期刊、引用数，
- 最相关结果的摘要和 BibTeX 条目。

### 4. 评审已有论文

**你说：**
> /ai-scientist:review --pdf path/to/paper.pdf

**典型输出：**
- 包含优点、缺点和问题的结构化评审，
- 原创性、质量、清晰度、重要性评分（1-4），
- 总评分（1-10）及录用/拒稿决定，
- 逐图的视觉质量评估。

## 技能一览

8 个技能覆盖完整的科研生命周期。

### 流程编排

| 类型 | 技能 | 说明 |
|------|------|------|
| 编排器 | `/ai-scientist` | 完整流程：创意生成 → 实验 → 图表 → 论文 → 评审 |

### 研究与实验

| 类型 | 技能 | 说明 |
|------|------|------|
| 技能 | `/ai-scientist:ideation` | 通过文献检索和新颖性检查生成研究创意 |
| 技能 | `/ai-scientist:experiment` | 4 阶段 BFTS 实验编排器，支持多代理并行探索 |
| 内部 | `/ai-scientist:experiment-step` | 单次 BFTS 迭代：生成代码、执行、解析指标、分析图表 |
| 技能 | `/ai-scientist:plot` | 从实验结果聚合生成发表级图表 |

### 写作与评审

| 类型 | 技能 | 说明 |
|------|------|------|
| 技能 | `/ai-scientist:writeup` | 生成 LaTeX 论文，含自动引文采集和迭代优化 |
| 技能 | `/ai-scientist:review` | NeurIPS 格式的结构化同行评审，含图表评估 |

### 工具

| 类型 | 技能 | 说明 |
|------|------|------|
| 工具 | `/ai-scientist:lit-search` | 独立的学术文献搜索（Semantic Scholar + WebSearch 备选） |

## 实验流程

实验阶段使用 **4 阶段 Best-First Tree Search (BFTS)**，忠实复现 AI-Scientist-v2 的 `AgentManager` 设计。

| 阶段 | 名称 | 目标 | 最大迭代 |
|------|------|------|----------|
| 1 | 初始实现 | 在简单数据集上获得可运行的代码 | 20 |
| 2 | 基线调优 | 优化超参数，不改变架构 | 12 |
| 3 | 创新研究 | 在 3 个 HuggingFace 数据集上探索新方法 | 12 |
| 4 | 消融实验 | 系统分析各组件贡献 | 18 |

**工作原理**

- 每次迭代：Claude 生成 Python 代码 → 带超时执行 → 从标准输出解析指标 → 通过原生视觉能力分析图表 → 更新搜索树。
- 多个代理并行探索搜索树（可配置，默认 2 个 worker）。
- 节点分支方式：`draft`（新根节点）、`debug`（修复有bug的父节点）或 `improve`（改进良好的父节点）。
- 最佳节点在阶段间传递。多种子评估验证结果的鲁棒性。
- 阶段完成条件与原版一致：阶段 1 需要一个可用节点；阶段 2 需要在 2+ 数据集上收敛；阶段 3 检查执行时间是否合理；阶段 4 运行到完成。

## Python 工具

所有工具通过 `python tools/<module>.py` 在项目根目录调用。

| 工具 | 用途 |
|------|------|
| `config.py` | 加载和合并 YAML 配置，支持 CLI 覆盖 |
| `device_utils.py` | 自动检测 CUDA / MPS / CPU；生成实验代码的设备预设 |
| `search.py` | Semantic Scholar API（含 bibtex）+ WebSearch 优雅降级 |
| `state_manager.py` | 基于 JSON 的实验状态：日志、节点树、阶段转换 |
| `metric_parser.py` | 从实验标准输出提取指标；支持新旧两种指标格式 |
| `latex_compiler.py` | 跨平台 pdflatex/bibtex 编译，含错误提取 |
| `pdf_reader.py` | PDF 文本提取（pymupdf4llm / PyMuPDF / pypdf） |

## 项目结构

```
ai-scientist-skills/
├── .claude-plugin/
│   └── plugin.json            # Agent Skills 插件清单
├── skills/                    # 8 个技能（Agent Skills 标准格式）
│   ├── pipeline/SKILL.md      #   主编排器
│   ├── ideation/SKILL.md      #   研究创意生成
│   ├── experiment/SKILL.md    #   4 阶段 BFTS 流水线
│   ├── experiment-step/SKILL.md #  单次 BFTS 迭代
│   ├── plot/SKILL.md          #   图表聚合
│   ├── writeup/SKILL.md       #   LaTeX 论文生成
│   ├── review/SKILL.md        #   同行评审
│   └── lit-search/SKILL.md    #   文献搜索
├── tools/                     # Python 工具
│   ├── verify_setup.py        #   环境验证
│   ├── config.py              #   配置加载
│   ├── device_utils.py        #   CUDA / MPS / CPU 检测
│   ├── search.py              #   文献搜索（S2 + WebSearch）
│   ├── state_manager.py       #   实验状态持久化
│   ├── metric_parser.py       #   指标提取
│   ├── latex_compiler.py      #   pdflatex / bibtex 封装
│   └── pdf_reader.py          #   PDF 文本提取
├── templates/
│   ├── latex/icml/             #   ICML 2025 8 页模板
│   ├── latex/icbinb/           #   ICBINB 4 页 workshop 模板
│   ├── bfts_config.yaml        #   默认 BFTS 配置
│   ├── idea_schema.json        #   研究创意 JSON 模式
│   └── review_fewshot/         #   Few-shot 评审示例
├── examples/ideas/             # 示例 workshop 描述和创意
├── CLAUDE.md                   # Claude Code 项目说明
├── requirements.txt
└── pyproject.toml
```

## 配置说明

编辑 `templates/bfts_config.yaml` 或在运行时传入覆盖参数：

```yaml
agent:
  num_workers: 2           # 并行 BFTS 代理数
  stages:
    stage1_max_iters: 20   # 减少可加快测试速度
    stage2_max_iters: 12
    stage3_max_iters: 12
    stage4_max_iters: 18
  search:
    num_drafts: 3          # 每阶段初始根节点数
    max_debug_depth: 3     # 最大连续调试重试次数
    debug_prob: 0.5        # 重试有 bug 节点的概率
exec:
  timeout: 3600            # 单次实验超时（秒）
writeup_type: icbinb       # "icbinb"（4 页）或 "icml"（8 页）
```

### 环境变量

| 变量 | 是否必须 | 说明 |
|------|----------|------|
| `S2_API_KEY` | 否 | Semantic Scholar API 密钥，提高速率限制。无密钥时降级为未认证访问或 WebSearch。 |

## 与 AI-Scientist-v2 对比

| 方面 | AI-Scientist-v2 | AI Scientist Skills |
|------|-----------------|---------------------|
| 代理 | 多个 LLM API（OpenAI、Anthropic、Gemini 等） | 仅 Claude Code |
| 界面 | Python CLI 脚本 | Claude Code 技能（`/ai-scientist`） |
| 设备支持 | 仅 CUDA | CUDA、MPS（Apple Silicon）、CPU |
| 状态管理 | 内存 + pickle | JSON 文件（可读、可恢复） |
| 视觉（VLM） | 单独的 VLM API 调用 | Claude 原生视觉能力 |
| 文献搜索 | 仅 Semantic Scholar | S2 + WebSearch 备选 |
| 并行方式 | ProcessPoolExecutor | Claude Code Agent 子代理 |
| 论文模板 | ICML + ICBINB | ICML + ICBINB（相同） |
| 评审格式 | NeurIPS JSON | NeurIPS JSON（相同） |

## 许可证

本项目是 Sakana AI 的 [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist) 的衍生作品，采用 [AI Scientist Source Code License](LICENSE) 分发。完整条款见 [LICENSE](LICENSE)。

## 致谢

基于 [Claude Code](https://claude.ai/claude-code) CLI 构建。

### 参考

- **[AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist)** — Sakana AI 开发的全自主科研系统，本项目忠实改编了其流程设计。
