"""Create the only chat bot. Model ids are passed through to LiteLLM."""


def create_bot(bot_type=None, credential_bot_type=None):
    """Return a LiteLLM bot. ``bot_type`` is accepted and ignored."""
    from models.litellm.litellm_bot import LiteLLMBot
    return LiteLLMBot(bot_type, credential_bot_type)
