# encoding:utf-8

import os
import random
import string
import logging
from typing import Tuple

import plugins
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.atomic_write import write_json_atomic
from config import conf, load_config, global_config
from plugins import *


COMMANDS = {
    "help": {
        "alias": ["help"],
        "desc": "Show this help",
    },
    "helpp": {
        "alias": ["help"],
        "args": ["plugin"],
        "desc": "Show detailed help for one plugin",
    },
    "auth": {
        "alias": ["auth"],
        "args": ["password"],
        "desc": "Authenticate as an admin",
    },
    "model": {
        "alias": ["model"],
        "desc": "Show or set the global model",
    },
    "set_openai_api_key": {
        "alias": ["set_openai_api_key"],
        "args": ["api_key"],
        "desc": "Set your OpenAI API key",
    },
    "reset_openai_api_key": {
        "alias": ["reset_openai_api_key"],
        "desc": "Reset to the default API key",
    },
    "set_gpt_model": {
        "alias": ["set_gpt_model"],
        "desc": "Set your private model",
    },
    "reset_gpt_model": {
        "alias": ["reset_gpt_model"],
        "desc": "Reset your private model",
    },
    "gpt_model": {
        "alias": ["gpt_model"],
        "desc": "Show the model you are using",
    },
    "id": {
        "alias": ["id"],
        "desc": "Show your user id",
    },
    "reset": {
        "alias": ["reset"],
        "desc": "Reset the session",
    },
}

ADMIN_COMMANDS = {
    "resume": {
        "alias": ["resume"],
        "desc": "Resume service",
    },
    "stop": {
        "alias": ["stop"],
        "desc": "Pause service",
    },
    "reconf": {
        "alias": ["reconf"],
        "desc": "Reload config (plugin config is not included)",
    },
    "resetall": {
        "alias": ["resetall"],
        "desc": "Reset every session",
    },
    "scanp": {
        "alias": ["scanp"],
        "desc": "Scan the plugin directory for new plugins",
    },
    "plist": {
        "alias": ["plist"],
        "desc": "Print the plugin list",
    },
    "setpri": {
        "alias": ["setpri"],
        "args": ["plugin", "priority"],
        "desc": "Set a plugin's priority. A higher number runs first.",
    },
    "reloadp": {
        "alias": ["reloadp"],
        "args": ["plugin"],
        "desc": "Reload one plugin's config",
    },
    "enablep": {
        "alias": ["enablep"],
        "args": ["plugin"],
        "desc": "Enable a plugin",
    },
    "disablep": {
        "alias": ["disablep"],
        "args": ["plugin"],
        "desc": "Disable a plugin",
    },
    "installp": {
        "alias": ["installp"],
        "args": ["repo_or_name"],
        "desc": "Install a plugin",
    },
    "uninstallp": {
        "alias": ["uninstallp"],
        "args": ["plugin"],
        "desc": "Uninstall a plugin",
    },
    "updatep": {
        "alias": ["updatep"],
        "args": ["plugin"],
        "desc": "Update a plugin",
    },
    "debug": {
        "alias": ["debug"],
        "desc": "Toggle debug logging",
    },
}



def get_help_text(isadmin, isgroup):
    help_text = "Commands\n"
    for cmd, info in COMMANDS.items():
        if cmd in ["auth", "set_openai_api_key", "reset_openai_api_key", "set_gpt_model", "reset_gpt_model", "gpt_model"]:  
            continue
        raw_ct = conf().get("channel_type", "web")
        active_channels = raw_ct if isinstance(raw_ct, list) else [c.strip() for c in str(raw_ct).split(",")]
        if cmd == "id" and not any(c in ["wxy", "wechatmp"] for c in active_channels):
            continue
        alias = ["#" + a for a in info["alias"][:1]]
        help_text += f"{','.join(alias)} "
        if "args" in info:
            args = [a for a in info["args"]]
            help_text += f"{' '.join(args)}"
        help_text += f": {info['desc']}\n"

    
    plugins = PluginManager().list_plugins()
    help_text += "\nPlugins"
    for plugin in plugins:
        if plugins[plugin].enabled and not plugins[plugin].hidden:
            namecn = plugins[plugin].namecn
            help_text += "\n%s: " % namecn
            help_text += PluginManager().instances[plugin].get_help_text(verbose=False).strip()

    if ADMIN_COMMANDS and isadmin:
        help_text += "\n\nAdmin commands:\n"
        for cmd, info in ADMIN_COMMANDS.items():
            alias = ["#" + a for a in info["alias"][:1]]
            help_text += f"{','.join(alias)} "
            if "args" in info:
                args = [a for a in info["args"]]
                help_text += f"{' '.join(args)}"
            help_text += f": {info['desc']}\n"
    return help_text


