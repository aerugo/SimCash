"""LaTeX table generators.

This module provides functions for generating LaTeX tables from experiment data.
All tables use the data provider types and format values consistently.

Example:
    >>> from src.data_provider import AgentIterationResult
    >>> results = [AgentIterationResult(...), ...]
    >>> table = generate_iteration_table(results, caption="Results", label="tab:results")
"""

from __future__ import annotations

from src.data_provider import AgentIterationResult, BootstrapStats
from src.latex.formatting import format_ci, format_money, format_percent, format_table_row


def generate_iteration_table(
    results: list[AgentIterationResult],
    caption: str,
    label: str,
) -> str:
    """Generate LaTeX table for iteration-by-iteration results.

    Creates a table showing agent costs and liquidity fractions per iteration.

    Args:
        results: List of AgentIterationResult from DataProvider
        caption: Table caption text
        label: LaTeX label for referencing (e.g., "tab:exp1_results")

    Returns:
        Complete LaTeX table string with tabular environment

    Example:
        >>> results = provider.get_iteration_results("exp1", pass_num=1)
        >>> table = generate_iteration_table(results, "Exp1 Results", "tab:exp1")
    """
    # Group results by iteration
    iterations: dict[int, list[AgentIterationResult]] = {}
    for r in results:
        if r["iteration"] not in iterations:
            iterations[r["iteration"]] = []
        iterations[r["iteration"]].append(r)

    # Build table rows
    rows: list[str] = []

    # Header row
    header = format_table_row(
        ["Iteration", "Agent", "Cost", "Liquidity", "Accepted"]
    )
    rows.append(header)
    rows.append(r"\hline")

    # Data rows
    for iteration in sorted(iterations.keys()):
        for r in sorted(iterations[iteration], key=lambda x: x["agent_id"]):
            row = format_table_row([
                str(r["iteration"]),
                r["agent_id"],
                format_money(r["cost"]),
                format_percent(r["liquidity_fraction"]),
                "Yes" if r["accepted"] else "No",
            ])
            rows.append(row)

    # Build complete table
    table_body = "\n        ".join(rows)

    return rf"""
\begin{{table}}[htbp]
    \centering
    \caption{{{caption}}}
    \label{{{label}}}
    \begin{{tabular}}{{llrrr}}
        \hline
        {table_body}
        \hline
    \end{{tabular}}
\end{{table}}
"""


def generate_bootstrap_table(
    stats: dict[str, BootstrapStats],
    caption: str,
    label: str,
) -> str:
    """Generate LaTeX table for bootstrap statistics.

    Creates a table showing mean cost, std dev, and confidence intervals.

    Args:
        stats: Dict mapping agent_id to BootstrapStats
        caption: Table caption text
        label: LaTeX label for referencing

    Returns:
        Complete LaTeX table string

    Example:
        >>> stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)
        >>> table = generate_bootstrap_table(stats, "Bootstrap Stats", "tab:bootstrap")
    """
    rows: list[str] = []

    # Header row
    header = format_table_row(
        ["Agent", "Mean Cost", "Std Dev", "95\\% CI", "Samples"]
    )
    rows.append(header)
    rows.append(r"\hline")

    # Data rows
    for agent_id in sorted(stats.keys()):
        s = stats[agent_id]
        row = format_table_row([
            agent_id,
            format_money(s["mean_cost"]),
            format_money(s["std_dev"]),
            format_ci(s["ci_lower"], s["ci_upper"]),
            str(s["num_samples"]),
        ])
        rows.append(row)

    table_body = "\n        ".join(rows)

    return rf"""
\begin{{table}}[htbp]
    \centering
    \caption{{{caption}}}
    \label{{{label}}}
    \begin{{tabular}}{{lrrrr}}
        \hline
        {table_body}
        \hline
    \end{{tabular}}
\end{{table}}
"""
