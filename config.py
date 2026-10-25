# encoding:utf-8

import ast
import json
import logging
import os
import pickle
import sys
import time

from common.log import logger
from common import i18n
from cli.config_json import deep_merge_dicts as _deep_merge_dicts, merge_duplicate_keys

# All available config keys are listed in this dict (use lowercase keys).
# The values here are placeholders only; the program does NOT read them.
# They merely document the expected format — put real values in config.json.
available_setting = {
    # global UI language for CLI, startup logs, error messages, agent prompts
    # and channel replies. Options: "auto" (detect from system locale, default),
    # "zh" (Chinese) or "en" (English). An explicit value locks the language.
    # value: auto/en/zh
    "maia_lang": "auto",
    # LiteLLM OpenAI-compatible proxy. Every model call uses this endpoint.
    "litellm_api_base": "http://127.0.0.1:4000/v1",
    "litellm_api_key": "",
    # openai api config (unused; kept out of the runtime path)
    # openai api protocol: "auto" (Responses only for models that require it), "chat" (/chat/completions) or "responses" (/responses)
    # Prompt cache TTL for the system prompt + tools in agent mode: "1h" or "5m".
    # Use "5m" if the endpoint rejects the 1h TTL; the conversation always uses 5m.
    # Multiple custom (OpenAI-compatible) providers. Activated via bot_type: "custom:<id>".
    # Each item: {"id": "3f2a9c1b", "name": "my-provider", "api_key": "sk-...", "api_base": "https://api.example.com/v1", "model": "model-name"}
    "proxy": "",  # proxy used by openai
    # chatgpt model; when use_azure_chatgpt is true, this is the Azure model deployment name
    "model": "",  # model id as advertised by the LiteLLM proxy
    "bot_type": "litellm",
    # Fallback chat models, tried in order after the primary one has failed
    # permanently for a turn (all retries exhausted). Opt-in: an empty `chain`
    # disables the switch and the error surfaces as before.
    #
    # The chain is ordered and unbounded: a turn walks it from the front, and
    # the number of models the user lists *is* the number of switches on offer
    # — there is no separate cap to raise. Each entry needs both a provider and
    # a model; an entry missing either is skipped, and an entry equal to the
    # primary model (or to an earlier link) is skipped too, so a misconfigured
    # chain can never bounce a turn back onto the model that just failed.
    # {"enabled": bool, "chain": [{"provider": str, "model": str}, ...]}
    "chat_fallback": {
        "enabled": False,
        # Each item: {"provider": "openai", "model": "gpt-4o-mini"}.
        # `provider` is a provider id as used by `bot_type`
        # (e.g. "openai", "qianfan", "custom:<id>").
        "chain": [],
    },
    # Bot trigger config
    "single_chat_prefix": ["bot", "@bot"],  # text must contain this prefix to trigger a reply in single chat
    "single_chat_reply_prefix": "[bot] ",  # auto-reply prefix in single chat, used to distinguish from a real person
    "single_chat_reply_suffix": "",  # auto-reply suffix in single chat; \n inserts a line break
    "group_chat_prefix": ["@bot"],  # messages containing this prefix trigger a reply in group chat
    "no_need_at": False,  # whether replying in group chat does not require an @mention
    "group_chat_reply_prefix": "",  # auto-reply prefix in group chat
    "group_chat_reply_suffix": "",  # auto-reply suffix in group chat; \n inserts a line break
    "group_chat_keyword": [],  # messages containing this keyword trigger a reply in group chat
    "group_at_off": False,  # whether to disable @bot triggering in group chat
    "group_name_white_list": ["group1", "group2"],  # group names where auto-reply is enabled
    "group_name_keyword_white_list": [],  # group-name keywords where auto-reply is enabled
    "group_chat_in_one_session": ["group1"],  # group names that share conversation context
    "group_shared_session": False,  # whether group chat shares conversation context (all members share). When False each user has an independent session in the group
    "nick_name_black_list": [],  # user nickname blacklist
    "group_welcome_msg": "",  # fixed welcome message for new group members; uses a random style when empty
    "trigger_by_self": False,  # whether the bot can be triggered by itself
    "image_create_prefix": ["draw", "paint", "sketch"],  # prefixes that enable image replies
    "concurrency_in_session": 1,  # max number of in-flight messages per session; values >1 may cause out-of-order replies
    "image_create_size": "256x256",  # image size, options: 256x256, 512x512, 1024x1024 (dall-e-3 defaults to 1024x1024)
    "group_chat_exit_group": False,
    # chatgpt session params
    "expires_in_seconds": 3600,  # idle session expiry time
    # persona description (only used in chat mode)
    "character_desc": "You are a helpful AI assistant. You aim to answer and solve any questions people have, and can communicate in multiple languages.",
    "conversation_max_tokens": 1000,  # max characters of context memory
    # chatgpt rate limit config
    "rate_limit_chatgpt": 20,  # chatgpt call rate limit
    "rate_limit_dalle": 50,  # openai dalle call rate limit
    # chatgpt api params, see https://platform.openai.com/docs/api-reference/chat/create
    "temperature": 0.9,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "request_timeout": 180,  # chatgpt request timeout; the openai api defaults to 600, hard questions usually need longer
    "timeout": 120,  # chatgpt retry timeout; will auto-retry within this window
    # Embedding model config
    "embedding_provider": "litellm",
    "embedding_model": "",     # empty disables embeddings; otherwise a model id on the LiteLLM proxy
    "embedding_dimensions": 0, # leave empty/0 to use the provider's default dimension (1024 recommended for consistency)
    # Memory rerank config (optional, off by default)
    "rerank_provider": "",  # leave empty to disable; "local" runs a cross-encoder via sentence-transformers (install it yourself)
    "rerank_model": "",     # leave empty to use the provider's default model (local: BAAI/bge-reranker-base)
    # voice config
    "speech_recognition": True,  # whether to enable speech recognition
    "group_speech_recognition": False,  # whether to enable group speech recognition
    "voice_reply_voice": False,  # whether to reply to voice with voice; requires the matching TTS engine api key
    "always_reply_voice": False,  # whether to always reply with voice
    "voice_to_text": "litellm",
    "text_to_voice": "litellm",
    "asr_model": "",
    "tts_model": "",
    "tts_voice": "alloy",
    "vision_model": "",
    "image_model": "",
    "agent_fallback_models": [],
    "text_to_voice_model": "",
    "tts_voice_id": "alloy",
    # service time limit
    "chat_time_module": False,  # whether to enable service-time limiting
    "chat_start_time": "00:00",  # service start time
    "chat_stop_time": "24:00",  # service stop time
    # custom trigger words for admin commands
    "clear_memory_commands": ["#reset"],  # session-reset command; must start with #
    # channel config
    "channel_type": "web",  # web console. "terminal" is the local stdin channel. Other chat providers are not supported.
    "web_console": True,  # whether to auto-start the Web console (on by default). Set False to disable
    "debug": False,  # whether to enable debug mode; prints more logs when on
    "appdata_dir": "",  # data directory
    # plugin config
    "plugin_trigger_prefix": "$",  # prefix for plugin chat commands; avoid clashing with the admin command prefix "#"
    # whether to use the global plugin config
    "use_global_plugin_config": False,
    "max_media_send_count": 3,  # max number of media resources sent at once
    "media_send_interval": 1,  # interval between sending images, in seconds
    "web_host": "",  # Web console bind address; empty means auto
    "web_port": 9899,
    "web_password": "",  # Web console password; empty means no authentication required
    "web_https_enabled": False,  # Serve the web console over HTTPS directly; needs web_ssl_certfile + web_ssl_keyfile
    "web_ssl_certfile": "",  # PEM certificate file for direct HTTPS (full chain recommended)
    "web_ssl_keyfile": "",  # PEM private key file for direct HTTPS
    "external_api_enabled": False,  # serve the OpenAI-compatible /v1 chat API
    "external_api_token": "",  # API key for the /v1 chat API; kept while the API is off
    "web_session_expire_days": 30,  # Auth session expiry in days
    "web_file_serve_root": "~",  # Root dir the /api/file endpoint may serve; "/" allows the whole filesystem
    "mcp_oauth_redirect_base": "",  # Base URL for MCP OAuth callback (e.g. http://your-ip:9899); empty uses local web console
    "agent": True,  # whether to enable Agent mode
    "agent_workspace": "~/maia",  # agent workspace path, used to store skills, memory, etc.
    # Optional native multi-agent registry. When empty or omitted, Maia
    # synthesizes one "default" agent from agent_workspace and behaves exactly
    # as before. Each configured workspace is a complete Maia workspace.
    "agents": [],
    # Agent handling conversations that no channel instance binds. Defaults to
    # the first configured agent when unset. When no agents list is configured,
    # also sets the built-in single agent's id.
    "default_agent_id": "",
    # Optional display name for the built-in single agent.
    "default_agent_name": "",
    # Optional description for the built-in single agent. Teammates see it on
    # the roster of a shared conversation and use it to route work.
    "default_agent_description": "",
    # Routes inbound conversations to an agent. Each entry needs channel_type
    # and agent_id; add conversation_id to bind one chat rather than the whole
    # channel. Unbound conversations go to default_agent_id.
    "agent_bindings": [],
    # Manual cap on the Agent-mode input budget, used to control cost / token
    # burn: history is compacted once the prompt reaches this many tokens, even
    # when the model's window is far larger. Defaults to 200000. This value is
    # still clamped below the effective model's window (window - output
    # reserve), so a small-window model is never asked for more than it allows.
    # Set 0 to disable the manual cap and follow the model window instead.
    "agent_max_context_tokens": 200000,
    "agent_max_context_turns": 30,  # max context memory turns in Agent mode
    "agent_max_steps": 100,  # max decision steps per run in Agent mode
    # Default permission mode for sessions that have not picked one of their own:
    # "read-only" | "workspace-write" | "full-access". Kept at full-access so an
    # existing install behaves exactly as before an upgrade. Only a fresh desktop
    # client (MAIA_DESKTOP=1 with no config.json yet) is tightened to the stricter
    # workspace-write in load_config(); docker/source stay at full-access.
    "agent_permission_mode": "full-access",
    # In-process sub agents: the Agent hands a self-contained task to a
    # short-lived worker with its own context, and gets back only the result.
    # Set enabled to false to withhold the subagent tool entirely.
    # Types live in <workspace>/subagents/*.md alongside the built-in ones.
    "subagent": {
        "enabled": True,
        "max_depth": 1,          # 1 = only the main Agent may spawn (range 1-5)
        "max_concurrent": 3,     # parallel sub agents per spawn call (range 1-10)
        "timeout_seconds": 300,  # budget for one spawn call (range 10-3600)
    },
    # Delegation between configured agents. Unlike a sub agent, the target is a
    # standing peer that answers in its own workspace. The call is synchronous:
    # the delegating Agent waits for the teammate's result. The tool only
    # appears in a team conversation (two+ enabled agents with members). Set to
    # false to withhold it entirely.
    "agent_delegation": {
        "enabled": True,
        # {"<source>": ["<target>", ...]} or "*" for any. Unset means every
        # agent may delegate to every other one. Targets are further bounded to
        # the teammates in the current conversation.
        "allowed_targets": None,
        "max_depth": 3,               # delegation hops in one chain (range 1-8)
        "timeout_seconds": 600,       # budget for one delegated run (range 0.01-3600)
        "max_message_chars": 8000,    # size limit for one delegated task
    },
    "enable_thinking": False,  # Enable deep-thinking mode for thinking-capable models
    "reasoning_effort": "high",  # Provider-native reasoning depth; allowed values depend on the active provider/model
    "reasoning_effort_by_model": {},  # Per-model effort intent: {"<provider>:<model>": "<value>"}; overrides the global key per model
    "knowledge": True,  # whether to enable the knowledge base feature
    # Self-evolution: review idle conversations to learn memory/skills. Flat keys.
    "self_evolution_enabled": True,         # switch to enable/disable self-evolution
    "self_evolution_idle_minutes": 10,      # idle time before a session is reviewed
    "self_evolution_min_turns": 6,          # min user turns (or context pressure) to trigger
    # Deep Dream: nightly memory distillation into MEMORY.md + dream diary.
    "deep_dream_enabled": True,             # scheduled deep dream switch; manual /memory dream is unaffected
    "skill": {},  # Per-skill runtime config; nested keys flatten to SKILL_<NAME>_<KEY> env vars at startup
    # Registry that installs by bare name, skill search and skill list --remote
    # use; empty means the default Skill Hub. It must speak the same API. The key,
    # if set, is sent as a bearer token to this registry only.
    "mcp_servers": [],  # MCP server list; each entry supports type "stdio" (local process) or "sse" (remote URL)
    # On-demand MCP tool retrieval: when many MCP tools are connected, inject
    # only the most query-relevant ones instead of all of them. Built-in tools
    # are always injected in full; degrades to full injection when disabled,
    # below threshold, or when no embedding provider is available.
    "mcp_tool_retrieval_enabled": False,    # switch for on-demand MCP tool retrieval
    "mcp_tool_retrieval_threshold": 20,     # only retrieve when MCP tool count exceeds this
    "mcp_tool_retrieval_top_k": 10,         # max relevant MCP tools injected per turn
}


