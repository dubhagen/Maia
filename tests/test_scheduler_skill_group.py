# encoding:utf-8
"""A scheduled skill_call must know whether its receiver is a group.

``_execute_skill_call`` read the group flag from ``action["isgroup"]`` while the
other executors in the same module read ``action["is_group"]``. The key a
task actually carries is ``is_group``.
"""

from agent.tools.scheduler import integration
from bridge.reply import Reply, ReplyType


class FakeChannel:
    def __init__(self):
        self.sent = []

    def send(self, reply, context):
        self.sent.append((reply, context))
        return True


class FakeBridge:
    def __init__(self):
        self.context = None

    def agent_reply(self, query, context=None, on_event=None, clear_history=False):
        self.context = context
        return Reply(ReplyType.TEXT, "done")


def _run(monkeypatch, action):
    monkeypatch.setattr(integration, "_primary_channel_type", lambda v: v)
    monkeypatch.setattr(
        integration, "_resolve_delivery_channel", lambda *a, **k: FakeChannel()
    )
    monkeypatch.setattr(integration, "_remember_delivered_output", lambda *a, **k: None)
    bridge = FakeBridge()
    ok = integration._execute_skill_call(
        {"id": "t1", "action": action}, bridge, agent_id="agent-1"
    )
    return ok, bridge.context


def _action(**extra):
    action = {
        "call_name": "digest",
        "receiver": "oc_group_1",
        "channel_type": "terminal",
    }
    action.update(extra)
    return action


def test_skill_call_to_a_group_sets_the_group_flag(monkeypatch):
    ok, context = _run(monkeypatch, _action(is_group=True))
    assert ok is True
    assert context.get("isgroup") is True
    assert "receive_id_type" not in context


def test_skill_call_to_a_user_is_not_a_group(monkeypatch):
    ok, context = _run(monkeypatch, _action(is_group=False))
    assert ok is True
    assert context.get("isgroup") is False
    assert "receive_id_type" not in context


def test_skill_call_without_the_flag_is_not_a_group(monkeypatch):
    ok, context = _run(monkeypatch, _action())
    assert ok is True
    assert context.get("isgroup") is False
    assert "receive_id_type" not in context


def test_group_flag_reaches_the_context_for_other_channels(monkeypatch):
    ok, context = _run(
        monkeypatch,
        {"call_name": "digest", "receiver": "u1", "channel_type": "web", "is_group": True},
    )
    assert ok is True
    assert context.get("isgroup") is True
