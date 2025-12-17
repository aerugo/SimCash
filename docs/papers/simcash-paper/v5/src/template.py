"""Template system for paper generation.

This module provides a template-based approach where:
- paper_src.tex contains LaTeX with {{variable}} placeholders
- paper.tex contains LaTeX with actual values substituted

Variables are collected from the DataProvider and stored in a context dict.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def collect_template_context(provider: DataProvider) -> dict[str, str]:
    """Collect all template variables from the data provider.

    Returns a dict mapping variable names to their string values.
    All values are pre-formatted for LaTeX output.

    Args:
        provider: DataProvider instance

    Returns:
        Dict mapping variable names to formatted string values
    """
    from src.latex.figures import include_figure
    from src.latex.tables import (
        generate_bootstrap_table,
        generate_convergence_table,
        generate_iteration_table,
        generate_pass_summary_table,
    )

    ctx: dict[str, str] = {}

    # Aggregate statistics
    aggregate = provider.get_aggregate_stats()
    ctx["total_experiments"] = str(aggregate["total_experiments"])
    ctx["total_passes"] = str(aggregate["total_passes"])
    ctx["overall_mean_iterations"] = f"{aggregate['overall_mean_iterations']:.1f}"
    ctx["overall_convergence_pct"] = f"{int(aggregate['overall_convergence_rate'] * 100)}"
    ctx["total_converged"] = str(aggregate["total_converged"])

    # Passes per experiment (for "3 passes × 3 experiments" style text)
    if aggregate["total_experiments"] > 0:
        passes_per_exp = aggregate["total_passes"] // aggregate["total_experiments"]
        ctx["passes_per_experiment"] = str(passes_per_exp)
    else:
        ctx["passes_per_experiment"] = "0"

    # Collect convergence stats for all experiments (for table)
    all_conv_stats = []

    # Per-experiment convergence statistics
    for exp_id in provider.get_experiment_ids():
        conv = provider.get_convergence_statistics(exp_id)
        all_conv_stats.append(conv)
        prefix = exp_id  # e.g., "exp1"

        ctx[f"{prefix}_num_passes"] = str(conv["num_passes"])
        ctx[f"{prefix}_mean_iterations"] = f"{conv['mean_iterations']:.1f}"
        ctx[f"{prefix}_min_iterations"] = str(conv["min_iterations"])
        ctx[f"{prefix}_max_iterations"] = str(conv["max_iterations"])
        ctx[f"{prefix}_convergence_pct"] = f"{int(conv['convergence_rate'] * 100)}"

        # Per-pass summaries
        summaries = provider.get_all_pass_summaries(exp_id)
        for summary in summaries:
            p = summary["pass_num"]
            pass_prefix = f"{prefix}_pass{p}"

            ctx[f"{pass_prefix}_iterations"] = str(summary["iterations"])
            ctx[f"{pass_prefix}_bank_a_liquidity"] = f"{summary['bank_a_liquidity']:.2f}"
            ctx[f"{pass_prefix}_bank_b_liquidity"] = f"{summary['bank_b_liquidity']:.2f}"
            ctx[f"{pass_prefix}_bank_a_liquidity_pct"] = f"{summary['bank_a_liquidity']*100:.0f}"
            ctx[f"{pass_prefix}_bank_b_liquidity_pct"] = f"{summary['bank_b_liquidity']*100:.0f}"
            ctx[f"{pass_prefix}_bank_a_cost_cents"] = f"{summary['bank_a_cost']:,}"
            ctx[f"{pass_prefix}_bank_b_cost_cents"] = f"{summary['bank_b_cost']:,}"
            ctx[f"{pass_prefix}_total_cost_cents"] = f"{summary['total_cost']:,}"
            # Dollar amounts
            ctx[f"{pass_prefix}_bank_a_cost"] = f"{summary['bank_a_cost']/100:.2f}"
            ctx[f"{pass_prefix}_bank_b_cost"] = f"{summary['bank_b_cost']/100:.2f}"
            ctx[f"{pass_prefix}_total_cost"] = f"{summary['total_cost']/100:.2f}"

        # Calculate averages across passes
        if summaries:
            avg_iters = sum(s["iterations"] for s in summaries) / len(summaries)
            avg_a_liq = sum(s["bank_a_liquidity"] for s in summaries) / len(summaries)
            avg_b_liq = sum(s["bank_b_liquidity"] for s in summaries) / len(summaries)
            avg_a_cost = sum(s["bank_a_cost"] for s in summaries) / len(summaries)
            avg_b_cost = sum(s["bank_b_cost"] for s in summaries) / len(summaries)
            avg_total = sum(s["total_cost"] for s in summaries) / len(summaries)
            liq_diff = abs(avg_a_liq - avg_b_liq)

            ctx[f"{prefix}_avg_iterations"] = f"{avg_iters:.1f}"
            ctx[f"{prefix}_avg_bank_a_liquidity"] = f"{avg_a_liq:.2f}"
            ctx[f"{prefix}_avg_bank_b_liquidity"] = f"{avg_b_liq:.2f}"
            ctx[f"{prefix}_avg_bank_a_liquidity_pct"] = f"{avg_a_liq*100:.0f}"
            ctx[f"{prefix}_avg_bank_b_liquidity_pct"] = f"{avg_b_liq*100:.0f}"
            ctx[f"{prefix}_liquidity_diff_pct"] = f"{liq_diff*100:.0f}"
            ctx[f"{prefix}_avg_bank_a_cost"] = f"{avg_a_cost/100:.2f}"
            ctx[f"{prefix}_avg_bank_b_cost"] = f"{avg_b_cost/100:.2f}"
            ctx[f"{prefix}_avg_total_cost"] = f"{avg_total/100:.2f}"

        # Generate tables for this experiment
        results = provider.get_iteration_results(exp_id, pass_num=1)
        ctx[f"{prefix}_iteration_table"] = generate_iteration_table(
            results,
            caption=f"Experiment {exp_id[-1]}: Iteration-by-iteration results (Pass 1)",
            label=f"tab:{prefix}_results",
        )

        ctx[f"{prefix}_summary_table"] = generate_pass_summary_table(
            summaries,
            caption=f"Experiment {exp_id[-1]}: Summary across all passes",
            label=f"tab:{prefix}_summary",
        )

        # Generate figure include
        ctx[f"{prefix}_figure"] = include_figure(
            path=f"charts/{prefix}_pass1_combined.png",
            caption=f"Experiment {exp_id[-1]}: Convergence visualization",
            label=f"fig:{prefix}_convergence",
            width=0.9,
        )

    # Generate convergence table for all experiments
    ctx["convergence_table"] = generate_convergence_table(
        all_conv_stats,
        caption="Convergence statistics across all experiments",
        label="tab:convergence_stats",
    )

    # Bootstrap statistics for exp2
    try:
        bootstrap = provider.get_final_bootstrap_stats("exp2", pass_num=1)
        if "BANK_A" in bootstrap:
            ctx["exp2_bootstrap_samples"] = str(bootstrap["BANK_A"]["num_samples"])
            ctx["exp2_bootstrap_a_mean"] = f"{bootstrap['BANK_A']['mean_cost']/100:.2f}"
            ctx["exp2_bootstrap_a_std"] = f"{bootstrap['BANK_A']['std_dev']/100:.2f}"
        if "BANK_B" in bootstrap:
            ctx["exp2_bootstrap_b_mean"] = f"{bootstrap['BANK_B']['mean_cost']/100:.2f}"
            ctx["exp2_bootstrap_b_std"] = f"{bootstrap['BANK_B']['std_dev']/100:.2f}"

        ctx["exp2_bootstrap_table"] = generate_bootstrap_table(
            bootstrap,
            caption="Experiment 2: Bootstrap evaluation statistics (Pass 1, 50 samples)",
            label="tab:exp2_bootstrap",
        )
    except Exception:
        ctx["exp2_bootstrap_samples"] = "N/A"
        ctx["exp2_bootstrap_a_mean"] = "N/A"
        ctx["exp2_bootstrap_a_std"] = "N/A"
        ctx["exp2_bootstrap_b_mean"] = "N/A"
        ctx["exp2_bootstrap_b_std"] = "N/A"
        ctx["exp2_bootstrap_table"] = "% Bootstrap table not available"

    return ctx


def render_template(template: str, context: dict[str, str]) -> str:
    """Render a template by substituting {{variable}} placeholders.

    Args:
        template: LaTeX string with {{variable}} placeholders
        context: Dict mapping variable names to values

    Returns:
        LaTeX string with values substituted
    """

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name in context:
            return context[var_name]
        # Keep placeholder if variable not found (for debugging)
        return f"{{{{MISSING:{var_name}}}}}"

    return re.sub(r"\{\{(\w+)\}\}", replace_var, template)


def format_placeholder(name: str) -> str:
    """Format a variable name as a placeholder.

    Args:
        name: Variable name

    Returns:
        Placeholder string like {{name}}
    """
    return "{{" + name + "}}"


# Convenience function for section generators
def var(name: str) -> str:
    """Create a template variable placeholder.

    Use this in section generators:
        f"Mean iterations: {var('overall_mean_iterations')}"

    Args:
        name: Variable name

    Returns:
        Placeholder string like {{overall_mean_iterations}}
    """
    return format_placeholder(name)
