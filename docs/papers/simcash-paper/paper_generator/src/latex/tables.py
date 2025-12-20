"""LaTeX table generators.

This module provides functions for generating LaTeX tables from experiment data.
All tables use the data provider types and format values consistently.

Example:
    >>> from src.data_provider import AgentIterationResult
    >>> results = [AgentIterationResult(...), ...]
    >>> table = generate_iteration_table(results, caption="Results", label="tab:results")
"""

from __future__ import annotations

from src.data_provider import (
    AgentIterationResult,
    BootstrapStats,
    ConvergenceStats,
    PassSummary,
)
from src.latex.formatting import escape_latex, format_ci, format_money, format_percent, format_table_row


def generate_iteration_table(
    results: list[AgentIterationResult],
    caption: str,
    label: str,
    max_rows: int | None = None,
    position: str = "htbp",
) -> str:
    """Generate LaTeX table for iteration-by-iteration results.

    Creates a table showing agent costs and liquidity fractions per iteration.
    Baseline iteration (-1) is displayed as "Baseline" in the table.

    For long experiments (>15 iterations), uses longtable to span multiple pages.

    The "Accepted" column is NOT included because the underlying data has a
    known bug where accepted_changes is always False. Acceptance should be
    inferred from cost improvement if needed.

    Args:
        results: List of AgentIterationResult from DataProvider
        caption: Table caption text
        label: LaTeX label for referencing (e.g., "tab:exp1_results")
        max_rows: If set, truncate to this many iterations (showing first and last)
        position: Float position specifier for short tables (default: htbp).
            Use "H" to force table to stay in place (requires float package).

    Returns:
        Complete LaTeX table string with tabular or longtable environment

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

    sorted_iters = sorted(iterations.keys())
    num_iterations = len(sorted_iters)

    # Build table rows
    rows: list[str] = []

    # Data rows
    for iteration in sorted_iters:
        for r in sorted(iterations[iteration], key=lambda x: x["agent_id"]):
            # Display "Baseline" for iteration -1, otherwise show the iteration number
            iter_display = "Baseline" if r.get("is_baseline", False) or r["iteration"] == -1 else str(r["iteration"])
            row = format_table_row([
                iter_display,
                escape_latex(r["agent_id"]),
                format_money(r["cost"]),
                format_percent(r["liquidity_fraction"]),
            ])
            rows.append(row)

    # Use longtable for experiments with many iterations (>15)
    if num_iterations > 15:
        # longtable format for multi-page tables
        table_body = "\n        ".join(rows)

        return rf"""
\begin{{longtable}}{{llrr}}
    \caption{{{caption}}} \label{{{label}}} \\
    \hline
    Iteration & Agent & Cost & Liquidity \\
    \hline
    \endfirsthead

    \multicolumn{{4}}{{c}}{{\tablename\ \thetable{{}} -- continued from previous page}} \\
    \hline
    Iteration & Agent & Cost & Liquidity \\
    \hline
    \endhead

    \hline
    \multicolumn{{4}}{{r}}{{Continued on next page}} \\
    \endfoot

    \hline
    \endlastfoot

        {table_body}
\end{{longtable}}
"""
    else:
        # Standard table for shorter experiments
        table_body = "\n        ".join(rows)
        header = format_table_row(["Iteration", "Agent", "Cost", "Liquidity"])

        return rf"""
\begin{{table}}[{position}]
    \centering
    \caption{{{caption}}}
    \label{{{label}}}
    \begin{{tabular}}{{llrr}}
        \hline
        {header}
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
            escape_latex(agent_id),
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


