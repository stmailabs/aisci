---
name: writeup
description: Generate a complete LaTeX research paper from experiment results — including citation gathering, figure descriptions, and iterative refinement.
---


# Paper Writeup

You are writing a complete research paper based on experiment results.

## Arguments

- `--exp-dir <path>`: Experiment directory (required)
- `--type <icbinb|icml>`: Paper template type — icbinb (4-page workshop) or icml (8-page, default: icbinb)
- `--cite-rounds <N>`: Number of citation gathering rounds (default: 5)
- `--reflections <N>`: Number of writeup reflection rounds (default: 3)
- `--no-scientific-skills`: Skip enhanced writing and citation verification even if plugin is available

Parse from the user's message.

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Load Experiment Context

Read the experiment artifacts:
```bash
# Idea description
cat <exp_dir>/idea.md

# Experiment state
uv run python3 -c "
import json
from tools.state_manager import load_experiment_state
state = load_experiment_state('<exp_dir>')
print(json.dumps(state, indent=2))
"
```

Read the best experiment code from the final completed stage. Read stage summaries and journal data for all stages to understand the full experimental narrative.

### 2. Setup LaTeX Directory

```bash
uv run ai-scientist-latex setup <exp_dir>/latex --type <icbinb|icml>
```

Create empty references file:
```bash
touch <exp_dir>/latex/references.bib
```

Copy figures into the LaTeX directory (template uses `\graphicspath{{./figures/}}`):
```bash
mkdir -p <exp_dir>/latex/figures
cp <exp_dir>/figures/*.png <exp_dir>/figures/*.pdf <exp_dir>/latex/figures/ 2>/dev/null || true
```

### 3. Gather Citations (up to cite-rounds iterations)

First, check search backend availability:
```bash
uv run ai-scientist-search check
```

If S2 API is unreachable or rate-limited, **use WebSearch exclusively** for all citation searches below. Do not waste rounds retrying a broken S2 backend.

For each round:

1. Identify sections with uncited claims (look for statements without `\cite{}`)
2. Formulate 2-3 targeted search queries for the needed citations
3. Search for papers — try S2 first, fall back to WebSearch immediately on failure:
   ```bash
   uv run ai-scientist-search "<citation query>" --limit 5 --json
   ```
   If this returns no results or exits with error, use **WebSearch** to search `arxiv.org`, `scholar.google.com`, or `semanticscholar.org` directly. Extract title, authors, year, venue from the search results.

4. For each relevant paper, add a BibTeX entry to `references.bib`:
   ```bash
   cat >> <exp_dir>/latex/references.bib << 'BIB_EOF'
   @article{authorYYYYkeyword,
     title={Paper Title},
     author={Author Names},
     journal={Venue},
     year={YYYY},
   }
   BIB_EOF
   ```

5. Update the paper text with `\cite{key}` for the added reference.

6. **Validate** — every `\cite{key}` must have a matching `references.bib` entry. No fabricated references.

**Stop early** when all major claims are cited (typically 10-20 for a workshop paper, 20-35 for a full paper). Do not force all rounds if citations are sufficient.

### 4. View and Describe Figures (VLM Review)

Use Claude's native vision capabilities to review each figure.

List all figures in `<exp_dir>/figures/`:
```bash
ls <exp_dir>/figures/*.png <exp_dir>/figures/*.pdf 2>/dev/null
```

View **each** figure using the Read tool. For each figure, analyze:
1. **Description**: What does the figure show? What data is represented?
2. **Quality**: Is the figure publication-ready? (axis labels, legends, resolution)
3. **Key Finding**: What is the main takeaway from this figure?
4. **Caption Draft**: Write a suggested figure caption (1-3 sentences)
5. **Redundancy Check**: Are any figures duplicates or near-duplicates? If so, select the best one and flag others for removal.
6. **Relevance**: Does this figure support a key claim in the paper? If not, consider moving to appendix or removing.

Build a figure description string that will be injected into the paper generation prompt. This ensures the LaTeX generator knows what each figure shows and can reference them accurately.

### 5. Generate LaTeX Paper

Write the complete paper content into `template.tex`. The paper structure should be:

#### For ICBINB (4-page):
1. **Title** — concise, informative
2. **Abstract** — adapted from the idea, updated with actual results
3. **Introduction** — motivation, problem, contributions (cite related work)
4. **Method** — technical description of the approach (from best experiment code)
5. **Experimental Setup** — datasets, baselines, hyperparameters, evaluation metrics
6. **Results** — key findings with figure references (`\ref{fig:...}`)
7. **Discussion** — interpretation, limitations, comparison to prior work
8. **Conclusion** — summary and future work
9. **References** — via `\bibliography{references}`

