"""Shell MCP server — `exec` runs a command in the sandboxed workspace.

The tool ALWAYS requires human approval (registered in tools.approval). The
MCP layer itself doesn't gate execution; the orchestrator's approval node
does. This module still enforces structural safety: args-as-list only (no
shell expansion), cwd=workspace, hard timeout.
"""

from __future__ import annotations

import subprocess

from mcp.server.fastmcp import FastMCP

from tools._sandbox import workspace_root

mcp = FastMCP("shell-tools")


DEFAULT_TIMEOUT_SECONDS = 30


@mcp.tool()
def exec(command: list[str], timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, object]:
    """Run `command` (a list of args) in the workspace. Returns stdout/stderr/code.

    Must receive a list. A string is rejected — there is no shell expansion.
    """
    if not isinstance(command, list) or not all(isinstance(a, str) for a in command):
        raise TypeError(
            "shell.exec requires `command` as a list[str] (no shell expansion). "
            f"Got {type(command).__name__}."
        )
    if not command:
        raise ValueError("shell.exec requires at least one argument in the command list")

    try:
        proc = subprocess.run(
            command,
            cwd=str(workspace_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[timed out after {timeout}s]",
            "returncode": -1,
        }

    return {
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
    }


if __name__ == "__main__":
    mcp.run()
