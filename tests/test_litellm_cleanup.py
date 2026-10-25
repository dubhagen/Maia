"""LiteLLM endpoint, discovery, channels, and SearXNG fail-closed behavior."""
import json
from unittest.mock import MagicMock

import pytest
import requests

from agent.tools.web_search import web_search as web_search_module
from channel.channel_factory import create_channel
from channel.web.api.models import (
    configured_litellm_models,
    discover_litellm_models,
    invalidate_litellm_discovery,
)
from channel.web.api.sessions import _session_model_catalog
from config import conf
from models import model_catalog
from models.litellm.endpoint import LiteLLMConfigError, litellm_api_base
from models.litellm.http_client import OpenAIHTTPClient


BASE = "http://127.0.0.1:4000/v1"


def _resp(payload, status=200, content=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.text = json.dumps(payload)
    response.content = content if content is not None else b""
    return response


def test_chat_completions_posts_model_and_optional_key(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, proxies=None, **kwargs):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return _resp({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("models.litellm.http_client.requests.post", fake_post)
    client = OpenAIHTTPClient(api_key="sk-proxy", api_base=BASE)
    body = client.chat_completions(model="openai/gpt-4o", messages=[{"role": "user", "content": "hi"}])
    assert body["choices"][0]["message"]["content"] == "ok"
    assert seen["url"] == BASE + "/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer sk-proxy"
    assert seen["json"]["model"] == "openai/gpt-4o"
    assert "HTTP-Referer" not in seen["headers"]


def test_empty_api_key_omits_authorization(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, proxies=None, **kwargs):
        seen["headers"] = headers
        return _resp({"data": [{"embedding": [0.1, 0.2], "index": 0}]})

    monkeypatch.setattr("models.litellm.http_client.requests.post", fake_post)
    client = OpenAIHTTPClient(api_key="", api_base=BASE)
    client.embeddings(model="embed-1", input=["hello"])
    assert "Authorization" not in seen["headers"]


def test_images_asr_and_tts_use_the_same_base(monkeypatch, tmp_path):
    urls = []

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None, proxies=None, **kwargs):
        urls.append(url)
        if url.endswith("/audio/speech"):
            return _resp({}, content=b"RIFF")
        if url.endswith("/audio/transcriptions"):
            return _resp({"text": "hello"})
        return _resp({"data": [{"url": "http://img.local/a.png"}]})

    monkeypatch.setattr("models.litellm.http_client.requests.post", fake_post)
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"wav")
    client = OpenAIHTTPClient(api_key="k", api_base=BASE)
    client.images_generate(model="image-1", prompt="a cat")
    client.audio_speech(model="tts-1", input="hello", voice="alloy")
    client.audio_transcriptions(file_path=str(audio), model="asr-1")
    assert urls == [
        BASE + "/images/generations",
        BASE + "/audio/speech",
        BASE + "/audio/transcriptions",
    ]


def test_missing_base_fails_closed_and_ignores_vendor_keys(monkeypatch):
    monkeypatch.setitem(conf(), "litellm_api_base", "")
    monkeypatch.setitem(conf(), "open_ai_api_key", "sk-vendor")
    monkeypatch.setitem(conf(), "open_ai_api_base", "https://api.openai.com/v1")
    monkeypatch.setitem(conf(), "unused_vendor_api_key", "sk-unused")
    with pytest.raises(LiteLLMConfigError):
        litellm_api_base()
    assert "open_ai_api_key" not in conf().get("litellm_api_key", "")


def test_discovery_maps_modes_and_ignores_a_failed_model_info(monkeypatch):
    def fake_get(url, headers=None, timeout=None, **kwargs):
        if url.endswith("/v1/models"):
            return _resp({"data": [
                {"id": "chat-a"},
                {"id": "embed-a"},
                {"id": "moderation-x"},
            ]})
        if url.endswith("/model/info"):
            return _resp({"data": [
                {"model_name": "chat-a", "model_info": {"mode": "chat", "supports_vision": True, "max_input_tokens": 8192}},
                {"model_name": "embed-a", "model_info": {"mode": "embedding"}},
            ]})
        raise AssertionError(url)

    monkeypatch.setattr("channel.web.api.models.requests.get", fake_get)
    models = discover_litellm_models(BASE, "sk-proxy")
    by_id = {item["id"]: item for item in models}
    assert "moderation-x" not in by_id
    assert by_id["chat-a"]["capabilities"] == ["text", "vision"]
    assert by_id["chat-a"]["context_window"] == 8192
    assert by_id["embed-a"]["capabilities"] == ["embedding"]


def test_unknown_mode_defaults_to_text(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None, proxies=None, **kwargs):
        seen["proxies"] = proxies
        if url.endswith("/model/info"):
            return _resp({}, status=404)
        return _resp({"data": [{"id": "mystery-model"}]})

    monkeypatch.setattr("channel.web.api.models.requests.get", fake_get)
    models = discover_litellm_models(BASE, "")
    assert models == [{"name": "mystery-model", "id": "mystery-model", "capabilities": ["text"]}]
    assert seen["proxies"] == {"http": None, "https": None}


def test_saved_endpoint_seeds_the_chat_model_list(monkeypatch):
    monkeypatch.setattr(
        "channel.web.api.models.discover_litellm_models",
        lambda base, key, timeout=20: [
            {"name": "grok-4.7", "id": "grok-4.7", "capabilities": ["text", "vision"]},
            {"name": "grok-image", "id": "grok-image", "capabilities": ["image"]},
        ],
    )
    monkeypatch.setattr(model_catalog, "get_catalog_map", lambda: {})
    monkeypatch.setattr(model_catalog, "get_hidden_map", lambda: {})
    monkeypatch.setitem(conf(), "litellm_api_base", BASE)
    monkeypatch.setitem(conf(), "litellm_api_key", "sk-test")
    monkeypatch.setitem(conf(), "model", "")
    invalidate_litellm_discovery()
    try:
        models, err = configured_litellm_models()
        assert err is None
        assert [item["name"] for item in models] == ["grok-4.7", "grok-image"]
        catalog = _session_model_catalog()
        assert catalog == [{"id": "litellm", "label": "LiteLLM", "models": ["grok-4.7"]}]
    finally:
        invalidate_litellm_discovery()


def test_discovery_failure_is_reported_and_does_not_raise(monkeypatch):
    def boom(url, headers=None, timeout=None, proxies=None, **kwargs):
        raise requests.ConnectionError("proxy refused")

    monkeypatch.setattr("channel.web.api.models.requests.get", boom)
    monkeypatch.setitem(conf(), "litellm_api_base", BASE)
    monkeypatch.setitem(conf(), "litellm_api_key", "sk-secret-value")
    invalidate_litellm_discovery()
    try:
        models, err = configured_litellm_models()
    finally:
        invalidate_litellm_discovery()
    assert models == []
    assert err is not None
    assert "could not reach" in err
    assert "proxy refused" in err
    assert "sk-secret-value" not in err


def test_channel_factory_rejects_removed_channels():
    with pytest.raises(RuntimeError):
        create_channel("feishu")
    with pytest.raises(RuntimeError):
        create_channel("weixin")


def test_vision_uses_the_chat_model_when_the_proxy_marks_it_visual(monkeypatch):
    from agent.tools.vision.vision import resolve_vision_model

    monkeypatch.setattr(
        "agent.tools.vision.vision.conf",
        lambda: {"vision_model": "", "model": "grok-4.7"},
    )
    monkeypatch.setattr(
        "channel.web.api.models.configured_litellm_models",
        lambda timeout=5: ([{"name": "grok-4.7", "capabilities": ["text", "vision"]}], None),
    )
    assert resolve_vision_model() == "grok-4.7"


def test_vision_stays_off_for_a_text_only_chat_model(monkeypatch):
    from agent.tools.vision.vision import resolve_vision_model

    monkeypatch.setattr(
        "agent.tools.vision.vision.conf",
        lambda: {"vision_model": "", "model": "grok-tts"},
    )
    monkeypatch.setattr(
        "channel.web.api.models.configured_litellm_models",
        lambda timeout=5: ([{"name": "grok-tts", "capabilities": ["tts"]}], None),
    )
    assert resolve_vision_model() == ""


def test_stream_retries_when_grok_rejects_presence_penalty():
    from models.litellm.http_client import OpenAIHTTPError
    from models.openai_compatible_bot import OpenAICompatibleBot

    message = "Model grok-4.7 does not support parameter presencePenalty."
    assert OpenAICompatibleBot._sampling_rejected(message)

    calls = []

    class FakeClient:
        def chat_completions(self, **kwargs):
            calls.append(kwargs)
            if "presence_penalty" in kwargs:
                raise OpenAIHTTPError(400, {"error": {"message": message}}, message)

            def chunks():
                yield {"choices": [{"delta": {"content": "hello"}}]}

            return chunks()

    bot = OpenAICompatibleBot()
    bot._get_http_client = lambda: FakeClient()
    result = list(bot._handle_stream_response(
        {
            "model": "grok-4.7",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "stream": True,
        },
        "sk-test",
        BASE,
    ))
    assert "presence_penalty" not in calls[1]
    assert "frequency_penalty" not in calls[1]
    assert "temperature" not in calls[1]
    assert result[0]["choices"][0]["delta"]["content"] == "hello"


def test_web_search_without_searxng_does_not_call_out(monkeypatch):
    monkeypatch.setattr(web_search_module, "conf", lambda: {"tools": {"web_search": {}}})
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    def boom(*args, **kwargs):
        raise AssertionError("web search called the network")

    monkeypatch.setattr(web_search_module.requests, "get", boom)
    result = web_search_module.WebSearch().execute({"query": "maia"})
    assert result.status == "error"
    assert "searxng" in str(result.result).lower()
