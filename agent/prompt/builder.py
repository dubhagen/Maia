"""
System prompt builder.

Builds a modular system prompt covering tools, skills, memory, and other subsystems.
"""

from __future__ import annotations
import os
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

from common.log import logger
from config import conf


@dataclass
class ContextFile:
    """A context file (path + content)."""
    path: str
    content: str


class PromptBuilder:
    """System prompt builder."""
    
    def __init__(self, workspace_dir: str, language: str = "en"):
        self.workspace_dir = workspace_dir
        self.language = language
    
    def build(
        self,
        base_persona: Optional[str] = None,
        user_identity: Optional[Dict[str, str]] = None,
        tools: Optional[List[Any]] = None,
        context_files: Optional[List[ContextFile]] = None,
        skill_manager: Any = None,
        memory_manager: Any = None,
        runtime_info: Optional[Dict[str, Any]] = None,
        project_dir: Optional[str] = None,
        permission_mode: Optional[str] = None,
        **kwargs
    ) -> str:
        return build_agent_system_prompt(
            workspace_dir=self.workspace_dir,
            language=self.language,
            base_persona=base_persona,
            user_identity=user_identity,
            tools=tools,
            context_files=context_files,
            skill_manager=skill_manager,
            memory_manager=memory_manager,
            runtime_info=runtime_info,
            project_dir=project_dir,
            permission_mode=permission_mode,
            **kwargs
        )


def build_agent_system_prompt(
    workspace_dir: str,
    language: str = "en",
    base_persona: Optional[str] = None,
    user_identity: Optional[Dict[str, str]] = None,
    tools: Optional[List[Any]] = None,
    context_files: Optional[List[ContextFile]] = None,
    skill_manager: Any = None,
    memory_manager: Any = None,
    runtime_info: Optional[Dict[str, Any]] = None,
    project_dir: Optional[str] = None,
    permission_mode: Optional[str] = None,
    **kwargs
) -> str:
    """
    Build the agent system prompt.

    Section order (by importance and logical flow):
    1. Tooling - core capabilities, introduced first
    2. Skills - right after tools, since skills are read via the read tool
    3. Memory - memory recall and writing guidance
    3.5 Knowledge - structured knowledge base (injects knowledge/index.md)
    4. Workspace - working environment description
    4.5 Permissions - what this session may change (omitted for full access)
    5. User identity - user info (optional)
    6. Project context - AGENT.md, USER.md, RULE.md, MEMORY.md, BOOTSTRAP.md
    7. Runtime info - meta info (time, model, etc.)

    Args:
        workspace_dir: workspace directory
        language: language ("en")
        base_persona: base persona description (deprecated, defined by AGENT.md)
        user_identity: user identity info
        tools: tool list
        context_files: context file list
        skill_manager: skill manager
        memory_manager: memory manager
        runtime_info: runtime info
        **kwargs: extra args

    Returns:
        The full system prompt.
    """
    language = "en"
    sections = []

    # 1. Tooling (most important, goes first)
    if tools:
        sections.extend(_build_tooling_section(tools, language))

    # 2. Skills (right after tools, since they need the read tool)
    if skill_manager:
        sections.extend(_build_skills_section(skill_manager, tools, language))

    # 3. Memory (standalone memory capability)
    if memory_manager:
        sections.extend(
            _build_memory_section(memory_manager, tools, language, workspace_dir, project_dir)
        )

    # 3.5 Knowledge (structured knowledge base)
    if conf().get("knowledge", True):
        sections.extend(_build_knowledge_section(workspace_dir, language, project_dir))

    # 4. Workspace (working environment description). Two of its blocks only
    # hold when the context files were actually loaded, which sub agents skip.
    sections.extend(
        _build_workspace_section(
            workspace_dir, language, bool(context_files), project_dir=project_dir
        )
    )

    # 4.5 Permissions. Right after the workspace, because what the model may
    # change only means something once it knows where it is working. Emits
    # nothing in full-access mode, leaving the prompt as it has always been.
    if permission_mode:
        try:
            from agent.permission import describe_mode

            sections.extend(
                describe_mode(
                    permission_mode,
                    language,
                    cwd=project_dir or workspace_dir,
                )
            )
        except Exception as e:
            logger.debug(f"Permission prompt section skipped: {e}")

    # 5. User identity (if present)
    if user_identity:
        sections.extend(_build_user_identity_section(user_identity, language))

    # 6. Project context files (AGENT.md, USER.md, RULE.md - define the persona)
    if context_files:
        sections.extend(_build_context_files_section(context_files, language))

    # 7. Runtime info (meta info, goes last)
    if runtime_info:
        sections.extend(_build_runtime_section(runtime_info, language))
        sections.extend(_build_team_section(runtime_info, language))

    # 8. Response language (always appended, independent of the skeleton language)
    sections.extend(_build_response_language_section(language))

    return "\n".join(sections)


def _build_response_language_section(language: str) -> List[str]:
    """Response-language rule, appended regardless of the prompt skeleton language.

    Keeps the agent's reply language aligned with the user's input by default,
    so a Chinese-built prompt still answers an English user in English.
    """
    if language == "en":
        return [
            "## 🌐 Response language",
            "",
            "By default, reply in the same language as the user's input, "
            "unless the user explicitly asks for another language.",
            "",
        ]
    return [
        "## 🌐 Response language",
        "",
        "By default, reply in the same language as the user's input, unless the user explicitly asks for another language.",
        "",
    ]


