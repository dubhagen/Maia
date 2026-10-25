# Skill Management

Skill management commands are used to install, query, and manage Maia skills. Use `/skill <subcommand>` in chat or `maia skill <subcommand>` in the terminal.

## list

List installed skills and their status.

**Chat**

```text
/skill list
```

**Terminal**

```bash
maia skill list
```

Example output:

```
📦 Installed skills (3/4)

✅ pptx
   Use this skill any time a .pptx file is involved…
   Source: github

✅ skill-creator
   Create, install, or update skills…
   Source: builtin

⏸️ image-vision (disabled)
   Image understanding and visual analysis
   Source: builtin
```

**List a registry** only when `skill_hub_url` is set. There is no default registry:

**Chat**

```text
/skill list --remote
```

**Terminal**

```bash
maia skill list --remote
```

**Options:**

| Option | Description | Default |
| --- | --- | --- |
| `--remote`, `-r` | List the registry at `skill_hub_url`, when set | No |
| `--page` | Page number for remote listing | 1 |

## search

Search the registry at `skill_hub_url`. With no URL set, this command does nothing.

**Chat**

```text
/skill search pptx
```

**Terminal**

```bash
maia skill search pptx
```

## install

Install skills from a git URL, a local path, or an archive URL. A bare name is sent to `skill_hub_url` only when you set that URL. There is no default registry.

**From GitHub:**

**Chat**

```text
# Install all skills in a repo (auto-discovers subdirectories with SKILL.md)
/skill install owner/repo

# Specify a subdirectory to install a single skill
/skill install https://github.com/owner/repo/tree/main/skills/one-skill

# Use # to specify a subdirectory
/skill install owner/repo#skills/one-skill
```

**Terminal**

```bash
# Install all skills in a repo (auto-discovers subdirectories with SKILL.md)
maia skill install owner/repo

# Specify a subdirectory to install a single skill
maia skill install https://github.com/owner/repo/tree/main/skills/one-skill

# Use # to specify a subdirectory
maia skill install owner/repo#skills/one-skill
```

Supports full GitHub URLs and `owner/repo` shorthand. For mono-repos (multiple skills in one repository), omitting the subdirectory auto-discovers and batch-installs all skills; specifying a subdirectory installs only that skill.

**From a URL you type:**

**Chat**

```text
/skill install https://github.com/owner/repo
/skill install https://example.com/path/to/SKILL.md
```

**Terminal**

```bash
maia skill install https://github.com/owner/repo
maia skill install https://example.com/path/to/SKILL.md
```

There is no bundled skill marketplace. `clawhub:` and `linkai:` prefixes are refused.

Supports installing from zip / tar.gz archive URLs — automatically extracts and discovers directories containing `SKILL.md`, with support for single or batch install. Also supports installing directly from a `SKILL.md` file URL, automatically parsing the skill name and description.

## uninstall

Uninstall an installed skill.

**Chat**

```text
/skill uninstall pptx
```

**Terminal**

```bash
maia skill uninstall pptx
```

> **Warning.** Uninstalling deletes all files in the skill directory. This action cannot be undone.

## enable / disable

Enable or disable a skill. Disabled skills will not be invoked by the Agent.

**Chat**

```text
/skill enable pptx
/skill disable pptx
```

**Terminal**

```bash
maia skill enable pptx
maia skill disable pptx
```

## info

View details of an installed skill, including a preview of its `SKILL.md`.

**Chat**

```text
/skill info pptx
```

**Terminal**

```bash
maia skill info pptx
```

## Skill Sources

Installed skills track their origin, viewable via `/skill list`:

| Source | Description |
| --- | --- |
| `builtin` | Built-in project skills |
| `maiahub` | Installed from the registry URL set in `skill_hub_url` |
| `github` | Installed directly from a GitHub URL |
| `url` | Installed from a SKILL.md or archive URL |
| `local` | Installed from a path on disk, or created locally |
