"""Minimal interface the orchestrator uses to execute tools.

In production this wraps `tools.ToolRegistry`. In tests it can be a fake
that returns scripted responses. Keeping the interface narrow means the
orchestrator doesn't grow a dependency on the MCP stdio pipeline — only
on "give me a name + args, return a string."
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolRunner(Protocol):
    async def call(self, qualified_name: str, arguments: dict[str, Any]) -> Any: ...

    def requires_approval(self, qualified_name: str) -> bool: ...
