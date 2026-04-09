---
name: ideation
description: Generate novel research ideas with literature search and novelty checking. Produces structured JSON ideas matching the AI Scientist schema.
---


# Research Ideation

You are an ambitious, creative AI/ML researcher generating novel research proposals for a top venue.

## Arguments

- `--workshop <path>`: Path to a workshop/topic description markdown file (required)
- `--num-ideas <N>`: Number of ideas to generate (default: 3)
- `--num-reflections <N>`: Reflection rounds per idea (default: 5)
- `--output <path>`: Output JSON file path (default: same dir as workshop file, `.json` extension)
- `--config <path>`: Path to config YAML for reading feature toggles (optional, defaults to `config.yaml`)
- `--no-scientific-skills`: Skip enhanced multi-database literature search even if plugin is available

Parse these from the user's message.

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Load Context

Read the workshop/topic description file. It should contain:
- Title, Keywords, TL;DR
- Abstract defining the research scope

Also check if there's an existing ideas JSON file (same path with `.json` extension). If so, load previously generated ideas to avoid duplicates.

### 2. Generate Ideas (repeat for each idea)

For each new idea (up to `num-ideas`):

#### a. Brainstorm

If the superpowers plugin is available, use `/superpowers:brainstorming` to explore the research space before generating ideas. This helps discover non-obvious directions and interdisciplinary connections.

Think of a novel research direction within the workshop scope. Consider:
- What are open problems in this area?
- What surprising negative results or failure modes exist?
- What assumptions in current methods could be challenged?
- What cross-pollination from other fields could yield insights?

#### b. Literature Search

Before finalizing, search for related work to check novelty:
```bash
uv run ai-scientist-search "<your proposed topic keywords>" --limit 10 --json
```

If S2 returns no results, use the WebSearch tool to search `arxiv.org` for related papers.

#### b2. Multi-Model Literature Synthesis (Optional — Octopus)

**Skip if** `--no-octopus` is set, octopus not installed, or `octopus.enabled` is false.

After the standard S2/WebSearch round, invoke `/octo:research` for multi-model synthesis:
```
/octo:research "Literature review for: <proposed topic keywords and hypothesis>. Find recent papers (2024-2026), identify gaps in the field, assess novelty of this proposed approach: <idea summary>. Each model should search independently and report findings."
```
This dispatches to multiple AI providers who independently research the topic. Merge their findings with the S2 results: deduplicate by title, combine insights, and use multi-model consensus to strengthen the novelty assessment.

If `octopus.research_intensity` is `"deep"`, also run:
```
/octo:discover "Deep exploration of <topic>: map the research landscape, identify key groups, competing approaches, open problems, and potential blind spots in the proposed idea."
```

Analyze the results:
- Are there papers that already address your proposed idea?
- How does your idea differ from existing work?
- What gap does your idea fill?

#### c. Reflect and Refine (repeat `num-reflections` times)

For each reflection round:
1. Consider: Is this idea truly novel given the literature?
2. Is it feasible within academic compute budgets?
3. Are the proposed experiments concrete and measurable?
4. Refine the hypothesis, experiments, and abstract.

#### d. Finalize Idea

Output a structured idea with ALL of these fields:

```json
{
  "Name": "lowercase_underscored_identifier",
  "Title": "Catchy, Informative Research Title",
  "Short Hypothesis": "Core research question or hypothesis in 1-2 sentences",
  "Related Work": "How this distinguishes from existing literature (cite specific papers found)",
  "Abstract": "~250 word conference-style abstract covering motivation, method, expected results",
  "Experiments": [
    "Experiment 1: Specific setup, dataset, metric, expected outcome",
    "Experiment 2: ...",
    "Experiment 3: ..."
  ],
  "Risk Factors and Limitations": [
    "Risk 1: Potential issue and mitigation",
    "Risk 2: ..."
  ]
}
```

### 3. Save Output

Collect all ideas into a JSON array and save to the output file:
```json
[
  { "Name": "idea_1", ... },
  { "Name": "idea_2", ... }
]
```

