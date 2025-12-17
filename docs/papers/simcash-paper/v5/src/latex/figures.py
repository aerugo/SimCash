"""LaTeX figure inclusion helpers."""

from __future__ import annotations


def include_figure(
    path: str,
    caption: str,
    label: str,
    width: float = 1.0,
    position: str = "htbp",
) -> str:
    """Generate LaTeX figure environment.

    Args:
        path: Path to image file (relative to document)
        caption: Figure caption text
        label: LaTeX label for cross-references
        width: Width as fraction of textwidth (default: 1.0)
        position: Float position specifier (default: htbp)

    Returns:
        Complete LaTeX figure environment string
    """
    return rf"""
\begin{{figure}}[{position}]
    \centering
    \includegraphics[width={width}\textwidth]{{{path}}}
    \caption{{{caption}}}
    \label{{{label}}}
\end{{figure}}
"""