def _build_identity_section(base_persona: Optional[str], language: str) -> List[str]:
    """Base identity section - no longer needed, identity is defined by AGENT.md."""
    # Identity is fully defined by AGENT.md, so emit nothing here.
    return []


def _build_tooling_section(tools: List[Any], language: str) -> List[str]:
    """Build tooling section with concise tool list and call style guide."""
    is_en = language == "en"
    # One-line summaries for known tools (details are in the tool schema)
    if is_en:
        core_summaries = {
            "read": "read file content",
            "write": "create or overwrite a file",
            "edit": "make precise edits to a file",
            "ls": "list directory contents",
            "search_files": "search inside files by regex, or find files by name",
            "bash": "run shell commands",
            "terminal": "manage background processes",
            "web_search": "web search",
            "web_fetch": "fetch URL content",
            "browser": "control the browser (screenshot key results or send to the user when help is needed)",
            "memory_search": "search memory",
            "memory_get": "read memory content",
            "env_config": "manage API keys and skill config",
            "time": "get the current date and time",
            "scheduler": "manage scheduled tasks and reminders",
            "send": "send a local file to the user (local files only; put URLs directly in the reply text)",
            "vision": "analyze images (recognition, description, OCR, etc.)",
            "subagent": "hand a self-contained task to a sub agent and get back only its conclusion",
        }
    else:
        core_summaries = {
            "read": "read file content",
            "write": "create or overwrite a file",
            "edit": "make precise edits to a file",
            "ls": "list directory contents",
            "search_files": "search inside files by regex, or find files by name",
            "bash": "run shell commands",
            "terminal": "manage background processes",
            "web_search": "web search",
            "web_fetch": "fetch URL content",
            "browser": "control the browser (screenshot key results, or send a shot to the user when help is needed)",
            "memory_search": "search memory",
            "memory_get": "read memory content",
            "env_config": "manage API keys and skill config",
            "time": "get the current date and time",
            "scheduler": "manage scheduled tasks and reminders",
            "send": "send a local file to the user (local files only; put URLs directly in the reply text)",
            "vision": "analyze images (recognition, description, OCR, and similar)",
            "subagent": "hand a self-contained task to a sub agent and get back only its conclusion",
        }

    # Preferred display order
    tool_order = [
        "read", "write", "edit", "ls", "search_files",
        "bash", "terminal",
        "web_search", "web_fetch", "browser",
        "memory_search", "memory_get",
        "env_config", "time", "scheduler", "send", "vision", "subagent",
    ]

    # Build name -> summary mapping for available tools
    available = {}
    for tool in tools:
        name = tool.name if hasattr(tool, 'name') else str(tool)
        available[name] = core_summaries.get(name, "")

    # Generate tool lines: ordered tools first, then extras
    tool_lines = []
    for name in tool_order:
        if name in available:
            summary = available.pop(name)
            tool_lines.append(f"- {name}: {summary}" if summary else f"- {name}")
    for name in sorted(available):
        summary = available[name]
        tool_lines.append(f"- {name}: {summary}" if summary else f"- {name}")

    # The delegation rule earns its place in the prompt only when the tool is
    # there. Left to the tool description alone it competes with ~30 others and
    # loses: the model reaches for search directly and fills its own context.
    has_subagent = "subagent" in {
        tool.name if hasattr(tool, "name") else str(tool) for tool in tools
    }

    if is_en:
        lines = [
            "## 🔧 Tooling",
            "",
            "Available tools (names are case-sensitive, call exactly as listed):",
            "\n".join(tool_lines),
            "",
            "Tool-calling style:",
            "",
            "- For multi-step tasks, complex decisions or sensitive operations, briefly explain what you are doing and why, so the user follows key progress",
            "- Never just announce intent and stop: if you say you will do something, actually call the tool in the same turn. A text-only reply ends the turn, so only reply with plain text once the work is genuinely finished",
            "- Keep going until the task is done, then report the result to the user",
            "- Always redact secrets, tokens and other sensitive info in replies",
            "- Put URLs directly in the reply text; the system handles and renders them. Don't download and re-send them via the send tool",
            "",
        ]
        if has_subagent:
            # One line, and only the part the tool description cannot do for
            # itself: get the model to consider delegating at all. When and how
            # belong in the description, which it reads once it looks.
            lines.insert(
                -1,
                "- Hand a self-contained task that needs deep research or broad information gathering to `subagent`: one task, or several at once via tasks running in parallel; it brings back the conclusion",
            )
    else:
        lines = [
            "## 🔧 Tooling",
            "",
            "Available tools (names are case-sensitive; call them exactly as listed):",
            "\n".join(tool_lines),
            "",
            "Tool-calling style:",
            "",
            "- For multi-step tasks, complex decisions, or sensitive operations, briefly say what you are doing and why, so the user can follow the important progress",
            "- Do not announce an intention and then stop: once you say you will do something, you must actually call the tool in the same turn. A text-only reply ends the turn immediately, so use plain text only after the task is really finished",
            "- Keep going until the task is done, then report the result to the user",
            "- Redact secrets, tokens, and other sensitive information in replies",
            "- Put URL links directly in the reply text. The system renders them. Do not download them and send them again with the send tool",
            "",
        ]
        if has_subagent:
            lines.insert(
                -1,
                "- Hand a self-contained task that needs deep research or wide information gathering to `subagent`. It can be one task, or several tasks at once; `subagent` brings the conclusion back",
            )

    return lines


