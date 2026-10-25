"""Pass-through reasoning effort for the LiteLLM chat-completions request.

LiteLLM applies provider-specific effort fields. This module only checks that
a saved value is one of the generic tiers the console offers.
"""

from __future__ import annotations

from typing import Optional


EFFORT_VALUES = ["low", "medium", "high", "xhigh", "max"]


def _capability() -> dict:
    return {
        "supported": True,
        "param": "reasoning_effort",
        "default": "high",
        "options": [{"value": value, "label": value} for value in EFFORT_VALUES],
    }


def get_reasoning_capability(provider_id: str, model_name: str = "") -> dict:
    """Every model may receive reasoning_effort. The proxy decides if it applies."""
    del provider_id, model_name
    return _capability()


def provider_reasoning_metadata(provider_id: str, model_name: str = "") -> dict:
    """Name the settings page already imports."""
    return get_reasoning_capability(provider_id, model_name)


def normalize_reasoning_effort(provider_id: str, model_name: str, value: object) -> Optional[str]:
    del provider_id, model_name
    effort = str(value or "").strip()
    if effort in EFFORT_VALUES:
        return effort
    return None


def resolve_reasoning_effort(
    provider_id: str, model_name: str, by_model: dict, legacy_value: object
) -> Optional[str]:
    """Prefer a per-model value, then the global ``reasoning_effort``."""
    del provider_id
    model = (model_name or "").strip().lower()
    if not isinstance(by_model, dict):
        by_model = {}
    for key in (model, f"litellm:{model}"):
        if key and key in by_model:
            return normalize_reasoning_effort("", model, by_model[key])
    return normalize_reasoning_effort("", model, legacy_value)
