#!/usr/bin/env bash
set -uo pipefail
# Note: NOT using set -e — we handle errors explicitly per step

# AI Scientist (aisci) — Install
# Usage: curl -fsSL https://raw.githubusercontent.com/stmailabs/aisci/main/scripts/install.sh | bash

REPO="https://github.com/stmailabs/aisci.git"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo "=== AI Scientist (aisci) — Install ==="
echo ""

# 1. Check prerequisites
for cmd in uv claude; do
    if ! command -v "$cmd" &>/dev/null; then
        fail "$cmd not found. Please install it first."
        exit 1
    fi
done

# 2. Create .venv and install Python tools
echo "[1/6] Python tools..."
if [ -d ".venv" ]; then
    warn ".venv exists — upgrading packages"
    uv pip install --upgrade "git+${REPO}" --quiet 2>&1 || {
        fail "Failed to upgrade packages. Check network and try again."
        exit 1
    }
else
    uv venv --quiet 2>&1 || {
        fail "Failed to create .venv. Check Python 3.11+ is available."
        exit 1
    }
    uv pip install "git+${REPO}" --quiet 2>&1 || {
        fail "Failed to install packages. Check network and try again."
        exit 1
    }
fi
ok "torch, numpy, matplotlib, seaborn, transformers, etc."

# 3. Add and update marketplaces
echo "[2/6] Marketplaces..."
for repo in stmailabs/aisci https://github.com/nyldn/claude-octopus K-Dense-AI/claude-scientific-skills; do
    claude plugin marketplace add "$repo" 2>/dev/null || true
done
for mkt in aisci nyldn-plugins claude-scientific-skills claude-plugins-official astral-sh claude-hud; do
    claude plugin marketplace update "$mkt" 2>/dev/null || true
done
ok "Marketplaces added and updated"

# 4. Install plugins at project scope
echo "[3/6] Plugins..."
core_plugins=(
    "ai-scientist@aisci"
    "octo@nyldn-plugins"
)
optional_plugins=(
    "scientific-skills@claude-scientific-skills"
)
extra_plugins=(
    "superpowers@claude-plugins-official"
    "context7@claude-plugins-official"
    "code-review@claude-plugins-official"
    "astral@astral-sh"
    "claude-hud@claude-hud"
)

core_ok=0
for plugin in "${core_plugins[@]}"; do
    # Force reinstall to ensure latest version from marketplace
    claude plugin uninstall "$plugin" --scope project 2>/dev/null || true
    if claude plugin install "$plugin" --scope project 2>/dev/null; then
        ok "$plugin"
        ((core_ok++))
    else
        fail "$plugin"
    fi
done

for plugin in "${optional_plugins[@]}"; do
    # Force reinstall optional core plugins too
    claude plugin uninstall "$plugin" --scope project 2>/dev/null || true
    if claude plugin install "$plugin" --scope project 2>/dev/null; then
        ok "$plugin"
    else
        warn "$plugin (optional, skipped)"
    fi
done

for plugin in "${extra_plugins[@]}"; do
    if claude plugin install "$plugin" --scope project 2>/dev/null; then
        ok "$plugin"
    else
        warn "$plugin (optional, skipped)"
    fi
done

if [ $core_ok -lt 2 ]; then
    warn "Some core plugins failed. Install manually:"
    echo "    claude plugin install ai-scientist@aisci --scope project"
    echo "    claude plugin install octo@nyldn-plugins --scope project"
fi

# 5. Choose compute backend
echo "[4/6] Compute backend..."
# Copy default config to project if not present
if [ ! -f config.yaml ]; then
    uv run ai-scientist-config --config templates/bfts_config.yaml > config.yaml 2>/dev/null
fi
current_backend=$(grep "backend:" config.yaml | head -1 | awk '{print $2}' | tr -d "'" | tr -d '"')

