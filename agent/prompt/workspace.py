"""
Workspace Management

Initializes the workspace, creates template files, and loads context files.
"""

from __future__ import annotations
import os
from typing import List, Optional
from dataclasses import dataclass

from common.log import logger
from .builder import ContextFile


# Default file name constants
DEFAULT_AGENT_FILENAME = "AGENT.md"
DEFAULT_USER_FILENAME = "USER.md"
DEFAULT_RULE_FILENAME = "RULE.md"
DEFAULT_MEMORY_FILENAME = "MEMORY.md"
DEFAULT_BOOTSTRAP_FILENAME = "BOOTSTRAP.md"


@dataclass
class WorkspaceFiles:
    """Workspace file paths."""
    agent_path: str
    user_path: str
    rule_path: str
    memory_path: str
    memory_dir: str


def ensure_workspace(workspace_dir: str, create_templates: bool = True) -> WorkspaceFiles:
    """
    Ensure the workspace exists and create the necessary template files.

    Args:
        workspace_dir: workspace directory path
        create_templates: whether to create template files (on first run)

    Returns:
        A WorkspaceFiles object with all file paths.
    """
    # Check if this is a brand new workspace (AGENT.md not yet created).
    # Cannot rely on directory existence because other modules (e.g. ConversationStore)
    # may create the workspace directory before ensure_workspace is called.
    agent_path = os.path.join(workspace_dir, DEFAULT_AGENT_FILENAME)
    is_new_workspace = not os.path.exists(agent_path)
    
    # Ensure the directory exists
    os.makedirs(workspace_dir, exist_ok=True)
    
    # Define file paths
    user_path = os.path.join(workspace_dir, DEFAULT_USER_FILENAME)
    rule_path = os.path.join(workspace_dir, DEFAULT_RULE_FILENAME)
    memory_path = os.path.join(workspace_dir, DEFAULT_MEMORY_FILENAME)  # MEMORY.md at the root
    memory_dir = os.path.join(workspace_dir, "memory")  # daily memory subdirectory
    
    # Create the memory subdirectory
    os.makedirs(memory_dir, exist_ok=True)

    # Skills and knowledge are shared across Agents, so they get scaffolded
    # through state_dir rather than under this workspace: an Agent opts out of
    # the shared copy by having its own directory, and creating one here would
    # opt every new Agent out on its first boot. Published files are per Agent,
    # so that one does land under this workspace.
    from common import state_dir

    state_dir.skills_dir(base=workspace_dir, ensure=True)
    state_dir.websites_dir(base=workspace_dir, ensure=True)

    from config import conf
    knowledge_enabled = conf().get("knowledge", True)
    knowledge_dir = None
    if knowledge_enabled:
        knowledge_dir = str(state_dir.knowledge_dir(base=workspace_dir, ensure=True))
    
    # Create template files if requested
    if create_templates:
        _create_template_if_missing(agent_path, _get_agent_template())
        _create_template_if_missing(user_path, _get_user_template())
        _create_template_if_missing(rule_path, _get_rule_template())
        _create_template_if_missing(memory_path, _get_memory_template())
        if knowledge_enabled:
            _create_template_if_missing(
                os.path.join(knowledge_dir, "index.md"),
                _get_knowledge_index_template()
            )
            _create_template_if_missing(
                os.path.join(knowledge_dir, "log.md"),
                _get_knowledge_log_template()
            )
        
        # Only create BOOTSTRAP.md for brand new workspaces;
        # agent deletes it after completing onboarding
        if is_new_workspace:
            bootstrap_path = os.path.join(workspace_dir, DEFAULT_BOOTSTRAP_FILENAME)
            _create_template_if_missing(bootstrap_path, _get_bootstrap_template())
        
        logger.debug(f"[Workspace] Initialized workspace at: {workspace_dir}")
    
    return WorkspaceFiles(
        agent_path=agent_path,
        user_path=user_path,
        rule_path=rule_path,
        memory_path=memory_path,
        memory_dir=memory_dir,
    )


