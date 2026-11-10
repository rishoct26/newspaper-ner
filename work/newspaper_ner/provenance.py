"""Helpers for recording the source revision used by evaluation runs."""

from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def git_provenance() -> dict[str, str | bool | None]:
    """Return the current commit and whether the working tree has changes."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        ).stdout
        return {
            "git_commit_hash": commit or None,
            "git_working_tree_dirty": bool(status.strip()),
        }
    except (OSError, subprocess.SubprocessError):
        return {"git_commit_hash": None, "git_working_tree_dirty": None}
