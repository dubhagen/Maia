# Skills

Skills are reusable instruction sets that extend the agent's capabilities. Each skill is a `SKILL.md` file in its own directory, providing specialized knowledge, workflows, and tool integrations for specific tasks.

## Install Skills

Install a skill from a git URL or a local path you type, via chat (`/skill`) or the terminal (`maia skill`):

```bash
/skill install <owner>/<repo>           # From GitHub
/skill install <url>                    # From a git URL, zip, or SKILL.md
```

There is no skill marketplace. `clawhub:` and `linkai:` prefixes are rejected.

## Manage Skills

```bash
/skill list                  # List installed skills
/skill info <name>           # View skill details
/skill enable <name>         # Enable a skill
/skill disable <name>        # Disable a skill
/skill uninstall <name>      # Uninstall a skill
```

> In terminal, replace `/skill` with `maia skill`.

## Skill Structure

```
skills/
  my-skill/
    SKILL.md          # Required: skill definition
    scripts/          # Optional: bundled scripts
    resources/        # Optional: reference files
```

`SKILL.md` uses YAML frontmatter:

```markdown
---
name: my-skill
description: Brief description of what the skill does
metadata: {"maia":{"emoji":"🔧","requires":{"bins":["tool"],"env":["API_KEY"]}}}
---

# My Skill

Instructions, examples, and usage patterns...
```

### Frontmatter Fields

| Field | Description |
|---|---|
| `name` | Skill name (must match directory name) |
| `description` | Brief description (required) |
| `metadata.maia.emoji` | Display emoji |
| `metadata.maia.always` | Always include this skill (default: false) |
| `metadata.maia.requires.bins` | Required binaries |
| `metadata.maia.requires.env` | Required environment variables |
| `metadata.maia.requires.config` | Required config paths |
| `metadata.maia.os` | Supported OS (e.g., `["darwin", "linux"]`) |

## Skill Loading Order

Skills are loaded from two locations (higher precedence overrides lower):

1. **Builtin skills** (lower): `<project_root>/skills/` — shipped with the codebase
2. **Custom skills** (higher): `~/maia/skills/` — installed via `maia skill install` or skill creator

Skills with the same name in the custom directory override builtin ones.

## Create & Contribute

See [docs/skills/create.mdx](../docs/skills/create.mdx).
