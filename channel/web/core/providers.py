"""The single model endpoint the console knows about.

Chat, vision, images, speech, and embeddings all use one LiteLLM
OpenAI-compatible proxy. There are no vendor cards and no custom providers.
"""

from collections import OrderedDict


PROVIDER_MODELS = OrderedDict([
    ("litellm", {
        "label": "LiteLLM",
        "api_key_field": "litellm_api_key",
        "api_base_key": "litellm_api_base",
        "api_base_default": "http://127.0.0.1:4000/v1",
        "api_base_placeholder": "http://127.0.0.1:4000/v1",
        "models": [],
    }),
])


def is_real_key(value: str) -> bool:
    """False for an unset key and for the placeholders the form ships with."""
    return bool(value) and value not in ("", "YOUR API KEY", "YOUR_API_KEY")


def mask_key(value: str) -> str:
    """Mask the middle part of an API key for display."""
    if not value or len(value) <= 8:
        return value
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def legacy_custom_in_use(local_config: dict) -> bool:
    """Custom providers are gone. Kept so older callers do not crash."""
    del local_config
    return False
