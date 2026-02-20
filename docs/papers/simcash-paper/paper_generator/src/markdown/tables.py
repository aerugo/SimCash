"""Markdown table generators.

Same functions as latex/tables.py but output GFM markdown tables.
"""

from __future__ import annotations

from src.data_provider import (
    AgentIterationResult,
    BootstrapStats,
    ConvergenceStats,
    PassSummary,
)
from src.markdown.formatting import format_ci, format_money, format_percent


def generate_iteration_table(results: list[AgentIterationResult]) -> str:
    """Generate markdown table for iteration-by-iteration results.

    Args:
        results: List of AgentIterationResult from DataProvider

    Returns:
        GFM markdown table string
    """
    lines = [
        "| Iteration | Agent | Cost | Liquidity |",
        "|-----------|-------|-----:|----------:|",
    ]

    iterations: dict[int, list[AgentIterationResult]] = {}
    for r in results:
        iterations.setdefault(r["iteration"], []).append(r)

    for iteration in sorted(iterations.keys()):
        for r in sorted(iterations[iteration], key=lambda x: x["agent_id"]):
            iter_display = "Baseline" if r.get("is_baseline") or r["iteration"] == -1 else str(r["iteration"])
            agent = r["agent_id"].replace("BANK_", "Bank ")
            lines.append(
                f"| {iter_display} | {agent} | {format_money(r['cost'])} | {format_percent(r['liquidity_fraction'])} |"
            )

    return "\n".join(lines)


def generate_bootstrap_table(stats: dict[str, BootstrapStats]) -> str:
    """Generate markdown table for bootstrap statistics.

    Args:
        stats: Dict mapping agent_id to BootstrapStats

    Returns:
        GFM markdown table string
    """
    lines = [
        "| Agent | Mean Cost | Std Dev | 95% CI | Samples |",
        "|-------|----------:|--------:|--------|--------:|",
    ]

    for agent_id in sorted(stats.keys()):
        s = stats[agent_id]
        agent = agent_id.replace("BANK_", "Bank ")
        lines.append(
            f"| {agent} | {format_money(s['mean_cost'])} | {format_money(s['std_dev'])} | {format_ci(s['ci_lower'], s['ci_upper'])} | {s['num_samples']} |"
        )

    return "\n".join(lines)


def generate_pass_summary_table(summaries: list[PassSummary]) -> str:
    """Generate markdown table summarizing all passes.

    Args:
        summaries: List of PassSummary from DataProvider

    Returns:
        GFM markdown table string
    """
    lines = [
        "| Pass | Iterations | Bank A Liq. | Bank B Liq. | Bank A Cost | Bank B Cost | Total Cost |",
        "|-----:|-----------:|------------:|------------:|------------:|------------:|-----------:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['pass_num']} | {s['iterations']} | {format_percent(s['bank_a_liquidity'])} | {format_percent(s['bank_b_liquidity'])} | {format_money(s['bank_a_cost'])} | {format_money(s['bank_b_cost'])} | {format_money(s['total_cost'])} |"
        )

    return "\n".join(lines)


def generate_convergence_table(stats: list[ConvergenceStats]) -> str:
    """Generate markdown table for convergence statistics.

    Args:
        stats: List of ConvergenceStats from DataProvider

    Returns:
        GFM markdown table string
    """
    lines = [
        "| Experiment | Mean Iters | Min | Max | Conv. Rate |",
        "|------------|----------:|----|----:|----------:|",
    ]

    for s in stats:
        lines.append(
            f"| {s['exp_id'].upper()} | {s['mean_iterations']:.1f} | {s['min_iterations']} | {s['max_iterations']} | {format_percent(s['convergence_rate'])} |"
        )

    return "\n".join(lines)


def generate_results_summary_table(
    exp1_summaries: list[PassSummary],
    exp2_summaries: list[PassSummary],
    exp3_summaries: list[PassSummary],
) -> str:
    """Generate comprehensive results summary table.

    Args:
        exp1_summaries: Pass summaries for Experiment 1
        exp2_summaries: Pass summaries for Experiment 2
        exp3_summaries: Pass summaries for Experiment 3

    Returns:
        GFM markdown table string
    """
    lines = [
        "| Exp | Pass | Iters | A Liq | B Liq | A Cost | B Cost | Total |",
        "|-----|-----:|------:|------:|------:|-------:|-------:|------:|",
    ]

    all_summaries = [
        ("Exp 1", exp1_summaries),
        ("Exp 2", exp2_summaries),
        ("Exp 3", exp3_summaries),
    ]

    for exp_name, summaries in all_summaries:
        for s in summaries:
            name = exp_name if s["pass_num"] == 1 else ""
            lines.append(
                f"| {name} | {s['pass_num']} | {s['iterations']} | {format_percent(s['bank_a_liquidity'])} | {format_percent(s['bank_b_liquidity'])} | {format_money(s['bank_a_cost'])} | {format_money(s['bank_b_cost'])} | {format_money(s['total_cost'])} |"
            )

    return "\n".join(lines)