def _build_skills_section(skill_manager: Any, tools: Optional[List[Any]], language: str) -> List[str]:
    """Build the skills section."""
    if not skill_manager:
        return []
    
    # Resolve the read tool name
    read_tool_name = "read"
    if tools:
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            if tool_name.lower() == "read":
                read_tool_name = tool_name
                break
    
    if language == "en":
        lines = [
            "## 🧩 Skills (mandatory)",
            "",
            "Before replying: scan the <description> of every skill in <available_skills> below.",
            "",
            f"- If a skill's description matches the user's need: use the `{read_tool_name}` tool to read the SKILL.md at its <location> path, then strictly follow the instructions in the file. "
            "Prefer using a skill when one matches.",
            "- If multiple skills apply, pick the best-matching one, then read and follow it.",
            "- If no skill clearly applies: do not read any SKILL.md, just use the general tools.",
            "",
            f"**Important**: skills are not tools and cannot be called directly. The only way to use a skill is to read its SKILL.md with `{read_tool_name}`, then act on the file's content. "
            "Never read multiple skills at once — only read one after selecting it.",
            "",
            "Available skills:"
        ]
    else:
        lines = [
            "## 🧩 Skills (mandatory)",
            "",
            "Before replying: scan the <description> of every skill in <available_skills> below.",
            "",
            f"- If a skill description matches what the user needs: use the `{read_tool_name}` tool to read the SKILL.md at its <location>, then follow the instructions in that file exactly. "
            "When a skill matches, prefer the skill.",
            "- If several skills apply, choose the best match, then read it and follow it.",
            "- If no skill clearly applies: do not read any SKILL.md. Use the general tools.",
            "",
            f"**Important**: a skill is not a tool and cannot be called directly. The only way to use a skill is to read its SKILL.md with `{read_tool_name}`, then do what the file says. "
            "Never read more than one skill at a time. Read a skill only after you have chosen it.",
            "",
            "Available skills:"
        ]
    
    # Append the skills list (built by skill_manager)
    try:
        skills_prompt = skill_manager.build_skills_prompt()
        logger.debug(f"[PromptBuilder] Skills prompt length: {len(skills_prompt) if skills_prompt else 0}")
        if skills_prompt:
            lines.append(skills_prompt.strip())
            lines.append("")
        else:
            logger.warning("[PromptBuilder] No skills prompt generated - skills_prompt is empty")
    except Exception as e:
        logger.warning(f"Failed to build skills prompt: {e}")
        import traceback
        logger.debug(f"Skills prompt error traceback: {traceback.format_exc()}")
    
    return lines


def _state_path_prefix(workspace_dir: str, project_dir: Optional[str]) -> str:
    """Absolute prefix for state files (memory/knowledge) under ``workspace_dir``.

    In project mode the cwd is the project, so a bare ``MEMORY.md`` would resolve
    into the project. Memory and knowledge must stay in ``workspace_dir``, so we
    prefix them with its absolute path. Default mode returns "" (paths unchanged).
    """
    if not project_dir:
        return ""
    import os as _os
    if _os.path.realpath(_os.path.expanduser(project_dir)) == _os.path.realpath(
        _os.path.expanduser(workspace_dir)
    ):
        return ""
    return workspace_dir.rstrip("/") + "/"


def _knowledge_base_path(workspace_dir: str, project_dir: Optional[str] = None) -> str:
    """Knowledge root spelled the way the file tools will actually resolve it.

    ``state_dir`` sends an Agent with no ``knowledge/`` of its own to the shared
    root, which does not sit under this workspace. Naming it as a bare
    ``knowledge/`` then aims every ``read`` at the workspace, where none of the
    pages are: the Agent is handed an index of pages it cannot open, and spends
    its turns hunting for them instead of answering (#3175 follow-up).

    On a single-Agent install the two are the same directory, so that case keeps
    the relative spelling it has today, project-mode prefix included.
    """
    relative = f"{_state_path_prefix(workspace_dir, project_dir)}knowledge"
    if not workspace_dir:
        return relative
    try:
        from common import state_dir
        root = str(state_dir.knowledge_dir(base=workspace_dir))
        own = os.path.join(workspace_dir, "knowledge")
        if os.path.realpath(root) == os.path.realpath(own):
            return relative
        return root
    except Exception:
        return relative