class Config(dict):
    def __init__(self, d=None):
        super().__init__()
        if d is None:
            d = {}
        for k, v in d.items():
            self[k] = v
        # user_datas: per-user data; key is the username, value is the user's data (also a dict)
        self.user_datas = {}

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def get(self, key, default=None):
        # skip comment fields starting with an underscore
        if key.startswith("_"):
            return super().get(key, default)
        
        # if the key is not in available_setting, fall back to dict.get and return the value actually loaded from config.json (or default if absent)
        if key not in available_setting:
            return super().get(key, default)
        
        try:
            return self[key]
        except KeyError:
            return default
        except Exception as e:
            raise e

    # Make sure to return a dictionary to ensure atomic
    def get_user_data(self, user) -> dict:
        if self.user_datas.get(user) is None:
            self.user_datas[user] = {}
        return self.user_datas[user]

    # SECURITY NOTE: pickle.load() can execute arbitrary code during
    # deserialization. This is safe as long as user_datas.pkl is trusted
    # (local app data directory, written only by this process). For a future
    # hardening pass, consider migrating to JSON (json.load/json.dump) if the
    # data structures are JSON-serializable, or adding an HMAC signature to
    # detect tampering of the pickle file.
    def load_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "rb") as f:
                self.user_datas = pickle.load(f)
                logger.debug("[Config] User datas loaded.")
        except FileNotFoundError:
            logger.debug("[Config] User datas file not found, ignore.")
        except Exception as e:
            logger.warning("[Config] User datas error: {}".format(e))
            self.user_datas = {}

    def save_user_datas(self):
        try:
            # SECURITY: pickle.dump output should only be loaded by this same
            # process. See note on load_user_datas() above.
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "wb") as f:
                pickle.dump(self.user_datas, f)
                logger.info("[Config] User datas saved.")
        except Exception as e:
            logger.info("[Config] User datas error: {}".format(e))


