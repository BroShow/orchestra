"""Filesystem MCP server — read/list/write inside the sandboxed workspace."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tools._sandbox import resolve_inside_workspace, workspace_root

mcp = FastMCP("fs-tools")


@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file. `path` is relative to the workspace root."""
    full = resolve_inside_workspace(path)
    if not full.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    return full.read_text()


@mcp.tool()
def list_dir(path: str = ".") -> list[str]:
    """List files and subdirectories in `path` (relative to workspace root).

    Directories get a trailing slash. Returns names only, not full paths.
    """
    full = resolve_inside_workspace(path)
    if not full.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = []
    for child in sorted(full.iterdir()):
        entries.append(child.name + ("/" if child.is_dir() else ""))
    return entries


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write `content` to `path` (relative to workspace root), creating parents.

    Returns the written path (relative to workspace root) so the agent can
    confirm and reference it.
    """
    full = resolve_inside_workspace(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return str(full.relative_to(workspace_root()))


if __name__ == "__main__":
    mcp.run()