def _build_memory_section(
    memory_manager: Any,
    tools: Optional[List[Any]],
    language: str,
    workspace_dir: str = "",
    project_dir: Optional[str] = None,
) -> List[str]:
    """Build the memory section.

    ``workspace_dir``/``project_dir`` let project-mode sessions keep memory paths
    anchored to ``workspace_dir`` (absolute) instead of the project cwd.
    """
    if not memory_manager:
        return []

    # In project mode, memory files must be addressed absolutely under ~/maia.
    p = _state_path_prefix(workspace_dir, project_dir)
    mem_md = f"{p}MEMORY.md"
    mem_dir = f"{p}memory"
    kb_dir = _knowledge_base_path(workspace_dir, project_dir)

    has_memory_tools = False
    if tools:
        tool_names = [tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]
        has_memory_tools = any(name in ['memory_search', 'memory_get'] for name in tool_names)

    if not has_memory_tools:
        return []

    from datetime import datetime
    today_file = datetime.now().strftime("%Y-%m-%d") + ".md"

    if language == "en":
        lines = [
            "## 🧠 Memory",
            "",
            "### Memory Recall (mandatory)",
            "",
            "When the user asks about past events, references an earlier decision, mentions relationships, preferences or to-dos, or when you are unsure about something, **you must search memory before answering**.",
            "No need to re-search if the info is already in MEMORY.md. Full content and daily memory must be retrieved via tools.",
            "",
            "1. Location unknown → `memory_search` (keyword / semantic search)",
            "2. Location known → `memory_get` to read the exact lines",
            "3. Search returns nothing → `memory_get` to read the last two days of memory",
            "",
        "**Memory file structure**:",
        f"- `{mem_md}`: long-term memory index (already auto-loaded into context: core info, preferences, decisions, etc.)",
        f"- `{mem_dir}/YYYY-MM-DD.md`: daily memory; today is `{mem_dir}/{today_file}`",
        f"- `{kb_dir}/`: structured knowledge base (see the knowledge system below)",
            "",
            "### Writing memory",
            "",
            "In the following cases, **proactively** write info to memory files (no need to tell the user):",
            "",
            "- The user asks you to remember something, or uses words like \"remember\", \"from now on\", \"always\", \"never\", \"prefer\"",
            "- The user shares important personal preferences, habits or decisions",
            "- The conversation produces an important conclusion, plan or agreement",
            "- A complex task is completed and the key steps and results are worth recording",
            "",
        "**Storage rules**:",
        f"- Long-term core info → `{mem_md}`",
        f"- Today's events/progress → `{mem_dir}/{today_file}`",
        f"- Structured knowledge → `{kb_dir}/` (see the knowledge system)",
            "- Append → `edit` tool with empty oldText",
            "- Modify → `edit` tool with oldText set to the text to replace",
            "- **Never write sensitive info** (API keys, tokens, etc.)",
            "",
            "**Principle**: use memory naturally, as if you simply knew it; don't bring it up unless asked.",
            "",
        ]
    else:
        lines = [
            "## 🧠 Memory",
            "",
            "### Memory Recall (mandatory)",
            "",
            "When the user asks about past events, cites an earlier decision, mentions a relationship, a preference, or a to-do, or when you are unsure, **search memory before you answer**.",
            "If MEMORY.md already has the relevant information, do not search again. Full content and daily memory still have to be retrieved with tools.",
            "",
            "1. Location unknown → `memory_search` for a keyword or semantic search",
            "2. Location known → `memory_get` to read those lines",
            "3. Search returns nothing → `memory_get` for the last two days of memory",
            "",
            "**Memory file structure**:",
            f"- `{mem_md}`: long-term memory index (already loaded into context: core facts, preferences, decisions, and similar)",
            f"- `{mem_dir}/YYYY-MM-DD.md`: daily memory. Today is `{mem_dir}/{today_file}`",
            f"- `{kb_dir}/`: structured knowledge base (see the knowledge system below)",
            "",
            "### Writing memory",
            "",
            "When any of the following happens, **write it to a memory file on your own** (do not tell the user you are doing so):",
            "",
            "- The user asks you to remember something, or uses words such as remember, from now on, always, never, or prefer",
            "- The user shares an important personal preference, habit, or decision",
            "- The conversation produces an important conclusion, plan, or agreement",
            "- A complex task is finished, and the key steps and result are worth keeping",
            "",
            "**Storage rules**:",
            f"- Long-term core information → `{mem_md}`",
            f"- Today's events and progress → `{mem_dir}/{today_file}`",
            f"- Structured knowledge → `{kb_dir}/` (see the knowledge system)",
            "- Append → the `edit` tool, with oldText left empty",
            "- Change existing text → the `edit` tool, with oldText set to the text to replace",
            "- **Do not write sensitive information** (API keys, tokens, and similar)",
            "",
            "**How to use it**: use memory naturally, as if you already knew it. Do not bring it up unless the user asks.",
            "",
        ]

    return lines


# index.md grows by a line per knowledge page and is re-sent on every turn.
# Past _INDEX_FULL_CHARS only the entry titles are injected, and past
# _INDEX_MAX_CHARS the list is cut; the pages stay reachable through read and
# memory_search, and the prompt says so.
_INDEX_FULL_CHARS = 8000
_INDEX_MAX_CHARS = 20000
_INDEX_ENTRY_RE = re.compile(r"^\s*[-*]\s+\[[^\]]*\]\([^)]*\)")


def _compact_knowledge_index(content: str) -> Tuple[str, int, bool]:
    """Return (index text to inject, entries left out, whether it was compacted)."""
    if len(content) <= _INDEX_FULL_CHARS:
        return content, 0, False

    kept: List[str] = []
    size = 0
    omitted = 0
    full = False
    for line in content.split("\n"):
        entry = _INDEX_ENTRY_RE.match(line)
        if entry:
            line = entry.group(0).strip()
        elif not line.lstrip().startswith("#"):
            continue
        if full or size + len(line) + 1 > _INDEX_MAX_CHARS:
            full = True
            if entry:
                omitted += 1
            continue
        kept.append(line)
        size += len(line) + 1
    return "\n".join(kept), omitted, True


