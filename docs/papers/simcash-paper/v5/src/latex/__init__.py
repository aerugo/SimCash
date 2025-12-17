"""LaTeX utilities for paper generation."""

from src.latex.formatting import format_ci, format_money, format_percent, format_table_row
from src.latex.tables import generate_bootstrap_table, generate_iteration_table

__all__ = [
    "format_money",
    "format_percent",
    "format_ci",
    "format_table_row",
    "generate_iteration_table",
    "generate_bootstrap_table",
]