#### For ICML (8-page):
Same structure plus:
- **Related Work** — expanded section
- **Ablation Studies** — from Stage 4 results
- **Background** — formal problem setup
- Appendix with additional results

#### LaTeX Requirements:
- Replace the placeholder sections in `template.tex` between `%%%%%%%%%SECTION%%%%%%%%%` markers
- Use `\begin{figure}` with `\includegraphics{<filename>}` for plots (graphicspath handles the directory)
- Use `\cite{key}` for citations matching `references.bib` keys
- Use proper math notation (`\mathbb{R}`, `\mathcal{L}`, etc.)
- Ensure all figures are referenced in the text
- Keep within page limits (4 for icbinb, 8 for icml, excluding references)

### 5b. Fact-Check Each Section (Hallucination Prevention)

**Before compiling**, verify every section you just wrote. For each section of the paper, perform a structured fact-check pass. This catches hallucinations during writing, not after.

#### Claim Extraction

Read through the section and extract every factual claim into one of these categories:

| Category | Example | Verification source |
|----------|---------|-------------------|
| **Metric claim** | "achieves 92.3% accuracy" | Experiment journal: `uv run ai-scientist-state best-node <exp_dir> <stage>` |
| **Method detail** | "3-layer CNN with dropout 0.3" | Experiment code: `cat <exp_dir>/state/<stage>/best_solution_*.py` |
| **Hyperparameter** | "trained for 100 epochs at lr=3e-4" | Experiment logs: `cat <exp_dir>/logs/step_*_output.txt` |
| **Citation claim** | "Smith et al. showed X outperforms Y" | S2/CrossRef: `uv run ai-scientist-search "Smith <topic>" --json` or CrossRef MCP |
| **SOTA comparison** | "current SOTA is 91.2%" | Live search: use WebSearch or S2 to find actual current SOTA |
| **Figure reference** | "as shown in Figure 2, loss decreases" | Actual figure: Read the PNG with the Read tool and verify |
| **Dataset claim** | "evaluated on 50K training samples" | Experiment code/logs: check actual data loading |

#### Verification Process

For each extracted claim:

1. **Check against ground truth source** (see table above)
2. **Rate the claim**:
   - **Verified** — ground truth confirms the claim exactly
   - **Imprecise** — close but numbers don't match exactly → fix to match ground truth
   - **Unverifiable** — no ground truth available → either add a citation, hedge the language ("approximately", "we estimate"), or remove
   - **False** — contradicts ground truth → rewrite immediately
3. **Fix before proceeding** — do not move to the next section with unresolved false or imprecise claims

#### Octopus Cross-Check (Optional)

If Octopus is available and `octopus.claim_verification` is true, delegate an independent verification pass for the Methods and Results sections:

```
/octo:debate "Fact-check this paper section using ALL available AI providers. Each provider should independently verify claims against evidence. The paper claims: [paste section text]. The experiment code is at: <exp_dir>/state/<stage>/best_solution_*.py. The experiment logs are at: <exp_dir>/logs/. Check: (1) Do the reported metrics match actual metrics in the logs? (2) Does the methods description match the actual code? (3) Are hyperparameters accurately reported? Use the 75% consensus gate — flag claims where providers disagree."
```

If Octopus flags discrepancies, fix them before compiling.

#### Claim Log

Save the verification results for the review phase:
```bash
cat > <exp_dir>/claim_verification.json << 'JSON_EOF'
{
  "total_claims": <N>,
  "verified": <N>,
  "fixed": <N>,
  "unverifiable": <N>,
  "false_caught": <N>,
  "octopus_checked": true|false,
  "sections_checked": ["abstract", "introduction", "method", "results", "discussion"],
  "issues_found": [
    {"section": "results", "claim": "...", "status": "fixed", "detail": "metric was 0.891, not 0.921"}
  ]
}
JSON_EOF
```

### 6. Compile and Check

```bash
uv run ai-scientist-latex compile <exp_dir>/latex --main template.tex
```

Check for errors:
```bash
uv run ai-scientist-latex pages <exp_dir>/latex/template.pdf
```

If there are LaTeX errors, read the log file and fix them:
```bash
cat <exp_dir>/latex/template.log | grep -A 2 "^!" | head -20
```

### 7. Reflection Loop (up to N rounds)

For each reflection round:

1. Check the compiled PDF page count — ensure within limits
2. Run chktex for LaTeX warnings (if available)
3. **Re-run fact-check** on any sections you modified this round (same process as step 5b — extract claims, verify against ground truth, fix discrepancies)
4. Re-read the paper content critically:
   - Is the abstract accurate given the actual results?
   - Are all figures referenced and described?
   - Are all citations used in the text?
   - Is the writing clear and concise?
   - Are there any LaTeX errors or formatting issues?
   - **Do all numbers in the paper match the experiment journal?**
   - **Are there any hedged or vague claims that could be made specific?**
