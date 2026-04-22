"""End-to-end: spawn real MCP stdio subprocesses and dispatch through them.

Verifies the wiring — config parsing, subprocess spawn, MCP initialize,
tool listing, tool dispatch — that unit tests can't reach. Self-contained
(no network, no Ollama), so it runs in the default test pass.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from tools.registry import ToolRegistry


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def config_path(tmp_path):
    """Minimal config with just fs tools — enough to prove discovery + dispatch.
    We skip web and shell here because web needs network and shell is tested
    via its unit tests; this test exists to prove the MCP pipeline itself.
    """
    cfg = tmp_path / "mcp_servers.yaml"
    cfg.write_text(
        textwrap.dedent(
            """\
            servers:
              - name: fs
                transport: stdio
                command: uv run python -m tools.fs_tools
            """
        )
    )
    return cfg


async def test_discovery_and_call(workspace, config_path):
    # Child process inherits WORKSPACE_DIR via env
    os.environ["WORKSPACE_DIR"] = str(workspace)
    (workspace / "hello.txt").write_text("world")

    async with await ToolRegistry.from_config(config_path) as reg:
        specs = reg.list_specs()
        names = {s.qualified_name for s in specs}
        assert {"fs.read_file", "fs.list_dir", "fs.write_file"} <= names

        result = await reg.call("fs.read_file", {"path": "hello.txt"})
        assert "world" in result


async def test_unknown_tool_raises(workspace, config_path):
    async with await ToolRegistry.from_config(config_path) as reg:
        with pytest.raises(KeyError, match="No such tool"):
            await reg.call("fs.does_not_exist", {})


async def test_approval_flag_round_trips(workspace, tmp_path):
    """A config that includes shell surfaces requires_approval=True on shell.exec."""
    cfg = tmp_path / "mcp_servers.yaml"
    cfg.write_text(
        textwrap.dedent(
            """\
            servers:
              - name: shell
                transport: stdio
                command: uv run python -m tools.shell_tools
            """
        )
    )
    async with await ToolRegistry.from_config(cfg) as reg:
        info = reg.get("shell.exec")
        assert info.requires_approval is True
