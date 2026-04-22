"""Factory swaps providers by env, and the Anthropic stub exists but raises."""

from __future__ import annotations

import pytest

from model_adapter import ModelMessage, ModelSettings, get_client
from model_adapter.providers.anthropic import AnthropicProvider
from model_adapter.providers.ollama import OllamaProvider
from model_adapter.providers.openai_compat import OpenAICompatProvider


def test_factory_picks_ollama():
    client = get_client(ModelSettings(MODEL_PROVIDER="ollama"))
    assert isinstance(client, OllamaProvider)


def test_factory_picks_openai_compat():
    client = get_client(
        ModelSettings(
            MODEL_PROVIDER="openai_compat",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_API_KEY="sk-x",
        )
    )
    assert isinstance(client, OpenAICompatProvider)


def test_factory_rejects_openai_compat_without_base_url():
    with pytest.raises(ValueError, match="OPENAI_BASE_URL"):
        get_client(ModelSettings(MODEL_PROVIDER="openai_compat"))


def test_factory_picks_anthropic_stub():
    client = get_client(ModelSettings(MODEL_PROVIDER="anthropic"))
    assert isinstance(client, AnthropicProvider)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown MODEL_PROVIDER"):
        get_client(ModelSettings(MODEL_PROVIDER="nonsense"))


async def test_anthropic_stub_raises_clearly():
    client = AnthropicProvider(api_key=None, default_model="claude-opus-4-7")
    with pytest.raises(NotImplementedError, match="v1 stub"):
        await client.complete(messages=[ModelMessage(role="user", content="hi")])