config = Config()


def _mask_value(val):
    """Mask a sensitive string value, keeping first 3 and last 3 chars."""
    if not isinstance(val, str) or len(val) <= 8:
        return val
    return val[0:3] + "*" * 5 + val[-3:]


def _mask_sensitive_recursive(obj):
    """Recursively mask values whose keys contain 'key' or 'secret'."""
    if isinstance(obj, dict):
        masked = {}
        for k, v in obj.items():
            if ("key" in k or "secret" in k) and isinstance(v, str):
                masked[k] = _mask_value(v)
            else:
                masked[k] = _mask_sensitive_recursive(v)
        return masked
    elif isinstance(obj, list):
        return [_mask_sensitive_recursive(item) for item in obj]
    return obj


def drag_sensitive(config):
    try:
        if isinstance(config, str):
            conf_dict: dict = json.loads(config)
            conf_dict_copy = _mask_sensitive_recursive(conf_dict)
            return json.dumps(conf_dict_copy, indent=4)

        elif isinstance(config, dict):
            return _mask_sensitive_recursive(config)
    except ValueError:
        # Unparseable config string (e.g. a corrupted config.json). This is
        # handled and reported by load_config's self-heal path, so don't scare
        # the log with a full traceback here — just return it unmasked.
        return config
    except Exception as e:
        logger.exception(e)
        return config
    return config