5. Make improvements and recompile

If everything looks good AND the claim verification log shows zero unresolved issues, declare "I am done" and exit the loop.

### 8. Finalize

Move the final PDF:
```bash
cp <exp_dir>/latex/template.pdf <exp_dir>/paper.pdf
```

Report:
- Paper path: `<exp_dir>/paper.pdf`
- Page count
- Number of citations
- Number of figures

## Enhanced Writing (Optional — claude-scientific-skills)

**Skip if** `--no-scientific-skills` is set, plugin not installed, or config disables it.

First, check if the claude-scientific-skills plugin is actually installed:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('sci-skills' in p['id'] for p in json.load(sys.stdin)) and print('SCIENTIFIC_PLUGIN_OK') or print('SCIENTIFIC_PLUGIN_MISSING')" 2>/dev/null
```
If `SCIENTIFIC_PLUGIN_MISSING`, skip this entire section silently.

Then check config:
```bash
uv run python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('<exp_dir>/config.yaml'))
    enabled = str(cfg.get('scientific_skills', {}).get('enabled', 'auto')).lower()
    writing = cfg.get('scientific_skills', {}).get('enhanced_writing', True)
    print(f'enabled={enabled} enhanced_writing={writing}')
except: print('enabled=auto enhanced_writing=True')
" 2>/dev/null
```
If `enabled` is `false` or `enhanced_writing` is `false`, skip this section.

When enabled, enhance the writing and citation process:

### Enhanced Citation Gathering (augments Step 3)

After the standard S2/WebSearch citation rounds, invoke citation management for validation:
```
/citation-management validate <exp_dir>/latex/references.bib
```
This verifies all DOIs via CrossRef, detects duplicates, checks for missing required fields, and reports broken references. Fix any issues before compiling.

For additional paper discovery beyond S2:
```
/paper-lookup "<query for missing citations>"
```
This searches 10 databases (PubMed, arXiv, bioRxiv, OpenAlex, Crossref, Semantic Scholar, CORE, Unpaywall) for papers that S2 may have missed.

### Enhanced Prose Quality (augments Step 5)

When generating the LaTeX paper content, apply `/scientific-writing` principles:

1. **Two-stage writing process**: First outline each section with bullet points (what to cover), then convert each outline into flowing academic prose. Never leave bullet points in the final paper.

2. **IMRAD structure**: Follow standard scientific manuscript structure:
   - **Introduction**: Motivation → gap → contribution → outline
   - **Methods**: Reproducible description of approach
   - **Results**: Data-driven presentation with figure references
   - **Discussion**: Interpretation → limitations → comparison → future work

3. **Reporting guidelines**: Where applicable, follow established standards:
   - Machine learning experiments: Report hyperparameters, random seeds, compute budget, dataset splits
   - Statistical claims: Include effect sizes, confidence intervals, not just p-values

### Enhanced Citation Verification (augments Step 7 reflection)

During each reflection round, also run citation verification:
```
/citation-management validate <exp_dir>/latex/references.bib
```
Ensure every `\cite{key}` resolves to a real paper with a valid DOI. Remove or replace any citations that fail validation.

## Writing Guidelines

- Write in formal academic style (third person, passive voice where appropriate)
- Be precise about experimental details — exact hyperparameters, dataset sizes, metrics
- Present negative results honestly — this is especially important for ICBINB
- Use consistent terminology throughout
- Every claim should be supported by experimental evidence or citations
- Avoid overclaiming — use "suggests" instead of "proves" for empirical results

## Error Handling

- **LaTeX compilation fails** → Read `template.log` for the specific error. Check for missing packages (`\usepackage` errors), fix undefined commands, and retry. If a specific section causes the failure, temporarily comment it out, compile the rest, then fix the problematic section separately.
- **BibTeX fails to process references** → Compile without bibliography as a fallback (`\bibliographystyle` and `\bibliography` commented out). Warn the user that citations will appear as `[?]` until BibTeX is fixed. Check `references.bib` for malformed entries.
- **Paper exceeds page limit** → Warn the user with the actual vs. allowed page count. Suggest sections that could be trimmed or moved to an appendix. Do not silently truncate content.
- **S2 search backend is unreachable** → Switch to WebSearch exclusively for all citation rounds. Do not waste rounds retrying a broken S2 backend.
- **Figures missing from LaTeX directory** → Re-copy from `<exp_dir>/figures/` to `<exp_dir>/latex/figures/`. If source figures do not exist, compile without them and warn the user which figures are missing.
- **Fabricated or unverifiable citation detected** → Remove the citation immediately. Never include a `\cite{}` key without a matching, real entry in `references.bib`.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
