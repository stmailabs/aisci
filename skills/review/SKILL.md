---
name: review
description: Perform a structured peer review of a research paper — text analysis, figure quality assessment, and NeurIPS-format scoring.
---


# Paper Review

You are an experienced AI researcher performing a rigorous peer review of a research paper.

## Arguments

- `--pdf <path>`: Path to the paper PDF (required)
- `--exp-dir <path>`: Experiment directory (optional, for additional context)
- `--output <path>`: Output directory for review files (default: same as PDF directory)
- `--no-octopus`: Skip multi-model review even if Octopus is available
- `--no-scientific-skills`: Skip scientific-critical-thinking assessment even if plugin is available

Parse from the user's message.

## Procedure

The review has two tiers:
- **Core Review (Steps 1-8)**: Always runs. Produces the primary review JSON.
- **Enhanced Review (Steps 9-12)**: Optional. Adds multi-perspective analysis and cross-validation. Depends on plugin availability.

---

### Core Review

### 1. Extract Paper Text

```bash
uv run aisci-pdf <pdf_path>
```

If the paper is long, also extract by sections:
```bash
uv run aisci-pdf <pdf_path> --sections
```

### 2. Load Review Examples

Read few-shot examples to calibrate your review standards:
```bash
cat templates/review_fewshot/attention.json
```

These show what good reviews look like — use them as a reference for depth and specificity, but do NOT copy their content.

### 3. Review the Paper Text

> **NOTE**: This step is DEPRECATED in favor of the Claude panel (step 10). A single Claude review is redundant with the 4-persona panel — the panel's Empiricist persona covers essentially the same ground. Skip this step entirely if the panel is being run — it's kept only for backward compatibility with scripts that expect `review.json`. If you must run it, understand you're duplicating work. Downstream tools should read `review.json` from the panel synthesis (step 10) instead.

Adopt the following reviewer persona:

> You are an AI researcher reviewing a paper submitted to a prestigious ML venue. Be critical and cautious in your decision. If a paper is bad or you are unsure, give it bad scores and reject it.

Carefully evaluate the paper along these dimensions:

#### Summary
Write a concise summary of the paper's content and contributions. The authors should generally agree with a well-written summary.

#### Strengths
List specific strengths with evidence:
- Is the problem well-motivated?
- Is the approach technically sound?
- Are the experiments comprehensive?
- Are the results significant?

#### Weaknesses
List specific weaknesses with constructive suggestions:
- Are there missing baselines or comparisons?
- Are claims insufficiently supported?
- Are there clarity issues?
- Are there methodological concerns?

### 4. Review Figures (VLM Review)

Read the PDF file to view its pages as images. For each figure in the paper:

1. **Image Description**: What does the figure show?
2. **Image Review**: Is the figure clear, informative, and well-designed?
3. **Caption Review**: Is the caption accurate and complete?
4. **Reference Review**: Is the figure properly referenced and discussed in the text?
5. **Overall Assessment**: Should this figure be in the main paper, moved to appendix, or removed?
6. **Sub-figures**: Are there too many sub-figures? Is the layout effective?
7. **Informativeness**: Does the figure effectively communicate the data?

### 4b. Multi-Model Figure Review (when Octopus available)

After Claude's figure-by-figure VLM review, also run Octopus multi-vision review for the **final paper submission only** (skip during BFTS iterations where Claude-alone is sufficient for speed):

```
/octo:debate "Review these paper figures. For each figure, assess: (1) publication quality (axes, labels, legends, resolution), (2) caption accuracy (does caption match what figure shows?), (3) scientific clarity (does the figure support the paper's claims?). Use ALL available vision-capable providers (Claude and Gemini minimum). Report per-figure scores 0-10 and any issues. Figures: [paste figure paths]"
```

Gemini is a strong vision model and catches different issues than Claude. For publication-quality submission, two vision models are better than one. For draft/iteration phases, Claude-alone is sufficient (speed > consensus).

### 5. Generate Structured Review

Produce the review in this exact JSON format:

```json
{
  "Summary": "A summary of the paper content and its contributions.",
  "Strengths": [
    "Strength 1: specific detail...",
    "Strength 2: specific detail..."
  ],
  "Weaknesses": [
    "Weakness 1: specific detail and suggestion...",
    "Weakness 2: specific detail and suggestion..."
  ],
  "Originality": 3,
  "Quality": 3,
  "Clarity": 3,
  "Significance": 2,
  "Questions": [
    "Question 1: ...",
    "Question 2: ..."
  ],
  "Limitations": [
    "Limitation 1: ...",
    "Limitation 2: ..."
  ],
  "Ethical Concerns": false,
  "Soundness": 3,
  "Presentation": 3,
  "Contribution": 2,
  "Overall": 5,
  "Confidence": 4,
  "Decision": "Accept or Reject"
}
```