def _quarantine_corrupted_config(config_path):
    """Move a corrupted config.json aside so startup can reinitialize cleanly.

    Renames the bad file to ``config.json.corrupted-<timestamp>`` (kept for
    inspection rather than deleted) and never raises: recovery must proceed even
    if the rename fails, in which case the fresh config is written over it.
    """
    try:
        backup_path = "{}.corrupted-{}".format(config_path, time.strftime("%Y%m%d%H%M%S"))
        os.replace(config_path, backup_path)
        logger.warning("[INIT] backed up corrupted config to {}".format(backup_path))
    except Exception as e:
        logger.warning("[INIT] failed to back up corrupted config: {}".format(e))


# Config keys mirrored into environment variables at startup so that
# subprocesses (e.g. shell skill scripts) can read them directly.
CONFIG_TO_ENV = {
    "litellm_api_key": "LITELLM_API_KEY",
    "litellm_api_base": "LITELLM_API_BASE",
    "model": "LITELLM_MODEL",
    "image_model": "LITELLM_IMAGE_MODEL",
    "vision_model": "LITELLM_VISION_MODEL",
    "embedding_model": "LITELLM_EMBEDDING_MODEL",
    "asr_model": "LITELLM_ASR_MODEL",
    "tts_model": "LITELLM_TTS_MODEL",
}


