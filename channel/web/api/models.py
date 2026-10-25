"""The models tab's endpoint: /api/models.

One LiteLLM proxy serves every capability. Model ids are stored as the user
typed them. Discovery reads GET {base}/models and, when the proxy offers it,
GET {origin}/model/info. The catalog overlay still wins over discovered tags.
"""

from collections import OrderedDict
from typing import List, Optional, Tuple
import json
import os
import threading
import time
from urllib.parse import urlparse

import requests
import web

from channel.web.core._common import (
    _read_config_file_for_write,
    _require_auth,
    _write_config_file_for_write,
)
from channel.web.core.providers import PROVIDER_MODELS, is_real_key, mask_key
from common.log import logger
from config import CONFIG_TO_ENV, conf, get_data_root
from models import model_catalog
from models.litellm.endpoint import LiteLLMConfigError, litellm_api_base, litellm_api_key


PROVIDER_ID = "litellm"

_CAPABILITY_KEYS = {
    "chat": "model",
    "vision": "vision_model",
    "image": "image_model",
    "asr": "asr_model",
    "tts": "tts_model",
    "embedding": "embedding_model",
}

_CAPABILITY_TAG = {
    "chat": "text",
    "chat_fallback": "text",
    "vision": "vision",
    "image": "image",
    "asr": "asr",
    "tts": "tts",
    "embedding": "embedding",
}

_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"]

_MODE_TAGS = {
    "chat": ["text"],
    "completion": ["text"],
    "responses": ["text"],
    "embedding": ["embedding"],
    "image_generation": ["image"],
    "image": ["image"],
    "audio_transcription": ["asr"],
    "audio_speech": ["tts"],
    "tts": ["tts"],
    "asr": ["asr"],
}


class ModelDiscoveryError(Exception):
    """The LiteLLM proxy did not return a usable model list."""


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_DISCOVERY_TTL = 30.0
_DISCOVERY_ERROR_TTL = 8.0
_discovery_lock = threading.Lock()
_discovery_cache = {}


def invalidate_litellm_discovery() -> None:
    """Drop the cached proxy model list after the endpoint or key changes."""
    with _discovery_lock:
        _discovery_cache.clear()


def _loopback_proxies(url: str):
    """Stop a machine-wide HTTP proxy from hijacking the local LiteLLM port.

    ``requests`` treats ``proxies=None`` as "honor HTTP_PROXY". A loopback
    proxy must be contacted directly, or model discovery fails closed with a
    connection error and the console shows an empty model list.
    """
    host = (urlparse(url).hostname or "").strip("[]").lower()
    if host in _LOOPBACK_HOSTS:
        return {"http": None, "https": None}
    return None


def _redact(message: str, api_key: str) -> str:
    if api_key and api_key in message:
        return message.replace(api_key, "***")
    return message


