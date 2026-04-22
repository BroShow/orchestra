"""Env-driven configuration for the model adapter."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from model_adapter.types import TaskClass


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    provider: str = Field(default="ollama", validation_alias="MODEL_PROVIDER")
    ollama_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL"
    )
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    default_model: str = Field(default="qwen2.5:14b", validation_alias="DEFAULT_MODEL")
    router_model: str = Field(default="llama3.2:3b", validation_alias="ROUTER_MODEL")
    heavy_model: str = Field(default="qwen2.5:32b", validation_alias="HEAVY_MODEL")

    def task_model_map(self) -> dict[TaskClass, str]:
        return {
            TaskClass.CLASSIFY: self.router_model,
            TaskClass.REASON: self.default_model,
            TaskClass.HEAVY: self.heavy_model,
        }
