"""Unit tests for the fs tools — exercised via the underlying functions,
not through the MCP stdio layer (that's covered in test_registry_roundtrip).
"""

from __future__ import annotations

import pytest

from tools.fs_tools import list_dir, read_file, write_file


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def test_read_file(workspace):
    (workspace / "hello.txt").write_text("hi")
    assert read_file("hello.txt") == "hi"


def test_read_file_missing(workspace):
    with pytest.raises(FileNotFoundError):
        read_file("does-not-exist.txt")


def test_list_dir_default_is_workspace_root(workspace):
    (workspace / "a.txt").write_text("")
    (workspace / "sub").mkdir()
    entries = list_dir(".")
    assert "a.txt" in entries
    assert "sub/" in entries


def test_write_file_creates_parents(workspace):
    result = write_file("notes/day1.md", "hello")
    assert result == "notes/day1.md"
    assert (workspace / "notes/day1.md").read_text() == "hello"


def test_path_traversal_blocked_on_read(workspace):
    with pytest.raises(ValueError, match="escapes workspace"):
        read_file("../etc/passwd")


def test_path_traversal_blocked_on_write(workspace):
    with pytest.raises(ValueError, match="escapes workspace"):
        write_file("../outside.txt", "x")


def test_path_traversal_blocked_on_list(workspace):
    with pytest.raises(ValueError, match="escapes workspace"):
        list_dir("..")