class ModelsHandler:
    @staticmethod
    def _config_path() -> str:
        return os.path.join(get_data_root(), "config.json")

    @classmethod
    def _read_file_config(cls) -> dict:
        return _read_config_file_for_write()

    @classmethod
    def _write_file_config(cls, data: dict) -> None:
        _write_config_file_for_write(cls._config_path(), data)

    @classmethod
    def _preset_seed(cls, pid: str) -> List[dict]:
        """Models currently advertised by the configured LiteLLM proxy.

        The saved catalog still overrides tags and can hide a name. An empty
        overlay no longer means an empty picker.
        """
        if pid != PROVIDER_ID:
            return []
        models, _error = configured_litellm_models()
        return models

    @classmethod
    def _merged_catalog(cls, pid, base_seed=None, catalog_map=None, hidden_map=None) -> List[dict]:
        """Preset base, minus tombstones, plus user overrides.

        ``base_seed`` defaults to ``_preset_seed``. Callers that already loaded
        the maps may pass them in."""
        if catalog_map is None:
            catalog_map = model_catalog.get_catalog_map()
        if hidden_map is None:
            hidden_map = model_catalog.get_hidden_map()
        overrides = catalog_map.get(pid) or []
        hidden = set(hidden_map.get(pid) or [])
        if base_seed is None:
            base_seed = cls._preset_seed(pid)

        override_by_name = {e["name"]: e for e in overrides}
        merged: "OrderedDict[str, dict]" = OrderedDict()
        for entry in base_seed:
            name = entry.get("name")
            if not name or name in hidden:
                continue
            merged[name] = override_by_name.get(name, entry)
        for entry in overrides:
            name = entry.get("name")
            if name and name not in merged:
                merged[name] = entry
        return list(merged.values())

    @classmethod
    def _effective(cls, pid: str = PROVIDER_ID) -> List[dict]:
        return cls._merged_catalog(pid)

    @classmethod
    def _names_for(cls, tag: str) -> List[str]:
        return [
            entry["name"]
            for entry in cls._effective()
            if tag in (entry.get("capabilities") or [])
        ]

    def GET(self):
        _require_auth()
        web.header("Content-Type", "application/json; charset=utf-8")
        try:
            local_config = conf()
            providers = self._provider_overview(local_config)
            return json.dumps({
                "status": "success",
                "providers": providers,
                "capabilities": self._capabilities(local_config),
                "discovery_error": (providers[0].get("discovery_error") if providers else "") or "",
            }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[ModelsHandler] GET failed: {e}")
            return json.dumps({"status": "error", "message": str(e)})

    def POST(self):
        _require_auth()
        web.header("Content-Type", "application/json; charset=utf-8")
        try:
            data = json.loads(web.data() or b"{}")
            action = data.get("action") or ""
            if action == "set_provider":
                return self._handle_set_provider(data)
            if action == "delete_provider":
                return self._handle_delete_provider(data)
            if action in (
                "set_custom_provider",
                "delete_custom_provider",
                "set_active_custom_provider",
            ):
                return json.dumps({
                    "status": "error",
                    "message": "custom providers are not supported; set litellm_api_base",
                })
            if action == "set_capability":
                return self._handle_set_capability(data)
            if action == "save_catalog":
                return self._handle_save_catalog(data)
            if action == "discover_models":
                return self._handle_discover_models(data)
            if action == "set_voice_reply_mode":
                return self._handle_set_voice_reply_mode(data)
            if action == "set_search_credential":
                return self._handle_set_search_credential(data)
            if action == "set_search_provider_enabled":
                return self._handle_set_search_provider_enabled(data)
            return json.dumps({"status": "error", "message": f"unknown action: {action!r}"})
        except Exception as e:
            logger.error(f"[ModelsHandler] POST failed: {e}")
            return json.dumps({"status": "error", "message": str(e)})

    def _provider_overview(self, local_config: dict) -> List[dict]:
        meta = PROVIDER_MODELS[PROVIDER_ID]
        raw_key = local_config.get("litellm_api_key") or ""
        raw_base = (local_config.get("litellm_api_base") or "").strip()
        configured = _base_is_usable(raw_base)
        catalog_map = model_catalog.get_catalog_map()
        hidden_map = model_catalog.get_hidden_map()
        seed, discovery_error = configured_litellm_models()
        effective = self._merged_catalog(PROVIDER_ID, seed, catalog_map, hidden_map)
        return [{
            "id": PROVIDER_ID,
            "label": meta["label"],
            "configured": configured,
            "is_custom": False,
            "api_key_field": meta["api_key_field"],
            "api_base_field": meta["api_base_key"],
            "api_key_masked": mask_key(raw_key) if is_real_key(raw_key) else "",
            "api_base": raw_base or meta["api_base_default"],
            "api_base_default": meta["api_base_default"],
            "api_base_placeholder": meta["api_base_placeholder"],
            "catalog": catalog_map.get(PROVIDER_ID) or [],
            "hidden": hidden_map.get(PROVIDER_ID) or [],
            "seed": seed,
            "effective": effective,
            "models": [entry["name"] for entry in effective],
            "discovery_error": discovery_error or "",
        }]

    def _capabilities(self, local_config: dict) -> dict:
        return {
            "chat": self._model_capability(local_config, "chat"),
            "chat_fallback": self._fallback_capability(local_config),
            "vision": self._model_capability(local_config, "vision"),
            "asr": self._model_capability(local_config, "asr"),
            "tts": self._tts_capability(local_config),
            "embedding": self._model_capability(local_config, "embedding"),
            "image": self._model_capability(local_config, "image"),
            "search": self._search_capability(local_config),
        }

    def _model_capability(self, local_config: dict, capability: str) -> dict:
        key = _CAPABILITY_KEYS[capability]
        model = str(local_config.get(key) or "").strip()
        tag = _CAPABILITY_TAG[capability]
        names = self._names_for(tag)
        if model and model not in names:
            names = [model] + names
        provider = PROVIDER_ID if model else ""
        body = {
            "editable": True,
            "current_provider": provider,
            "suggested_provider": "",
            "current_model": model,
            "providers": [PROVIDER_ID],
            "provider_models": {PROVIDER_ID: names},
        }
        if capability == "embedding":
            dim = local_config.get("embedding_dimensions") or 0
            try:
                dim = int(dim)
            except (TypeError, ValueError):
                dim = 0
            body["current_dim"] = dim or None
        return body

    def _tts_capability(self, local_config: dict) -> dict:
        body = self._model_capability(local_config, "tts")
        voice = str(local_config.get("tts_voice") or local_config.get("tts_voice_id") or "").strip()
        body["current_voice"] = voice
        body["provider_voices"] = {PROVIDER_ID: list(_TTS_VOICES)}
        body["reply_mode"] = _tts_reply_mode(local_config)
        return body

    def _fallback_capability(self, local_config: dict) -> dict:
        models = _fallback_model_ids(local_config)
        chain = [{"provider": PROVIDER_ID, "model": model} for model in models]
        names = self._names_for("text")
        for model in models:
            if model not in names:
                names.append(model)
        primary = str(local_config.get("model") or "").strip()
        return {
            "editable": True,
            "enabled": bool(models),
            "providers": [PROVIDER_ID],
            "provider_models": {PROVIDER_ID: names},
            "chain": chain,
            "current_provider": PROVIDER_ID if chain else "",
            "current_model": chain[0]["model"] if chain else "",
            "primary_provider": PROVIDER_ID if primary else "",
            "primary_model": primary,
        }

    def _search_capability(self, local_config: dict) -> dict:
        tools_cfg = local_config.get("tools") or {}
        ws_cfg = tools_cfg.get("web_search") if isinstance(tools_cfg, dict) else {}
        if not isinstance(ws_cfg, dict):
            ws_cfg = {}
        url = str(ws_cfg.get("searxng_url") or "").strip()
        disabled = _disabled_search(ws_cfg)
        configured = bool(url) and "searxng" not in disabled
        is_disabled = bool(url) and "searxng" in disabled
        provider = {
            "id": "searxng",
            "label": "SearXNG",
            "configured": configured,
            "disabled": is_disabled,
            "anonymous": False,
            "needs_dedicated_key": False,
            "needs_url": True,
            "url_masked": url,
            "api_base": "",
            "api_key_masked": "",
        }
        strategy = str(ws_cfg.get("strategy") or "auto").strip().lower()
        if strategy not in ("auto", "fixed"):
            strategy = "auto"
        fixed = "searxng" if strategy == "fixed" and configured else ""
        current = "searxng" if configured else ""
        return {
            "editable": True,
            "strategy": strategy,
            "providers": [provider],
            "configured_providers": ["searxng"] if configured else [],
            "current_provider": current,
            "fixed_provider": fixed,
            "available": configured,
        }

    def _handle_set_provider(self, data: dict) -> str:
        provider_id = (data.get("provider_id") or "").strip()
        if provider_id != PROVIDER_ID:
            return json.dumps({
                "status": "error",
                "message": "only the litellm endpoint is supported",
            })
        api_key_raw = data.get("api_key")
        api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else ""
        api_base_present = "api_base" in data
        api_base = (data.get("api_base") or "").strip() if api_base_present else None
        if api_base_present and api_base and not _base_is_usable(api_base):
            return json.dumps({
                "status": "error",
                "message": "litellm_api_base must be an http(s) URL ending with /v1",
            })

        local_config = conf()
        file_cfg = self._read_file_config()
        applied = {}
        if isinstance(api_key_raw, str) and api_key and "*" not in api_key:
            local_config["litellm_api_key"] = api_key
            file_cfg["litellm_api_key"] = api_key
            applied["litellm_api_key"] = True
            _mirror_env("litellm_api_key", api_key)
        if api_base_present:
            local_config["litellm_api_base"] = api_base
            file_cfg["litellm_api_base"] = api_base
            applied["litellm_api_base"] = True
            _mirror_env("litellm_api_base", api_base)
        local_config["bot_type"] = PROVIDER_ID
        file_cfg["bot_type"] = PROVIDER_ID
        if not applied:
            self._write_file_config(file_cfg)
            return json.dumps({"status": "success", "provider": provider_id, "noop": True})
        self._write_file_config(file_cfg)
        invalidate_litellm_discovery()
        self._reset_bridge()
        return json.dumps({"status": "success", "provider": provider_id})

    def _handle_delete_provider(self, data: dict) -> str:
        provider_id = (data.get("provider_id") or "").strip()
        if provider_id != PROVIDER_ID:
            return json.dumps({"status": "error", "message": "only the litellm endpoint is supported"})
        local_config = conf()
        file_cfg = self._read_file_config()
        for key in ("litellm_api_key", "litellm_api_base"):
            previous = local_config.get(key)
            local_config[key] = ""
            file_cfg[key] = ""
            env_key = CONFIG_TO_ENV.get(key)
            if env_key and previous and os.environ.get(env_key) == previous:
                os.environ.pop(env_key, None)
        self._write_file_config(file_cfg)
        invalidate_litellm_discovery()
        self._reset_bridge()
        return json.dumps({"status": "success", "provider": provider_id})

    def _handle_set_capability(self, data: dict) -> str:
        capability = (data.get("capability") or "").strip()
        if capability == "search":
            return self._set_search(data)
        if capability == "chat_fallback":
            return self._set_fallback(data)
        if capability not in _CAPABILITY_KEYS:
            return json.dumps({"status": "error", "message": f"unknown capability: {capability!r}"})
        provider_id = (data.get("provider_id") or "").strip()
        if provider_id and provider_id != PROVIDER_ID:
            return json.dumps({"status": "error", "message": "only the litellm endpoint is supported"})
        model = str(data.get("model") or "").strip()
        key = _CAPABILITY_KEYS[capability]
        local_config = conf()
        file_cfg = self._read_file_config()
        local_config[key] = model
        file_cfg[key] = model
        local_config["bot_type"] = PROVIDER_ID
        file_cfg["bot_type"] = PROVIDER_ID
        if capability == "tts":
            voice = str(data.get("voice") or local_config.get("tts_voice") or "alloy").strip() or "alloy"
            local_config["tts_voice"] = voice
            file_cfg["tts_voice"] = voice
            local_config["tts_voice_id"] = voice
            file_cfg["tts_voice_id"] = voice
        self._write_file_config(file_cfg)
        _mirror_env(key, model)
        if capability in ("asr", "tts"):
            self._refresh_voice_routing()
        else:
            self._reset_bridge()
        logger.info(f"[ModelsHandler] {capability} model set: {model!r}")
        return json.dumps({"status": "success", "provider": PROVIDER_ID, "model": model})

    def _set_fallback(self, data: dict) -> str:
        raw_chain = data.get("chain")
        models = []
        if isinstance(raw_chain, list):
            for item in raw_chain:
                if not isinstance(item, dict):
                    continue
                model = str(item.get("model") or "").strip()
                if model and model not in models:
                    models.append(model)
        elif str(data.get("model") or "").strip():
            models = [str(data.get("model")).strip()]
        enabled = data.get("enabled")
        if enabled is False:
            models = []
        local_config = conf()
        file_cfg = self._read_file_config()
        local_config["agent_fallback_models"] = models
        file_cfg["agent_fallback_models"] = models
        chain = [{"provider": PROVIDER_ID, "model": model} for model in models]
        fallback = {"enabled": bool(models), "chain": chain}
        local_config["chat_fallback"] = fallback
        file_cfg["chat_fallback"] = fallback
        self._write_file_config(file_cfg)
        return json.dumps({"status": "success", "chain": chain, "enabled": bool(models)})

    def _set_search(self, data: dict) -> str:
        strategy = str(data.get("strategy") or data.get("model") or "auto").strip().lower()
        if strategy not in ("auto", "fixed"):
            strategy = "auto"
        provider = "searxng" if strategy == "fixed" else ""
        local_config = conf()
        file_cfg = self._read_file_config()
        _set_nested(local_config, "tools", "web_search", "strategy", strategy)
        _set_nested(file_cfg, "tools", "web_search", "strategy", strategy)
        _set_nested(local_config, "tools", "web_search", "provider", provider)
        _set_nested(file_cfg, "tools", "web_search", "provider", provider)
        self._write_file_config(file_cfg)
        return json.dumps({"status": "success", "strategy": strategy, "provider": provider})

    def _handle_save_catalog(self, data: dict) -> str:
        provider_id = (data.get("provider_id") or "").strip()
        if provider_id != PROVIDER_ID:
            return json.dumps({"status": "error", "message": "only the litellm catalog is supported"})
        try:
            entries = model_catalog.save_catalog(
                provider_id, data.get("models") or [], data.get("hidden") or [],
            )
        except ValueError as exc:
            return json.dumps({"status": "error", "message": str(exc)})
        return json.dumps({"status": "success", "models": entries}, ensure_ascii=False)

    def _handle_discover_models(self, data: dict) -> str:
        provider_id = (data.get("provider_id") or PROVIDER_ID).strip() or PROVIDER_ID
        if provider_id != PROVIDER_ID:
            return json.dumps({"status": "error", "message": "only the litellm endpoint can be discovered"})
        requested_base = (data.get("api_base") or "").strip()
        requested_key = data.get("api_key")
        key = requested_key.strip() if isinstance(requested_key, str) else ""
        if not key or "*" in key:
            try:
                key = litellm_api_key()
            except Exception:
                key = ""
        base = requested_base
        if not base:
            try:
                base = litellm_api_base()
            except LiteLLMConfigError as exc:
                return json.dumps({"status": "error", "message": str(exc)})
        if not _base_is_usable(base):
            return json.dumps({
                "status": "error",
                "message": "litellm_api_base must be an http(s) URL ending with /v1",
            })
        try:
            models = discover_litellm_models(base, key)
        except ModelDiscoveryError as exc:
            return json.dumps({"status": "error", "message": str(exc)})
        return json.dumps({
            "status": "success",
            "provider_id": PROVIDER_ID,
            "models": models,
            "count": len(models),
        }, ensure_ascii=False)

    def _handle_set_voice_reply_mode(self, data: dict) -> str:
        mode = (data.get("mode") or "").strip().lower()
        if mode not in ("off", "voice_if_voice", "always"):
            return json.dumps({"status": "error", "message": f"invalid mode: {mode!r}"})
        local_config = conf()
        file_cfg = self._read_file_config()
        local_config["always_reply_voice"] = mode == "always"
        local_config["voice_reply_voice"] = mode == "voice_if_voice"
        file_cfg["always_reply_voice"] = mode == "always"
        file_cfg["voice_reply_voice"] = mode == "voice_if_voice"
        self._write_file_config(file_cfg)
        return json.dumps({"status": "success", "mode": mode})

    def _handle_set_search_credential(self, data: dict) -> str:
        provider = (data.get("provider") or "").strip().lower()
        if provider != "searxng":
            return json.dumps({
                "status": "error",
                "message": "only a SearXNG instance URL is supported",
            })
        url = (data.get("url") or "").strip() if isinstance(data.get("url"), str) else ""
        if url and not url.startswith(("http://", "https://")):
            return json.dumps({"status": "error", "message": "SearXNG URL must be http(s)"})
        local_config = conf()
        file_cfg = self._read_file_config()
        _set_nested(local_config, "tools", "web_search", "searxng_url", url)
        _set_nested(file_cfg, "tools", "web_search", "searxng_url", url)
        if url:
            _set_search_disabled(local_config, "searxng", False)
            _set_search_disabled(file_cfg, "searxng", False)
        self._write_file_config(file_cfg)
        return json.dumps({"status": "success", "provider": "searxng"})

    def _handle_set_search_provider_enabled(self, data: dict) -> str:
        provider = (data.get("provider") or "").strip().lower()
        if provider != "searxng":
            return json.dumps({"status": "error", "message": "only SearXNG can be toggled"})
        enabled = data.get("enabled")
        if not isinstance(enabled, bool):
            return json.dumps({"status": "error", "message": "enabled must be a boolean"})
        local_config = conf()
        file_cfg = self._read_file_config()
        _set_search_disabled(local_config, "searxng", not enabled)
        _set_search_disabled(file_cfg, "searxng", not enabled)
        self._write_file_config(file_cfg)
        return json.dumps({"status": "success", "provider": provider, "enabled": enabled})

    @staticmethod
    def _reset_bridge() -> None:
        try:
            from bridge.bridge import Bridge
            Bridge().reset_bot()
        except Exception as exc:
            logger.warning(f"[ModelsHandler] Bridge reset failed: {exc}")

    @staticmethod
    def _refresh_voice_routing() -> None:
        try:
            from bridge.bridge import Bridge
            Bridge().refresh_voice()
        except Exception as exc:
            logger.warning(f"[ModelsHandler] Bridge voice refresh failed: {exc}")


def _base_is_usable(base: str) -> bool:
    raw = (base or "").strip().rstrip("/")
    if not raw.endswith("/v1"):
        return False
    parsed = urlparse(raw)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _tts_reply_mode(local_config: dict) -> str:
    if local_config.get("always_reply_voice", False):
        return "always"
    if local_config.get("voice_reply_voice", False):
        return "voice_if_voice"
    return "off"


def _fallback_model_ids(local_config: dict) -> List[str]:
    raw = local_config.get("agent_fallback_models")
    if isinstance(raw, list):
        out = []
        for item in raw:
            model = str(item or "").strip()
            if model and model not in out:
                out.append(model)
        return out
    cfg = local_config.get("chat_fallback") or {}
    chain = cfg.get("chain") if isinstance(cfg, dict) else None
    out = []
    if isinstance(chain, list):
        for item in chain:
            if isinstance(item, dict):
                model = str(item.get("model") or "").strip()
                if model and model not in out:
                    out.append(model)
    return out


def _disabled_search(ws_cfg: dict) -> set:
    raw = ws_cfg.get("disabled_providers")
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _set_nested(cfg: dict, top: str, name: str, key: str, value) -> None:
    bucket = cfg.get(top)
    if not isinstance(bucket, dict):
        bucket = {}
    node = bucket.get(name)
    if not isinstance(node, dict):
        node = {}
    node[key] = value
    bucket[name] = node
    cfg[top] = bucket


def _set_search_disabled(cfg: dict, provider: str, disabled: bool) -> None:
    tools_cfg = cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {}
    ws_cfg = tools_cfg.get("web_search") if isinstance(tools_cfg.get("web_search"), dict) else {}
    current = [p for p in _disabled_search(ws_cfg)]
    if disabled and provider not in current:
        current.append(provider)
    elif not disabled and provider in current:
        current = [p for p in current if p != provider]
    _set_nested(cfg, "tools", "web_search", "disabled_providers", current)


def _mirror_env(conf_key: str, value: str) -> None:
    env_key = CONFIG_TO_ENV.get(conf_key)
    if not env_key:
        return
    if value:
        os.environ[env_key] = value
    else:
        os.environ.pop(env_key, None)


def configured_litellm_models(timeout: float = 5) -> Tuple[List[dict], Optional[str]]:
    """Models on the saved LiteLLM endpoint, plus a short error when it failed.

    The result is cached so the settings page, the chat menu, and capability
    pickers share one request. A failure is cached briefly so a down proxy
    does not stall every console refresh for the full timeout.
    """
    local = conf()
    base = str(local.get("litellm_api_base") or "").strip()
    key = local.get("litellm_api_key") or ""
    if not isinstance(key, str):
        key = ""
    if not _base_is_usable(base):
        return [], "litellm_api_base must be an http(s) URL ending with /v1"
    now = time.monotonic()
    token = (base, key)
    with _discovery_lock:
        hit = _discovery_cache.get(token)
        if hit is not None:
            cached_at, cached_models, cached_error = hit
            ttl = _DISCOVERY_ERROR_TTL if cached_error else _DISCOVERY_TTL
            if now - cached_at < ttl:
                return list(cached_models or []), cached_error
    try:
        models = discover_litellm_models(base, key, timeout=timeout)
        error = None
    except ModelDiscoveryError as exc:
        models = []
        error = _redact(str(exc), key)
    with _discovery_lock:
        _discovery_cache[token] = (time.monotonic(), models, error)
    return list(models), error


def discover_litellm_models(api_base: str, api_key: str, timeout: float = 20) -> List[dict]:
    """List models on the proxy and tag them from /model/info when present."""
    base = api_base.strip().rstrip("/")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    proxies = _loopback_proxies(f"{base}/models")
    try:
        response = requests.get(
            f"{base}/models", headers=headers, timeout=timeout, proxies=proxies,
        )
    except requests.RequestException as exc:
        raise ModelDiscoveryError(
            _redact(f"could not reach {base}/models: {exc}", api_key)
        ) from exc
    if response.status_code >= 400:
        raise ModelDiscoveryError(
            _redact(
                f"GET /models returned HTTP {response.status_code}: {response.text[:200]}",
                api_key,
            )
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ModelDiscoveryError("GET /models did not return JSON") from exc
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ModelDiscoveryError("GET /models did not return a data list")

    info = _model_info(base, headers, timeout=timeout, proxies=proxies)
    models = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("id") or row.get("name") or "").strip()
        if not name or name in seen:
            continue
        if any(word in name.lower() for word in ("moderation", "rerank", "realtime")):
            continue
        seen.add(name)
        models.append(_tag_model(name, info.get(name) or {}))
    return models


def _model_info(api_base: str, headers: dict, timeout: float = 20, proxies=None) -> dict:
    origin = api_base[:-3] if api_base.endswith("/v1") else api_base
    try:
        response = requests.get(
            f"{origin}/model/info", headers=headers, timeout=timeout, proxies=proxies,
        )
    except requests.RequestException:
        return {}
    if response.status_code >= 400:
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {}
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("model_name") or row.get("id") or "").strip()
        meta = row.get("model_info") if isinstance(row.get("model_info"), dict) else row
        if name and isinstance(meta, dict):
            out[name] = meta
    return out


def _tag_model(name: str, info: dict) -> dict:
    mode = str(info.get("mode") or "").strip().lower()
    tags = list(_MODE_TAGS.get(mode, ["text"]))
    if info.get("supports_vision") and "vision" not in tags:
        tags.append("vision")
        if "text" not in tags:
            tags.insert(0, "text")
    entry = {"name": name, "id": name, "capabilities": tags}
    for src, dst in (("max_input_tokens", "context_window"), ("max_tokens", "max_output_tokens")):
        value = info.get(src) or info.get(dst)
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            entry[dst] = value
    return entry