if [ -z "$current_backend" ] || [ "$current_backend" = "''" ] || [ "$current_backend" = '""' ]; then
    echo ""
    echo "  Where would you like to run experiments?"
    echo "    1) Local — use this machine"
    echo "    2) Modal.com — cloud GPUs (A100, H100, T4, etc.)"
    echo ""
    printf "  Choose [1/2] (default: 1): "
    choice=""
    read -r choice < /dev/tty 2>/dev/null || choice="1"
    case "$choice" in
        2|modal|Modal)
            # Install modal if not present
            if ! uv run modal --version &>/dev/null; then
                echo "  Installing modal..."
                uv pip install modal --quiet 2>&1 || {
                    fail "Failed to install modal package"
                    warn "Defaulting to local"
                    uv run ai-scientist-config --config config.yaml --set compute.backend=local --save >/dev/null 2>&1
                    ok "Local (modal install failed)"
                    choice="done"
                }
            fi

            if [ "$choice" != "done" ]; then
                # Authenticate
                if ! uv run modal profile current &>/dev/null; then
                    echo ""
                    echo "  Modal authentication required."
                    echo "  Get your token command at: https://modal.com/settings/tokens"
                    echo ""
                    echo "    1) Paste your 'modal token set' command"
                    echo "    2) Open browser (modal setup)"
                    echo "    3) Skip — I'll set it up later"
                    echo ""
                    printf "  Choose [1-3]: "
                    auth_choice=""
                    read -r auth_choice < /dev/tty 2>/dev/null || auth_choice="3"
                    case "$auth_choice" in
                        1)
                            echo ""
                            echo "  Paste the command from Modal (e.g., modal token set --token-id ak-xxx --token-secret as-xxx):"
                            printf "  > "
                            token_cmd=""
                            read -r token_cmd < /dev/tty 2>/dev/null || token_cmd=""
                            # Run the command directly
                            eval "uv run $token_cmd" 2>&1 || true
                            if uv run modal profile current &>/dev/null; then
                                ok "Modal authenticated"
                            else
                                warn "Auth may have failed — verify with: uv run modal profile current"
                            fi
                            ;;
                        2)
                            echo "  Running modal setup (opens browser)..."
                            uv run modal setup < /dev/tty || warn "modal setup failed"
                            ;;
                        *)
                            warn "Skipped auth — run 'uv run modal setup' before using Modal"
                            ;;
                    esac
                else
                    ok "Modal already authenticated"
                fi

                # Choose GPU
                echo ""
                echo "  Which GPU?"
                echo "    1) A100 (default)  2) H100  3) T4  4) L4"
                printf "  Choose [1-4] (default: 1): "
                gpu_choice=""
                read -r gpu_choice < /dev/tty 2>/dev/null || gpu_choice="1"
                case "$gpu_choice" in
                    2) gpu="H100" ;;
                    3) gpu="T4" ;;
                    4) gpu="L4" ;;
                    *) gpu="A100" ;;
                esac
                uv run ai-scientist-config --config config.yaml --set compute.backend=modal compute.modal.gpu="$gpu" --save >/dev/null 2>&1
                ok "Modal.com with $gpu GPU"
            fi
            ;;
        *)
            uv run ai-scientist-config --config config.yaml --set compute.backend=local --save >/dev/null 2>&1
            ok "Local"
            ;;
    esac
else
    ok "Already set: $current_backend"
fi

# 6. Verify installation
echo "[5/6] Verifying..."
if uv run ai-scientist-verify --quiet 2>/dev/null; then
    ok "Environment check passed"
else
    warn "Some checks failed — run 'uv run ai-scientist-verify' for details"
fi

# 7. Create/update CLAUDE.md
echo "[6/6] CLAUDE.md..."
cat > CLAUDE.md << 'CLAUDEMD'
# AI Scientist (aisci)

## Environment

This project uses `uv` with a `.venv` directory.

**CRITICAL RULES:**
1. **ALWAYS** prefix `ai-scientist-*` commands with `uv run`
2. **ALWAYS** use `--config config.yaml` (NOT `templates/bfts_config.yaml`) — the project config has the user's compute backend and settings
3. **Never** `cd` into the plugin cache directory

CLI commands:

