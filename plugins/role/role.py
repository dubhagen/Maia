# encoding:utf-8

import json
import os

import plugins
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.log import logger
from config import conf
from plugins import *


class RolePlay:
    def __init__(self, bot, sessionid, desc, wrapper=None):
        self.bot = bot
        self.sessionid = sessionid
        self.wrapper = wrapper or "%s"  
        self.desc = desc
        self.bot.sessions.build_session(self.sessionid, system_prompt=self.desc)

    def reset(self):
        self.bot.sessions.clear_session(self.sessionid)

    def action(self, user_action):
        session = self.bot.sessions.build_session(self.sessionid)
        if session.system_prompt != self.desc:  
            session.set_system_prompt(self.desc)
        prompt = self.wrapper % user_action
        return prompt


@plugins.register(
    name="Role",
    desire_priority=0,
    namecn="Role",
    desc="Set a preset role for the bot",
    version="1.0",
    author="lanvent",
)
class Role(Plugin):
    def __init__(self):
        super().__init__()
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "roles.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.tags = {tag: (desc, []) for tag, desc in config["tags"].items()}
                self.roles = {}
                for role in config["roles"]:
                    self.roles[role["title"].lower()] = role
                    for tag in role["tags"]:
                        if tag not in self.tags:
                            logger.warning(f"[Role] unknown tag {tag} ")
                            self.tags[tag] = (tag, [])
                        self.tags[tag][1].append(role)

                
                roles_dir = os.path.join(curdir, "roles")
                if os.path.isdir(roles_dir):
                    for fname in sorted(os.listdir(roles_dir)):
                        if fname.endswith(".json"):
                            self._load_role_file(os.path.join(roles_dir, fname))

                for tag in list(self.tags.keys()):
                    if len(self.tags[tag][1]) == 0:
                        logger.debug(f"[Role] no role found for tag {tag} ")
                        del self.tags[tag]

            if len(self.roles) == 0:
                raise Exception("no role found")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.roleplays = {}
            logger.debug("[Role] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[Role] init failed, {config_path} not found. See plugins/role.")
            else:
                logger.warn("[Role] init failed. See plugins/role.")
            raise e

    def _load_role_file(self, filepath):
        """Load one role file from roles/. A matching title replaces a built-in role."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                role = json.load(f)
            tags = role.get("tags", [])
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ValueError("role tags must be a list of strings")
            title_lower = role["title"].lower()
            if title_lower in self.roles:
                old_tags = self.roles[title_lower].get("tags", [])
                for tag in old_tags:
                    if tag in self.tags:
                        description, members = self.tags[tag]
                        self.tags[tag] = (description, [r for r in members if r["title"].lower() != title_lower])
                logger.info(f"[Role] overridden: {role['title']}")
            self.roles[title_lower] = role
            for tag in role.get("tags", []):
                if tag not in self.tags:
                    self.tags[tag] = (tag, [])
                self.tags[tag][1].append(role)
            logger.debug(f"[Role] loaded: {role['title']} from {os.path.basename(filepath)}")
        except Exception as e:
            logger.warn(f"[Role] failed to load {filepath}: {e}")

    def get_role(self, name, find_closest=True, min_sim=0.35):
        name = name.lower()
        found_role = None
        if name in self.roles:
            found_role = name
        elif find_closest:
            import difflib

            def str_simularity(a, b):
                return difflib.SequenceMatcher(None, a, b).ratio()

            max_sim = min_sim
            max_role = None
            for role in self.roles:
                sim = str_simularity(name, role)
                if sim >= max_sim:
                    max_sim = sim
                    max_role = role
            found_role = max_role
        return found_role

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        btype = Bridge().get_bot_type("chat")
        if btype != const.LITELLM:
            logger.debug(f"Unsupported bot: {btype}")
            return
        bot = Bridge().get_bot("chat")
        content = e_context["context"].content[:]
        if not content.strip():
            return
        clist = e_context["context"].content.split(maxsplit=1)
        sessionid = e_context["context"]["session_id"]
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        trigger = f"{trigger_prefix}role"
        if clist[0].lower() == trigger:
            argument = clist[1].strip() if len(clist) > 1 else ""
            lowered = argument.lower()
            if argument == "" or lowered == "help":
                reply = Reply(ReplyType.INFO, self.get_help_text(verbose=True))
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            if lowered == "stop":
                if sessionid in self.roleplays:
                    self.roleplays[sessionid].reset()
                    del self.roleplays[sessionid]
                reply = Reply(ReplyType.INFO, "Role play ended.")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            if lowered == "custom" or lowered.startswith("custom "):
                # An empty description used to raise IndexError and produce no reply.
                description = argument[len("custom"):].strip()
                if not description:
                    reply = Reply(ReplyType.INFO, self.get_help_text(verbose=True))
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
                    return
                self.roleplays[sessionid] = RolePlay(bot, sessionid, description, "%s")
                reply = Reply(ReplyType.INFO, f"Role set to:\n{description}")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            if lowered == "tags" or lowered.startswith("tags "):
                tag = argument[len("tags"):].strip()
                tag_labels = ", ".join(self.tags[item][0] for item in self.tags)
                if not tag:
                    help_text = "Enter a role tag.\nTags: " + tag_labels + "\n"
                else:
                    matched = None
                    for key, value in self.tags.items():
                        if value[0].lower() == tag.lower() or key.lower() == tag.lower():
                            matched = key
                            break
                    if tag.lower() == "all":
                        help_text = "Roles:\n"
                        for role in self.roles.values():
                            help_text += f"{role['title']}: {role['remark']}\n"
                    elif matched in self.tags:
                        help_text = "Roles:\n"
                        for role in self.tags[matched][1]:
                            help_text += f"{role['title']}: {role['remark']}\n"
                    else:
                        help_text = "Unknown role tag.\nTags: " + tag_labels + "\n"
                reply = Reply(ReplyType.INFO, help_text)
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            role = self.get_role(argument)
            if role is None:
                reply = Reply(ReplyType.ERROR, "Role does not exist")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            self.roleplays[sessionid] = RolePlay(
                bot,
                sessionid,
                self.roles[role]["description"],
                self.roles[role].get("wrapper", "%s"),
            )
            reply = Reply(ReplyType.INFO, f"Role set to {role}:\n" + self.roles[role]["description"])
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return
        if sessionid not in self.roleplays:
            return
        logger.debug("[Role] on_handle_context. content: %s" % content)
        e_context["context"]["generate_breaked_by"] = EventAction.BREAK
        prompt = self.roleplays[sessionid].action(content)
        e_context["context"].type = ContextType.TEXT
        e_context["context"].content = prompt
        e_context.action = EventAction.BREAK

    def get_help_text(self, verbose=False, **kwargs):
        if not verbose:
            return "Play as a different role.\n"
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        trigger = f"{trigger_prefix}role"
        tags = ", ".join(self.tags[tag][0] for tag in self.tags)
        return (
            "Usage:\n"
            f"{trigger} <name>: set a preset role.\n"
            f"{trigger} custom <description>: set a custom role.\n"
            f"{trigger} stop: clear the role.\n"
            f"{trigger} tags <tag>: list preset roles for a tag. Use all to list every role.\n"
            f"\nTags: {tags}.\n"
            f"\nExamples:\n{trigger} Writing assistant\n"
            f"{trigger} tags all\n"
            f"{trigger} stop\n"
        )
