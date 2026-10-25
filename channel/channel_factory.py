"""Channel factory. Only the web console and the local terminal are supported."""

from .channel import Channel


_SUPPORTED = ("web", "terminal")


def create_channel(channel_type, instance_id="", bound_agent_id="", credentials=None, members=None, peers=None) -> Channel:
    """Create a web or terminal channel.

    Extra instance arguments are accepted and ignored.
    """
    del instance_id, bound_agent_id, credentials, members, peers
    name = (channel_type or "").strip()
    if name not in _SUPPORTED:
        raise RuntimeError(f"unsupported channel_type: {channel_type!r}")
    if name == "terminal":
        from channel.terminal.terminal_channel import TerminalChannel
        ch = TerminalChannel()
    else:
        from channel.web.web_channel import WebChannel
        ch = WebChannel()
    ch.channel_type = name
    return ch
