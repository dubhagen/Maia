"""Blank environment placeholders must not wipe settings saved in config.json."""
import json

import config


def _load(tmp_path, monkeypatch, saved, env):
    (tmp_path / "config.json").write_text(json.dumps(saved))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MAIA_DATA_DIR", str(tmp_path))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    config.load_config()
    return config.conf()


def test_blank_env_keeps_saved_litellm_key(tmp_path, monkeypatch):
    conf = _load(
        tmp_path,
        monkeypatch,
        {"litellm_api_key": "sk-saved", "model": "saved-model"},
        {"LITELLM_API_KEY": ""},
    )
    assert conf.get("litellm_api_key") == "sk-saved"


def test_non_blank_litellm_env_overrides(tmp_path, monkeypatch):
    conf = _load(
        tmp_path,
        monkeypatch,
        {"litellm_api_key": "sk-saved", "model": "saved-model"},
        {"LITELLM_API_KEY": "sk-env", "MODEL": "env-model"},
    )
    assert conf.get("litellm_api_key") == "sk-env"
    assert conf.get("model") == "env-model"


def test_vendor_env_does_not_override_config(tmp_path, monkeypatch):
    conf = _load(
        tmp_path,
        monkeypatch,
        {"deepseek_api_key": "sk-saved", "litellm_api_base": "http://127.0.0.1:4000/v1"},
        {"DEEPSEEK_API_KEY": "sk-env"},
    )
    assert conf.get("deepseek_api_key") == "sk-saved"
    assert conf.get("litellm_api_base") == "http://127.0.0.1:4000/v1"
