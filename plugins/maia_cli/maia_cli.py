"""
MaiaCli plugin - Intercept maia/slash commands in chat messages.

Matches messages like:
  maia skill list
  maia install-browser
  /skill list
  /context clear
  /status
  /install-browser

Does NOT match:
  what is maia
  maia is useful
  a slash that is not a known command
"""

import os
import threading

import plugins
from plugins import Plugin, Event, EventContext, EventAction
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.atomic_write import write_json_atomic
from common.log import logger
from common.utils import tail_lines
from config import conf
from cli import __version__


# Known top-level subcommands that maia supports.
# "start" / "stop" / "restart" refer to daemon lifecycle on the host shell;
# in chat, "/cancel" aborts the in-flight agent run instead.
KNOWN_COMMANDS = {
    "help", "version", "status", "logs",
    "start", "stop", "restart",
    "cancel",
    "skill", "context", "config", "tasks",
    "knowledge", "memory", "compact", "clear",
    "install-browser",
}

# Commands that can only run from the CLI (terminal), not in chat.
CLI_ONLY_COMMANDS = {"start", "stop", "restart"}

# Commands that can only run from chat (need access to in-process memory)
CHAT_ONLY_COMMANDS = set()  # context is allowed in both, but behaves differently

# Convenience shorthands for the slash form only. Values are *full command
# strings* so an alias can carry arguments (e.g. "cc" -> "context clear").
# These shorthands are deliberate and NOT derivable from prefix/typo rules:
#   - "c"  is a prefix of cancel/config/context (ambiguous) -> needs explicit map
#   - "cc" is a prefix of nothing and expands to a command + argument
#   - "s"  would otherwise be an ambiguous prefix (skill/start/status/stop)
# Users may override / extend these via config.json "command_aliases".
DEFAULT_ALIASES = {
    "c":   "cancel",
    "cc":  "clear",
    "cp":  "compact",
    "ctx": "context",
    "h":   "help",
    "s":   "status",
    "cfg": "config",
    "k":   "knowledge",
}


def _app_name() -> str:
    """Product name shown in command output; a desktop build may rename it."""
    return (os.environ.get("MAIA_APP_NAME") or "").strip() or "Maia"


