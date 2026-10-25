# encoding:utf-8
"""``$role custom`` without a role description must answer, not die.

``Role.on_handle_context`` splits the command with ``split(maxsplit=1)``
(plugins/role/role.py:136) and, on the ``customize`` branch, reads the missing
description straight from ``clist[1]`` (plugins/role/role.py:207-208). The
sibling branches all guard that mistake first: ``$role`` answers with its help
text when the name is absent (lines 184-188) and ``$role tags`` asks for the
missing tag (lines 172-176), but ``$role custom`` has no such guard. So the
``IndexError`` leaves ``on_handle_context`` untouched by
``PluginManager.emit_event`` (plugins/plugin_manager.py:287-295 calls the
handler directly) and reaches the worker's exception callback, which only logs
it (channel/chat_channel.py:452-453). The user's command then produces no
message of any kind -- even though the plugin is enabled out of the box.
"""

from unittest.mock import patch

import plugins
from bridge.context import Context, ContextType
from bridge.reply import ReplyType
from common import const
from plugins import Event, EventContext

# ``@plugins.register`` reads the importing plugin's path off the plugin
# instance, so it has to be pointed at the role directory before the import.
plugins.instance.current_plugin_path = "./plugins/role"
from plugins.role import role as role_module  # noqa: E402

plugins.instance.current_plugin_path = None

# The decorator hands the class to the plugin manager and binds nothing back,
# so the module attribute is None and the registered class has to be taken from
# the manager the same way the runtime does.
Role = plugins.instance.plugins["ROLE"]


class FakeSessions:
    def __init__(self):
        self.system_prompts = {}

    def build_session(self, session_id, system_prompt=None):
        self.system_prompts[session_id] = system_prompt


class FakeBot:
    def __init__(self):
        self.sessions = FakeSessions()


class FakeBridge:
    """Stands in for the bot bridge so the command parser is reached at all."""

    _bot = FakeBot()

    def __init__(self, *args, **kwargs):
        pass

    def get_bot_type(self, bot_role):
        return const.OPENAI

    def get_bot(self, bot_role):
        return FakeBridge._bot


def _run(content):
    """Hand ``content`` to the role plugin and report what came back."""
    plugin = Role()
    context = Context(ContextType.TEXT, content)
    context["session_id"] = "s1"
    event = EventContext(
        Event.ON_HANDLE_CONTEXT, {"context": context, "reply": None}
    )
    # conf() is read inside on_handle_context, so the call has to stay inside
    # the patch or the stub never reaches the plugin.
    with patch.object(role_module, "conf", lambda: {"plugin_trigger_prefix": "$"}), \
            patch.object(role_module, "Bridge", FakeBridge):
        plugin.on_handle_context(event)
    return event["reply"]


def test_bare_customize_command_gets_a_reply_instead_of_raising():
    # Sending the command on its own is the same mistake the sibling commands
    # already answer for, so it has to reach the user the same way.
    reply = _run("$role custom")

    assert reply is not None, "the command died before it could reply"
    assert reply.type is ReplyType.INFO
    assert reply.content.strip()


def test_customize_command_with_a_description_still_sets_the_role():
    # The guard must not swallow the documented happy path.
    reply = _run("$role custom a pirate captain")

    assert reply.type is ReplyType.INFO
    assert "Role set to:" in reply.content
    assert "a pirate captain" in reply.content
    assert FakeBridge._bot.sessions.system_prompts["s1"] == "a pirate captain"


def test_bare_preset_role_command_keeps_its_existing_help_reply():
    # Pins the behaviour the new guard mirrors, so the two commands cannot drift.
    reply = _run("$role")

    assert reply.type is ReplyType.INFO
    assert reply.content.strip()
