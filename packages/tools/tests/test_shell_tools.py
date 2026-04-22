"""Unit tests for shell.exec — structural guards, not approval (handled upstream)."""

from __future__ import annotations

import pytest

from tools.shell_tools import exec as shell_exec


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def test_rejects_string_command(workspace):
    with pytest.raises(TypeError, match="list"):
        shell_exec("ls -la")  # type: ignore[arg-type]


def test_rejects_empty_list(workspace):
    with pytest.raises(ValueError):
        shell_exec([])


def test_rejects_non_str_args(workspace):
    with pytest.raises(TypeError):
        shell_exec(["ls", 42])  # type: ignore[list-item]


def test_runs_in_workspace_cwd(workspace):
    (workspace / "marker.txt").write_text("")
    result = shell_exec(["ls"])
    assert result["returncode"] == 0
    assert "marker.txt" in result["stdout"]


def test_captures_nonzero_exit(workspace):
    result = shell_exec(["sh", "-c", "exit 3"])
    assert result["returncode"] == 3


def test_timeout(workspace):
    result = shell_exec(["sleep", "2"], timeout=1)
    assert result["returncode"] == -1
    assert "timed out" in result["stderr"]