# Written to config.json when it is missing or incomplete, and used as the
# fallback for a config that is empty or only half-filled in.
DEFAULT_CONFIG = {"password": "", "admin_users": []}


@plugins.register(
    name="Godcmd",
    desire_priority=999,
    hidden=True,
    desc="Adds user and admin commands. Load this plugin first. After the first run, set an admin password in the plugin config to sign in.",
    version="1.0",
    author="lanvent",
)
class Godcmd(Plugin):
    def __init__(self):
        super().__init__()

        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        gconf = super().load_config()
        # A config.json that exists but is empty or half-filled in used to reach
        # gconf["password"]/["admin_users"] as {} and raise KeyError.
        # `activate_plugins` answers a plugin that fails to initialise by
        # disabling it and *persisting* enabled=false, so the command plugin
        # stayed off across restarts even after the file was put right. Fill in
        # the documented defaults and write the repaired config out instead.
        if not isinstance(gconf, dict) or not all(k in gconf for k in DEFAULT_CONFIG):
            gconf = {**DEFAULT_CONFIG, **(gconf if isinstance(gconf, dict) else {})}
            try:
                write_json_atomic(config_path, gconf)
            except OSError as e:
                # Repairing the file on disk is a convenience; the defaults above
                # are enough to run. Raising here would reach activate_plugins,
                # which persists enabled=false — the very outcome this fallback
                # exists to avoid — so a plugin directory that is read-only
                # (packaged builds) or a full disk must not take the plugin down.
                logger.warning(f"[Godcmd] cannot write {config_path}: {e}")
        if gconf["password"] == "":
            self.temp_password = "".join(random.sample(string.digits, 4))
            logger.info("[Godcmd] No password is set. Temporary password for this run: %s." % self.temp_password)
        else:
            self.temp_password = None
        custom_commands = conf().get("clear_memory_commands", [])
        for custom_command in custom_commands:
            if custom_command and custom_command.startswith("#"):
                custom_command = custom_command[1:]
                if custom_command and custom_command not in COMMANDS["reset"]["alias"]:
                    COMMANDS["reset"]["alias"].append(custom_command)

        self.password = gconf["password"]
        self.admin_users = gconf["admin_users"]
        global_config["admin_users"] = self.admin_users
        self.isrunning = True  

        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.debug("[Godcmd] inited")

    def on_handle_context(self, e_context: EventContext):
        context_type = e_context["context"].type
        if context_type != ContextType.TEXT:
            if not self.isrunning:
                e_context.action = EventAction.BREAK_PASS
            return

        content = e_context["context"].content
        logger.debug("[Godcmd] on_handle_context. content: %s" % content)
        if content.startswith("#"):
            if len(content) == 1:
                reply = Reply()
                reply.type = ReplyType.ERROR
                reply.content = "Empty command. Enter #help to list commands.\n"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            # msg = e_context['context']['msg']
            channel = e_context["channel"]
            user = e_context["context"]["receiver"]
            session_id = e_context["context"]["session_id"]
            isgroup = e_context["context"].get("isgroup", False)
            bottype = Bridge().get_bot_type("chat")
            bot = Bridge().get_bot("chat")
            
            command_parts = content[1:].strip().split()
            cmd = command_parts[0]
            args = command_parts[1:]
            isadmin = False
            if user in self.admin_users:
                isadmin = True
            ok = False
            result = "string"
            if any(cmd in info["alias"] for info in COMMANDS.values()):
                cmd = next(c for c, info in COMMANDS.items() if cmd in info["alias"])
                if cmd == "auth":
                    ok, result = self.authenticate(user, args, isadmin, isgroup)
                elif cmd == "help" or cmd == "helpp":
                    if len(args) == 0:
                        ok, result = True, get_help_text(isadmin, isgroup)
                    else:
                        # This can replace the helpp command
                        plugins = PluginManager().list_plugins()
                        query_name = args[0].upper()
                        # search name and namecn
                        for name, plugincls in plugins.items():
                            if not plugincls.enabled:
                                continue
                            if query_name == name or query_name == plugincls.namecn:
                                ok, result = True, PluginManager().instances[name].get_help_text(isgroup=isgroup, isadmin=isadmin, verbose=True)
                                break
                        if not ok:
                            result = "Plugin does not exist or is not enabled"
                elif cmd == "model":
                    if not isadmin and not self.is_admin_in_group(e_context["context"]):
                        ok, result = False, "Admin permission is required"
                    elif len(args) == 0:
                        model = conf().get("model") or const.GPT35
                        ok, result = True, "Current model: " + str(model)
                    elif len(args) == 1:
                        model_id = args[0].strip()
                        if not model_id:
                            ok, result = False, "Provide a model name"
                        else:
                            conf()["model"] = self.model_mapping(model_id)
                            Bridge().reset_bot()
                            model = conf().get("model") or model_id
                            ok, result = True, "Model set to: " + str(model)
                    else:
                        ok, result = False, "Only one model name is allowed"
                elif cmd == "id":
                    ok, result = True, user
                elif cmd == "set_openai_api_key":
                    if len(args) == 1:
                        user_data = conf().get_user_data(user)
                        user_data["openai_api_key"] = args[0]
                        ok, result = True, "Your OpenAI API key is set to " + args[0]
                    else:
                        ok, result = False, "Provide an API key"
                elif cmd == "reset_openai_api_key":
                    try:
                        user_data = conf().get_user_data(user)
                        user_data.pop("openai_api_key")
                        ok, result = True, "Your OpenAI API key has been cleared"
                    except Exception:
                        ok, result = False, "You have not set a private API key"
                elif cmd == "set_gpt_model":
                    if len(args) == 1:
                        user_data = conf().get_user_data(user)
                        user_data["gpt_model"] = args[0]
                        ok, result = True, "Your model is set to " + args[0]
                    else:
                        ok, result = False, "Provide a model"
                elif cmd == "gpt_model":
                    user_data = conf().get_user_data(user)
                    model = conf().get("model")
                    if "gpt_model" in user_data:
                        model = user_data["gpt_model"]
                    ok, result = True, "Your model is " + str(model)
                elif cmd == "reset_gpt_model":
                    try:
                        user_data = conf().get_user_data(user)
                        user_data.pop("gpt_model")
                        ok, result = True, "Your model has been reset"
                    except Exception:
                        ok, result = False, "You have not set a private model"
                elif cmd == "reset":
                    if bottype in [const.LITELLM, const.OPEN_AI, const.OPENAI, const.CHATGPT, const.CHATGPTONAZURE, const.BAIDU, const.QIANFAN, const.XUNFEI, const.QWEN, const.QWEN_DASHSCOPE, const.GEMINI, const.ZHIPU_AI, const.CLAUDEAPI]:
                        bot.sessions.clear_session(session_id)
                        if Bridge().chat_bots.get(bottype):
                            Bridge().chat_bots.get(bottype).sessions.clear_session(session_id)
                        channel.cancel_session(
                            session_id, agent_id=e_context["context"].get("agent_id")
                        )
                        ok, result = True, "Session reset"
                    else:
                        ok, result = False, "This bot cannot reset the session"
                logger.debug("[Godcmd] command: %s by %s" % (cmd, user))
            elif any(cmd in info["alias"] for info in ADMIN_COMMANDS.values()):
                if isadmin:
                    if isgroup:
                        ok, result = False, "Admin commands cannot run in a group"
                    else:
                        cmd = next(c for c, info in ADMIN_COMMANDS.items() if cmd in info["alias"])
                        if cmd == "stop":
                            self.isrunning = False
                            ok, result = True, "Service paused"
                        elif cmd == "resume":
                            self.isrunning = True
                            ok, result = True, "Service resumed"
                        elif cmd == "reconf":
                            load_config()
                            ok, result = True, "Config reloaded"
                        elif cmd == "resetall":
                            if bottype in [const.LITELLM, const.OPEN_AI, const.OPENAI, const.CHATGPT, const.CHATGPTONAZURE,
                                           const.BAIDU, const.QIANFAN, const.XUNFEI, const.QWEN, const.QWEN_DASHSCOPE, const.GEMINI, const.ZHIPU_AI, const.MOONSHOT,
                                           const.MODELSCOPE]:
                                channel.cancel_all_session()
                                bot.sessions.clear_all_session()
                                ok, result = True, "All sessions reset"
                            else:
                                ok, result = False, "This bot cannot reset the session"
                        elif cmd == "debug":
                            if logger.getEffectiveLevel() == logging.DEBUG:  
                                logger.setLevel(logging.INFO)
                                ok, result = True, "Debug mode off"
                            else:
                                logger.setLevel(logging.DEBUG)
                                ok, result = True, "Debug mode on"
                        elif cmd == "plist":
                            plugins = PluginManager().list_plugins()
                            ok = True
                            result = "Plugins:\n"
                            for name, plugincls in plugins.items():
                                result += f"{plugincls.name}_v{plugincls.version} {plugincls.priority} - "
                                if plugincls.enabled:
                                    result += "enabled\n"
                                else:
                                    result += "disabled\n"
                        elif cmd == "scanp":
                            new_plugins = PluginManager().scan_plugins()
                            ok, result = True, "Plugin scan finished"
                            PluginManager().activate_plugins()
                            if len(new_plugins) > 0:
                                result += "\nNew plugins:\n"
                                result += "\n".join([f"{p.name}_v{p.version}" for p in new_plugins])
                            else:
                                result += ", no new plugins"
                        elif cmd == "setpri":
                            if len(args) != 2:
                                ok, result = False, "Provide a plugin name and a priority"
                            else:
                                try:
                                    priority = int(args[1])
                                except ValueError:
                                    ok, result = False, f"Priority {args[1]} is invalid. Use an integer"
                                else:
                                    ok = PluginManager().set_plugin_priority(args[0], priority)
                                    if ok:
                                        result = f"Plugin {args[0]} priority set to {args[1]}"
                                    else:
                                        result = "Plugin does not exist"
                        elif cmd == "reloadp":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name"
                            else:
                                ok = PluginManager().reload_plugin(args[0])
                                if ok:
                                    result = "Plugin config reloaded"
                                else:
                                    result = "Plugin does not exist"
                        elif cmd == "enablep":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name"
                            else:
                                ok, result = PluginManager().enable_plugin(args[0])
                        elif cmd == "disablep":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name"
                            else:
                                ok = PluginManager().disable_plugin(args[0])
                                if ok:
                                    result = "Plugin disabled"
                                else:
                                    result = "Plugin does not exist"
                        elif cmd == "installp":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name or a repository URL ending in .git"
                            else:
                                ok, result = PluginManager().install_plugin(args[0])
                        elif cmd == "uninstallp":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name"
                            else:
                                ok, result = PluginManager().uninstall_plugin(args[0])
                        elif cmd == "updatep":
                            if len(args) != 1:
                                ok, result = False, "Provide a plugin name"
                            else:
                                ok, result = PluginManager().update_plugin(args[0])
                        logger.debug("[Godcmd] admin command: %s by %s" % (cmd, user))
                else:
                    ok, result = False, "Admin permission is required for this command"
            else:
                trigger_prefix = conf().get("plugin_trigger_prefix", "$")
                if trigger_prefix == "#":  
                    return
                ok, result = False, f"Unknown command: {cmd}\nEnter #help to list commands.\n"

            reply = Reply()
            if ok:
                reply.type = ReplyType.INFO
            else:
                reply.type = ReplyType.ERROR
            reply.content = result
            e_context["reply"] = reply

            e_context.action = EventAction.BREAK_PASS  
        elif not self.isrunning:
            e_context.action = EventAction.BREAK_PASS

    def authenticate(self, userid, args, isadmin, isgroup) -> Tuple[bool, str]:
        if isgroup:
            return False, "Do not authenticate in a group"

        if isadmin:
            return False, "This account is already an admin"

        if len(args) != 1:
            return False, "Provide the password"

        password = args[0]
        if password == self.password:
            self.admin_users.append(userid)
            global_config["admin_users"].append(userid)
            return True, "Authenticated"
        elif password == self.temp_password:
            self.admin_users.append(userid)
            global_config["admin_users"].append(userid)
            return True, "Authenticated. Set a password soon."
        else:
            return False, "Authentication failed"

    def get_help_text(self, isadmin=False, isgroup=False, **kwargs):
        return get_help_text(isadmin, isgroup)


    def is_admin_in_group(self, context):
        if context["isgroup"]:
            return context.kwargs.get("msg").actual_user_id in global_config["admin_users"]
        return False


    def model_mapping(self, model) -> str:
        if model == "gpt-4-turbo":
            return const.GPT4_TURBO_PREVIEW
        return model

    def reload(self):
        gconf = pconf(self.name)
        if gconf:
            if gconf.get("password"):
                self.password = gconf["password"]
            if gconf.get("admin_users"):
                self.admin_users = gconf["admin_users"]
