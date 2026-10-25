"""Channel endpoints. Only the web console and the local terminal remain."""

import json

import web

from channel.web.core._common import _require_auth
from common.log import logger
from config import conf


_UNSUPPORTED = (
    "Chat is the web console and the local terminal. "
    "Set channel_type to \"terminal\" for the local process."
)


class ChannelsHandler:
    """Lists the web console. Any other channel type is rejected."""

    def GET(self):
        _require_auth()
        web.header("Content-Type", "application/json; charset=utf-8")
        try:
            channel_type = conf().get("channel_type", "web")
            if isinstance(channel_type, list):
                active = "web" in channel_type
            else:
                active = channel_type in ("web", ["web"], "web,terminal")
            return json.dumps({
                "status": "success",
                "channels": [{
                    "name": "web",
                    "label": "Web console",
                    "icon": "fa-globe",
                    "color": "primary",
                    "active": bool(active) or channel_type in ("web", ""),
                    "fields": [],
                }],
            }, ensure_ascii=False)
        except Exception as exc:
            logger.error("[ChannelsHandler] GET failed: %s", exc)
            return json.dumps({"status": "error", "message": str(exc)})

    def POST(self):
        _require_auth()
        web.header("Content-Type", "application/json; charset=utf-8")
        return json.dumps({"status": "error", "message": _UNSUPPORTED})