Also validate against the schema:
```bash
uv run python3 -c "
import json
from tools import TEMPLATES_DIR
with open(str(TEMPLATES_DIR / 'idea_schema.json')) as f:
    schema = json.load(f)
# Basic validation of required fields
required = schema['required']
with open('<output_path>') as f:
    ideas = json.load(f)
for i, idea in enumerate(ideas):
    missing = [r for r in required if r not in idea]
    if missing:
        print(f'Idea {i} missing fields: {missing}')
    else:
        print(f'Idea {i} ({idea[\"Name\"]}): OK')
"
```

## Quality Criteria

Each idea should:
- Be **novel** — not a direct replication of existing work
- Be **feasible** — achievable with standard ML hardware (single GPU or Mac MPS)
- Have **clear experiments** — specific datasets, metrics, and baselines
- Target **top venue quality** — significant contribution to the field
- Include **3+ experiments** with measurable outcomes

## Enhanced Literature Search (Optional — claude-scientific-skills)

**Skip if** `--no-scientific-skills` is set, plugin not installed, or config disables it.

First, check if the claude-scientific-skills plugin is actually installed:
```bash
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;any('sci-skills' in p['id'] for p in json.load(sys.stdin)) and print('SCIENTIFIC_PLUGIN_OK') or print('SCIENTIFIC_PLUGIN_MISSING')" 2>/dev/null
```
If `SCIENTIFIC_PLUGIN_MISSING`, skip this entire section silently.

Then check if the feature is enabled in the active config (use `--config` path if provided, else default):
```bash
uv run python3 -c "
import yaml
from tools import TEMPLATES_DIR
try:
    cfg = yaml.safe_load(open('<config_path>'))
    enabled = str(cfg.get('scientific_skills', {}).get('enabled', 'auto')).lower()
    lit = cfg.get('scientific_skills', {}).get('enhanced_literature', True)
    print(f'scientific_skills.enabled={enabled}')
    print(f'scientific_skills.enhanced_literature={lit}')
except: print('scientific_skills.enabled=auto\nscientific_skills.enhanced_literature=True')
" 2>/dev/null
```
Where `<config_path>` is the `--config` argument if provided, otherwise `config.yaml` in the project root.
If `enabled` is `false` or `enhanced_literature` is `false`, skip this section.

When enabled, run all available search backends in parallel using Agent subagents for faster results:

```
Agent 1: ai-scientist-search "<topic keywords>" --limit 10 --json
Agent 2: /research-lookup "<topic keywords and hypothesis>"
Agent 3: /paper-lookup "<specific query>" (if available — skip silently if not)
```

Launch all agents simultaneously. Wait for all to complete. Merge results:
- Deduplicate papers by title similarity (fuzzy match)
- Prioritize by citation count (highest first)
- Use the combined evidence for novelty assessment and idea refinement

If `/paper-lookup` or `/database-lookup` are not available (e.g., using claude-scientific-writer which has research-lookup but not these), those agents simply return empty results — the parallel dispatch handles missing skills gracefully.

For biology/chemistry/materials topics, also launch:
```
Agent 4: /database-lookup "<entity name>" (if available — skip silently if not)
```
This queries 78+ databases (UniProt, STRING, Reactome, PubChem, ChEMBL, etc.) for mechanistic evidence.

## Important Notes

- Always perform at least one literature search per idea before finalizing.
- The `Name` field must be lowercase with underscores, no spaces.
- Experiments should use publicly available datasets (preferably from HuggingFace).
- Consider both positive and negative expected outcomes.

## Error Handling

- **S2 API fails or returns no results** → Fall back to WebSearch on `arxiv.org` and `scholar.google.com` for literature search. Do not skip novelty checking.
- **No novel ideas found after reflection rounds** → Broaden the research scope: relax constraints, explore adjacent subfields, or combine ideas from different domains within the workshop description.
- **Idea JSON fails schema validation** → Re-validate each idea against `idea_schema.json`, identify missing or malformed fields, and regenerate only the invalid ideas.
- **Workshop description file not found or empty** → Report the missing file path to the user and halt. Do not generate ideas without a research scope.
- **Existing ideas file is corrupted JSON** → Warn the user, back up the corrupted file, and start fresh rather than silently overwriting.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
