"""Resolve the single LiteLLM endpoint from config.

Vendor keys are never consulted. A missing or malformed base fails the call.
"""

from urllib.parse import urlparse


class LiteLLMConfigError(RuntimeError):
    """litellm_api_base is missing or not a usable /v1 URL."""


def litellm_api_base() -> str:
    """Return the configured base, with no trailing slash, ending in /v1."""
    from config import conf

    raw = conf().get("litellm_api_base") or ""
    base = raw.strip().rstrip("/") if isinstance(raw, str) else ""
    if not base:
        raise LiteLLMConfigError(
            "litellm_api_base is required (for example http://127.0.0.1:4000/v1)"
        )
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LiteLLMConfigError("litellm_api_base must be an http(s) URL")
    if not base.endswith("/v1"):
        raise LiteLLMConfigError("litellm_api_base must end with /v1")
    return base


def litellm_api_key() -> str:
    """Bearer token for the proxy. Empty when the proxy does not require one."""
    from config import conf

    raw = conf().get("litellm_api_key") or ""
    return raw.strip() if isinstance(raw, str) else ""


def litellm_origin() -> str:
    """Origin of the proxy, without the /v1 suffix. Used for /model/info."""
    base = litellm_api_base()
    if base.endswith("/v1"):
        return base[:-3]
    return base
