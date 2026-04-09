---
name: octo-review
description: Multi-model paper review using claude-octopus — independent AI reviewers with consensus gate, venue calibration, and code-methods alignment. Requires claude-octopus plugin.
---


# Multi-Model Paper Review (Octopus)

You are a review coordinator that leverages the claude-octopus plugin to produce a multi-perspective review of a research paper, optionally verifying that the paper's methods section accurately describes the experiment code.

## Arguments

- `--pdf <path>`: Path to the paper PDF (required)
- `--exp-dir <path>`: Experiment directory for code-methods alignment (optional)
- `--no-alignment`: Skip code-methods alignment even if `--exp-dir` provided
- `--output <path>`: Output directory for review files (default: same as PDF directory)

Parse from the user's message.

## Prerequisites

Check that claude-octopus is installed:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('octo' in p['id'] for p in json.load(sys.stdin)) and print('OCTOPUS_OK') or print('OCTOPUS_MISSING')" 2>/dev/null
```
If `OCTOPUS_MISSING`, report the error and stop:
> claude-octopus plugin is not installed. Install with: `claude plugin install octo@nyldn-plugins`

## Procedure

### 1. Extract Paper Text

```bash
uv run ai-scientist-pdf <pdf_path>
```

### 2. Multi-Model Paper Review

Invoke `/octo:debate` with the paper text and review instructions:

```
/octo:debate "Peer review this research paper for a top ML venue. Each reviewer should independently evaluate and provide:

1. Summary (2-3 sentences)
2. Strengths (specific, with evidence from the paper)
3. Weaknesses (specific, with constructive suggestions)
4. Scores: Originality (1-4), Quality (1-4), Clarity (1-4), Significance (1-4), Soundness (1-4), Overall (1-10), Confidence (1-5)
5. Decision: Accept or Reject

Paper text:
[paste extracted paper text]

Be critical. If unsure, give lower scores. Check for: missing baselines, unsupported claims, reproducibility issues, statistical rigor."
```

The `/octo:debate` dispatches to multiple AI providers (Codex, Gemini, Claude, etc.) who independently review the paper. The 75% consensus gate flags disagreements.

### 3. Code-Methods Alignment (Optional)

**Skip if** `--no-alignment` is set or `--exp-dir` not provided.

Get the best experiment code:
```bash
uv run ai-scientist-state save-best <exp_dir> stage4_ablation 2>/dev/null || \
uv run ai-scientist-state save-best <exp_dir> stage3_creative 2>/dev/null || \
uv run ai-scientist-state save-best <exp_dir> stage2_baseline 2>/dev/null || \
uv run ai-scientist-state save-best <exp_dir> stage1_initial
```

Then invoke alignment check:
```
/octo:debate "Verify that this paper's methods section accurately describes the experiment code. Check for:
1. Hyperparameter mismatches (paper says X, code uses Y)
2. Undocumented preprocessing steps
3. Data leakage between train/test
4. Statistical errors or missing error bars
5. Missing algorithmic steps described in paper but not in code

Paper methods section:
[paste methods + experimental setup sections]

Experiment code:
[paste best solution code]

Report each discrepancy with severity: critical / major / minor."
```

### 4. Save Outputs

```bash
cat > <output_dir>/octopus_review.md << 'MD_EOF'
<multi-model review output>
MD_EOF
```

If alignment was run:
```bash
cat > <output_dir>/octopus_alignment.md << 'MD_EOF'
<alignment check output>
MD_EOF
```

### 5. Report Summary

Present:
- Number of providers that participated
- Consensus score (% agreement)
- Aggregated Overall score
- Key strengths (agreed by 75%+ of reviewers)
- Key weaknesses (agreed by 75%+ of reviewers)
- Alignment issues found (if applicable)

## Error Handling

- **Octopus plugin not installed** → Report error, suggest install command. Do not attempt fallback.
- **No external providers available** → Octopus falls back to Claude-only multi-agent. Warn user that results may be less diverse.
- **Paper PDF extraction fails** → Try `--sections` flag. If still fails, report the error.
- **Code-methods alignment finds critical issues** → Flag prominently in the summary. These should block publication.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
