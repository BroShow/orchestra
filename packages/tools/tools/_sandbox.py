"""Shared sandboxing helpers — every tool that touches disk uses these."""

from __future__ import annotations

import os
from pathlib import Path


def workspace_root() -> Path:
    raw = os.environ.get("WORKSPACE_DIR", "./workspace")
    p = Path(raw).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_inside_workspace(path: str) -> Path:
    """Resolve `path` (relative to workspace) and block any escape via `..` or symlink.

    Raises ValueError if the resolved path lies outside the workspace root.
    """
    root = workspace_root()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {path!r}")
    return candidate
