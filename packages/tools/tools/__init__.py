"""Tool servers and registry.

Public surface:
- `ToolRegistry`: open/close MCP sessions, list tools, dispatch calls.
- `ToolInfo`: metadata for a single discovered tool.
- `requires_approval(name)`: does this tool need a human gate?
"""

from tools.approval import TOOLS_REQUIRING_APPROVAL, requires_approval
from tools.registry import ToolInfo, ToolRegistry, load_config

__all__ = [
    "TOOLS_REQUIRING_APPROVAL",
    "ToolInfo",
    "ToolRegistry",
    "load_config",
    "requires_approval",
]