def load_config():
    global config

    # print ASCII logo
    logger.info(" __  __       _       ")
    logger.info("|  \\/  | __ _(_) __ _ ")
    logger.info("| |\\/| |/ _` | |/ _` |")
    logger.info("| |  | | (_| | | (_| |")
    logger.info("|_|  |_|\\__,_|_|\\__,_|")
    logger.info("")
    logger.info("")
    # User config lives in the data root: source deployments use CWD (./), while
    # the desktop build points MAIA_DATA_DIR at ~/.maia so config survives updates.
    user_config_path = os.path.join(get_data_root(), "config.json")
    config_path = user_config_path
    if not os.path.exists(config_path):
        logger.info("config file not found, falling back to config-template.json")
        config_path = get_config_template_path()

    config_str = read_file(config_path)
    logger.debug("[INIT] config str: {}".format(drag_sensitive(config_str)))

    # Deserialize the json string into a dict.
    # `object_pairs_hook` lets us catch users who accidentally typed the
    # same key twice (e.g. two `"tools"` blocks) — json.loads would
    # otherwise silently drop all but the last occurrence.
    #
    # Self-heal a corrupted user config.json instead of crashing on startup —
    # but ONLY for the packaged desktop client (MAIA_DESKTOP=1). A truncated or
    # invalid file (e.g. a bad write during a previous update) would otherwise
    # make json.loads raise and strand the desktop app on "Initialization
    # Failed" forever, with no way for an end user to recover short of manually
    # deleting the file. Source deployments deliberately keep the original
    # behavior (raise): a developer editing config.json wants a clear error to
    # fix, not to have their file silently backed up and replaced by defaults.
    desktop_mode = os.environ.get("MAIA_DESKTOP") == "1"
    try:
        config = Config(json.loads(config_str, object_pairs_hook=_merge_duplicate_keys))
    except ValueError as parse_err:
        if not desktop_mode or config_path != user_config_path:
            # Source run, or the bundled template itself is broken (a packaging
            # bug we can't heal by falling back further) — surface it.
            raise
        logger.error(
            "[INIT] config.json is corrupted ({}); backing it up and "
            "reinitializing from config-template.json".format(parse_err)
        )
        _quarantine_corrupted_config(user_config_path)
        template_str = read_file(get_config_template_path())
        config = Config(json.loads(template_str, object_pairs_hook=_merge_duplicate_keys))
        # Persist the fresh config so the recovered defaults survive the next
        # launch (and the app has a valid file to write user changes back into).
        try:
            with open(user_config_path, mode="w", encoding="utf-8") as f:
                json.dump(dict(config), f, ensure_ascii=False, indent=2)
        except Exception as write_err:
            # A failed rewrite must not re-crash startup: we already hold a valid
            # in-memory config, so run with it and retry the write next launch.
            logger.warning("[INIT] failed to write recovered config.json: {}".format(write_err))

    # Migrate legacy singular keys (`tool`, `skill`) into the canonical
    # plural buckets so the rest of the codebase only reads one schema.
    # Deep-merge so existing `tools`/`skills` entries are preserved and
    # only missing namespaces are filled in from the legacy section.
    _merge_legacy_namespace(config, legacy="tool",  canonical="tools")
    _merge_legacy_namespace(config, legacy="skill", canonical="skills")
    # A backup model configured before the fallback chain must survive the
    # upgrade, so normalize it into the current shape before anything reads it.
    _migrate_chat_fallback(config)

    # Fresh desktop installs default to the stricter "workspace-write"; every
    # other case keeps the template's "full-access". A packaged client only
    # lacks config.json on its very first launch (config_path fell back to the
    # bundled template) — once the user configures anything (e.g. a model) the
    # console persists config.json, so an existing install always has it and is
    # never silently tightened by an upgrade. Non-desktop (docker, source) is
    # untouched. Placed before the env override so AGENT_PERMISSION_MODE still
    # wins if explicitly set.
    if os.environ.get("MAIA_DESKTOP") == "1" and config_path != user_config_path:
        config["agent_permission_mode"] = "workspace-write"

    # override config with environment variables.
    # Some online deployment platforms (e.g. Railway) deploy project from github directly. So you shouldn't put your secrets like api key in a config file, instead use environment variables to override the default config.
    for name, value in os.environ.items():
        name = name.lower()
        # skip comment fields starting with an underscore
        if name.startswith("_"):
            continue
        # A blank value is a placeholder (docker-compose lists every key as
        # ''), not a request to wipe what the user saved in config.json.
        if value == "":
            continue
        if name in available_setting:
            logger.info("[INIT] override config by environ args: {}={}".format(
                name, drag_sensitive({name: value})[name]))
            try:
                # SECURITY: Use ast.literal_eval instead of eval().
                # ast.literal_eval only parses Python literals (strings, numbers,
                # tuples, lists, dicts, booleans, None) and CANNOT execute
                # arbitrary code, preventing environment-variable injection.
                config[name] = ast.literal_eval(value)
            except Exception:
                # literal_eval can raise ValueError/SyntaxError for non-literal
                # strings, but also TypeError/RecursionError on malformed input
                # (e.g. unhashable dict keys); catch broadly to avoid crashing
                # startup, and fall back to treating the value as a plain string.
                # Numeric keys reject it instead: a string there fails much later.
                if value.lower() == "false":
                    config[name] = False
                elif value.lower() == "true":
                    config[name] = True
                elif type(available_setting[name]) in (int, float):
                    logger.warning("[INIT] ignoring environment override {}: not a {}".format(
                        name, type(available_setting[name]).__name__))
                else:
                    config[name] = value

    if config.get("debug", False):
        logger.setLevel(logging.DEBUG)
        logger.debug("[INIT] set log level to DEBUG")

    # The registry caches profiles on first access. Anything that resolved a
    # path before this point cached the pre-config workspace, so drop it.
    # Rebuilding here also surfaces an invalid "agents" block at startup
    # rather than on the first inbound message.
    from agent.registry import get_agent_registry, set_agent_registry

    set_agent_registry(None)
    agent_registry = get_agent_registry()

    # Resolve the global UI language as early as possible so that every
    # downstream layer (logs, CLI, agent prompts, channel replies) shares it.
    resolved_lang = i18n.resolve_language(config.get("maia_lang", "auto"))

    logger.info("[INIT] load config: {}".format(drag_sensitive(config)))

    # print system initialization info
    logger.info("[INIT] ========================================")
    logger.info("[INIT] System Initialization")
    logger.info("[INIT] ========================================")
    logger.info("[INIT] Language: {}".format(resolved_lang))
    logger.info("[INIT] Channel: {}".format(config.get("channel_type", "unknown")))
    logger.info("[INIT] Model: {}".format(config.get("model", "unknown")))
    _base = config.get("litellm_api_base") or ""
    if not (isinstance(_base, str) and _base.strip().rstrip("/").endswith("/v1")):
        logger.error(
            "[INIT] litellm_api_base is missing or does not end with /v1; "
            "model calls will fail until it is set"
        )

    # Agent mode info
    if config.get("agent", True):
        profiles = agent_registry.list(include_disabled=False)
        if len(profiles) == 1:
            logger.info("[INIT] Mode: Agent (workspace: {})".format(profiles[0].workspace))
        else:
            logger.info("[INIT] Mode: Agent ({} agents)".format(len(profiles)))
            for profile in profiles:
                marker = " (default)" if profile.id == agent_registry.default_agent_id else ""
                logger.info(
                    "[INIT]   - {}{}: {}".format(profile.id, marker, profile.workspace)
                )
    else:
        logger.info("[INIT] Mode: Chat (set \"agent\":true in config.json to enable Agent mode)")

    logger.info("[INIT] Debug: {}".format(config.get("debug", False)))
    logger.info("[INIT] ========================================")

    # Sync selected config values to environment variables so that
    # subprocesses (e.g. shell skill scripts) can access them directly.
    # Existing env vars are NOT overwritten (env takes precedence).
    injected = 0
    for conf_key, env_key in CONFIG_TO_ENV.items():
        if not os.environ.get(env_key):
            val = config.get(conf_key, "")
            if val:
                os.environ[env_key] = str(val)
                injected += 1

    injected += _sync_skill_config_to_env(config.get("skills", {}))
    injected += sync_image_generation_custom_provider_env(config)

    if injected:
        logger.info("[INIT] Synced {} config values to environment variables".format(injected))

    config.load_user_datas()


