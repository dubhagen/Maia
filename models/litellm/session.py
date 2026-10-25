"""Chat session for the non-agent reply path.

Token counts are a character estimate. Agent turns do not use this session;
they send the full message list through call_with_tools.
"""

from models.session_manager import Session


class LiteLLMSession(Session):
    def __init__(self, session_id, system_prompt=None, **kwargs):
        super().__init__(session_id, system_prompt)

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        cur_tokens = self.calc_tokens() if cur_tokens is None else cur_tokens
        while cur_tokens > max_tokens and len(self.messages) > 2:
            self.messages.pop(1)
            cur_tokens = self.calc_tokens()
        return cur_tokens

    def calc_tokens(self):
        total = 0
        for message in self.messages:
            content = message.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            total += max(1, len(content) // 4)
        return total
