"""Run ID generation. ULIDs are lexicographically sortable by time, which
makes event log and run list queries cheap to read in chronological order
without a separate sort."""

from __future__ import annotations

from ulid import ULID


def new_run_id() -> str:
    return f"run_{ULID()!s}"