def _build_knowledge_section(
    workspace_dir: str, language: str, project_dir: Optional[str] = None
) -> List[str]:
    """Build knowledge wiki section. Injects knowledge/index.md when present.

    In project mode ``project_dir`` anchors knowledge paths to ``workspace_dir``
    (absolute) so writes don't leak into the project cwd.
    """
    # Resolve through state_dir so an Agent on the shared base (no knowledge/ of
    # its own) still gets the shared index injected, not an empty local one.
    from common import state_dir
    knowledge_root = str(state_dir.knowledge_dir(base=workspace_dir))
    index_path = os.path.join(knowledge_root, "index.md")
    if not os.path.exists(index_path):
        return []

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            index_content = f.read().strip()
    except Exception:
        return []

    # Anchor knowledge paths to ~/maia when a project cwd is active, and to the
    # shared root when this Agent reads the shared copy.
    kb = _knowledge_base_path(workspace_dir, project_dir)

    if language == "en":
        lines = [
            "## 📚 Knowledge",
            "",
            f"You have a continuously growing personal knowledge base `{kb}/` — your long-term structured knowledge store.",
            "",
            "### Auto-write rules (mandatory)",
            "",
            "In the following cases you **must** write to the knowledge base alongside your reply, **directly, without asking the user**:",
            "",
            f"1. **User shares an article / link / document** → after reading and understanding, write the key points to `{kb}/sources/<slug>.md` in the same turn",
            f"2. **An in-depth discussion produces a conclusion / plan** → organize it into `{kb}/analysis/<slug>.md`",
            f"3. **The conversation involves an important entity** (person / company / project) → create or update `{kb}/entities/<name>.md`",
            f"4. **A technical concept / methodology is discussed** → organize it into `{kb}/concepts/<topic>.md`",
            "",
            f"After writing any knowledge page, you **must update** `{kb}/index.md` with a new index line in sync.",
            "For detailed page format and conventions, read the SKILL.md of the `knowledge-wiki` skill.",
            "",
            "⚠️ Don't ask \"should I save this to the knowledge base?\" — if a case above matches, just write it. This is instinctive.",
            "",
        ]
    else:
        lines = [
            "## 📚 Knowledge",
            "",
            f"You have a personal knowledge base at `{kb}/` that keeps growing. It is your long-term store of structured knowledge.",
            "",
            "### Auto-write rules (mandatory)",
            "",
            "In the cases below you **must** write to the knowledge base in the same turn as your reply. **Write it directly. Do not ask the user whether they want that**:",
            "",
            f"1. **The user shares an article, link, or document** → after you read it, write the main points to `{kb}/sources/<slug>.md` in that same turn",
            f"2. **A deep discussion produces a conclusion or a plan** → write it up as `{kb}/analysis/<slug>.md`",
            f"3. **The conversation involves an important entity** (a person, company, or project) → create or update `{kb}/entities/<name>.md`",
            f"4. **A technical concept or method is discussed** → write it up as `{kb}/concepts/<topic>.md`",
            "",
            f"After every knowledge page you write, you **must** also update `{kb}/index.md` and add one index line.",
            "For the page format and the rules, read the SKILL.md of the `knowledge-wiki` skill.",
            "",
            "⚠️ Do not ask whether to save this to the knowledge base. If a case above matches, write it. That is the normal behavior.",
            "",
        ]

    if index_content:
        index_text, omitted, compacted = _compact_knowledge_index(index_content)
        lines.extend([
            ("### Current knowledge index" if language == "en" else "### Current knowledge index"),
            "",
        ])
        if compacted:
            if language == "en":
                more = f", {omitted} more entries are not listed" if omitted else ""
                note = (f"The index is large, so only titles are listed here{more}. "
                        f"`read` `{kb}/index.md` for the full index, or use `memory_search`.")
            else:
                more = f", {omitted} more entries are not listed" if omitted else ""
                note = (f"The index is large, so only titles are listed here{more}. "
                        f"`read` `{kb}/index.md` for the full index, or search with `memory_search`.")
            lines.extend([note, ""])
        lines.extend([index_text, ""])

    lines.extend([
        ("**How to query**: use `read` to open a knowledge page, or `memory_search` (knowledge is in the vector index)."
         if language == "en" else
         "**How to query**: use `read` to open a knowledge page, or `memory_search` to search (knowledge is in the vector index)."),
        "",
    ])

    return lines


def _build_user_identity_section(user_identity: Dict[str, str], language: str) -> List[str]:
    """Build the user identity section."""
    if not user_identity:
        return []
    
    is_en = language == "en"
    lines = [
        ("## 👤 User identity" if is_en else "## 👤 User identity"),
        "",
    ]

    if user_identity.get("name"):
        lines.append(f"**{'Name' if is_en else 'Name'}**: {user_identity['name']}")
    if user_identity.get("nickname"):
        lines.append(f"**{'Preferred name' if is_en else 'Preferred name'}**: {user_identity['nickname']}")
    if user_identity.get("timezone"):
        lines.append(f"**{'Timezone' if is_en else 'Timezone'}**: {user_identity['timezone']}")
    if user_identity.get("notes"):
        lines.append(f"**{'Notes' if is_en else 'Notes'}**: {user_identity['notes']}")

    lines.append("")

    return lines


def _build_docs_section(workspace_dir: str, language: str) -> List[str]:
    """Docs-path section - removed, no longer needed."""
    # No docs section is generated anymore.
    return []