def _merge_duplicate_keys(pairs):
    """Merge duplicate keys with the app's existing diagnostic behavior."""
    def report_duplicates(unique):
        # logger may not be wired yet — fall back to print so we never lose the warning.
        try:
            logger.warning("[INIT] config.json has duplicate keys (merged): %s", unique)
        except Exception:
            print("[INIT] config.json has duplicate keys (merged):", unique)

    return merge_duplicate_keys(pairs, on_duplicates=report_duplicates)


def _migrate_chat_fallback(cfg) -> None:
    """Upgrade the single-model ``chat_fallback`` to the chain shape.

    Before the fallback chain, ``chat_fallback`` held one ``provider`` and one
    ``model`` (plus a ``max_switches`` cap). An existing config with a backup
    model configured would otherwise load as an empty chain — silently
    disabling a safety net the user had turned on — so fold those fields into
    a one-entry chain here. ``max_switches`` is dropped rather than carried
    over: the chain length is the new bound, and the old counter never
    actually bounded anything (the fallback was already sticky for a run).
    """
    raw = cfg.get("chat_fallback")
    if not isinstance(raw, dict):
        return
    chain = raw.get("chain")
    if isinstance(chain, list):
        raw.pop("max_switches", None)
        return
    provider = (raw.get("provider") or "").strip()
    model = (raw.get("model") or "").strip()
    entry = []
    if provider and model:
        entry = [{"provider": provider, "model": model}]
    raw.pop("provider", None)
    raw.pop("model", None)
    raw.pop("max_switches", None)
    raw["chain"] = entry
    if entry:
        logger.warning(
            "[INIT] chat_fallback.provider/model is deprecated; migrated into "
            "chat_fallback.chain. Please rewrite it as a list in config.json."
        )