```bash
uv run ai-scientist-verify
uv run ai-scientist-device --info
uv run ai-scientist-config --config config.yaml
uv run ai-scientist-state status <exp_dir>
uv run ai-scientist-search "query" --limit 10
uv run ai-scientist-metrics <file>
uv run ai-scientist-latex compile <dir>
uv run ai-scientist-pdf <file>
uv run ai-scientist-budget --config config.yaml
```

**Never** run `ai-scientist-*` commands without `uv run` — they are installed in `.venv/bin/` and won't be found otherwise.

**Never** `cd` into the plugin cache directory. Always run commands from this project directory.

## Skills

| Command | Description |
|---------|-------------|
| `/ai-scientist` | Full pipeline: ideation → experiment → plot → writeup → review |
| `/ai-scientist:ideation` | Generate research ideas with literature search |
| `/ai-scientist:experiment` | 4-stage BFTS experiment pipeline |
| `/ai-scientist:experiment-step` | Single BFTS iteration (internal) |
| `/ai-scientist:experiment-generate` | Code generation only (internal) |
| `/ai-scientist:experiment-execute` | Execution only (internal) |
| `/ai-scientist:plot` | Aggregate publication-quality figures |
| `/ai-scientist:writeup` | Generate LaTeX paper with citations |
| `/ai-scientist:review` | Structured peer review (single + panel + Octopus) |
| `/ai-scientist:lit-search` | Standalone literature search |
| `/ai-scientist:workshop` | Interactive workshop description creator |
| `/ai-scientist:octo-review` | Octopus multi-model panel paper review (optional) |

## Installed Plugins

### Core
- **ai-scientist** — Full research pipeline (ideation, experiment, writeup, review)
- **octopus** — Multi-model consensus review via claude-octopus (GPT-4o, Gemini, Claude panel)

### Optional
- **scientific-skills** — 134 scientific skills (databases, tools, analysis)

### Extras
- **superpowers** — Planning before BFTS stages, brainstorming during ideation
- **context7** — Library docs lookup before experiment code generation
- **code-review** — Code quality review between BFTS stages (complements Octopus ML review)
- **astral** — ruff lint + format on experiment code before execution
- **claude-hud** — Status line display

## Octopus Integration

When claude-octopus is installed and configured:
- Multi-model consensus review (GPT-4o, Gemini, Claude — 3+ models vote)
- Stage-gate code review between BFTS stages
- Panel paper review (3 independent model personas + synthesis)
- Code-methods alignment (verifies paper claims match experiment code)
- Rescue delegation for stuck experiments

Control via config:
```yaml
octopus:
  enabled: auto           # auto | true | false
  stage_gate_review: true
  panel_paper_review: true
  code_alignment: true
  rescue_on_stuck: true
  venue: auto             # auto | neurips | icml | iclr | workshop
```

## Scientific Skills Integration (Optional)

When claude-scientific-skills is installed:
- Multi-database literature search during ideation
- Enhanced scientific writing during writeup
- Publication-quality figure formatting
- Evidence quality assessment during review (GRADE framework)

Control via config:
```yaml
scientific_skills:
  enabled: auto               # auto | true | false
  enhanced_literature: true
  enhanced_writing: true
  enhanced_figures: true
  enhanced_review: true
```

## Review Pipeline

The paper review has 3 independent layers:
1. **Claude single reviewer** — NeurIPS-style review (always runs)
2. **Claude panel** — 3 personas (Empiricist, Theorist, Practitioner) + synthesis
3. **Octopus multi-model** — GPT-4o + Gemini + Claude consensus + code-methods alignment (optional)

Plus cross-review comparison that flags divergences >2 points.

## Install / Update

```bash
curl -fsSL https://raw.githubusercontent.com/stmailabs/aisci/main/scripts/install.sh | bash
```

## Run

```bash
claude '/ai-scientist --workshop examples/ideas/i_cant_believe_its_not_better.md'
claude '/ai-scientist'  # interactive — guides you through topic creation
```
CLAUDEMD
ok "CLAUDE.md created (always regenerated to stay current)"


echo ""
echo "=== Done ==="
echo ""
echo "  Verify: uv run ai-scientist-verify"
echo "  Run:    claude '/ai-scientist'"
