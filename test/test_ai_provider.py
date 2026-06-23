from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.ai_provider import AIProviderConfig, build_chat_openai, resolve_ai_provider_config


def test_resolve_ai_provider_prefers_global_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")

    config = resolve_ai_provider_config(
        {
            "ai_api_key": "global-key",
            "ai_base_url": "https://global.example.com/v1",
            "ai_model": "global-model",
        }
    )

    assert config.api_key == "global-key"
    assert config.base_url == "https://global.example.com/v1"
    assert config.model == "global-model"


def test_resolve_ai_provider_falls_back_to_openai_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL_NAME", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)

    config = resolve_ai_provider_config({})

    assert config.api_key == "openai-key"
    assert config.base_url == "https://openai.example.com/v1"
    assert config.model == "gpt-test"


def test_resolve_ai_provider_supports_legacy_deepseek_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")

    config = resolve_ai_provider_config({})

    assert config.api_key == "legacy-key"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-chat"


def test_build_chat_openai_passes_provider_settings(monkeypatch):
    captured: dict[str, object] = {}

    class DummyChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.core.ai_provider.ChatOpenAI", DummyChatOpenAI)

    provider = AIProviderConfig(
        api_key="abc",
        base_url="https://provider.example.com/v1",
        model="provider-model",
    )
    build_chat_openai(
        provider_config=provider,
        temperature=0.3,
        max_tokens=1234,
        request_timeout=45,
        max_retries=2,
    )

    assert captured["api_key"] == "abc"
    assert captured["base_url"] == "https://provider.example.com/v1"
    assert captured["model"] == "provider-model"
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 1234
    assert captured["request_timeout"] == 45
    assert captured["max_retries"] == 2


def test_build_chat_openai_requires_api_key():
    with pytest.raises(ValueError, match="AI API Key"):
        build_chat_openai(provider_config=AIProviderConfig(api_key="", base_url=None, model="any-model"))
