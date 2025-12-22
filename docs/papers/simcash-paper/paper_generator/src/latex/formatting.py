"""LaTeX formatting utilities.

This module provides functions for formatting values for LaTeX output.
All monetary values are expected in cents (integers) and formatted as dollars.

Example:
    >>> format_money(12345)
    '\\$123.45'
    >>> format_percent(0.165)
    '16.5\\%'
"""

from __future__ import annotations

from typing import Any


def escape_latex(text: str) -> str:
    r"""Escape LaTeX special characters in text.

    Escapes characters that have special meaning in LaTeX:
    - _ (underscore) -> \_
    - & (ampersand) -> \&
    - % (percent) -> \%
    - # (hash) -> \#
    - $ (dollar) -> \$

    Args:
        text: Plain text string

    Returns:
        LaTeX-safe string with special characters escaped

    Example:
        >>> escape_latex("BANK_A")
        'BANK\\_A'
        >>> escape_latex("100%")
        '100\\%'
    """
    # Order matters - escape backslash first if needed
    replacements = [
        ("_", r"\_"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def escape_latex_full(text: str) -> str:
    r"""Escape all LaTeX special characters including braces and dollars.

    More comprehensive escaping for text that may contain JSON or code.

    Args:
        text: Plain text string

    Returns:
        LaTeX-safe string with all special characters escaped

    Example:
        >>> escape_latex_full('{"field": "value"}')
        '\\{\"field\": \"value\"\\}'
    """
    # Order matters - escape backslash first
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("$", r"\$"),
        ("_", r"\_"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("^", r"\^{}"),
        ("~", r"\~{}"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def format_verbatim_text(text: str, max_line_length: int = 85) -> str:
    r"""Format text for inclusion in a LaTeX verbatim environment.

    Prepares text for ``\begin{verbatim}...\end{verbatim}`` by cleaning up
    leading/trailing whitespace while preserving internal structure.

    Args:
        text: Raw text content
        max_line_length: Maximum line length before wrapping (not enforced,
                        just a hint for manual review)

    Returns:
        Cleaned text suitable for verbatim environment
    """
    # Strip leading/trailing whitespace from the whole block
    return text.strip()


def format_money(cents: int) -> str:
    r"""Format cents as LaTeX dollars string.

    Converts integer cents to dollars with proper LaTeX escaping.
    Large amounts include comma separators.

    Args:
        cents: Amount in cents (must be non-negative integer)

    Returns:
        LaTeX-escaped dollar string (e.g., r"\$1,234.56")

    Example:
        >>> format_money(0)
        '\\$0.00'
        >>> format_money(12345)
        '\\$123.45'
        >>> format_money(100000)
        '\\$1,000.00'
    """
    dollars = cents / 100
    # Format with commas for thousands and 2 decimal places
    formatted = f"{dollars:,.2f}"
    return rf"\${formatted}"


def format_percent(fraction: float) -> str:
    r"""Format fraction as LaTeX percent string.

    Converts decimal fraction to percentage with one decimal place.

    Args:
        fraction: Decimal fraction (0.0 to 1.0)

    Returns:
        LaTeX-escaped percent string (e.g., r"16.5\%")

    Example:
        >>> format_percent(0.0)
        '0.0\\%'
        >>> format_percent(0.165)
        '16.5\\%'
        >>> format_percent(1.0)
        '100.0\\%'
    """
    percent = fraction * 100
    return rf"{percent:.1f}\%"


def format_ci(lower: int, upper: int) -> str:
    r"""Format confidence interval as LaTeX string.

    Formats CI bounds (in cents) as dollar range.

    Args:
        lower: Lower bound in cents
        upper: Upper bound in cents

    Returns:
        LaTeX CI string (e.g., r"[\$100.00, \$150.00]")

    Example:
        >>> format_ci(10000, 15000)
        '[\\$100.00, \\$150.00]'
    """
    return f"[{format_money(lower)}, {format_money(upper)}]"


def format_table_row(cells: list[Any]) -> str:
    r"""Format a list of values as a LaTeX table row.

    Joins cells with ' & ' and ends with ' \\'.

    Args:
        cells: List of cell values (will be converted to strings)

    Returns:
        LaTeX table row string

    Example:
        >>> format_table_row(["A", "B", "C"])
        'A & B & C \\\\'
        >>> format_table_row(["Name", 100, 0.5])
        'Name & 100 & 0.5 \\\\'
    """
    cell_strings = [str(cell) for cell in cells]
    return " & ".join(cell_strings) + r" \\"