#### Scoring Rubric:

**Originality** (1-4): 1=known, 2=minor variation, 3=clear novelty, 4=groundbreaking
**Quality** (1-4): 1=flawed, 2=concerns, 3=solid, 4=excellent
**Clarity** (1-4): 1=unclear, 2=mostly clear, 3=well-written, 4=exemplary
**Significance** (1-4): 1=limited, 2=moderate, 3=important, 4=transformative
**Soundness** (1-4): 1=poor, 2=fair, 3=good, 4=excellent
**Presentation** (1-4): 1=poor, 2=fair, 3=good, 4=excellent
**Contribution** (1-4): 1=poor, 2=fair, 3=good, 4=excellent
**Overall** (1-10): 1=strong reject, 3=reject, 5=borderline, 7=accept, 10=award
**Confidence** (1-5): 1=low, 2=medium, 3=high, 4=very high, 5=absolute

### 6. Generate Figure Review

Create a separate figure-level review:

```json
{
  "figures": [
    {
      "figure_id": "Figure 1",
      "img_description": "...",
      "img_review": "...",
      "caption_review": "...",
      "reference_review": "...",
      "overall_comments": "Keep in main paper / Move to appendix",
      "containing_sub_figures": "Description of sub-figure layout",
      "informative_review": "How effectively the data is communicated"
    }
  ]
}
```

### 7. Save Review Output

Save the text review:
```bash
cat > <output_dir>/review.json << 'JSON_EOF'
<review JSON>
JSON_EOF
```

Save the figure review:
```bash
cat > <output_dir>/review_figures.json << 'JSON_EOF'
<figure review JSON>
JSON_EOF
```

### 8. Report Summary

Present a concise summary:
- Overall score and decision
- Top 3 strengths
- Top 3 weaknesses
- Key recommendation

**The Core Review is now complete.** Steps 9-12 below are optional enhancements that run if the relevant plugins are available. If none are available, the review from steps 1-8 is the final output.

---

### Enhanced Review (Optional)

### 9. Scientific Critical Thinking Assessment (Optional)

**Skip this step if** `--no-scientific-skills` is set, plugin not installed, or config disables it.

First, check if the claude-scientific-skills plugin is actually installed:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('sci-skills' in p['id'] for p in json.load(sys.stdin)) and print('SCIENTIFIC_PLUGIN_OK') or print('SCIENTIFIC_PLUGIN_MISSING')" 2>/dev/null
```
If `SCIENTIFIC_PLUGIN_MISSING`, skip this entire step silently.

Then check config (if `--exp-dir` is provided):
```bash
uv run python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('<exp_dir>/config.yaml'))
    enabled = str(cfg.get('scientific_skills', {}).get('enabled', 'auto')).lower()
    review = cfg.get('scientific_skills', {}).get('enhanced_review', True)
    print(f'enabled={enabled} enhanced_review={review}')
except: print('enabled=auto enhanced_review=True')
" 2>/dev/null
```
If `enabled` is `false` or `enhanced_review` is `false`, skip this step.

When enabled, augment the review with a rigorous evidence quality assessment:

1. **Invoke scientific critical thinking**:
   ```
   /scientific-critical-thinking
   ```
   Provide the paper text and ask it to evaluate:
   - **Methodology critique**: Is the study design appropriate? Are controls adequate? Is there selection bias?
   - **Statistical evaluation**: Are tests appropriate? Are multiple comparisons corrected? Are effect sizes reported?
   - **Evidence quality**: Using GRADE framework, rate the quality of evidence (High/Moderate/Low/Very Low)
   - **Logical fallacy detection**: Check for correlation-causation confusion, hasty generalization, cherry-picking, survivorship bias
   - **Bias assessment**: Identify potential cognitive, selection, measurement, and analysis biases

2. **Save the assessment**:
   ```bash
   cat > <output_dir>/evidence_assessment.md << 'MD_EOF'
   <critical thinking assessment output>
   MD_EOF
   ```

3. **Integrate findings** into the review summary:
   - Add evidence quality grade alongside overall score
   - Flag any logical fallacies or methodological concerns
   - Note bias risks that may affect interpretation

This assessment adds scientific rigor to the review without changing the NeurIPS-format scores from steps 1-8.

### 10. Claude Panel Review

Run a second, multi-perspective review using 4 independent reviewer personas. This mirrors the Octopus multi-model debate and gives you comparable outputs to cross-reference.

Launch **4 parallel agents**, each with a distinct persona. Each agent receives the paper text and produces a review in the same JSON format as step 5.

**Agent 1 — The Empiricist** (focus: experimental rigor):
> You are a meticulous experimentalist. You care most about reproducibility, statistical validity, proper baselines, ablation studies, and whether the results actually support the claims. You are skeptical of results without error bars, missing baselines, or cherry-picked metrics.

**Agent 2 — The Theorist** (focus: conceptual soundness):
> You are a theoretical researcher. You care most about whether the approach is principled, the problem formulation is sound, the connections to prior work are clear, and the contribution advances understanding. You are skeptical of ad-hoc methods without motivation.

**Agent 3 — The Practitioner** (focus: real-world impact):
> You are an applied ML researcher. You care most about whether the method actually works in practice, scales to real problems, is easy to reproduce and adopt, and whether the paper provides sufficient implementation detail. You are skeptical of toy experiments on MNIST.

**Agent 4 — The Skeptic** (focus: finding reasons to reject):
> You are a critical peer reviewer who defaults to rejection. You care most about: unsupported claims, weak baselines, missing ablations, reproducibility concerns, and overclaiming. If unsure whether the paper is good, reject it. This is the "negative reviewer" from the Sakana AI Scientist v1 methodology — biased toward rejection to counter Claude's tendency to be too generous.

Each agent produces a review JSON (same format as step 5). Save them:
```bash
cat > <output_dir>/claude_panel_empiricist.json << 'JSON_EOF'
<review JSON>
JSON_EOF