@plugins.register(
    name="maia_cli",
    desc="Handle slash commands in chat messages",
    version="0.1.0",
    author="Maia",
    desire_priority=1000,
)
class MaiaCliPlugin(Plugin):

    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.aliases = self._build_aliases()
        logger.debug("[MaiaCli] initialized")

    def reload(self):
        """Rebuild the alias table (e.g. after config changes)."""
        self.aliases = self._build_aliases()

    @staticmethod
    def _build_aliases() -> dict:
        """Merge DEFAULT_ALIASES with optional config.json ``command_aliases``.

        User-supplied entries (keys lowercased / stripped) override defaults.
        An alias whose target's first token is not a known command is dropped
        with a warning, so a bad alias can never create a dead command. An
        alias key that shadows a real command is kept but warned about — the
        exact-command stage in ``_resolve`` runs first, so the command wins.
        """
        merged = dict(DEFAULT_ALIASES)
        try:
            overrides = conf().get("command_aliases", {}) or {}
        except Exception as e:
            logger.warning(f"[MaiaCli] could not read command_aliases from config: {e}")
            overrides = {}
        if not isinstance(overrides, dict):
            logger.warning(f"[MaiaCli] command_aliases must be an object, got {type(overrides).__name__}; ignoring")
            overrides = {}
        for key, value in overrides.items():
            if not isinstance(key, str) or not isinstance(value, str):
                logger.warning(f"[MaiaCli] ignoring non-string alias entry: {key!r} -> {value!r}")
                continue
            k = key.strip().lower()
            if k:
                merged[k] = value.strip()

        valid = {}
        for key, value in merged.items():
            head = value.split(None, 1)[0].lower() if value.strip() else ""
            if head not in KNOWN_COMMANDS:
                logger.warning(f"[MaiaCli] dropping alias '/{key}' -> '{value}': unknown command '{head}'")
                continue
            if key in KNOWN_COMMANDS:
                logger.warning(f"[MaiaCli] alias '/{key}' shadows a real command; the command takes precedence")
            valid[key] = value
        return valid

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        content = e_context["context"].content.strip()
        parsed = self._parse_command(content)
        if parsed is None:
            return

        token, user_args = parsed
        result = self._resolve(token, user_args)
        kind = result[0]

        if kind == "passthrough":
            # Not a command and not a near-typo: let the agent handle it.
            return

        if kind == "run":
            _, cmd, args = result
            logger.info(f"[MaiaCli] intercepted command: {cmd} {args}")
            reply_text = self._dispatch(cmd, args, e_context)
        elif kind == "ambiguous":
            reply_text = self._ambiguous_hint(token, result[1])
        else:  # "typo"
            reply_text = self._typo_hint(token, result[1])

        reply_text = self._harden_line_breaks(reply_text, e_context)
        e_context["reply"] = Reply(ReplyType.TEXT, reply_text)
        e_context.action = EventAction.BREAK_PASS

    def _parse_command(self, content: str):
        """
        Parse maia command from message text.

        Supported formats:
          maia <command> [args...]   e.g. "maia skill list"
          /<command> [args...]      e.g. "/skill list"

        Returns:
          - (command, args_string): when the message looks like a command.
            'command' may NOT be in KNOWN_COMMANDS; caller should validate.
          - None: when the message is not command-like at all.

        We deliberately return parsed-but-unknown for the slash form so the
        caller can offer a typo hint instead of silently passing the message
        through to the agent.
        """
        if content.startswith("/"):
            rest = content[1:].strip()
            if not rest:
                return None
            parts = rest.split(None, 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            return cmd, args

        if content.startswith("maia "):
            rest = content[4:].strip()
            if not rest:
                return None
            parts = rest.split(None, 1)
            cmd = parts[0].lower()
            if cmd not in KNOWN_COMMANDS:
                # 'maia xxx' that isn't a command — don't intercept (could be
                
                return None
            args = parts[1] if len(parts) > 1 else ""
            return cmd, args

        return None

    @staticmethod
    def _suggest_command(cmd: str) -> str:
        """
        Return the closest known command if cmd is a likely typo, else "".
        Returns None to indicate "do not intercept" (when input is too far off).

        Heuristic: edit distance <= 1 (single insert/delete/substitute) when
        |cmd| >= 3, and the candidate shares the same first letter.
        """
        if not cmd:
            return ""
        if len(cmd) < 3:
            return None

        def edit_distance_le1(a: str, b: str) -> bool:
            if a == b:
                return True
            la, lb = len(a), len(b)
            if abs(la - lb) > 1:
                return False
            if la == lb:
                diffs = sum(1 for x, y in zip(a, b) if x != y)
                return diffs <= 1
            short, long_ = (a, b) if la < lb else (b, a)
            i = j = 0
            skipped = False
            while i < len(short) and j < len(long_):
                if short[i] != long_[j]:
                    if skipped:
                        return False
                    skipped = True
                    j += 1
                else:
                    i += 1
                    j += 1
            return True

        for known in KNOWN_COMMANDS:
            if known[0] == cmd[0] and edit_distance_le1(cmd, known):
                return known
        return None

    def _resolve(self, token: str, user_args: str):
        """Resolve a parsed slash token to an action.

        Precedence (first hit wins):
          1. exact command            -> ("run", cmd, args)
          2. alias (exact key)        -> expand to a full command string, merge args
          3. unique prefix            -> ("run", cmd, args)
          4. ambiguous prefix (>1)    -> ("ambiguous", sorted_candidates)
          5. typo (edit-distance <=1) -> ("typo", suggestion_or_None)
          6. no match                 -> ("passthrough",)

        Pure function of (token, user_args, KNOWN_COMMANDS, self.aliases) so it
        is trivially unit-testable. Note the `maia ` form never reaches stages
        2-5: `_parse_command` only returns known tokens for it, so it stays
        strict and alias/prefix matching applies to the `/` form only.
        """
        token = token.lower()

        # 1. exact command (a real command can never be shadowed by an alias)
        if token in KNOWN_COMMANDS:
            return ("run", token, user_args)

        # 2. alias -> full command string; merge alias args with user args.
        #    Alias expansion is applied at most once (no alias -> alias chains).
        if token in self.aliases:
            parts = self.aliases[token].split(None, 1)
            cmd = parts[0].lower()
            alias_args = parts[1] if len(parts) > 1 else ""
            merged = f"{alias_args} {user_args}".strip() if user_args else alias_args
            return ("run", cmd, merged)

        # 3 / 4. prefix match
        candidates = sorted(c for c in KNOWN_COMMANDS if c.startswith(token))
        if len(candidates) == 1:
            return ("run", candidates[0], user_args)
        if len(candidates) > 1:
            return ("ambiguous", candidates)

        # 5. typo (keeps its own len>=3 + edit-distance<=1 guards)
        suggestion = self._suggest_command(token)
        if suggestion is not None:
            return ("typo", suggestion)

        # 6. nothing matched
        return ("passthrough",)

    @staticmethod
    def _typo_hint(token: str, suggestion) -> str:
        hint = f"Unknown command: /{token}"
        if suggestion:
            hint += f"\nDid you mean /{suggestion} ?"
        hint += "\nSend /help to see all commands."
        return hint

    @staticmethod
    def _ambiguous_hint(token: str, candidates) -> str:
        options = " ".join(f"/{c}" for c in candidates)
        return f"Ambiguous command: /{token}\nDid you mean: {options}\nSend /help to see all commands."

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def execute(self, query: str, session_id: str = "") -> str:
        """Execute a maia/slash command string without a channel context.

        Used by cloud on_chat to intercept commands before the agent runs.
        Returns None when *query* is not command-like at all (e.g. natural
        language). For slash-prefixed typos returns a hint string so the
        caller still short-circuits the agent round.
        """
        parsed = self._parse_command(query.strip())
        if parsed is None:
            return None
        token, user_args = parsed
        result = self._resolve(token, user_args)
        kind = result[0]
        if kind == "passthrough":
            return None
        if kind == "run":
            _, cmd, args = result
            return self._dispatch(cmd, args, e_context=None, session_id=session_id)
        if kind == "ambiguous":
            return self._ambiguous_hint(token, result[1])
        return self._typo_hint(token, result[1])  # "typo"

    def _dispatch(self, cmd: str, args: str, e_context: EventContext, session_id: str = "") -> str:
        if cmd in CLI_ONLY_COMMANDS:
            return f"⚠️ `maia {cmd}` can only run in a terminal.\nRun it in your shell: maia {cmd}"

        handler_attr = "_cmd_" + cmd.replace("-", "_")
        handler = getattr(self, handler_attr, None)
        if handler:
            try:
                return handler(args, e_context, session_id=session_id)
            except Exception as e:
                logger.error(f"[MaiaCli] command '{cmd}' failed: {e}")
                return f"Command failed: {e}"

        return f"Unknown command: {cmd}"

    # ------------------------------------------------------------------
    # help / version
    # ------------------------------------------------------------------

    def _cmd_help(self, args: str, e_context, **_) -> str:
        lines = [
            f"📋 {_app_name()} Commands",
            "",
            "/help: Show this help",
            "/version: Show version",
            "/status: Show running status",
            "/cancel: Abort the running Agent task",
            "/logs [N]: Show the last N log lines (default 20)",
            "/context: Show current conversation context",
            "/clear: Clear current conversation context",
            "/compact: Summarize older turns to free up context",
            "/tasks: List scheduled tasks for this chat",
            "/skill list: List installed skills",
            "/skill list --remote: Browse Skill Hub",
            "/skill search <keyword>: Search skills",
            "/skill install <name>: Install a skill",
            "/skill info <name>: Show skill details",
            "/config: Show current config",
            "/config <key>: Show a config item",
            "/config <key> <val>: Update a config item",
            "/memory status: Show memory index status",
            "/memory rebuild-index: Rebuild the vector index (required after switching embedding model)",
            "/memory dream [N]: Trigger memory distillation (last N days, default 3, max 30)",
            "/knowledge: Show knowledge base stats",
            "/knowledge list: Show knowledge base file tree",
            "/knowledge on|off: Enable/disable knowledge base",
            "",
            "💡 You can also use maia <command> instead of /<command>",
        ]
        # The `maia` prefix is named after the default product; a renamed build
        # keeps the slash form only in its help.
        if os.environ.get("MAIA_APP_NAME"):
            lines = [l for l in lines if "maia <command>" not in l]
        return "\n".join(lines).rstrip()

    def _cmd_version(self, args: str, e_context, **_) -> str:
        return f"{_app_name()} v{__version__}"

    # ------------------------------------------------------------------
    # tasks — read-only scheduler list scoped to the current chat.
    # ------------------------------------------------------------------

    def _cmd_tasks(self, args: str, e_context, session_id: str = "", **_) -> str:
        from agent.tools.scheduler.integration import get_task_store

        task_store = get_task_store()
        if task_store is None:
            from agent.tools.scheduler.task_store import TaskStore
            from common.state_dir import scheduler_file_global

            task_store = TaskStore(str(scheduler_file_global()))

        channel_type = ""
        receiver = ""
        if e_context is not None:
            context = e_context["context"]
            channel_type = context.get("channel_type", "") or ""
            receiver = context.get("receiver", "") or ""
            session_id = context.get("session_id", "") or session_id

        visible = []
        for task in task_store.list_tasks():
            action = task.get("action") or {}
            if receiver:
                if action.get("receiver") != receiver:
                    continue
                if channel_type and action.get("channel_type") != channel_type:
                    continue
            elif session_id not in {
                action.get("receiver"),
                action.get("notify_session_id"),
            }:
                continue
            visible.append(task)

        return self._format_tasks(visible)

    @staticmethod
    def _format_tasks(tasks) -> str:
        if not tasks:
            return "📅 No scheduled tasks in this chat."

        lines = ["📅 Scheduled tasks in this chat", ""]
        for index, task in enumerate(tasks[:20], 1):
            enabled = task.get("enabled", True)
            status = "✅" if enabled else "⏸️"
            schedule = task.get("schedule") or {}
            schedule_type = schedule.get("type")
            if schedule_type == "cron":
                schedule_text = "cron {}".format(schedule.get("expression") or "?")
            elif schedule_type == "interval":
                schedule_text = "every {}s".format(schedule.get("seconds") or "?")
            elif schedule_type == "once":
                schedule_text = "once at {}".format(schedule.get("run_at") or "?")
            else:
                schedule_text = str(schedule_type or "unknown")

            next_run = str(task.get("next_run_at") or "-").replace("T", " ")
            lines.extend(
                [
                    "{}. {} {}".format(index, status, task.get("name") or "Unnamed task"),
                    "   ID: {}".format(task.get("id") or "-"),
                    "   {} · Next: {}".format(schedule_text, next_run),
                ]
            )

        hidden = len(tasks) - 20
        if hidden > 0:
            lines.append("\n{} more tasks are hidden.".format(hidden))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # cancel — abort the in-flight agent run for the current session.
    # Fallback handler; in practice chat_channel/web_channel intercept
    # /cancel earlier so it bypasses the per-session serial queue.
    # ------------------------------------------------------------------

    def _cmd_cancel(self, args: str, e_context: EventContext, session_id: str = "", **_) -> str:
        """Signal the running agent to halt at its next checkpoint."""
        from agent.protocol import get_cancel_registry

        target_session = self._get_session_id(e_context, fallback=session_id)
        registry = get_cancel_registry()

        # Prefer per-turn request_id (matches the key agent_bridge registered)
        cancelled = 0
        request_id = ""
        if e_context is not None:
            try:
                ctx = e_context["context"]
                request_id = ctx.kwargs.get("request_id") or ctx.get("request_id", "")
            except Exception:
                request_id = ""

        if request_id and registry.cancel_request(request_id):
            cancelled = 1

        # Fall back to session-wide cancel, under the agent-scoped key the run
        # was registered with.
        if cancelled == 0 and target_session:
            from bridge.bridge import Bridge
            agent_bridge = Bridge().get_agent_bridge()
            agent_id = (
                agent_bridge.route_context(e_context["context"])
                if e_context is not None
                else None
            )
            cancelled = registry.cancel_session(
                agent_bridge.scoped_session_key(target_session, agent_id)
            )

        if cancelled <= 0:
            return "Nothing to cancel."

        return "🛑 Cancelled"

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def _cmd_status(self, args: str, e_context: EventContext, session_id: str = "", **_) -> str:
        from config import conf

        cfg = conf()
        lines = [f"📊 {_app_name()} Status", ""]

        lines.append(f"  Version: v{__version__}")
        lines.append(f"  Process: PID {os.getpid()}")

        channel = cfg.get("channel_type", "unknown")
        if isinstance(channel, list):
            channel = ", ".join(channel)
        lines.append(f"  Channel: {channel}")

        model_name = cfg.get("model", "unknown")
        lines.append(f"  Model: {model_name}")

        mode = "Chat" if cfg.get("agent") is False else "Agent"
        lines.append(f"  Mode: {mode}")

        lang_label = "English"
        lines.append(f"  Language: {lang_label}")

        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)
        if agent:
            lines.append("")
            with agent.messages_lock:
                msg_count = len(agent.messages)
            lines.append(f"  Session messages: {msg_count}")

            if agent.skill_manager:
                total = len(agent.skill_manager.skills)
                enabled = sum(
                    1 for v in agent.skill_manager.skills_config.values()
                    if v.get("enabled", True)
                )
                lines.append(f"  Loaded skills: {enabled}/{total}")

            lines.append(self._mcp_status_line(agent))
        else:
            lines.append("")
            lines.append("  Agent: not initialized (created on first chat)")

        return "\n".join(lines)

    def _mcp_status_line(self, agent) -> str:
        """One line of MCP servers, shown "ready/total" like the skills line.

        Same source the web console uses (mcp.json, config.json fallback,
        ToolManager runtime state), and reading it never boots a server.
        The numerator counts only servers whose live status is "ready"; the
        denominator counts every configured server (failed, disabled, and
        not-yet-loaded included). No per-status breakdown ("ready 2, failed 1"
        in parentheses) is shown here by design. The console's MCP page
        carries that detail.
        """
        try:
            from agent.tools.mcp.service import list_servers_with_status

            servers = list_servers_with_status(agent.workspace_dir).get("servers") or []
        except Exception as e:
            logger.warning(f"[MaiaCli] status: failed to read MCP servers: {e}")
            servers = []

        ready = sum(1 for item in servers if item.get("status") == "ready")
        return f"  Loaded MCP: {ready}/{len(servers)}"

    # ------------------------------------------------------------------
    # logs
    # ------------------------------------------------------------------

    def _cmd_logs(self, args: str, e_context, **_) -> str:
        num_lines = 20
        if args.strip().isdigit():
            num_lines = min(int(args.strip()), 50)

        log_file = self._find_log_file()
        if not log_file:
            return "No log file found"

        try:
            tail = tail_lines(log_file, num_lines)
            content = "".join(tail).strip()
            if not content:
                return "Log is empty"
            return f"📄 Last {len(tail)} log lines:\n\n{content}"
        except Exception as e:
            return f"Failed to read log: {e}"

    def _find_log_file(self) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates = [
            os.path.join(project_root, "nohup.out"),
            os.path.join(project_root, "run.log"),
        ]
        import glob as glob_mod
        candidates.extend(sorted(glob_mod.glob(os.path.join(project_root, "logs", "*.log")), reverse=True))
        for f in candidates:
            if os.path.isfile(f) and os.path.getsize(f) > 0:
                return f
        return ""

    # ------------------------------------------------------------------
    # context
    # ------------------------------------------------------------------

    def _cmd_context(self, args: str, e_context: EventContext, session_id: str = "", **_) -> str:
        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)

        sub = args.strip().lower()
        if sub == "clear":
            # Kept for backward compatibility; /clear is the preferred form.
            return self._context_clear(agent, session_id)
        else:
            return self._context_info(agent, session_id)

    def _cmd_clear(self, args: str, e_context: EventContext, session_id: str = "", **_) -> str:
        """Clear the current conversation context (alias of /context clear)."""
        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)
        return self._context_clear(agent, session_id)

    def _context_info(self, agent, session_id: str) -> str:
        if not agent:
            return "⚠️ Agent not initialized, no context yet"

        with agent.messages_lock:
            messages = agent.messages.copy()

        if not messages:
            return "Current conversation context is empty"

        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        assistant_msgs = sum(1 for m in messages if m.get("role") == "assistant")
        tool_msgs = sum(1 for m in messages if m.get("role") == "tool")

        total_chars = sum(len(str(m.get("content", ""))) for m in messages)

        lines = [
            "💬 Current Conversation Context",
            "",
            f"  Session: {session_id or 'default'}",
            f"  Total messages: {len(messages)}",
            f"  User messages: {user_msgs}",
            f"  Assistant replies: {assistant_msgs}",
            f"  Tool calls: {tool_msgs}",
            f"  Total content length: ~{total_chars} chars",
            "",
            "  Send /clear to clear the conversation context",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # compact — summarize older turns and free up context on demand.
    # ------------------------------------------------------------------

    def _cmd_compact(self, args: str, e_context: EventContext, session_id: str = "", **_) -> str:
        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)
        if not agent:
            return "⚠️ Agent not initialized, no context to compact"

        if not hasattr(agent, "compact_context"):
            return "⚠️ This Agent does not support manual compaction"

        result = agent.compact_context()
        if not result.get("ok"):
            return "💬 Context is already short, nothing to compact"

        turns = result.get("compacted_turns", 0)
        before = result.get("before", 0)
        after = result.get("after", 0)
        return (f"🗜️ Context compacted\n\n  Turns summarized: {turns}\n  Messages: {before} → {after}\n\n"
            f"Older conversation was summarized; recent turns are kept as-is.")

    def _context_clear(self, agent, session_id: str) -> str:
        if not agent:
            return "⚠️ Agent not initialized"

        with agent.messages_lock:
            count = len(agent.messages)
            agent.messages.clear()

        return f"✅ Conversation context cleared ({count} messages)"

    # ------------------------------------------------------------------
    # config
    # ------------------------------------------------------------------

    _CONFIG_WRITABLE = {
        "model",
        "agent_max_context_tokens",
        "agent_max_context_turns",
        "agent_max_steps",
        "knowledge",
        "enable_thinking",
        "self_evolution_enabled",
        "self_evolution_idle_minutes",
        "self_evolution_min_turns",
    }

    _CONFIG_READABLE = _CONFIG_WRITABLE | {"channel_type"}

    def _cmd_config(self, args: str, e_context, **_) -> str:
        parts = args.strip().split(None, 1)
        if not parts:
            return self._config_show_all()

        key = parts[0].lower()
        if len(parts) == 1:
            return self._config_get(key)

        value_str = parts[1].strip()
        return self._config_set(key, value_str)

    def _config_show_all(self) -> str:
        from config import conf
        cfg = conf()
        lines = ["⚙️ Current Config", ""]
        for key in sorted(self._CONFIG_READABLE):
            val = cfg.get(key, "")
            lines.append(f"  {key}: {val}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 /config <key>: Show a config item")
        lines.append("💡 /config <key> <val>: Update a config item")
        return "\n".join(lines)

    def _config_get(self, key: str) -> str:
        from config import conf
        if key not in self._CONFIG_READABLE:
            available = ", ".join(sorted(self._CONFIG_READABLE))
            return f"Cannot show '{key}'\n\nReadable config items: {available}"
        val = conf().get(key, "")
        return f"⚙️ {key}: {val}"

    def _config_set(self, key: str, value_str: str) -> str:
        from config import conf, load_config, available_setting
        import json as _json

        if key not in self._CONFIG_WRITABLE:
            if key in self._CONFIG_READABLE:
                return f"⚠️ '{key}' is read-only and cannot be modified"
            available = ", ".join(sorted(self._CONFIG_WRITABLE))
            return f"Cannot modify '{key}'\n\nWritable config items: {available}"

        old_val = conf().get(key, "")

        try:
            new_val = _json.loads(value_str)
        except (_json.JSONDecodeError, ValueError):
            if value_str.lower() == "true":
                new_val = True
            elif value_str.lower() == "false":
                new_val = False
            else:
                new_val = value_str

        updates = {key: new_val}
        old_bot_type = conf().get("bot_type", "")

        if key == "model" and old_bot_type:
            from common import const
            if old_bot_type not in (const.CUSTOM,):
                resolved = self._resolve_bot_type_for_model(str(new_val))
                if resolved:
                    updates["bot_type"] = resolved

        # Write to the data dir (~/.maia in desktop, project root otherwise), not
        # __file__-relative — the latter lives inside the read-only .app bundle
        # when frozen and writing there breaks the macOS code-signature seal.
        from config import get_data_root
        config_path = os.path.join(get_data_root(), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                file_config = _json.load(f)
            file_config.update(updates)
            write_json_atomic(config_path, file_config)
        except Exception as e:
            return f"Failed to write config.json: {e}"

        # Sync updated values to environment variables so that load_config()
        # won't overwrite the new value with a stale env var (common in Docker).
        # Match env var keys case-insensitively (Docker compose typically uses
        # upper-case like MODEL, but lower-case is also possible).
        synced_envs = {}
        for k, v in updates.items():
            if k not in available_setting:
                continue
            str_val = str(v)
            k_lower = k.lower()
            for env_key in list(os.environ):
                if env_key.lower() == k_lower:
                    os.environ[env_key] = str_val
                    synced_envs[env_key] = str_val
        logger.info(f"[MaiaCli] config update: {updates}, synced envs: {synced_envs}")

        try:
            load_config()
        except Exception as e:
            logger.warning(f"[MaiaCli] config reload warning: {e}")

        if key in ("agent_max_context_tokens", "agent_max_steps"):
            try:
                from bridge.bridge import Bridge
                agent_bridge = Bridge().get_agent_bridge()
                if agent_bridge is not None:
                    agent_bridge.apply_runtime_limits()
            except Exception as e:
                logger.warning(f"[MaiaCli] apply runtime limits failed: {e}")

        result = f"✅ Config updated\n\n  {key}: {old_val} → {new_val}"
        if "bot_type" in updates and updates["bot_type"] != old_bot_type:
            result += f"\n  bot_type: {old_bot_type} → {updates['bot_type']}"
        return result

    @staticmethod
    def _resolve_bot_type_for_model(model_name: str) -> str:
        """Every model id is sent to the LiteLLM endpoint unchanged."""
        return "litellm"

    # ------------------------------------------------------------------
    # install-browser (shared logic with maia install-browser CLI)
    # ------------------------------------------------------------------

    @staticmethod
    def _send_install_progress(e_context, text: str) -> None:
        """Push a short status line to the chat channel (SSE: phase event, not done)."""
        if e_context is None:
            logger.info(f"[MaiaCli] install-browser: {text}")
            return
        try:
            channel = e_context["channel"]
            context = e_context["context"]
            if channel and context:
                r = Reply(ReplyType.TEXT, text)
                r.sse_phase = True
                channel.send(r, context)
        except Exception as e:
            logger.warning(f"[MaiaCli] install-browser progress send failed: {e}")

    def _cmd_install_browser(self, args: str, e_context, **_) -> str:
        from cli.commands.install import run_install_browser

        if args.strip():
            return ("Usage: /install-browser\n\n"
                "No arguments needed; equivalent to running `maia install-browser` in a terminal.\n"
                "Installation may take a few minutes; progress is pushed as multiple messages, and detailed pip output goes to the service log.")

        # Suppress detailed stream in chat; phases go through channel.send
        def _noop_stream(msg: str, fg=None):
            pass

        code = run_install_browser(
            stream=_noop_stream,
            on_phase=lambda m: self._send_install_progress(e_context, m),
        )
        if code != 0:
            return ("❌ Installation did not finish successfully. Check the messages above or the server log; "
                "you can also run `maia install-browser` in a terminal.")
        return f"✅ Installation finished. Restart {_app_name()} to use the browser tool."

    # ------------------------------------------------------------------
    # skill
    # ------------------------------------------------------------------

    def _cmd_skill(self, args: str, e_context, **_) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        sub_args = parts[1].strip() if len(parts) > 1 else ""
        # An Agent with its own skill set must not have commands typed in its
        # chat land on the shared library instead.
        agent_id = self._current_agent_id(e_context)

        if sub == "list":
            return self._skill_list(sub_args, agent_id=agent_id)
        elif sub == "search":
            return self._skill_search(sub_args, agent_id=agent_id)
        elif sub == "install":
            return self._skill_install(sub_args, agent_id=agent_id)
        elif sub == "uninstall":
            return self._skill_uninstall(sub_args, agent_id=agent_id)
        elif sub == "info":
            return self._skill_info(sub_args, agent_id=agent_id)
        elif sub == "enable":
            return self._skill_set_enabled(sub_args, True, agent_id=agent_id)
        elif sub == "disable":
            return self._skill_set_enabled(sub_args, False, agent_id=agent_id)
        else:
            return ("Usage: /skill <subcommand>\n\n"
                "Subcommands:\n"
                "list [--remote]: List skills\n"
                "search <keyword>: Search skills\n"
                "install <name>: Install a skill\n"
                "uninstall <name>: Uninstall a skill\n"
                "info <name>: Show skill details\n"
                "enable <name>: Enable a skill\n"
                "disable <name>: Disable a skill")

    def _refresh_skill_manager(self, agent_id=None):
        """Re-scan skill directories so skills_config.json reflects disk state."""
        try:
            from bridge.bridge import Bridge
            bridge = Bridge()
            agent_bridge = bridge.get_agent_bridge()
            for live_id, _session_id, agent in agent_bridge.iter_agent_instances():
                if not (agent and getattr(agent, 'skill_manager', None)):
                    continue
                if not agent_id or live_id == agent_id:
                    agent.skill_manager.refresh_skills()
                    return
            if agent_id:
                # No live instance for this Agent yet: scanning its directory
                # brings the config file in line just the same.
                from agent.skills.manager import SkillManager
                from cli.utils import get_skills_dir
                SkillManager(custom_dir=get_skills_dir(agent_id))
        except Exception as e:
            logger.debug(f"[MaiaCli] skill refresh skipped: {e}")

    def _skill_list_local(self, agent_id=None) -> str:
        from cli.utils import load_skills_config, get_skills_dir, get_builtin_skills_dir
        self._refresh_skill_manager(agent_id)
        config = load_skills_config(agent_id)

        # Scope to this Agent's selection: a subset picked in team.json means
        # /skill list here shows only what this Agent actually draws on, not the
        # whole shared library. ``None`` selection = every shared skill; an empty
        # list is a deliberate "none" and must NOT fall through to a disk scan.
        selection = self._agent_skill_selection(agent_id)
        scoped = selection is not None
        if scoped:
            config = {n: e for n, e in config.items() if n in selection}
            if not config:
                return "This Agent has no skills enabled.\n\n💡 Pick skills for it under Agents"

        if not config:
            skills_dir = get_skills_dir(agent_id)
            builtin_dir = get_builtin_skills_dir()
            entries = []
            for d, source in [(builtin_dir, "builtin"), (skills_dir, "custom")]:
                if not os.path.isdir(d):
                    continue
                for name in sorted(os.listdir(d)):
                    skill_path = os.path.join(d, name)
                    if os.path.isdir(skill_path) and not name.startswith("."):
                        if os.path.exists(os.path.join(skill_path, "SKILL.md")):
                            entries.append({"name": name, "source": source, "enabled": True})
            if not entries:
                return "No skills installed yet\n\n💡 /skill list --remote: Browse Skill Hub"
            config = {e["name"]: e for e in entries}

        sorted_entries = sorted(config.values(), key=lambda e: e.get("name", ""))
        enabled_count = sum(1 for e in sorted_entries if e.get("enabled", True))

        lines = [f"📦 Installed Skills ({enabled_count}/{len(sorted_entries)})", ""]
        for entry in sorted_entries:
            name = entry.get("name", "")
            enabled = entry.get("enabled", True)
            source = entry.get("source", "")
            icon = "✅" if enabled else "⏸️"
            display = entry.get("display_name", "") or name
            desc = entry.get("display_description", "") or entry.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "…"
            line = f"{icon} {display}"
            if display != name:
                line += f" ({name})"
            if desc:
                line += f"\n   {desc}"
            if source:
                line += f"\n   Source: {source}"
            lines.append(line)
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 /skill list --remote: Browse Skill Hub")
        lines.append("💡 /skill info <name>: Show details")
        return "\n".join(lines)

    def _skill_list(self, args: str, agent_id=None) -> str:
        parts = args.strip().split()
        if "--remote" in parts or "-r" in parts:
            page = 1
            for i, p in enumerate(parts):
                if p == "--page" and i + 1 < len(parts) and parts[i + 1].isdigit():
                    page = max(1, int(parts[i + 1]))
            return self._skill_list_remote(page=page, agent_id=agent_id)
        return self._skill_list_local(agent_id)

    def _agent_skill_selection(self, agent_id):
        """The set of skill names this Agent draws on, or ``None`` for "all".

        Mirrors SkillManager's first gate: a profile with an explicit ``skills``
        list is a subset; ``None``/absent means the full shared library.
        """
        try:
            from agent.registry import get_agent_registry
            profile = get_agent_registry().get(agent_id or None, require_enabled=False)
            return None if profile.skills is None else set(profile.skills)
        except Exception:
            return None

    def _current_agent_id(self, e_context):
        """Resolve which Agent this /skill command is running inside, so the
        listing can be scoped to that Agent's selection rather than the whole
        shared library."""
        if e_context is None:
            return None
        try:
            from bridge.bridge import Bridge
            agent_bridge = Bridge().get_agent_bridge()
            return agent_bridge.route_context(e_context["context"])
        except Exception:
            return None

    _REMOTE_PAGE_SIZE = 10

    def _skill_list_remote(self, page: int = 1, agent_id=None) -> str:
        import requests
        from cli.utils import load_skills_config, skill_hub
        page_size = self._REMOTE_PAGE_SIZE
        hub_api, hub_headers = skill_hub()
        if not hub_api:
            return "Skill Hub is disabled. Install a skill from a git URL."
        try:
            resp = requests.get(
                f"{hub_api}/skills",
                params={"page": page, "limit": page_size},
                headers=hub_headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            skills = data.get("skills", [])
            total = data.get("total", len(skills))
        except Exception as e:
            return f"Failed to fetch Skill Hub: {e}"

        if not skills and page == 1:
            return "No skills available on Skill Hub"

        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        installed = set(load_skills_config(agent_id).keys())

        lines = ["🌐 Skill Hub", ""]
        for s in skills:
            name = s.get("name", "")
            display = s.get("display_name", "") or name
            desc = s.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "…"
            badge = " [installed]" if name in installed else ""
            lines.append(f"📌 {display}{badge}")
            lines.append(f"   Name: {name}")
            if desc:
                lines.append(f"   {desc}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📄 Page {page}/{total_pages}")
        if page < total_pages:
            lines.append(f"💡 /skill list --remote --page {page + 1}: Next page")
        if page > 1:
            lines.append(f"💡 /skill list --remote --page {page - 1}: Previous page")
        lines.append("💡 /skill install <name>: Install a skill")
        lines.append("💡 /skill search <keyword>: Search skills")
        # The hub site is the default product's; a renamed build or another
        # registry leaves it out.
        return "\n".join(lines)

    def _skill_search(self, query: str, agent_id=None) -> str:
        if not query:
            return "Please specify a search keyword: /skill search <keyword>"

        import requests
        from cli.utils import load_skills_config, skill_hub
        hub_api, hub_headers = skill_hub()
        if not hub_api:
            return "Skill Hub is disabled. Install a skill from a git URL."
        try:
            resp = requests.get(f"{hub_api}/skills/search", params={"q": query}, headers=hub_headers, timeout=10)
            resp.raise_for_status()
            skills = resp.json().get("skills", [])
        except Exception as e:
            return f"Search failed: {e}"

        if not skills:
            return f"No skills found for \"{query}\""

        installed = set(load_skills_config(agent_id).keys())
        lines = [f"🔍 Search \"{query}\" ({len(skills)} results)", ""]
        for s in skills:
            name = s.get("name", "")
            display = s.get("display_name", "") or name
            desc = s.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "…"
            badge = " [installed]" if name in installed else ""
            lines.append(f"📌 {display}{badge}")
            lines.append(f"   Name: {name}")
            if desc:
                lines.append(f"   {desc}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 /skill install <name>: Install a skill")
        return "\n".join(lines)

    _INSTALL_TIMEOUT = 60

    def _skill_install(self, name: str, agent_id=None) -> str:
        if not name:
            return "Please specify a skill to install: /skill install <name>"

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        from cli.commands.skill import install_skill

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(install_skill, name, agent_id)
                result = future.result(timeout=self._INSTALL_TIMEOUT)

            if result.error:
                return f"Install failed: {result.error}"

            if not result.installed:
                return "\n".join(result.messages) if result.messages else "No installable skill found"

            return self._format_install_result(result, agent_id)
        except FuturesTimeout:
            return "Install timed out. Please retry later or check your network connection."
        except Exception as e:
            return f"Install failed: {e}"

    @staticmethod
    def _format_install_result(result, agent_id=None) -> str:
        """Format InstallResult into a chat-friendly message."""
        from cli.commands.skill import _read_skill_description
        from cli.utils import get_skills_dir, load_skills_config
        skills_dir = get_skills_dir(agent_id)
        config = load_skills_config(agent_id)

        lines = []
        for skill_name in result.installed:
            desc = _read_skill_description(os.path.join(skills_dir, skill_name))
            display = config.get(skill_name, {}).get("display_name", "")
            lines.append(f"✅ Skill installed: {skill_name}")
            if display and display != skill_name:
                lines.append(f"   Name: {display}")
            if desc:
                lines.append(f"   Description: {desc}")

        if len(result.installed) > 1:
            lines.append(f"\nInstalled {len(result.installed)} skills")

        return "\n".join(lines)

    def _skill_uninstall(self, name: str, agent_id=None) -> str:
        if not name:
            return "Please specify a skill to uninstall: /skill uninstall <name>"

        import shutil
        import json
        from cli.commands.skill import SkillInstallError, _check_skill_name
        from cli.utils import get_skills_dir

        # The name comes from chat and is passed to rmtree below. Use the raising
        # check: the CLI variant calls sys.exit.
        try:
            _check_skill_name(name)
        except SkillInstallError as e:
            return f"Cannot uninstall: {e}"

        skills_dir = get_skills_dir(agent_id)
        skill_dir = os.path.join(skills_dir, name)

        if not os.path.exists(skill_dir):
            skill_dir = self._resolve_skill_dir(name, skills_dir)

        if not skill_dir:
            return f"Skill '{name}' is not installed"

        shared = os.path.realpath(skills_dir) == os.path.realpath(get_skills_dir())

        shutil.rmtree(skill_dir)

        config_path = os.path.join(skills_dir, "skills_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config.pop(name, None)
                write_json_atomic(config_path, config)
            except Exception:
                pass

        # The skill is gone from the shared library, so scrub its name from any
        # Agent's selection list in team.json instead of leaving dead entries.
        # Removing an Agent's own copy leaves the shared one other Agents pick.
        if shared:
            try:
                from agent.admin import get_agent_admin_service
                get_agent_admin_service().prune_skill(name)
            except Exception as e:
                logger.debug(f"[MaiaCli] skill prune skipped: {e}")

        return f"✅ Skill '{name}' uninstalled"

    @staticmethod
    def _resolve_skill_dir(name: str, skills_dir: str):
        """Find actual directory for a skill whose folder name may differ from its config name."""
        if not os.path.isdir(skills_dir):
            return None
        for entry in os.listdir(skills_dir):
            entry_path = os.path.join(skills_dir, entry)
            if not os.path.isdir(entry_path) or entry.startswith("."):
                continue
            if entry == name or entry.startswith(name + "-") or entry.endswith("-" + name):
                skill_md = os.path.join(entry_path, "SKILL.md")
                if os.path.exists(skill_md):
                    return entry_path
        return None

    @staticmethod
    def _strip_frontmatter(content: str):
        """Strip YAML frontmatter and return (metadata_dict, body)."""
        if not content.startswith("---"):
            return {}, content
        end = content.find("\n---", 3)
        if end == -1:
            return {}, content
        fm_text = content[3:end].strip()
        body = content[end + 4:].lstrip("\n")
        meta = {}
        for line in fm_text.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().strip('"').strip("'")
        return meta, body

    def _skill_info(self, name: str, agent_id=None) -> str:
        if not name:
            return "Please specify a skill name: /skill info <name>"

        from cli.utils import get_skills_dir, get_builtin_skills_dir

        skills_dir = get_skills_dir(agent_id)
        builtin_dir = get_builtin_skills_dir()

        skill_dir = None
        source = None
        for d, src in [(skills_dir, "custom"), (builtin_dir, "builtin")]:
            candidate = os.path.join(d, name)
            if os.path.isdir(candidate):
                skill_dir = candidate
                source = src
                break

        if not skill_dir:
            resolved = self._resolve_skill_dir(name, skills_dir)
            if resolved:
                skill_dir = resolved
                source = "custom"

        if not skill_dir:
            return f"Skill '{name}' not found"

        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.exists(skill_md):
            return f"Skill '{name}' has no SKILL.md file"

        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        meta, body = self._strip_frontmatter(content)

        header_lines = [f"📖 Skill: {name} [{source}]", ""]
        desc = meta.get("description", "")
        if desc:
            header_lines.append(f"  {desc}")
            header_lines.append("")

        lines = body.split("\n")
        preview = "\n".join(lines[:30])
        result = "\n".join(header_lines) + preview
        if len(lines) > 30:
            result += f"\n\n... ({len(lines) - 30} more lines)"
        return result

    def _skill_set_enabled(self, name: str, enabled: bool, agent_id=None) -> str:
        if not name:
            return f"Please specify a skill name: /skill {'enable' if enabled else 'disable'} <name>"

        import json
        from cli.utils import get_skills_dir

        skills_dir = get_skills_dir(agent_id)
        config_path = os.path.join(skills_dir, "skills_config.json")

        if not os.path.exists(config_path):
            return "Skills config file not found"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            return f"Failed to read config: {e}"

        if name not in config:
            return f"Skill '{name}' not found in config"

        config[name]["enabled"] = enabled
        write_json_atomic(config_path, config)

        icon = "✅" if enabled else "⬚"
        if enabled:
            return f"{icon} Skill '{name}' enabled"
        return f"{icon} Skill '{name}' disabled"

    # ------------------------------------------------------------------
    # memory
    # ------------------------------------------------------------------

    def _cmd_memory(self, args: str, e_context, session_id: str = "", **_) -> str:
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "dream":
            days = 3
            if len(parts) > 1 and parts[1].isdigit():
                days = max(1, min(int(parts[1]), 30))
            return self._memory_dream(days, e_context, session_id)
        elif sub in ("rebuild-index", "rebuild_index", "rebuild"):
            return self._memory_rebuild_index(e_context, session_id)
        elif sub in ("status", "info", ""):
            if sub == "":
                return self._memory_help()
            return self._memory_status()
        else:
            return self._memory_help()

    @staticmethod
    def _memory_help() -> str:
        return ("🧠 Memory Management\n\n"
            "Usage: /memory <subcommand>\n\n"
            "Subcommands:\n"
            "status: Show index status (provider / model / dim / chunks)\n"
            "rebuild-index: Rebuild the vector index (required after switching embedding model)\n"
            "dream [N]: Trigger memory distillation (last N days, default 3, max 30)")

    def _memory_dream(self, days: int, e_context, session_id: str) -> str:
        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)

        flush_mgr = None
        if agent and agent.memory_manager:
            flush_mgr = agent.memory_manager.flush_manager

        if not flush_mgr:
            try:
                flush_mgr = self._create_standalone_flush_manager()
            except Exception as e:
                return f"⚠️ Failed to initialize memory distillation: {e}"

        if not flush_mgr.llm_model:
            return "⚠️ No LLM model configured, cannot run memory distillation"

        # SaaS (e_context is None): run synchronously, return full result
        if e_context is None:
            return self._memory_dream_sync(flush_mgr, days)

        # Local channels: run in background, notify via channel.send()
        is_web = self._is_web_channel(e_context)

        def _run():
            try:
                result = flush_mgr.deep_dream(lookback_days=days, force=True)
                if result:
                    self._notify(e_context, self._build_dream_result(flush_mgr, is_web))
                else:
                    self._notify(e_context, "💤 Memory distillation skipped — no new memories to process")
            except Exception as e:
                logger.warning(f"[MaiaCli] /memory dream failed: {e}")
                self._notify(e_context, f"❌ Memory distillation failed: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return f"🌙 Memory distillation started (processing the last {days} days)\n\nRunning in the background; you'll be notified when it's done."

    def _memory_dream_sync(self, flush_mgr, days: int) -> str:
        """Run deep dream synchronously and return the full result."""
        try:
            result = flush_mgr.deep_dream(lookback_days=days, force=True)
            if result:
                return self._build_dream_result(flush_mgr, is_web=True)
            return "💤 Memory distillation skipped — no new memories to process"
        except Exception as e:
            logger.warning(f"[MaiaCli] /memory dream sync failed: {e}")
            return f"❌ Memory distillation failed: {e}"

    @staticmethod
    def _resolve_active_embedding():
        """
        Resolve (provider_label, model, dim) from the LATEST config, not the
        possibly-stale provider instance cached on a running agent. Used by
        /memory status and rebuild-index hints so they reflect what a rebuild
        will actually run as after the user changes embedding_provider.
        Returns (label, model, dim) where any field may be None when unknown.
        """
        from config import conf

        cfg_model = (conf().get("embedding_model") or "").strip()
        try:
            cfg_dim = int(conf().get("embedding_dimensions") or 0)
        except (TypeError, ValueError):
            cfg_dim = 0

        if not cfg_model:
            return "litellm", None, None
        return "litellm", cfg_model, cfg_dim or None

    def _memory_status(self) -> str:
        """Show current memory index status."""
        from agent.memory.embedding import detect_index_dim, detect_chunker_version
        from config import conf

        agent = self._get_agent("")
        memory_manager = agent.memory_manager if agent else None

        lines = ["🧠 Memory Index Status", ""]
        if not memory_manager:
            lines.append("  ⚠️ Agent not initialized yet, send a normal message first")
            return "\n".join(lines)

        stats = memory_manager.storage.get_stats()
        db_path = memory_manager.config.get_db_path()
        embedded = stats.get('embedded', 0)
        chunks = stats.get('chunks', 0)
        lines.append(f"  Index DB: {db_path}")
        lines.append(f"  Files   : {stats.get('files', 0)}")
        lines.append(f"  Chunks  : {chunks} (embedded: {embedded})")
        lines.append("")

        # Resolve from the latest config so users see what /memory rebuild-index
        # will actually run as — not what the cached agent was initialized with.
        cfg_provider, cfg_model, cfg_dim = self._resolve_active_embedding()
        provider_obj = memory_manager.embedding_provider
        if cfg_model:
            lines.append(f"  Provider : {cfg_provider}")
            lines.append(f"  Model    : {cfg_model}")
            lines.append(f"  Dim      : {cfg_dim if cfg_dim else '?'}")
        else:
            lines.append("  Provider : (not initialized, keyword-only)")

        # Health hints — only shown when the user has explicitly opted into
        # vector search via `embedding_provider`. Legacy users (no explicit
        # provider) are running in a "best-effort vectors" mode by design;
        # nagging them about missing/mismatched vectors would be noise.
        warnings = []
        explicitly_opted_in = (conf().get("embedding_provider") or "").strip() != ""
        if explicitly_opted_in and provider_obj is not None:
            if chunks > 0 and embedded < chunks:
                missing = chunks - embedded
                warnings.append(f"  ⚠️ {missing}/{chunks} chunks have no vectors; run /memory rebuild-index to enable vector search for all memories")

            index_dim = detect_index_dim(memory_manager.storage)
            if index_dim is not None and cfg_dim and index_dim != cfg_dim:
                warnings.append(f"  ⚠️ Existing vectors are {index_dim}-dim, mismatching the current {cfg_dim}-dim config; run /memory rebuild-index to make vector search work")

            # Index predates (or doesn't match) the current chunker. Chunked
            # files only re-split when their content hash changes, so a chunker
            # upgrade alone never refreshes old boundaries — suggest a rebuild.
            # This is only a hint: rebuild re-embeds everything and is costly,
            # so the user decides.
            from agent.memory.chunker import TextChunker
            if detect_chunker_version(memory_manager.storage) != TextChunker.CHUNKER_VERSION:
                warnings.append("  ⚠️ Index was built by an older chunking strategy; consider running /memory rebuild-index to bring it in line with the current one (a rebuild re-embeds everything, so it's your call)")

        if warnings:
            lines.append("")
            lines.extend(warnings)

        return "\n".join(lines)

    def _memory_rebuild_index(self, e_context, session_id: str) -> str:
        """Rebuild the vector index using the current agent's memory_manager."""
        session_id = self._get_session_id(e_context, fallback=session_id)
        agent = self._get_agent(session_id)
        if not agent or not agent.memory_manager:
            return ("⚠️ Agent not initialized, cannot rebuild the index.\n"
                "Send a normal message first to start the Agent, then try again.")

        memory_manager = agent.memory_manager

        # Rebuild against the LATEST config: build a fresh provider from
        # config.json and swap it onto memory_manager. The agent's
        # conversation_history and other state are untouched.
        try:
            from bridge.agent_initializer import AgentInitializer
            fresh_provider = AgentInitializer(bridge=None, agent_bridge=None) \
                ._init_embedding_provider(memory_manager.config, session_id=session_id)
        except Exception as e:
            logger.exception("[MaiaCli] /memory rebuild-index: build provider failed")
            return f"⚠️ Failed to build embedding provider from current config: {e}"

        if fresh_provider is None:
            return ("⚠️ No embedding provider available.\n"
                "Check the embedding settings in config.json (provider / api key).")
        memory_manager.embedding_provider = fresh_provider

        model_label = getattr(fresh_provider, "model", "?")
        dim_label = getattr(fresh_provider, "dimensions", "?")

        # SaaS (e_context is None): run synchronously, return final result
        if e_context is None:
            return self._memory_rebuild_sync(memory_manager, model_label, dim_label)

        # Local channels: run in background, push progress + final result
        from agent.memory.embedding import rebuild_in_process

        def _run():
            try:
                result = rebuild_in_process(memory_manager)
                if result.ok:
                    self._notify(
                        e_context,
                        (f"✅ Index rebuild complete\n"
                            f"  cleared : {result.removed}\n"
                            f"  chunks  : {result.chunks}\n"
                            f"  files   : {result.files}"),
                    )
                else:
                    self._notify(e_context, f"❌ Index rebuild failed: {result.error}")
            except Exception as e:
                logger.exception("[MaiaCli] /memory rebuild-index failed")
                self._notify(e_context, f"❌ Index rebuild failed: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return (f"🔧 Index rebuild started (model={model_label}, dim={dim_label})\n\n"
            f"Re-vectorizing all memory and knowledge files; you'll be notified when done.")

    @staticmethod
    def _memory_rebuild_sync(memory_manager, model_label, dim_label) -> str:
        from agent.memory.embedding import rebuild_in_process

        try:
            result = rebuild_in_process(memory_manager)
        except Exception as e:
            logger.exception("[MaiaCli] /memory rebuild-index sync failed")
            return f"❌ Index rebuild failed: {e}"

        if not result.ok:
            return f"❌ Index rebuild failed: {result.error}"
        return (f"✅ Index rebuild complete (model={model_label}, dim={dim_label})\n"
            f"  cleared : {result.removed}\n"
            f"  chunks  : {result.chunks}\n"
            f"  files   : {result.files}")

    @staticmethod
    def _notify(e_context, text: str):
        """Push a notification message back to the chat channel."""
        if e_context is None:
            logger.info(f"[MaiaCli] {text}")
            return
        try:
            channel = e_context["channel"]
            context = e_context["context"]
            if channel and context:
                channel.send(Reply(ReplyType.TEXT, text), context)
        except Exception as e:
            logger.warning(f"[MaiaCli] notify failed: {e}")

    @staticmethod
    def _is_web_channel(e_context) -> bool:
        if e_context is None:
            return False
        try:
            return e_context["context"].kwargs.get("channel_type") == "web"
        except Exception:
            return False

    @staticmethod
    def _harden_line_breaks(text: str, e_context) -> str:
        """Chat replies keep their original line breaks."""
        del e_context
        return text

    @staticmethod
    def _build_dream_result(flush_mgr, is_web: bool) -> str:
        """Build dream completion message with diary content."""
        from datetime import datetime
        lines = ["✅ Memory distillation complete"]

        # Read today's dream diary
        today = datetime.now().strftime("%Y-%m-%d")
        diary_file = flush_mgr.memory_dir / "dreams" / f"{today}.md"
        if diary_file.exists():
            diary = diary_file.read_text(encoding="utf-8").strip()
            # Strip the "# Dream Diary: ..." header line
            diary_lines = diary.split("\n")
            if diary_lines and diary_lines[0].startswith("# "):
                diary = "\n".join(diary_lines[1:]).strip()
            if diary:
                lines.append(f"\n{diary}")

        if is_web:
            lines.append("\n[MEMORY.md](/memory/MEMORY.md) | [Dream Diary](/memory/dreams)")
        else:
            lines.append("\nMEMORY.md updated")

        return "\n".join(lines)

    @staticmethod
    def _create_standalone_flush_manager():
        """Create a MemoryFlushManager without a running agent (for pre-init dream)."""
        from common.state_dir import state_root
        from agent.memory.summarizer import MemoryFlushManager
        from bridge.bridge import Bridge
        from bridge.agent_bridge import AgentLLMModel

        flush_mgr = MemoryFlushManager(workspace_dir=state_root())
        flush_mgr.llm_model = AgentLLMModel(Bridge())
        return flush_mgr

    # ------------------------------------------------------------------
    # knowledge
    # ------------------------------------------------------------------

    def _cmd_knowledge(self, args: str, e_context, **_) -> str:
        sub = args.strip().lower().split(None, 1)[0] if args.strip() else ""

        if sub == "on":
            return self._knowledge_toggle(True)
        elif sub == "off":
            return self._knowledge_toggle(False)
        elif sub in ("list", "tree"):
            return self._knowledge_tree()
        else:
            return self._knowledge_stats()

    def _knowledge_toggle(self, enabled: bool) -> str:
        from config import conf
        import json as _json

        conf()["knowledge"] = enabled

        # Data dir (~/.maia in desktop), not __file__-relative — see _config_set.
        from config import get_data_root
        config_path = os.path.join(get_data_root(), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                file_config = _json.load(f)
            file_config["knowledge"] = enabled
            write_json_atomic(config_path, file_config)
        except Exception as e:
            return f"⚠️ Switched in memory, but failed to write config.json: {e}"

        if enabled:
            return "📚 Knowledge base enabled ✅\n\nIt will take effect in the next conversation"
        return "📚 Knowledge base disabled ❌\n\nThe knowledge system is off; no prompt injection or file indexing"

    def _knowledge_stats(self) -> str:
        from config import conf
        from common import state_dir
        knowledge_dir = str(state_dir.knowledge_dir())
        if not os.path.isdir(knowledge_dir):
            return "📚 Knowledge base directory not found\n\n💡 Enable it: /knowledge on"

        enabled = conf().get("knowledge", True)
        total_files = 0
        total_bytes = 0
        cat_count = {}

        for root, dirs, files in os.walk(knowledge_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            rel_root = os.path.relpath(root, knowledge_dir)
            category = rel_root.split(os.sep)[0] if rel_root != "." else "root"
            for f in files:
                if f.endswith(".md") and f not in ("index.md", "log.md"):
                    total_files += 1
                    total_bytes += os.path.getsize(os.path.join(root, f))
                    cat_count[category] = cat_count.get(category, 0) + 1

        status = "✅ Enabled" if enabled else "❌ Disabled"
        lines = [
            "📚 Knowledge Base Stats",
            "",
            f"Status: {status}",
            f"Pages: {total_files}",
            f"Size: {total_bytes / 1024:.1f} KB",
            "",
        ]
        if cat_count:
            for cat in sorted(cat_count.keys()):
                lines.append(f"- {cat}/ ({cat_count[cat]} pages)")
            lines.append("")

        lines.append(f"Path: {knowledge_dir}")
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "💡 /knowledge list: Show file tree",
            "💡 /knowledge on|off: Toggle knowledge base",
        ])
        return "\n".join(lines)

    def _knowledge_tree(self) -> str:
        from common import state_dir
        knowledge_dir = str(state_dir.knowledge_dir())
        if not os.path.isdir(knowledge_dir):
            return "📚 Knowledge base directory not found\n\n💡 Enable it: /knowledge on"

        tree = ["knowledge/"]

        subdirs = sorted([
            d for d in os.listdir(knowledge_dir)
            if os.path.isdir(os.path.join(knowledge_dir, d)) and not d.startswith(".")
        ])

        for i, subdir in enumerate(subdirs):
            is_last_dir = (i == len(subdirs) - 1)
            branch = "└── " if is_last_dir else "├── "
            subdir_path = os.path.join(knowledge_dir, subdir)
            md_files = sorted([
                f for f in os.listdir(subdir_path)
                if f.endswith(".md") and not f.startswith(".")
            ])
            tree.append(f"{branch}{subdir}/ ({len(md_files)})")

            child_prefix = "    " if is_last_dir else "│   "
            max_show = 12
            for j, fname in enumerate(md_files[:max_show]):
                is_last_file = (j == len(md_files[:max_show]) - 1) and len(md_files) <= max_show
                fb = "└── " if is_last_file else "├── "
                name = fname.replace(".md", "")
                tree.append(f"{child_prefix}{fb}{name}")
            if len(md_files) > max_show:
                tree.append(f"{child_prefix}└── ... +{len(md_files) - max_show} more")

        if not subdirs:
            tree.append("(empty)")

        return "```\n" + "\n".join(tree) + "\n```"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_session_id(self, e_context, fallback: str = "") -> str:
        if e_context is None:
            return fallback
        context = e_context["context"]
        return context.kwargs.get("session_id") or context.get("session_id", "")

    def _get_agent(self, session_id: str):
        try:
            from bridge.bridge import Bridge
            bridge = Bridge()
            if not bridge._agent_bridge:
                return None
            return bridge._agent_bridge.get_agent(session_id=session_id or None)
        except Exception:
            return None

    def get_help_text(self, **kwargs):
        return "Use /help or maia help in chat to see available commands"
