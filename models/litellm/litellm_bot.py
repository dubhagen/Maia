"""Single chat bot. Every model id is sent to the LiteLLM endpoint as-is."""

from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.i18n import t as _t
from common.log import logger
from config import conf, load_config
from models.bot import Bot
from models.litellm.endpoint import LiteLLMConfigError, litellm_api_base, litellm_api_key
from models.litellm.http_client import OpenAIHTTPClient, OpenAIHTTPError
from models.litellm.session import LiteLLMSession
from models.openai_compatible_bot import OpenAICompatibleBot
from models.session_manager import SessionManager


class LiteLLMBot(Bot, OpenAICompatibleBot):
    def __init__(self, bot_type=None, credential_bot_type=None):
        # bot_type is ignored. One endpoint serves every model.
        del bot_type, credential_bot_type
        super().__init__()
        self.sessions = SessionManager(LiteLLMSession, model=conf().get("model") or "")

    def get_api_config(self):
        try:
            api_base = litellm_api_base()
        except LiteLLMConfigError as exc:
            api_base = ""
            logger.error("[LiteLLM] %s", exc)
        return {
            "api_key": litellm_api_key(),
            "api_base": api_base,
            "model": conf().get("model") or "",
            "default_temperature": conf().get("temperature", 0.9),
            "default_top_p": conf().get("top_p", 1.0),
            "default_frequency_penalty": conf().get("frequency_penalty", 0.0),
            "default_presence_penalty": conf().get("presence_penalty", 0.0),
            "api_type": "chat",
        }

    def _get_http_client(self) -> OpenAIHTTPClient:
        proxy = conf().get("proxy") or None
        try:
            api_base = litellm_api_base()
        except LiteLLMConfigError:
            api_base = ""
        return OpenAIHTTPClient(
            api_key=litellm_api_key(),
            api_base=api_base,
            proxy=proxy,
        )

    def reply(self, query, context=None):
        if context is None or context.type != ContextType.TEXT:
            if context is not None and context.type == ContextType.IMAGE_CREATE:
                return self._reply_image(query)
            kind = getattr(context, "type", "")
            return Reply(
                ReplyType.ERROR,
                _t("Bot does not support message type {}").format(kind),
            )

        clear_memory_commands = conf().get("clear_memory_commands", ["#reset"])
        session_id = context["session_id"]
        if query in clear_memory_commands:
            self.sessions.clear_session(session_id)
            return Reply(ReplyType.INFO, _t("Memory cleared"))
        if query == "#resetall":
            self.sessions.clear_all_session()
            return Reply(ReplyType.INFO, _t("All memories cleared"))
        if query == "#reconf":
            load_config()
            return Reply(ReplyType.INFO, _t("Config updated"))

        try:
            api_base = litellm_api_base()
        except LiteLLMConfigError as exc:
            return Reply(ReplyType.ERROR, str(exc))

        model = context.get("gpt_model") or conf().get("model") or ""
        if not model:
            return Reply(ReplyType.ERROR, "model is not set")

        session = self.sessions.session_query(query, session_id)
        try:
            data = self._get_http_client().chat_completions(
                api_key=litellm_api_key(),
                api_base=api_base,
                model=model,
                messages=session.messages,
                temperature=conf().get("temperature", 0.9),
            )
        except OpenAIHTTPError as exc:
            logger.error("[LiteLLM] chat error: %s", exc.message)
            return Reply(ReplyType.ERROR, exc.message or "model request failed")

        try:
            content = data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            return Reply(ReplyType.ERROR, "model response had no message")
        usage = data.get("usage") or {}
        self.sessions.session_reply(content, session_id, usage.get("total_tokens"))
        return Reply(ReplyType.TEXT, content)

    def _reply_image(self, query):
        model = (conf().get("image_model") or "").strip()
        if not model:
            return Reply(ReplyType.ERROR, "image_model is not set")
        try:
            data = self._get_http_client().images_generate(
                api_key=litellm_api_key(),
                api_base=litellm_api_base(),
                model=model,
                prompt=query,
                n=1,
            )
            url = data["data"][0].get("url") or ""
        except LiteLLMConfigError as exc:
            return Reply(ReplyType.ERROR, str(exc))
        except (OpenAIHTTPError, KeyError, IndexError, TypeError) as exc:
            logger.error("[LiteLLM] image error: %s", exc)
            return Reply(ReplyType.ERROR, "image generation failed")
        if not url:
            return Reply(ReplyType.ERROR, "image generation returned no url")
        return Reply(ReplyType.IMAGE_URL, url)
