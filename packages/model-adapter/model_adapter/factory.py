"""Factory for picking a provider from env config."""

from __future__ import annotations

from model_adapter.client import ModelClient
from model_adapter.config import ModelSettings
from model_adapter.providers.anthropic import AnthropicProvider
from model_adapter.providers.ollama import OllamaProvider
from model_adapter.providers.openai_compat import OpenAICompatProvider


def get_client(settings: ModelSettings | None = None) -> ModelClient:
    """Return a ModelClient based on the configured provider."""
    s = settings or ModelSettings()
    if s.provider == "ollama":
        return OllamaProvider(base_url=s.ollama_base_url, default_model=s.default_model)
    if s.provider == "openai_compat":
        if not s.openai_base_url:
            raise ValueError("OPENAI_BASE_URL must be set when MODEL_PROVIDER=openai_compat")
        return OpenAICompatProvider(
            base_url=s.openai_base_url,
            api_key=s.openai_api_key,
            default_model=s.default_model,
        )
    if s.provider == "anthropic":
        return AnthropicProvider(api_key=s.anthropic_api_key, default_model=s.default_model)
    raise ValueError(f"Unknown MODEL_PROVIDER: {s.provider!r}")