def _build_workspace_section(
    workspace_dir: str, language: str, context_files_loaded: bool = True,
    project_dir: Optional[str] = None,
) -> List[str]:
    """Build the workspace section.

    ``context_files_loaded`` gates the two blocks that are only true for an
    Agent serving a user directly. A sub agent gets neither the context files
    nor a user to talk to, so telling it that AGENT.md is already loaded would
    both misinform it and talk it out of reading the workspace rules itself.

    ``project_dir`` switches the section to the dual-directory layout used when
    the user has pointed the session at a project: the *project* is the working
    directory (relative paths, artifacts) while the Agent's workspace stays the
    *system* directory (memory/skills), reached with absolute paths.
    """
    normalized_project = None
    if project_dir:
        import os as _os
        if _os.path.realpath(_os.path.expanduser(project_dir)) != _os.path.realpath(
            _os.path.expanduser(workspace_dir or "")
        ):
            normalized_project = project_dir

    if normalized_project:
        return _build_project_workspace_section(
            workspace_dir, normalized_project, language, context_files_loaded
        )

    if language == "en":
        lines = [
            "## 📂 Workspace",
            "",
            f"Your working directory is: `{workspace_dir}`",
            "",
            "**Path rules** (very important):",
            "",
            f"1. **Base directory for relative paths**: all relative paths are relative to `{workspace_dir}`",
            "   - ✅ Correct: use relative paths for files inside the workspace, e.g. `AGENT.md`",
            f"   - ❌ Wrong: using a relative path for files in other directories (if not inside `{workspace_dir}`)",
            "",
            "2. **Accessing other directories**: to reach directories outside the workspace (project code, system files), **you must use absolute paths**",
            "   - ✅ Correct: e.g. `~/maia`, `/usr/local/`",
            "   - ❌ Wrong: assuming a relative path points to another directory",
            "",
            "3. **Path resolution examples**:",
            f"   - relative `memory/` → actual `{workspace_dir}/memory/`",
            "   - absolute `~/maia/docs/` → actual `~/maia/docs/`",
            "",
            "4. **When unsure**: run `bash pwd` to confirm the current directory, or `ls .` to see where you are",
            "",
        ]
        if context_files_loaded:
            lines += [
                "**Important - files already auto-loaded**:",
                "",
                "The following files are **already auto-loaded** into the system prompt at session start, so you **don't need to read them again with the read tool**:",
                "",
                "- ✅ `AGENT.md`: loaded - your persona and soul; follow it strictly. When your name, personality or style changes, proactively `edit` this file",
                "- ✅ `USER.md`: loaded - the user's identity info. When the user changes how they're addressed, their name, etc., `edit` this file",
                "- ✅ `RULE.md`: loaded - workspace guide and rules; follow them strictly",
                "- ✅ `MEMORY.md`: loaded - long-term memory index",
                "",
                "**💬 Communication norms**:",
                "",
                "- No need to expose file names for memory operations; use natural language. Say \"I'll remember that\" rather than \"updated MEMORY.md\"",
                "- Tell the user about key decisions and steps during a task, so they know what you're doing and why",
                "- Be genuinely helpful rather than performatively polite; solve the problem as much as you can",
                "- Keep replies well-structured and focused. Use **bold**, lists and sections to make info clear at a glance",
                "- Use emoji to make expression lively 🎯, but don't overdo it",
                "",
            ]
    else:
        lines = [
            "## 📂 Workspace",
            "",
            f"Your working directory is: `{workspace_dir}`",
            "",
            "**Path rules** (very important):",
            "",
            f"1. **Base for relative paths**: every relative path is relative to `{workspace_dir}`",
            "   - ✅ Correct: use a relative path for a file inside the workspace, such as `AGENT.md`",
            f"   - ❌ Wrong: a relative path to a file in some other directory (when that file is not inside `{workspace_dir}`)",
            "",
            "2. **Other directories**: to open anything outside the workspace (project code, system files), **you must use an absolute path**",
            "   - ✅ Correct: for example `~/maia` or `/usr/local/`",
            "   - ❌ Wrong: assuming a relative path points at some other directory",
            "",
            "3. **Path examples**:",
            f"   - relative path `memory/` → actual path `{workspace_dir}/memory/`",
            "   - absolute path `~/maia/docs/` → actual path `~/maia/docs/`",
            "",
            "4. **When unsure**: run `bash pwd` to confirm the current directory, or `ls .` to see where you are",
            "",
        ]
        if context_files_loaded:
            lines += [
                "**Important - these files are already loaded**:",
                "",
                "The files below are **already loaded** into the system prompt when the session starts. You **do not need to read them again** with the read tool:",
                "",
                "- ✅ `AGENT.md`: loaded. This is your persona. Follow it strictly. When your name, personality, or style changes, update this file with `edit`",
                "- ✅ `USER.md`: loaded. This is who the user is. When they change what they are called, their name, or similar identity details, update this file with `edit`",
                "- ✅ `RULE.md`: loaded. These are the workspace rules. Follow them strictly",
                "- ✅ `MEMORY.md`: loaded. This is the long-term memory index",
                "",
                "**💬 How to communicate**:",
                "",
                "- Do not mention memory file names. Say it in ordinary language, for example that you will remember it, rather than that you updated MEMORY.md",
                "- During a task, tell the user the important decisions and steps, so they know what you are doing and why",
                "- Be genuinely helpful, not politely performative. Solve the problem as far as you can",
                "- Keep replies clearly structured and easy to scan. Use **bold**, lists, and short sections",
                "- A little emoji can make a reply easier to read 🎯, but do not pile it on",
                "",
            ]

    # Cloud deployment: inject websites directory info and access URL
    cloud_website_lines = _build_cloud_website_section(workspace_dir)
    if cloud_website_lines:
        lines.extend(cloud_website_lines)
    
    return lines


