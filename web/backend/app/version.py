"""SimCash version info — single source of truth from repo root VERSION file."""
from __future__ import annotations

import subprocess
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"

VERSION: str = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "0.0.0-unknown"


def _git_hash() -> str:
    """Get short git commit hash, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_VERSION_FILE.parent,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    """Check if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD"],
            capture_output=True, timeout=5,
            cwd=_VERSION_FILE.parent,
        )
        return result.returncode != 0
    except Exception:
        return False


# Computed once at import time
GIT_HASH: str = _git_hash()
GIT_DIRTY: bool = _git_dirty()

# Full version string: "0.2.0+abc12345" or "0.2.0+abc12345.dirty"
VERSION_FULL: str = f"{VERSION}+{GIT_HASH}" + (".dirty" if GIT_DIRTY else "")


def version_info() -> dict[str, str]:
    """Return version metadata dict for embedding in checkpoints/API responses."""
    return {
        "version": VERSION,
        "git_hash": GIT_HASH,
        "git_dirty": GIT_DIRTY,
        "version_full": VERSION_FULL,
    }
