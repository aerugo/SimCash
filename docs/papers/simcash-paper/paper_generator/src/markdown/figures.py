"""Markdown figure inclusion helpers."""

from __future__ import annotations

from pathlib import PurePosixPath


def include_figure(path: str, caption: str) -> str:
    """Generate markdown image reference for web docs.

    Args:
        path: Path to image file (e.g., "charts/exp1_pass1_combined.png")
        caption: Image caption/alt text

    Returns:
        Markdown image string with web API path
    """
    filename = PurePosixPath(path).name
    return f"![{caption}](/api/docs/images/paper/{filename})"
