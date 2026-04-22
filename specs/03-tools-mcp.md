# 03 — Tools (MCP-defined)

## Goal
Every tool the agent can use is defined as an MCP tool. The orchestrator discovers tools at startup; adding a new tool means dropping a new MCP server into config, not touching agent code.

## Location
`packages/tools/` contains in-process MCP servers we own. External MCP servers (e.g., a future Slack MCP) connect via stdio or HTTP.

## Initial Tool Set (PoC)
1. **`fs.read_file`** — read a file from a sandboxed workspace dir
2. **`fs.list_dir`** — list contents of a workspace dir
3. **`web.search`** — web search; uses a free provider (DuckDuckGo via `ddgs` package, or Brave Search free tier with optional API key)
4. **`web.fetch`** — fetch a URL, return cleaned text (use `trafilatura` or `readability-lxml`)
5. **`shell.exec`** — run a shell command in a sandboxed dir; **always requires human approval** (see HITL section)

That's it for v1. Resist the urge to add more. Each tool is a place agents can fail unpredictably.

## Tool Definition Pattern
```python
# packages/tools/tools/fs_tools.py
from mcp.server.fastmcp import FastMCP
from pathlib import Path

mcp = FastMCP("fs-tools")
WORKSPACE = Path(os.environ["WORKSPACE_DIR"]).resolve()

@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the workspace. Path must be relative to workspace root."""
    full = (WORKSPACE / path).resolve()
    if not full.is_relative_to(WORKSPACE):
        raise ValueError("Path escapes workspace")
    return full.read_text()
```

## Sandboxing Rules
- All filesystem tools operate inside `WORKSPACE_DIR` (env var, defaults to `./workspace`).
- Path traversal must be blocked — resolve and check `is_relative_to`.
- `shell.exec` runs with `cwd=WORKSPACE_DIR`, no shell expansion (`shell=False`, args list only), 30-second timeout.
- Network tools have no sandbox but must respect a denylist (env var `WEB_FETCH_DENYLIST`, comma-separated domains).

## Human-in-the-Loop (HITL)
Each tool declares a `requires_approval` flag. Tools with this flag set cause the orchestrator to pause and emit an `approval_required` event. The user approves/denies via the UI before execution proceeds.

```python
@mcp.tool(requires_approval=True)  # custom decorator we add
def exec(command: list[str]) -> str:
    ...
```

If the MCP SDK doesn't support custom flags, maintain a separate registry: `TOOLS_REQUIRING_APPROVAL: set[str] = {"shell.exec"}`.

## Discovery
On orchestrator startup, connect to all configured MCP servers, list their tools, and build a unified `ToolSpec` registry that the model adapter receives. Config:

```yaml
# config/mcp_servers.yaml
servers:
  - name: fs
    transport: stdio
    command: python -m tools.fs_tools
  - name: web
    transport: stdio
    command: python -m tools.web_tools
  - name: shell
    transport: stdio
    command: python -m tools.shell_tools
```

## Acceptance Criteria
- [ ] Each tool implemented as an MCP server, runnable standalone via `python -m tools.<name>`.
- [ ] Discovery loads tools dynamically from `config/mcp_servers.yaml`.
- [ ] Sandboxing: unit tests confirm path-traversal attempts raise; shell tool rejects strings (must be list).
- [ ] HITL flag round-trips: orchestrator can identify which tools need approval.
- [ ] Integration test: agent (using a real local model) successfully reads a file and fetches a URL in a single multi-step run.
- [ ] No tool can be added by editing agent code — only by adding/configuring an MCP server.

## Anti-Goals
- Don't add Gmail, Calendar, GitHub, etc. in v1. Those are integration tickets, not PoC scope.
- Don't build a tool sandbox using Docker/firecracker yet. Path checks + workspace dir is enough for PoC.
