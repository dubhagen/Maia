# encoding:utf-8

import plugins
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf
from plugins import *


# https://github.com/bupticybee/ChineseAiDungeonChatGPT
class StoryTeller:
    def __init__(self, bot, sessionid, story):
        self.bot = bot
        self.sessionid = sessionid
        bot.sessions.clear_session(sessionid)
        self.first_interact = True
        self.story = story

    def reset(self):
        self.bot.sessions.clear_session(self.sessionid)
        self.first_interact = True

    def action(self, user_action):
        if user_action[-1] not in ".!?":
            user_action = user_action + "."
        if self.first_interact:
            prompt = (
                "You are a text adventure. Keep the pace slow. Describe how people feel "
                "and what the place is like. Write four to six sentences. The opening is: "
                + self.story
                + " "
                + user_action
            )
            self.first_interact = False
        else:
            prompt = (
                "Continue. Write only the next four to six sentences, covering about five minutes. "
                + user_action
            )
        return prompt


@plugins.register(
    name="Dungeon",
    desire_priority=0,
    enabled=False,
    namecn="Dungeon",
    desc="A plugin to play dungeon game",
    version="1.0",
    author="lanvent",
)
class Dungeon(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.debug("[Dungeon] inited")
        
        if conf().get("expires_in_seconds"):
            self.games = ExpiredDict(conf().get("expires_in_seconds"))
        else:
            self.games = dict()

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        bottype = Bridge().get_bot_type("chat")
        if bottype not in [const.LITELLM, const.OPEN_AI, const.OPENAI, const.CHATGPT, const.CHATGPTONAZURE]:
            return
        bot = Bridge().get_bot("chat")
        content = e_context["context"].content[:]
        if not content.strip():
            return
        clist = e_context["context"].content.split(maxsplit=1)
        sessionid = e_context["context"]["session_id"]
        logger.debug("[Dungeon] on_handle_context. content: %s" % clist)
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        trigger = f"{trigger_prefix}dungeon"
        argument = ""
        is_command = clist[0].lower() == trigger
        if is_command and len(clist) > 1:
            argument = clist[1].strip()
        lowered = argument.lower()
        if is_command and lowered == "stop":
            if sessionid in self.games:
                self.games[sessionid].reset()
                del self.games[sessionid]
                reply = Reply(ReplyType.INFO, "Adventure ended.")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        elif (is_command and (lowered == "start" or lowered.startswith("start "))) or sessionid in self.games:
            starting = is_command and (lowered == "start" or lowered.startswith("start "))
            if sessionid not in self.games or starting:
                story = argument[len("start"):].strip() if starting else ""
                if not story:
                    story = (
                        "You walk into the woods with a pistol in your hand, hoping to find "
                        "something valuable. Strange things could step out from anywhere. "
                        "You head deeper into the trees."
                    )
                self.games[sessionid] = StoryTeller(bot, sessionid, story)
                reply = Reply(
                    ReplyType.INFO,
                    "Adventure started. Send any message to continue. The setting is: " + story,
                )
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                prompt = self.games[sessionid].action(content)
                e_context["context"].type = ContextType.TEXT
                e_context["context"].content = prompt
                e_context.action = EventAction.BREAK

    def get_help_text(self, **kwargs):
        if kwargs.get("verbose") != True:
            return "Play a text adventure with the bot.\n"
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        trigger = f"{trigger_prefix}dungeon"
        return (
            f"{trigger} start <setting>: start an adventure from that setting. Later messages continue the story.\n"
            f"{trigger} stop: end the game.\n"
            f"\nExample: '{trigger} start You walk into the woods with a pistol in your hand.'"
        )