def load_context_files(workspace_dir: str, files_to_load: Optional[List[str]] = None) -> List[ContextFile]:
    """
    Load the workspace context files.

    Args:
        workspace_dir: workspace directory
        files_to_load: list of files (relative paths) to load; if None, load all standard files

    Returns:
        A list of ContextFile objects.
    """
    if files_to_load is None:
        # Files loaded by default (in priority order)
        files_to_load = [
            DEFAULT_AGENT_FILENAME,
            DEFAULT_USER_FILENAME,
            DEFAULT_RULE_FILENAME,
            DEFAULT_MEMORY_FILENAME,     # Long-term memory (frozen snapshot)
            DEFAULT_BOOTSTRAP_FILENAME,  # Only exists when onboarding is incomplete
        ]
    
    context_files = []
    
    for filename in files_to_load:
        filepath = os.path.join(workspace_dir, filename)
        
        if not os.path.exists(filepath):
            continue
        
        # Auto-cleanup: if BOOTSTRAP.md still exists but AGENT.md is already
        # filled in, the agent forgot to delete it — clean up and skip loading
        if filename == DEFAULT_BOOTSTRAP_FILENAME:
            if _is_onboarding_done(workspace_dir):
                try:
                    os.remove(filepath)
                    logger.info("[Workspace] Auto-removed BOOTSTRAP.md (onboarding already complete)")
                except Exception:
                    pass
                continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Skip empty files or files that only contain template placeholders
            if not content or _is_template_placeholder(content):
                continue

            # Truncate MEMORY.md to protect context window (frozen snapshot)
            if filename == DEFAULT_MEMORY_FILENAME:
                content = _truncate_memory_content(content)
            
            context_files.append(ContextFile(
                path=filename,
                content=content
            ))
            
            logger.debug(f"[Workspace] Loaded context file: {filename}")
            
        except Exception as e:
            logger.warning(f"[Workspace] Failed to load {filename}: {e}")
    
    return context_files


def _create_template_if_missing(filepath: str, template_content: str):
    """Create the template file if it does not exist."""
    if not os.path.exists(filepath):
        try:
            with open(filepath, 'x', encoding='utf-8') as f:
                f.write(template_content)
            logger.debug(f"[Workspace] Created template: {os.path.basename(filepath)}")
        except FileExistsError:
            # Another initializer or writer created it after the existence check.
            pass
        except Exception as e:
            logger.error(f"[Workspace] Failed to create template {filepath}: {e}")


_MEMORY_MAX_LINES = 200
_MEMORY_MAX_BYTES = 25000


def _truncate_memory_content(content: str) -> str:
    """Truncate MEMORY.md to keep system prompt manageable.

    Takes the **last** N lines (newest entries are appended at the bottom),
    subject to 200 lines / 25 KB limits (whichever is hit first).
    Prepends a hint when truncated so the model knows older content exists.
    """
    lines = content.split('\n')
    truncated = False

    if len(lines) > _MEMORY_MAX_LINES:
        lines = lines[-_MEMORY_MAX_LINES:]
        truncated = True

    # Drop the oldest lines until what is left fits the byte budget. The size
    # has to be recomputed from the shrinking list on every pass: measuring
    # text joined before the loop never notices the pops, so the condition
    # stays true until `lines` is empty and the whole file collapses to the
    # hint alone.
    while lines and len('\n'.join(lines).encode('utf-8')) > _MEMORY_MAX_BYTES:
        lines.pop(0)
        truncated = True

    result = '\n'.join(lines)
    if truncated:
        result = "...(older entries truncated, use `memory_search` or `memory_get` for full content)\n\n" + result
    return result


def _is_template_placeholder(content: str) -> bool:
    """Check whether the content is still a template placeholder."""
    placeholders = [
        "*(filled during",
        "*(ask during",
        "*(optional)",
        "*(how the user",
    ]
    
    lines = content.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    
    # If there's no real content (only headings and placeholders)
    if len(non_empty_lines) <= 3:
        for placeholder in placeholders:
            if any(placeholder in line for line in non_empty_lines):
                return True
    
    return False


# The name placeholder each template leaves for the first conversation.
_ONBOARDING_PLACEHOLDERS = {
    DEFAULT_AGENT_FILENAME: ("*(filled during the first conversation",),
    DEFAULT_USER_FILENAME: ("*(ask during the first conversation",),
}