cat > <output_dir>/claude_panel_theorist.json << 'JSON_EOF'
<review JSON>
JSON_EOF

cat > <output_dir>/claude_panel_practitioner.json << 'JSON_EOF'
<review JSON>
JSON_EOF

cat > <output_dir>/claude_panel_skeptic.json << 'JSON_EOF'
<review JSON>
JSON_EOF
```

**Synthesize** the 4 reviews into a panel summary:
- Where do all 4 agree? (consensus strengths/weaknesses)
- Where do they disagree? (flag for author response)
- Aggregated scores (average across all 4 personas)
- Overall panel recommendation (accept/reject with confidence)

Save the synthesis:
```bash
cat > <output_dir>/claude_panel_synthesis.json << 'JSON_EOF'
{
  "consensus_strengths": ["..."],
  "consensus_weaknesses": ["..."],
  "disagreements": ["..."],
  "aggregated_scores": {
    "Originality": 3, "Quality": 3, "Clarity": 3, "Significance": 2,
    "Soundness": 3, "Presentation": 3, "Contribution": 2,
    "Overall": 5, "Confidence": 4
  },
  "panel_decision": "Accept or Reject",
  "priority_actions": ["..."]
}
JSON_EOF
```

**Also write `review.json` from the panel synthesis** so downstream tools (which expect the step-5 format) don't break when the deprecated single review is skipped:

```bash
cat > <output_dir>/review.json << 'JSON_EOF'
{
  "Summary": "Synthesized from the 4-persona Claude panel (Empiricist, Theorist, Practitioner, Skeptic).",
  "Strengths": ["<consensus strengths from panel synthesis>"],
  "Weaknesses": ["<consensus weaknesses from panel synthesis>"],
  "Originality": <aggregated>,
  "Quality": <aggregated>,
  "Clarity": <aggregated>,
  "Significance": <aggregated>,
  "Questions": ["..."],
  "Limitations": ["..."],
  "Ethical Concerns": false,
  "Soundness": <aggregated>,
  "Presentation": <aggregated>,
  "Contribution": <aggregated>,
  "Overall": <aggregated>,
  "Confidence": <aggregated>,
  "Decision": "Accept or Reject",
  "source": "claude_panel_synthesis"
}
JSON_EOF
```

This keeps the `review.json` contract stable while letting the deprecated single-reviewer path be skipped.

### 11. Multi-Model Review (Optional — Octopus)

**Skip this step if** Octopus is not available, the user specified `--no-octopus`, or `octopus.enabled` is `"false"` in config.

Check Octopus availability (plugin):
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('octo' in p['id'] for p in json.load(sys.stdin)) and print('OCTOPUS_OK') or print('OCTOPUS_MISSING')" 2>/dev/null
```
If `OCTOPUS_MISSING`, skip this step silently.

If `OCTOPUS_AVAILABLE`, enhance the review with a multi-model debate:

1. **Read Octopus config values** from the experiment's config (if `--exp-dir` provided):
   ```bash
   uv run aisci-config --config <exp_dir>/config.yaml 2>/dev/null
   ```
   Extract:
   - `octopus.enabled` — if `"false"`, **skip this entire step** even if the plugin is installed
   - `octopus.research_intensity` — if `"auto"`, derive from `writeup_type` (icbinb→workshop, icml→icml). Otherwise use the configured value.
   - `octopus.multi_model_paper_review` — if `false`, skip the debate
   - `octopus.claim_verification` — if `false`, skip code-methods alignment even when `--exp-dir` is provided

   If no config available, use defaults: enabled=`"auto"`, venue=`workshop`, panel=`true`, alignment=`true`.

