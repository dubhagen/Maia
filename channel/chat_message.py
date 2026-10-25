"""
Unified chat message class for different channel implementations.

Fill in the required fields (6 for a group chat, 8 otherwise) to plug into ChatChannel, with plugin support. See TerminalChannel.

ChatMessage
msg_id: message id (required)
create_time: when the message was created

ctype: message type: ContextType (required)
content: message content. For audio or an image, this is a file path (required)

from_user_id: sender id (required)
from_user_nickname: sender nickname
to_user_id: recipient id (required)
to_user_nickname: recipient nickname

other_user_id: the other party's id. If you are the sender, this is the recipient id. If you are the recipient, this is the sender id. For a group message, this is always the group id (required)
other_user_nickname: same as above

is_group: whether this is a group message (required for a group chat)
is_at: whether this message mentions the bot

- (A group message usually also has the real sender, a member id and nickname. The fields below exist only for group messages.)
actual_user_id: real sender id (required for a group chat)
actual_user_nickname: real sender nickname
self_display_name: this bot's display name. When a group nickname is set, this field is that nickname

_prepare_fn: prepare callback, used to get the message ready, for example by downloading an image,
_prepared: whether the prepare callback has already run
_rawmsg: the original message object

"""


import os
import re


def safe_filename(name) -> str:
    """Reduce a server-supplied filename to a single path component.

    Channels hand us a ``file_name`` the sender picked, and every inbound
    attachment is written to ``tmp_dir()/<file_name>``. A name holding a path
    separator (``../../etc/x``), a backslash, or an absolute path therefore
    redirects that write outside the directory the app manages and cleans.
    Strip it down before it reaches ``os.path.join``; callers fall back to
    their own generated name when this returns ``""``.
    """
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = re.sub(r"[^\w.\- ]+", "_", name).strip(" .")
    return name[:180]


class ChatMessage(object):
    msg_id = None
    create_time = None

    ctype = None
    content = None

    from_user_id = None
    from_user_nickname = None
    to_user_id = None
    to_user_nickname = None
    other_user_id = None
    other_user_nickname = None
    my_msg = False
    self_display_name = None

    is_group = False
    is_at = False
    actual_user_id = None
    actual_user_nickname = None
    at_list = None

    _prepare_fn = None
    _prepared = False
    _rawmsg = None

    def __init__(self, _rawmsg):
        self._rawmsg = _rawmsg

    def prepare(self):
        if self._prepare_fn and not self._prepared:
            self._prepared = True
            self._prepare_fn()

    def __str__(self):
        return "ChatMessage: id={}, create_time={}, ctype={}, content={}, from_user_id={}, from_user_nickname={}, to_user_id={}, to_user_nickname={}, other_user_id={}, other_user_nickname={}, is_group={}, is_at={}, actual_user_id={}, actual_user_nickname={}, at_list={}".format(
            self.msg_id,
            self.create_time,
            self.ctype,
            self.content,
            self.from_user_id,
            self.from_user_nickname,
            self.to_user_id,
            self.to_user_nickname,
            self.other_user_id,
            self.other_user_nickname,
            self.is_group,
            self.is_at,
            self.actual_user_id,
            self.actual_user_nickname,
            self.at_list
        )