def _merge_legacy_namespace(cfg, legacy: str, canonical: str) -> None:
    """Fold deprecated singular keys (``tool`` / ``skill``) into their plural
    canonical counterparts at load time. Canonical entries always win."""
    legacy_section = cfg.get(legacy)
    if not isinstance(legacy_section, dict) or not legacy_section:
        cfg.pop(legacy, None)
        return
    canonical_section = cfg.get(canonical)
    if not isinstance(canonical_section, dict):
        canonical_section = {}
    merged_keys = []
    for name, val in legacy_section.items():
        if name in canonical_section:
            if isinstance(canonical_section[name], dict) and isinstance(val, dict):
                for sub_key, sub_val in val.items():
                    if (
                        sub_key in canonical_section[name]
                        and isinstance(canonical_section[name][sub_key], dict)
                        and isinstance(sub_val, dict)
                    ):
                        _deep_merge_dicts(sub_val, canonical_section[name][sub_key])
                        canonical_section[name][sub_key] = sub_val
                    else:
                        canonical_section[name].setdefault(sub_key, sub_val)
            continue
        canonical_section[name] = val
        merged_keys.append(name)
    cfg[canonical] = canonical_section
    cfg.pop(legacy, None)
    if merged_keys:
        logger.warning(
            "[INIT] Legacy config key '{}' is deprecated; merged into '{}': {}. "
            "Please rename '{}' to '{}' in your config.json.".format(
                legacy, canonical, merged_keys, legacy, canonical,
            )
        )


