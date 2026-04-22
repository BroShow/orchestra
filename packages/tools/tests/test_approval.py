"""The approval registry is part of the HITL contract — keep it tested."""

from __future__ import annotations

from tools import TOOLS_REQUIRING_APPROVAL, requires_approval


def test_shell_exec_requires_approval():
    assert requires_approval("shell.exec")


def test_fs_tools_do_not_require_approval():
    assert not requires_approval("fs.read_file")
    assert not requires_approval("fs.write_file")
    assert not requires_approval("fs.list_dir")


def test_web_tools_do_not_require_approval():
    assert not requires_approval("web.search")
    assert not requires_approval("web.fetch")


def test_unknown_tool_does_not_require_approval():
    assert not requires_approval("made.up")


def test_registry_has_shell_exec():
    assert "shell.exec" in TOOLS_REQUIRING_APPROVAL