def generate_pass_summary_table(
    summaries: list[PassSummary],
    caption: str,
    label: str,
    exp_name: str = "Experiment",
) -> str:
    """Generate LaTeX table summarizing all passes of an experiment.

    Args:
        summaries: List of PassSummary from DataProvider
        caption: Table caption text
        label: LaTeX label for referencing
        exp_name: Name of experiment for context

    Returns:
        Complete LaTeX table string

    Example:
        >>> summaries = provider.get_all_pass_summaries("exp1")
        >>> table = generate_pass_summary_table(summaries, "Summary", "tab:exp1_summary")
    """
    rows: list[str] = []

    # Header row
    header = format_table_row([
        "Pass",
        "Iterations",
        "BANK\\_A Liq.",
        "BANK\\_B Liq.",
        "BANK\\_A Cost",
        "BANK\\_B Cost",
        "Total Cost",
    ])
    rows.append(header)
    rows.append(r"\hline")

    # Data rows
    for s in summaries:
        row = format_table_row([
            str(s["pass_num"]),
            str(s["iterations"]),
            format_percent(s["bank_a_liquidity"]),
            format_percent(s["bank_b_liquidity"]),
            format_money(s["bank_a_cost"]),
            format_money(s["bank_b_cost"]),
            format_money(s["total_cost"]),
        ])
        rows.append(row)

    table_body = "\n        ".join(rows)

    return rf"""
\begin{{table}}[htbp]
    \centering
    \caption{{{caption}}}
    \label{{{label}}}
    \begin{{tabular}}{{ccrrrrrr}}
        \hline
        {table_body}
        \hline
    \end{{tabular}}
\end{{table}}
"""


def generate_convergence_table(
    stats: list[ConvergenceStats],
    caption: str,
    label: str,
) -> str:
    """Generate LaTeX table for convergence statistics across experiments.

    Args:
        stats: List of ConvergenceStats from DataProvider
        caption: Table caption text
        label: LaTeX label for referencing

    Returns:
        Complete LaTeX table string

    Example:
        >>> stats = [provider.get_convergence_statistics(e) for e in ["exp1", "exp2", "exp3"]]
        >>> table = generate_convergence_table(stats, "Convergence", "tab:convergence")
    """
    rows: list[str] = []

    # Header row
    header = format_table_row([
        "Experiment",
        "Mean Iters",
        "Min",
        "Max",
        "Conv. Rate",
    ])
    rows.append(header)
    rows.append(r"\hline")

    # Data rows
    for s in stats:
        row = format_table_row([
            s["exp_id"].upper(),
            f"{s['mean_iterations']:.1f}",
            str(s["min_iterations"]),
            str(s["max_iterations"]),
            format_percent(s["convergence_rate"]),
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


def generate_results_summary_table(
    exp1_summaries: list[PassSummary],
    exp2_summaries: list[PassSummary],
    exp3_summaries: list[PassSummary],
    caption: str,
    label: str,
) -> str:
    """Generate comprehensive results summary table for appendix.

    Creates a table showing final equilibrium outcomes for all experiments and passes.

    Args:
        exp1_summaries: Pass summaries for Experiment 1
        exp2_summaries: Pass summaries for Experiment 2
        exp3_summaries: Pass summaries for Experiment 3
        caption: Table caption text
        label: LaTeX label for referencing

    Returns:
        Complete LaTeX table string
    """
    rows: list[str] = []

    # Header row
    header = format_table_row([
        "Exp",
        "Pass",
        "Iters",
        "A Liq",
        "B Liq",
        "A Cost",
        "B Cost",
        "Total",
    ])
    rows.append(header)
    rows.append(r"\hline")

    # Data rows for each experiment
    all_summaries = [
        ("Exp1", exp1_summaries),
        ("Exp2", exp2_summaries),
        ("Exp3", exp3_summaries),
    ]

    for exp_name, summaries in all_summaries:
        for s in summaries:
            row = format_table_row([
                exp_name if s["pass_num"] == 1 else "",  # Only show exp name on first row
                str(s["pass_num"]),
                str(s["iterations"]),
                format_percent(s["bank_a_liquidity"]),
                format_percent(s["bank_b_liquidity"]),
                format_money(s["bank_a_cost"]),
                format_money(s["bank_b_cost"]),
                format_money(s["total_cost"]),
            ])
            rows.append(row)
        rows.append(r"\hline")

    table_body = "\n        ".join(rows)

    return rf"""
\begin{{table}}[htbp]
    \centering
    \caption{{{caption}}}
    \label{{{label}}}
    \small
    \begin{{tabular}}{{llrrrrrr}}
        \hline
        {table_body}
    \end{{tabular}}
\end{{table}}
"""
