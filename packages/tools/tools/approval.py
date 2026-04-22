"""Registry of tool names that require human approval before execution.

The MCP SDK doesn't support custom `requires_approval=True` flags on
@mcp.tool() decorators, so we keep the list here. Any tool whose
fully-qualified name appears in TOOLS_REQUIRING_APPROVAL triggers the
orchestrator's approval gate.
"""

from __future__ import annotations

TOOLS_REQUIRING_APPROVAL: set[str] = {
    "shell.exec",
}


def requires_approval(qualified_name: str) -> bool:
    return qualified_name in TOOLS_REQUIRING_APPROVAL
