---
name: experiment-generate
description: Generate experiment code for a BFTS iteration. Produces Python code without executing it — pairs with experiment-execute for the full iteration.
---


# Experiment Code Generation

You generate Python experiment code for a single BFTS iteration. This skill produces code only — it does NOT execute it. Use `/ai-scientist:experiment-execute` to run the generated code.

## Arguments

Same as experiment-step: `--exp-dir`, `--stage`, `--parent-id`, `--action`, `--task-desc`, `--stage-goals`

## Procedure

### 0. Locate Plugin Root

```bash
```

### 1. Load Context

```bash
uv run ai-scientist-state journal-summary <exp_dir> <stage>
```

If parent node ID provided:
```bash
uv run ai-scientist-state node-info <exp_dir> <stage> <parent_id> --show-code
```

### 2. Detect Device

```bash
uv run ai-scientist-device --preamble
```

### 3. Generate Code

**Library docs lookup** (if context7 plugin available — skip silently if not): Before writing code, use context7 to look up documentation for the key libraries you'll use (e.g., PyTorch, datasets, transformers). This ensures you use current APIs and avoid deprecated patterns.

Based on action type (draft/debug/improve), generate the complete Python experiment script. Follow all code requirements from experiment-step (device preamble with SEED env var, metric printing as `metric_name: value`, figures/ directory, <60 min execution).

### 4. Write Code (do NOT execute)

```bash
cat > <exp_dir>/workspace/runfile.py << 'PYTHON_EOF'
<generated code>
PYTHON_EOF
mkdir -p <exp_dir>/workspace/figures
```

### 5. Check for Duplicates

```bash
uv run ai-scientist-state dedup-check <exp_dir> <stage> --code <exp_dir>/workspace/runfile.py
```

If duplicate found, report it and skip — no need to execute.

### 6. Report

Print the generated code path and a brief description of the approach. Do NOT execute the code.

## Error Handling

- **Code generation produces syntax errors** → Run `python3 -c "import ast; ast.parse(open('runfile.py').read())"` to detect syntax issues. If invalid, retry with a simpler approach: reduce complexity, remove advanced features, and regenerate.
- **Device detection fails** → Default to CPU (`device = torch.device("cpu")`). Log a warning but do not block code generation.
- **Parent node code is missing or unreadable** → Fall back to using the stage briefing and journal summary only. Generate code based on the stage goals without referencing prior code.
- **Duplicate check detects a match** → Report the duplicate node ID and skip. Do not write duplicate code to the workspace.
- **Journal or state files are corrupted** → Report the corruption to the user with the specific file path. Do not generate code against an inconsistent experiment state.

**Golden rule**: Never silently skip a failure. Either succeed clearly, fail loudly with a specific next step, or degrade gracefully with a fallback.
