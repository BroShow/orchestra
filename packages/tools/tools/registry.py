"""Tool discovery + dispatch.

Reads `config/mcp_servers.yaml`, spins up each configured MCP server as a
stdio subprocess, pulls its tool list, and exposes a unified registry keyed
by `<server>.<tool>`.

Design note: the orchestrator imports `ToolRegistry` and holds an instance
open for the lifetime of a run. MCP sessions live inside an AsyncExitStack
so teardown is deterministic.
"""

from __future__ import annotations

import os
import shlex
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.approval import requires_approval


@dataclass(frozen=True)
class ToolInfo:
    qualified_name: str
    description: str
    parameters: dict[str, Any]
    requires_approval: bool


@dataclass
class _ServerConfig:
    name: str
    command: str
    transport: str = "stdio"


def load_config(path: str | Path) -> list[_ServerConfig]:
    raw = yaml.safe_load(Path(path).read_text())
    servers = []
    for entry in raw.get("servers") or []:
        servers.append(
            _ServerConfig(
                name=entry["name"],
                command=entry["command"],
                transport=entry.get("transport", "stdio"),
            )
        )
    return servers


class ToolRegistry:
    """Holds open MCP sessions to all configured servers.

    Usage:
        async with ToolRegistry.from_config("config/mcp_servers.yaml") as reg:
            specs = reg.list_specs()
            result = await reg.call("fs.read_file", {"path": "x.txt"})
    """

    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}  # server_name -> session
        self._tool_owner: dict[str, str] = {}  # qualified_name -> server_name
        self._tool_info: dict[str, ToolInfo] = {}  # qualified_name -> info

    @classmethod
    async def from_config(cls, path: str | Path) -> "ToolRegistry":
        reg = cls()
        reg._stack = AsyncExitStack()
        try:
            for cfg in load_config(path):
                await reg._add_stdio_server(cfg)
            return reg
        except BaseException:
            await reg._stack.aclose()
            reg._stack = None
            raise

    async def __aenter__(self) -> "ToolRegistry":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self._sessions.clear()
        self._tool_owner.clear()
        self._tool_info.clear()

    async def _add_stdio_server(self, cfg: _ServerConfig) -> None:
        if cfg.transport != "stdio":
            raise NotImplementedError(f"Transport {cfg.transport!r} is not supported yet")
        assert self._stack is not None
        argv = shlex.split(cfg.command)
        # Inherit the parent env so the child tool servers see WORKSPACE_DIR,
        # OLLAMA_BASE_URL, PATH, etc. MCP defaults to a minimal env otherwise.
        params = StdioServerParameters(
            command=argv[0],
            args=argv[1:],
            env=dict(os.environ),
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[cfg.name] = session

        listed = await session.list_tools()
        for tool in listed.tools:
            qname = f"{cfg.name}.{tool.name}"
            self._tool_owner[qname] = cfg.name
            self._tool_info[qname] = ToolInfo(
                qualified_name=qname,
                description=tool.description or "",
                parameters=tool.inputSchema or {"type": "object"},
                requires_approval=requires_approval(qname),
            )

    def list_specs(self) -> list[ToolInfo]:
        return list(self._tool_info.values())

    def get(self, qualified_name: str) -> ToolInfo:
        if qualified_name not in self._tool_info:
            raise KeyError(f"No such tool: {qualified_name}")
        return self._tool_info[qualified_name]

    async def call(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        if qualified_name not in self._tool_owner:
            raise KeyError(f"No such tool: {qualified_name}")
        server = self._tool_owner[qualified_name]
        local_name = qualified_name.split(".", 1)[1]
        session = self._sessions[server]
        result = await session.call_tool(local_name, arguments)
        # FastMCP returns a CallToolResult with `.content` (list of content blocks).
        # The orchestrator wants a string or structured payload; we concatenate text
        # content blocks. Structured content (images, etc.) is out of scope for v1.
        if getattr(result, "isError", False):
            # surface as an exception so the orchestrator's ToolMessage carries it
            raise RuntimeError(_stringify_content(result.content))
        return _stringify_content(result.content)


def _stringify_content(blocks: list) -> str:
    parts: list[str] = []
    for b in blocks or []:
        text = getattr(b, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts) if parts else ""
