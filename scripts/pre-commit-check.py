# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Pre-commit validation for ai-scientist-skills.

Usage: uv run scripts/pre-commit-check.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

errors = []

# 1. Validate all SKILL.md files have valid frontmatter
for skill_md in Path("skills").rglob("SKILL.md"):
    text = skill_md.read_text()
    if not text.startswith("---"):
        errors.append(f"{skill_md}: missing frontmatter (must start with ---)")
        continue
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append(f"{skill_md}: malformed frontmatter (no closing ---)")
        continue
    fm = parts[1].strip()
    if "name:" not in fm:
        errors.append(f"{skill_md}: frontmatter missing 'name:' field")
    if "description:" not in fm:
        errors.append(f"{skill_md}: frontmatter missing 'description:' field")

# 2. Validate settings.json matches skill directories
settings_path = Path(".claude/settings.json")
if settings_path.exists():
    settings = json.loads(settings_path.read_text())
    for name, info in settings.get("skills", {}).items():
        skill_path = Path(info["path"])
        if not skill_path.exists():
            errors.append(f"settings.json: skill '{name}' points to missing {skill_path}")

# 3. Validate bfts_config.yaml parses
config_path = Path("templates/bfts_config.yaml")
if config_path.exists():
    import yaml
    try:
        cfg = yaml.safe_load(config_path.read_text())
        if not isinstance(cfg, dict):
            errors.append("bfts_config.yaml: does not parse to a dict")
    except yaml.YAMLError as e:
        errors.append(f"bfts_config.yaml: YAML parse error: {e}")

# 4. Check step numbering in SKILL.md files
for skill_md in Path("skills").rglob("SKILL.md"):
    text = skill_md.read_text()
    headers = re.findall(r"^### (\d+)\.", text, re.MULTILINE)
    if headers:
        nums = [int(h) for h in headers]
        for i in range(1, len(nums)):
            if nums[i] != nums[i-1] + 1:
                errors.append(f"{skill_md}: step numbering gap: {nums[i-1]} -> {nums[i]}")

# 5. Check marketplace.json lists all skills from settings.json
marketplace_path = Path(".claude-plugin/marketplace.json")
if marketplace_path.exists() and settings_path.exists():
    marketplace = json.loads(marketplace_path.read_text())
    mp_skills = set()
    for plugin in marketplace.get("plugins", []):
        for s in plugin.get("skills", []):
            mp_skills.add(Path(s).name)
    settings_skills = set()
    for name, info in settings.get("skills", {}).items():
        settings_skills.add(Path(info["path"]).parent.name)
    missing = settings_skills - mp_skills
    if missing:
        errors.append(f"marketplace.json missing skills: {missing}")

if errors:
    print(f"Pre-commit check found {len(errors)} issue(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("Pre-commit check passed.")
    sys.exit(0)
