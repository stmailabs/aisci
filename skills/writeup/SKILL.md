---
name: writeup
description: Generate a complete LaTeX research paper from experiment results — including citation gathering, figure descriptions, and iterative refinement.
---


# Paper Writeup

You are writing a complete research paper based on experiment results.

## Arguments

- `--exp-dir <path>`: Experiment directory (required)
- `--type <icbinb|icml>`: Paper template type — icbinb (4-page workshop) or icml (8-page, default: icbinb)
- `--cite-rounds <N>`: Number of citation gathering rounds (default: 20)
- `--reflections <N>`: Number of writeup reflection rounds (default: 3)

Parse from the user's message.

## Procedure

### 1. Load Experiment Context

Read the experiment artifacts:
```bash
# Idea description
cat <exp_dir>/idea.md

# Experiment state
python3 -c "
import json, sys
sys.path.insert(0, '.')
from tools.state_manager import load_experiment_state
state = load_experiment_state('<exp_dir>')
print(json.dumps(state, indent=2))
"
```

Read the best experiment code from the final completed stage. Read stage summaries and journal data for all stages to understand the full experimental narrative.

### 2. Setup LaTeX Directory

```bash
python3 tools/latex_compiler.py setup <exp_dir>/latex --type <icbinb|icml>
```

Create empty references file:
```bash
touch <exp_dir>/latex/references.bib
```

Create figures symlink so LaTeX can find figures:
```bash
ln -sf ../../figures <exp_dir>/latex/figures 2>/dev/null || cp -r <exp_dir>/figures <exp_dir>/latex/figures
```

### 3. Gather Citations (up to cite-rounds iterations)

For each round:

1. Identify what citations are still needed based on the paper content so far
2. Search for relevant papers:
   ```bash
   python3 tools/search.py "<citation query>" --limit 5 --json
   ```
   If S2 is unavailable, use WebSearch to find papers on arxiv.org or scholar.google.com.

3. For each relevant paper found, extract or construct a BibTeX entry and append to `references.bib`:
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

4. Ensure no duplicate citation keys. Clean citation keys:
   - Lowercase, no accents, no special characters except `_:-@{},`

5. **Validate citations** — ensure no hallucinated references:
   - Every `\cite{key}` in the paper must have a matching entry in `references.bib`
   - Every BibTeX entry should come from a real search result (not fabricated)
   - Check for duplicate keys and merge if needed

Stop gathering when you have sufficient citations (typically 15-30 for a workshop paper, 30-50 for a full paper) or all rounds are exhausted.

**Citation Workflow Summary**:
```
For each round (1 to cite_rounds):
  1. Read current paper text
  2. Identify sections that need citations (claims without \cite{})
  3. For each uncited claim, formulate a search query
  4. Search via tools/search.py (S2 with bibtex) or WebSearch
  5. Select most relevant paper from results
  6. Extract/construct BibTeX entry
  7. Add to references.bib (skip if key already exists)
  8. Update paper text with \cite{key}
```

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
- Use `\begin{figure}` with `\includegraphics{figures/<filename>}` for plots
- Use `\cite{key}` for citations matching `references.bib` keys
- Use proper math notation (`\mathbb{R}`, `\mathcal{L}`, etc.)
- Ensure all figures are referenced in the text
- Keep within page limits (4 for icbinb, 8 for icml, excluding references)

### 6. Compile and Check

```bash
python3 tools/latex_compiler.py compile <exp_dir>/latex --main template.tex
```

Check for errors:
```bash
python3 tools/latex_compiler.py pages <exp_dir>/latex/template.pdf
```

If there are LaTeX errors, read the log file and fix them:
```bash
cat <exp_dir>/latex/template.log | grep -A 2 "^!" | head -20
```

### 7. Reflection Loop (up to N rounds)

For each reflection round:

1. Check the compiled PDF page count — ensure within limits
2. Run chktex for LaTeX warnings (if available)
3. Re-read the paper content critically:
   - Is the abstract accurate given the actual results?
   - Are all figures referenced and described?
   - Are all citations used in the text?
   - Is the writing clear and concise?
   - Are there any LaTeX errors or formatting issues?
4. Make improvements and recompile

If everything looks good, declare "I am done" and exit the loop.

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

## Writing Guidelines

- Write in formal academic style (third person, passive voice where appropriate)
- Be precise about experimental details — exact hyperparameters, dataset sizes, metrics
- Present negative results honestly — this is especially important for ICBINB
- Use consistent terminology throughout
- Every claim should be supported by experimental evidence or citations
- Avoid overclaiming — use "suggests" instead of "proves" for empirical results
