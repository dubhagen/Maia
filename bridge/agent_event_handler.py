"""
Agent Event Handler - Handles agent events and thinking process output
"""

from common.log import logger


class AgentEventHandler:
    """
    Handles agent events and optionally sends intermediate messages to channel
    """

    def __init__(self, context=None, original_callback=None):
        self.context = context
        self.original_callback = original_callback

        self.channel = None
        if context:
            self.channel = context.kwargs.get("channel") if hasattr(context, "kwargs") else None

        self.current_content = ""
        self.turn_number = 0

        self._thinking_sent_count = 0

    def handle_event(self, event):
        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "turn_start":
            self._handle_turn_start(data)
        elif event_type == "message_update":
            self._handle_message_update(data)
        elif event_type == "message_end":
            self._handle_message_end(data)
        elif event_type == "reasoning_update":
            pass
        elif event_type == "tool_execution_start":
            self._handle_tool_execution_start(data)
        elif event_type == "tool_execution_end":
            self._handle_tool_execution_end(data)
        elif event_type == "agent_end":
            self._handle_agent_end(data)

        if self.original_callback:
            self.original_callback(event)

    def _handle_turn_start(self, data):
        self.turn_number = data.get("turn", 0)
        self.current_content = ""

    def _handle_message_update(self, data):
        delta = data.get("delta", "")
        self.current_content += delta

    def _handle_message_end(self, data):
        tool_calls = data.get("tool_calls", [])

        if tool_calls:
            if self.current_content.strip():
                logger.info(f"💭 {self.current_content.strip()[:200]}{'...' if len(self.current_content) > 200 else ''}")
                self._send_to_channel(self.current_content.strip())
        else:
            if self.current_content.strip():
                logger.debug(f"💬 {self.current_content.strip()[:200]}{'...' if len(self.current_content) > 200 else ''}")
        self.current_content = ""

    def _handle_agent_end(self, data):
        return

    def _handle_tool_execution_start(self, data):
        pass

    def _handle_tool_execution_end(self, data):
        pass

    def _send_to_channel(self, message):
        if self.context and self.context.get("on_event"):
            return
        if not self.channel:
            return

        self._do_send(message)
        self._thinking_sent_count += 1

    def _do_send(self, message):
        try:
            from bridge.reply import Reply, ReplyType
            reply = Reply(ReplyType.TEXT, message)
            self.channel._send(reply, self.context)
        except Exception as e:
            logger.debug(f"[AgentEventHandler] Failed to send to channel: {e}")

    def log_summary(self):
        pass