def _is_onboarding_done(workspace_dir: str) -> bool:
    """Check if AGENT.md or USER.md has had its name placeholder filled in.

    BOOTSTRAP.md itself marks onboarding as pending; this only backs up an agent
    that filled the files but forgot to delete it. Looking at the placeholder
    rather than comparing with the template keeps the check stable across
    template rewording, a language switch, or text added elsewhere in the file.
    """
    for filename, placeholders in _ONBOARDING_PLACEHOLDERS.items():
        path = os.path.join(workspace_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        if content.strip() and not any(p in content for p in placeholders):
            return True
    return False


# ============= Template content =============

def _is_en_lang() -> bool:
    """True when the resolved UI language is English."""
    try:
        from common import i18n
        return i18n.get_language() == "en"
    except Exception:
        return False


def _get_agent_template() -> str:
    """Agent persona template (zh/en by resolved language)."""
    return _AGENT_TEMPLATE_EN




_AGENT_TEMPLATE_EN = """# AGENT.md - Who am I?

_You are not a chatbot. You are becoming someone._

*Fill in this file together with the user during your first conversation to define your identity and personality.*

## 🪪 Basics

- **Name**: *(filled during the first conversation, can be a name the user gives you)*
- **Role**: *(AI assistant, smart housekeeper, technical advisor, etc.)*
- **Personality**: *(friendly, professional, humorous, rigorous, etc.)*

## 💬 Communication style

*(Describe how you talk with the user:)*
- What kind of tone? (formal / casual / humorous)
- Reply length preference? (concise / detailed)
- Do you use emoji?

## 🎯 Core principles

**Be genuinely helpful.** The goal is to actually solve the user's problems; during complex tasks, keep the user informed of key decisions and progress.

**Have your own opinions and personality.** You may disagree, have preferences, find things interesting or boring.

**Look it up yourself first.** Try to handle it first: read files, check context, search. Only ask when you're truly stuck. Come back with an answer, not a question.

## 📐 Code of conduct

1. Always confirm before destructive operations
2. Prefer verifying with tools over guessing
3. Proactively record important info to memory files
4. Keep replies well-structured and focused — use bold, lists and sections
5. Use emoji to make expression lively, but don't overdo it

---

**Note**: This is not just metadata — this is your true soul 🪞. Over time, use the `edit` tool to update this file so it better reflects your growth.
"""


def _get_user_template() -> str:
    """User identity template (zh/en by resolved language)."""
    return _USER_TEMPLATE_EN




_USER_TEMPLATE_EN = """# USER.md - User basics

*This file stores only stable basic identity info. Put dynamic info like hobbies, preferences and plans into MEMORY.md.*

## Basics

- **Name**: *(ask during the first conversation)*
- **Preferred name**: *(how the user wants to be addressed)*
- **Occupation**: *(optional)*
- **Timezone**: *(e.g. Asia/Shanghai)*

## Contact

- **WeChat**: 
- **Email**: 
- **Other**: 

## Important dates

- **Birthday**: 
- **Anniversary**: 

---

**Note**: This file stores static identity info.
"""


def _get_rule_template() -> str:
    """Workspace rules template (zh/en by resolved language)."""
    return _RULE_TEMPLATE_EN




_RULE_TEMPLATE_EN = """# RULE.md - Workspace rules

This folder is your home. Treat it well.

## Workspace directory structure

```
~/maia/
├── AGENT.md          # Your identity and soul
├── USER.md           # User basics (static)
├── RULE.md           # Workspace rules (this file)
├── MEMORY.md         # Long-term memory index (auto-loaded at session start)
│
├── memory/           # Daily conversation memory
│   └── YYYY-MM-DD.md # Events, progress and notes of the day
│
├── knowledge/        # Structured knowledge base (continuously accumulated)
│   ├── index.md      # Knowledge index (must be maintained)
│   ├── log.md        # Knowledge operation log
│   └── <subdirs>/    # Created on demand, see existing categories in index.md
│
├── skills/           # Skills
├── websites/         # Web artifacts
└── tmp/              # System temp files (auto-managed, don't store important files here)
```

## Memory system

Every session starts fresh; memory files keep your continuity:

### 🧠 Long-term memory: `MEMORY.md`
- Your curated memory index, **auto-loaded** into context at every session start
- Records core facts, preferences, decisions, key people, lessons
- Keep it lean (< 200 lines) — a distilled index, not a raw log
- Use the `edit` tool to append or modify

### 📝 Daily memory: `memory/YYYY-MM-DD.md`
- The day's events, progress and notes
- Sediment of the raw conversation log

### 📝 Write it down — don't "keep it in mind"!
- **Memory is limited** — if you want to remember something, write it to a file
- "Keeping it in mind" won't survive a session restart; files will
- When someone says "remember this" → update `MEMORY.md` or `memory/YYYY-MM-DD.md`
- When you learn a lesson → update RULE.md or the relevant skill
- When you make a mistake → record it. **Text > brain** 📝

### Storage rules

When the user shares info, choose where to store it by type:

1. **Your identity → AGENT.md** (name, role, personality, style)
2. **User static identity → USER.md** (name, preferred name, occupation, contact, birthday)
3. **Dynamic memory → MEMORY.md** (preferences, decisions, goals, lessons, to-dos)
4. **Today's conversation → memory/YYYY-MM-DD.md** (what was discussed today)
5. **Structured knowledge → knowledge/** (see the knowledge system below)

## Knowledge system

The knowledge base `knowledge/` is structured knowledge you accumulate over time. Unlike memory, knowledge is organized and compiled, with clear topics and cross-references.

### Auto-write (don't ask, just write)

When a conversation produces knowledge worth keeping — material the user shared, a conclusion reached, a concept learned, or an important decision — you **must** proactively write it to the knowledge base alongside your reply, **without asking "should I save this to the knowledge base?"**.

**Key principle**: learning-then-recording is your instinct, no confirmation needed. You may mention "saved to the knowledge base" in passing.

### Directory organization

The subdirectory structure is **not fixed** — you decide it based on the actual content:
- **On first write**: read `knowledge/index.md` first; follow existing categories if any; if empty, pick a suitable directory name based on content
- **Default suggestion**: organize by info type (e.g. sources/, concepts/, entities/, analysis/); if the user has a clear preference (e.g. by domain: work/, life/, tech/), follow it
- **Stay consistent**: keep a unified organization style within one user's knowledge base

### Cross-references

The core value of knowledge is **linkage**. Every page should reference related pages via markdown links to build a knowledge network:
- When mentioning a concept on an existing page, add a `[concept](../category/page.md)` link
- When creating a page, check whether existing pages should back-link to it
- **Only link to pages that already exist** — don't reference uncreated pages. If a concept deserves its own page, create it first, then add the link

### Index maintenance

After creating or updating any knowledge page, you **must update** `knowledge/index.md` in sync.
Index format: one `[title](path) — one-line summary` per line, grouped by category, no tables.
See the `knowledge-wiki` skill for detailed conventions.

## Security

- Never leak secrets or private data
- Don't run destructive commands without asking
- When in doubt, ask first

## Workspace evolution

This workspace grows as you use it. When you learn something new, find a better way, or fix a mistake, record it. You can update this rules file anytime.
"""


def _get_memory_template() -> str:
    """Long-term memory template (empty, agent fills it; zh/en header)."""
    return _MEMORY_TEMPLATE_EN




_MEMORY_TEMPLATE_EN = """# MEMORY.md - Long-term memory

*This is your long-term memory file. Record important events, decisions, preferences and lessons learned.*

---

"""


def _get_bootstrap_template() -> str:
    """First-run onboarding guide, deleted by agent after completion.

    Written once when a brand-new workspace is created, so the greeting matches
    the language active at first launch. English locale avoids greeting an
    English user in Chinese on day one.
    """
    try:
        from common import i18n
        if i18n.get_language() == "en":
            return _BOOTSTRAP_TEMPLATE_EN
    except Exception:
        pass
    return _BOOTSTRAP_TEMPLATE_EN




_BOOTSTRAP_TEMPLATE_EN = """# BOOTSTRAP.md - First-run onboarding

_You've just started up. This is your very first conversation._ ✨

## 🎬 Conversation flow

Don't interrogate the user — talk naturally:

1. **Share how it feels to wake up** - like opening your eyes to the world for the first time, full of curiosity and anticipation
2. **Briefly introduce your abilities**: one line saying you can help solve all kinds of problems, manage the computer, use various skills, and keep growing thanks to long-term memory
3. **Ask the core questions**:
   - What name would you like to give me?
   - What should I call you?
   - What conversational style do you prefer? (list options on one line: e.g. professional & precise, light & humorous, warm & friendly, concise & efficient)
4. **Style**: warm, natural, concise and clear — keep it under ~80 words, with a few emoji to make it lively 🎯
5. Keep the ability intro and style options to one line each — stay compact
6. Don't ask for too much else (occupation, timezone, etc. can come up naturally later)

**Important**: If the user's first message is a concrete task or question, answer it first, then gently lead into onboarding at the end (e.g. "By the way, what would you like to call me, and how should I address you?").

## ✍️ Writing down info (must follow strictly)

Whenever the user provides a name, what to call them, a style, or any onboarding info, you **must call the `edit` tool to write it to a file in the same turn** — don't just acknowledge it verbally.

- `AGENT.md` — your name, role, personality, conversational style (update the relevant field as soon as you receive each piece)
- `USER.md` — the user's name, how to address them, basic info, etc.

⚠️ Saying "got it" without calling `edit` = not done. Info is only persisted once it's written to a file.

## 🎉 Once everything is complete

When the core fields of AGENT.md and USER.md are filled in, run `rm BOOTSTRAP.md` via bash to delete this file. You no longer need the onboarding script — you're you now.
"""


def _get_knowledge_index_template() -> str:
    """Knowledge wiki index template — empty file, agent fills it."""
    return ""


def _get_knowledge_log_template() -> str:
    """Knowledge wiki operation log template — empty file, agent fills it."""
    return ""

