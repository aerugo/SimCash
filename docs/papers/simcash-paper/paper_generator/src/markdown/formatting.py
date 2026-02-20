"""Markdown formatting utilities.

Same interface as latex/formatting.py but for markdown/web output.
"""

from __future__ import annotations


def format_money(cents: int) -> str:
    r"""Format cents as dollar string for markdown.

    Uses \\$ to prevent remark-math from treating $ as math delimiter.

    Args:
        cents: Amount in cents

    Returns:
        Dollar string (e.g., "\\$1,234")
    """
    dollars = cents / 100
    if dollars == int(dollars):
        return f"\\${int(dollars):,}"
    return f"\\${dollars:,.2f}"


def format_percent(fraction: float) -> str:
    """Format fraction as percent string for markdown.

    Args:
        fraction: Decimal fraction (0.0 to 1.0)

    Returns:
        Percent string (e.g., "16.5%")
    """
    percent = fraction * 100
    if percent == int(percent):
        return f"{int(percent)}%"
    return f"{percent:.1f}%"


def format_ci(lower: int, upper: int) -> str:
    """Format confidence interval.

    Args:
        lower: Lower bound in cents
        upper: Upper bound in cents

    Returns:
        CI string (e.g., "[$100, $150]")
    """
    return f"[{format_money(lower)}, {format_money(upper)}]"