def _sync_skill_config_to_env(skill_section) -> int:
    """Flatten skill-namespaced config into environment variables.

    Mapping rule: ``config["skills"][<name>][<key>]`` -> ``SKILL_<NAME>_<KEY>``
    (e.g. ``skills["image-generation"].model`` -> ``SKILL_IMAGE_GENERATION_MODEL``).

    This lets subprocess-based skill scripts read their own settings without
    importing project code. Existing env vars are NOT overwritten so the
    real environment always wins.

    Returns the number of variables actually injected.
    """
    if not isinstance(skill_section, dict):
        return 0
    injected = 0
    for skill_name, skill_conf in skill_section.items():
        if not isinstance(skill_conf, dict):
            continue
        name_part = str(skill_name).replace("-", "_").upper()
        for key, val in skill_conf.items():
            if val is None or val == "":
                continue
            env_key = "SKILL_{}_{}".format(name_part, str(key).upper())
            if env_key in os.environ:
                continue
            os.environ[env_key] = str(val)
            injected += 1
    return injected


def sync_image_generation_custom_provider_env(
    config_data,
    overwrite=False,
) -> int:
    """No custom image providers. Image generation uses the LiteLLM endpoint."""
    del config_data, overwrite
    os.environ.pop("SKILL_IMAGE_GENERATION_CUSTOM_PROVIDER", None)
    return 0


def get_root():
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_root():
    """Directory holding bundled read-only resources (e.g. config-template.json).

    Under PyInstaller, data files live in sys._MEIPASS (the onedir _internal
    folder), which differs from get_root() — the latter is used for writable
    user data and should stay next to the executable, not inside the bundle.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_config_template_path():
    """Path to the bundled config-template.json.

    Resolved via get_resource_root() so it works both from source and from a
    frozen (PyInstaller) bundle, where the template ships inside sys._MEIPASS
    and CWD may differ.
    """
    template_path = os.path.join(get_resource_root(), "config-template.json")
    return template_path if os.path.exists(template_path) else "./config-template.json"


def read_config_template():
    """Load config-template.json as a dict; returns {} when unreadable."""
    try:
        return json.loads(read_file(get_config_template_path()))
    except Exception as e:
        logger.warning("[Config] failed to read config template: {}".format(e))
        return {}


def get_data_root():
    """Directory for writable user data (config.json, user_datas.pkl, run.log).

    The desktop build sets MAIA_DATA_DIR (e.g. ~/.maia) so data lives in the
    user's home rather than inside the read-only app bundle and survives app
    updates. When unset (source deployment), it falls back to get_root(), so
    existing behavior is unchanged.
    """
    data_dir = os.environ.get("MAIA_DATA_DIR")
    if data_dir:
        data_dir = os.path.expanduser(data_dir)
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    return get_root()


def read_file(path):
    with open(path, mode="r", encoding="utf-8-sig") as f:
        return f.read()


def conf():
    return config


def get_appdata_dir():
    data_path = os.path.join(get_data_root(), conf().get("appdata_dir", ""))
    if not os.path.exists(data_path):
        logger.info("[INIT] data path not exists, create it: {}".format(data_path))
        os.makedirs(data_path, exist_ok=True)
    return data_path


def subscribe_msg():
    prefixes = conf().get("single_chat_prefix") or [""]
    trigger_prefix = prefixes[0]
    msg = conf().get("subscribe_msg", "")
    return msg.format(trigger_prefix=trigger_prefix)


# global plugin config
plugin_config = {}


def write_plugin_config(pconf: dict):
    """
    Write the global plugin config.
    :param pconf: the full plugin config
    """
    global plugin_config
    for k in pconf:
        plugin_config[k.lower()] = pconf[k]

def remove_plugin_config(name: str):
    """
    Remove the global config of a plugin pending reload.
    :param name: name of the plugin to reload
    """
    global plugin_config
    plugin_config.pop(name.lower(), None)


def pconf(plugin_name: str) -> dict:
    """
    Get the config for a plugin by name.
    :param plugin_name: plugin name
    :return: the plugin's config
    """
    return plugin_config.get(plugin_name.lower())


# global config holding globally-effective state
global_config = {"admin_users": []}