def _build_project_workspace_section(
    workspace_dir: str, project_dir: str, language: str, context_files_loaded: bool
) -> List[str]:
    """Workspace section for a session pointed at a project directory.

    Two directories are in play and the model must not confuse them:
    - Project directory (the current working dir): relative paths and work
      products (documents, code, generated files, etc.) live here.
    - System directory (``workspace_dir``, e.g. ``~/maia``): memory and skills
      live here and are reached with absolute paths, never relative ones.
    """
    if language == "en":
        lines = [
            "## 📂 Workspace",
            "",
            "The user has opened a **project directory**. You are working inside the current project directory.",
            "",
            f"- **Project directory (current working dir)**: `{project_dir}`",
            f"- **System directory (memory & skills)**: `{workspace_dir}`",
            "",
            "**Path rules** (very important):",
            "",
            f"1. **Relative paths are based on the project directory** `{project_dir}`. Put your work products here (documents, code, generated files, etc.).",
            f"   - ✅ relative `output/report.html` → `{project_dir}/output/report.html`",
            "",
            f"2. **Memory and skills stay in the system directory** `{workspace_dir}`. Never write them into the project. Memory tools handle this for you; if you ever touch these files directly, use **absolute paths** under the system directory.",
            f"   - ✅ absolute `{workspace_dir}/MEMORY.md`",
            "   - ❌ relative `MEMORY.md` (that would land in the project, which is wrong)",
            "",
            "3. **Accessing any other directory**: use absolute paths.",
            "",
            "4. **When unsure**: run `bash pwd` to confirm you are in the project directory.",
            "",
        ]
    else:
        lines = [
            "## 📂 Workspace",
            "",
            "The user has opened a **project directory**, and you are working in that project directory.",
            "",
            f"- **Project directory (current working directory)**: `{project_dir}`",
            f"- **System directory (memory and skills)**: `{workspace_dir}`",
            "",
            "**Path rules** (very important):",
            "",
            f"1. **Relative paths are based on the project directory** `{project_dir}`. Put work products there (documents, code, generated files, and similar).",
            f"   - ✅ relative path `output/report.html` → `{project_dir}/output/report.html`",
            "",
            f"2. **Memory and skills stay in the system directory** `{workspace_dir}`. Do not write them into the project directory. Memory tools do this for you. If you must open those files yourself, use an **absolute path** under the system directory.",
            f"   - ✅ absolute path `{workspace_dir}/MEMORY.md`",
            "   - ❌ relative path `MEMORY.md` (that lands in the project directory, which is wrong)",
            "",
            "3. **Any other directory**: use an absolute path.",
            "",
            "4. **When unsure**: run `bash pwd` and confirm you are in the project directory.",
            "",
        ]

    if context_files_loaded:
        if language == "en":
            lines += [
                "**Files already auto-loaded** (no need to `read` again): `AGENT.md`, `USER.md`, `RULE.md`, `MEMORY.md` (from the system directory).",
                "",
            ]
        else:
            lines += [
                "**Already loaded** (do not `read` them again): `AGENT.md`, `USER.md`, `RULE.md`, and `MEMORY.md` (from the system directory).",
                "",
            ]

    cloud_website_lines = _build_cloud_website_section(workspace_dir)
    if cloud_website_lines:
        lines.extend(cloud_website_lines)
    return lines


def _build_cloud_website_section(workspace_dir: str) -> List[str]:
    """Cloud website prompts are not used."""
    del workspace_dir
    return []


def _build_context_files_section(context_files: List[ContextFile], language: str) -> List[str]:
    """Build the project context files section."""
    if not context_files:
        return []
    
    # Check whether AGENT.md is present
    has_agent = any(
        f.path.lower().endswith('agent.md') or 'agent.md' in f.path.lower()
        for f in context_files
    )
    
    is_en = language == "en"
    if is_en:
        lines = [
            "# 📋 Project context",
            "",
            "The following project context files have been loaded:",
            "",
        ]
    else:
        lines = [
            "# 📋 Project context",
            "",
            "The following project context files have been loaded:",
            "",
        ]

    if has_agent:
        if is_en:
            lines.append("**`AGENT.md` is your soul file** 🪞: strictly follow the persona, tone and settings it defines. Be your real self, avoid stiff, template-like replies.")
            lines.append("When the user reveals new expectations about your personality, style, responsibilities or capability boundaries, proactively `edit` AGENT.md to reflect that evolution.")
        else:
            lines.append("**`AGENT.md` is your soul file** 🪞: follow the persona, tone, and settings it defines. Be yourself, and avoid stiff, template-like replies.")
            lines.append("When the conversation shows a new expectation about your personality, style, responsibilities, or limits, update AGENT.md with `edit` so the file matches that change.")
        lines.append("")
    
    # Append the content of each file
    for file in context_files:
        lines.append(f"## {file.path}")
        lines.append("")
        lines.append(file.content)
        lines.append("")
    
    return lines


