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

Parse these from the user's message.

## Procedure

### 1. Load Context

Read the workshop/topic description file. It should contain:
- Title, Keywords, TL;DR
- Abstract defining the research scope

Also check if there's an existing ideas JSON file (same path with `.json` extension). If so, load previously generated ideas to avoid duplicates.

### 2. Generate Ideas (repeat for each idea)

For each new idea (up to `num-ideas`):

#### a. Brainstorm

Think of a novel research direction within the workshop scope. Consider:
- What are open problems in this area?
- What surprising negative results or failure modes exist?
- What assumptions in current methods could be challenged?
- What cross-pollination from other fields could yield insights?

#### b. Literature Search

Before finalizing, search for related work to check novelty:
```bash
python3 tools/search.py "<your proposed topic keywords>" --limit 10 --json
```

If S2 returns no results, use the WebSearch tool to search `arxiv.org` for related papers.

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
python3 -c "
import json
with open('templates/idea_schema.json') as f:
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

## Important Notes

- Always perform at least one literature search per idea before finalizing.
- The `Name` field must be lowercase with underscores, no spaces.
- Experiments should use publicly available datasets (preferably from HuggingFace).
- Consider both positive and negative expected outcomes.
