"""API-layer settings — loaded from env via pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./orchestra.db",
        validation_alias="DATABASE_URL",
    )
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:3000", validation_alias="CORS_ORIGINS"
    )

    # Path to the MCP server config file (relative to repo root)
    mcp_config: str = Field(
        default="config/mcp_servers.yaml", validation_alias="MCP_CONFIG"
    )

    # Checkpointer: "memory" (volatile, single-process) or "postgres"
    checkpointer: str = Field(default="memory", validation_alias="CHECKPOINTER")

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
