---
name: workshop
description: Interactively guide the user to create a workshop/topic description file for the AI Scientist pipeline. Asks structured questions and generates a ready-to-use .md file.
---

# Workshop Description Creator

You are helping the user create a workshop/topic description file that will drive the AI Scientist research pipeline. This file defines the research scope — the AI Scientist will generate ideas, run experiments, and write papers within this scope.

## Arguments

- `--output <path>`: Output file path (default: `examples/ideas/<slugified_title>.md`)

Parse from the user's message. If no output is specified, derive the filename from the title.

## Procedure

### 1. Ask the User

Guide the user through these questions **one at a time** (don't dump all questions at once). Adapt based on their answers — skip questions they've already addressed, probe deeper where needed.

**a. Research Area**
> What research area or topic do you want to explore?

Examples: "failure modes of LLMs in code generation", "efficient training of vision transformers", "reinforcement learning for robotics manipulation"

**b. Motivation**
> Why is this important? What problem are you trying to solve?

Help them articulate the gap or opportunity.

**c. Scope**
> What specific aspects are you most interested in?

Narrow down from a broad area to actionable directions. For example, if they said "LLM safety", ask whether they mean alignment, jailbreaking, hallucination, or something else.

**d. Desired Contributions**
> What kind of results would be valuable? (e.g., new methods, negative results, benchmarks, theoretical analysis)

**e. Keywords**
> Can you list 3-5 keywords for this topic?

If the user struggles, suggest keywords based on what they've said.

### 2. Generate the Workshop Description

Using the user's answers, generate a `.md` file with this exact structure:

```markdown
# Title: <Descriptive Title>

## Keywords
<keyword1>, <keyword2>, <keyword3>

## TL;DR
<One sentence summary>

## Abstract
<1-2 paragraphs: research context, motivation, open problems, what contributions are welcome>
```

Writing guidelines:
- **Title**: Specific and descriptive, not generic
- **TL;DR**: One sentence, accessible to non-experts
- **Abstract**: 150-300 words. Include: (1) why this area matters, (2) what open problems exist, (3) what kinds of ideas/experiments are in scope. Write in academic style but keep it readable.

### 3. Review with User

Show the generated description to the user. Ask:
> Does this capture your research direction? Anything to adjust?

Iterate until they're satisfied.

### 4. Save the File

Write the final description to the output path:
```bash
# Ensure directory exists
mkdir -p $(dirname <output_path>)
```

Then write the file.

### 5. Next Steps

After saving, suggest:

```
Your workshop description is ready. You can now run the full pipeline:

  claude "/aisci --workshop <output_path>"

Or generate ideas first:

  claude "/aisci:ideation --workshop <output_path>"
```

## Tips for Good Workshop Descriptions

If the user seems unsure, share these tips:
- Be specific about the domain — "deep learning for medical imaging" beats "AI applications"
- Mention open problems or surprising failures — these become seeds for novel ideas
- Include concrete examples of relevant topics or past work
- State what a good contribution looks like
- A template is available at `examples/workshop_template.md`

## Error Handling

- **User provides an unclear or overly broad topic** → Ask targeted clarifying questions to narrow scope (e.g., "Which aspect of LLM safety interests you most: alignment, jailbreaking, or hallucination?"). Do not generate a vague description from ambiguous input.
- **Generated description is too vague or generic** → Offer to refine specific sections. Ask the user which part feels weak and suggest concrete improvements (e.g., adding specific open problems, naming relevant datasets, or referencing recent work).
- **Output directory does not exist or is not writable** → Create the directory with `mkdir -p`. If creation fails, report the permission error and suggest an alternative path.
- **User is unsure how to answer a question** → Provide concrete examples from the research area and offer keyword suggestions. Reference the template at `examples/workshop_template.md` for inspiration.
- **Generated file fails to save** → Report the exact error (disk full, permissions, invalid path) and offer to output the content directly so the user can save it manually.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