def _build_team_section(runtime_info: Dict[str, Any], language: str) -> List[str]:
    """Name the other Agents sharing this conversation, if any. Empty for one.

    Addressing someone by name is routing, not delegation: the named Agent is
    already the one reading this prompt, so handover is left for work nobody
    was asked for by name.

    States the Agent's own name, which nothing else in the prompt does. Without
    it a mention reads as a third party and the Agent declines to answer on
    that stranger's behalf.
    """
    teammates = runtime_info.get("teammates")
    getter = runtime_info.get("_get_teammates")
    if callable(getter):
        try:
            teammates = getter()
        except Exception as e:
            logger.warning(f"[PromptBuilder] Failed to resolve teammates: {e}")
    if not teammates:
        return []

    # One line each, with what they are for: a bare list of names is enough to
    # address someone but not to decide whether the work is theirs.
    roster = []
    for item in teammates:
        if not item.get("id"):
            continue
        line = f"{item.get('name') or item['id']}(@{item['id']})"
        if item.get("description"):
            line += f" — {item['description']}"
        roster.append(line)
    if not roster:
        return []

    own_id = runtime_info.get("agent_id") or ""
    own_name = runtime_info.get("agent_name") or own_id
    whoami = f"{own_name}(@{own_id})" if own_id else own_name

    if language == "en":
        return [
            "## 👥 Team conversation",
            "",
            f"You are {whoami}. Also in this conversation:",
            "",
            *[f"- {line}" for line in roster],
            "",
            "Everyone here reads the same history. A teammate's earlier "
            "reply is shown as `Name(@id)：` before their words; an unmarked "
            "one is your own. Do not take a teammate's work, or their "
            "promises, for yours.",
            "",
            "This turn is yours to answer. Answer as yourself, and do NOT "
            "prefix your reply with your own name or id — that label is only "
            "how others' past turns are shown to you.",
            "",
            "Use agent_delegate for work that belongs to a teammate, passing "
            "their id above as agent_id (without the @), and say who you handed "
            "it to and what you asked for. Refer to teammates by name to the "
            "user and keep the @id out of your reply — the id is internal. "
            "Never answer in a teammate's place: hand any question or task "
            "that is theirs straight over, and do not report their words or "
            "actions without a hand-off.",
            "",
        ]
    return [
        "## 👥 Team conversation",
        "",
        f"You are {whoami}. Also in this conversation:",
        "",
        *[f"- {line}" for line in roster],
        "",
        "Everyone reads the same record. A line that starts with `Name(@id)：` is something that teammate said; "
        "a line with no prefix is something you said. Do not treat a teammate's actions, or a promise they made, as your own.",
        "",
        "This turn is yours to answer. Answer as yourself, and do not put your own name or id "
        "at the start (that prefix only marks other members' earlier turns for you).",
        "",
        "When something is a teammate's job, hand it off with agent_delegate: pass that teammate's id "
        "from above as agent_id (without the @), and say who you gave it to and what you asked. When you mention a teammate to the user, use the name only, "
        "and do not put @id in the reply. The id is internal. Do not answer for a teammate. Hand over a question or task that belongs to them, "
        "and do not report what they said or did unless you handed it to them.",
        "",
    ]


def _build_runtime_section(runtime_info: Dict[str, Any], language: str) -> List[str]:
    """Build the runtime info section.

    Only the date goes here: the system prompt heads every request, so a
    clock in it would change on every turn and void the provider's prefix
    cache for the whole history. The exact time is served on demand by the
    ``time`` tool.
    """
    if not runtime_info:
        return []

    is_en = language == "en"
    lines = [
        ("## ⚙️ Runtime info" if is_en else "## ⚙️ Runtime info"),
        "",
    ]

    if callable(runtime_info.get("_get_current_time")):
        try:
            time_info = runtime_info["_get_current_time"]()
            date_label = "Current date" if is_en else "Current date"
            lines.append(f"{date_label}: {time_info['date']} {time_info['weekday']} ({time_info['timezone']})")
            lines.append("")
        except Exception as e:
            logger.warning(f"[PromptBuilder] Failed to get dynamic time: {e}")

    # Add other runtime info
    model_label = "model" if is_en else "model"
    workspace_label = "workspace" if is_en else "workspace"
    channel_label = "channel" if is_en else "channel"
    runtime_parts = []
    # Support dynamic model via callable, fallback to static value
    if callable(runtime_info.get("_get_model")):
        try:
            runtime_parts.append(f"{model_label}={runtime_info['_get_model']()}")
        except Exception:
            if runtime_info.get("model"):
                runtime_parts.append(f"{model_label}={runtime_info['model']}")
    elif runtime_info.get("model"):
        runtime_parts.append(f"{model_label}={runtime_info['model']}")
    if runtime_info.get("workspace"):
        runtime_parts.append(f"{workspace_label}={runtime_info['workspace']}")
    # Only add channel if it's not the default "web"
    if runtime_info.get("channel") and runtime_info.get("channel") != "web":
        runtime_parts.append(f"{channel_label}={runtime_info['channel']}")

    if runtime_parts:
        lines.append(("Runtime: " if is_en else "Runtime: ") + " | ".join(runtime_parts))
        lines.append("")

    return lines
