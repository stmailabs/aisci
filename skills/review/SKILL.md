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

Parse from the user's message.

## Procedure

### 1. Extract Paper Text

```bash
python tools/pdf_reader.py <pdf_path>
```

If the paper is long, also extract by sections:
```bash
python tools/pdf_reader.py <pdf_path> --sections
```

### 2. Load Review Examples

Read few-shot examples to calibrate your review standards:
```bash
cat templates/review_fewshot/attention.json
```

These show what good reviews look like — use them as a reference for depth and specificity, but do NOT copy their content.

### 3. Review the Paper Text

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

## Review Standards

- Be **specific** — point to exact sections, figures, or claims
- Be **constructive** — every weakness should suggest a fix
- Be **fair** — consider the paper's intended scope and venue
- Be **calibrated** — use the few-shot examples as anchors
- For automated AI research papers, pay special attention to:
  - Whether experiments are run on real data (not synthetic)
  - Whether results are reproducible from the described methodology
  - Whether the paper correctly distinguishes what was automated vs. human-guided