2. **Run Octopus debate** (respecting config toggles):

   If `octopus.claim_verification` is `true` and `--exp-dir` is provided, save the promoted best solution to a known path and use that:
   ```bash
   uv run aisci-state save-best <exp_dir> stage4_ablation 2>/dev/null || \
   uv run aisci-state save-best <exp_dir> stage3_creative 2>/dev/null || \
   uv run aisci-state save-best <exp_dir> stage2_baseline 2>/dev/null || \
   uv run aisci-state save-best <exp_dir> stage1_initial
   ```
   This writes `best_solution_<id>.py` to the stage's state directory and prints the file path. Use the printed directory (e.g., `<exp_dir>/state/stage4_ablation/`) as `<best_solution_dir>`.

   If `save-best` fails for all stages (no good nodes in any stage), skip code-methods alignment and log a warning.

   Invoke the multi-model debate with paper context:
   ```
   /octo:debate "Peer review this research paper using ALL available AI providers. Each provider should independently evaluate as a reviewer for <venue>. Score: Originality (1-4), Quality (1-4), Clarity (1-4), Significance (1-4), Soundness (1-4), Overall (1-10). Provide strengths, weaknesses, and decision. Use the 75% consensus gate. Paper: <pdf_path>. Code: <best_solution_dir> (verify code-methods alignment — check hyperparameters, data leakage, undocumented steps)."
   ```

   If alignment is disabled or no code available, omit the code reference:
   ```
   /octo:debate "Peer review this research paper using ALL available AI providers. Each provider should independently evaluate as a reviewer for <venue>. Score: Originality (1-4), Quality (1-4), Clarity (1-4), Significance (1-4), Soundness (1-4), Overall (1-10). Provide strengths, weaknesses, and decision. Use the 75% consensus gate. Paper: <pdf_path>."
   ```

3. **Save Octopus outputs** (Octopus returns rendered Markdown, not raw JSON):
   ```bash
   cat > <output_dir>/octopus_review.md << 'MD_EOF'
   <octopus review output — Markdown>
   MD_EOF
   ```

4. **Report Octopus additions** alongside the Claude reviews:
   - Multi-model recommendation and aggregated scores
   - Any code-methods alignment issues found

If Octopus is not available, skip silently — the Claude reviews are complete on their own.

### 12. Final Synthesis (Octopus when available)

We've now gathered 4 independent review layers:
- Claude panel (4 personas: Empiricist, Theorist, Practitioner, Skeptic)
- Scientific critical thinking assessment (optional)
- Octopus multi-model debate (optional, from step 11)

**Aggregating these through a single Claude call reintroduces the bias we just eliminated with multi-model review.** Use Octopus for the synthesis itself when available.

**Check Octopus availability first**:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('octo' in p['id'] for p in json.load(sys.stdin)) and print('OCTOPUS_OK') or print('OCTOPUS_MISSING')" 2>/dev/null
```

**If `OCTOPUS_OK`** (and `--no-octopus` not passed):
```
/octo:debate "Synthesize these independent paper reviews into a final recommendation. Reviews to synthesize: [paste all panel JSONs + octopus review]. Identify: (1) consensus strengths (agreed by 75%+ reviewers), (2) consensus weaknesses, (3) genuine disagreements (where reviewers diverge >2 points), (4) aggregated scores, (5) final accept/reject recommendation with confidence level. Use the 75% consensus gate — flag anything where providers genuinely disagree."
```

**If `OCTOPUS_MISSING` or `--no-octopus`** (fallback): use Claude alone to aggregate the 4 panel reviews into the same JSON structure. Add `"synthesized_by": "claude_alone"` to the output and note in the summary that this is a single-model aggregation (less robust than multi-model synthesis).

Save the synthesis to `<output_dir>/final_synthesis.json`:

```bash
cat > <output_dir>/final_synthesis.json << 'JSON_EOF'
{
  "claude_panel": { "Overall": <N>, "Decision": "..." },
  "octopus_panel": { "Overall": <N>, "Decision": "..." },
  "consensus_strengths": ["..."],
  "consensus_weaknesses": ["..."],
  "genuine_disagreements": ["..."],
  "aggregated_scores": { "Overall": <N> },
  "consensus_decision": "Accept or Reject",
  "confidence": "high|medium|low",
  "synthesized_by": "octopus|claude-alone",
  "final_recommendation": "..."
}
JSON_EOF
```

## Review Standards

- Be **specific** — point to exact sections, figures, or claims
- Be **constructive** — every weakness should suggest a fix
- Be **fair** — consider the paper's intended scope and venue
- Be **calibrated** — use the few-shot examples as anchors
- For automated AI research papers, pay special attention to:
  - Whether experiments are run on real data (not synthetic)
  - Whether results are reproducible from the described methodology
  - Whether the paper correctly distinguishes what was automated vs. human-guided
