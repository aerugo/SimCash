"""Generate a plain-text summary of all data used in paper generation.

This module produces paper_data.txt showing all computed values
without LaTeX formatting, making it easy to verify the data.
"""

from __future__ import annotations

from pathlib import Path

from src.data_provider import DataProvider


def generate_data_summary(provider: DataProvider, output_path: Path) -> Path:
    """Generate a plain-text summary of all paper data.

    Args:
        provider: DataProvider instance with experiment data
        output_path: Path to write paper_data.txt

    Returns:
        Path to generated file
    """
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    def section(title: str) -> None:
        add()
        add("=" * 70)
        add(title)
        add("=" * 70)

    def subsection(title: str) -> None:
        add()
        add(f"--- {title} ---")

    # Header
    add("SimCash Paper - Data Summary")
    add("Generated from experiment databases")
    add("All monetary values in cents unless noted")

    # Aggregate Statistics
    section("AGGREGATE STATISTICS (used in Abstract, Introduction)")
    aggregate = provider.get_aggregate_stats()
    add(f"Total experiments:        {aggregate['total_experiments']}")
    add(f"Total passes:             {aggregate['total_passes']}")
    add(f"Overall mean iterations:  {aggregate['overall_mean_iterations']:.1f}")
    add(f"Overall convergence rate: {aggregate['overall_convergence_rate'] * 100:.0f}%")
    add(f"Total converged passes:   {aggregate['total_converged']}")

    # Per-Experiment Statistics
    section("PER-EXPERIMENT CONVERGENCE STATISTICS")
    for exp_id in provider.get_experiment_ids():
        conv = provider.get_convergence_statistics(exp_id)
        subsection(f"{exp_id.upper()}")
        add(f"Number of passes:    {conv['num_passes']}")
        add(f"Mean iterations:     {conv['mean_iterations']:.1f}")
        add(f"Min iterations:      {conv['min_iterations']}")
        add(f"Max iterations:      {conv['max_iterations']}")
        add(f"Convergence rate:    {conv['convergence_rate'] * 100:.0f}%")

    # Per-Pass Summaries
    section("PER-PASS SUMMARIES (used in Results tables)")
    for exp_id in provider.get_experiment_ids():
        subsection(f"{exp_id.upper()} - Pass Summaries")
        add(f"{'Pass':<6} {'Iters':<6} {'A Liq':<8} {'B Liq':<8} {'A Cost':<12} {'B Cost':<12} {'Total':<12}")
        add("-" * 70)

        summaries = provider.get_all_pass_summaries(exp_id)
        for s in summaries:
            add(
                f"{s['pass_num']:<6} "
                f"{s['iterations']:<6} "
                f"{s['bank_a_liquidity']:<8.2f} "
                f"{s['bank_b_liquidity']:<8.2f} "
                f"{s['bank_a_cost']:<12,} "
                f"{s['bank_b_cost']:<12,} "
                f"{s['total_cost']:<12,}"
            )

        # Calculate averages
        avg_iters = sum(s['iterations'] for s in summaries) / len(summaries)
        avg_a_liq = sum(s['bank_a_liquidity'] for s in summaries) / len(summaries)
        avg_b_liq = sum(s['bank_b_liquidity'] for s in summaries) / len(summaries)
        avg_a_cost = sum(s['bank_a_cost'] for s in summaries) // len(summaries)
        avg_b_cost = sum(s['bank_b_cost'] for s in summaries) // len(summaries)
        avg_total = sum(s['total_cost'] for s in summaries) // len(summaries)

        add("-" * 70)
        add(
            f"{'AVG':<6} "
            f"{avg_iters:<6.1f} "
            f"{avg_a_liq:<8.2f} "
            f"{avg_b_liq:<8.2f} "
            f"{avg_a_cost:<12,} "
            f"{avg_b_cost:<12,} "
            f"{avg_total:<12,}"
        )

    # Detailed Iteration Data (final iteration only)
    section("FINAL ITERATION DETAILS (used in Results)")
    for exp_id in provider.get_experiment_ids():
        num_passes = provider.get_num_passes(exp_id)
        for pass_num in range(1, num_passes + 1):
            subsection(f"{exp_id.upper()} Pass {pass_num}")

            run_id = provider.get_run_id(exp_id, pass_num)
            add(f"Run ID: {run_id}")

            final_iter = provider.get_convergence_iteration(exp_id, pass_num)
            add(f"Converged at iteration: {final_iter}")

            results = provider.get_iteration_results(exp_id, pass_num)
            final_results = [r for r in results if r["iteration"] == final_iter]

            add()
            add(f"{'Agent':<10} {'Liquidity':<12} {'Cost (cents)':<15} {'Cost ($)':<12}")
            add("-" * 50)
            for r in final_results:
                cost_dollars = r["cost"] / 100
                add(
                    f"{r['agent_id']:<10} "
                    f"{r['liquidity_fraction']:<12.4f} "
                    f"{r['cost']:<15,} "
                    f"${cost_dollars:<11,.2f}"
                )

    # Bootstrap Statistics (for stochastic experiments)
    section("BOOTSTRAP STATISTICS (Exp2/Exp3 - stochastic)")
    for exp_id in ["exp2", "exp3"]:
        if exp_id not in provider.get_experiment_ids():
            continue

        num_passes = provider.get_num_passes(exp_id)
        for pass_num in range(1, num_passes + 1):
            subsection(f"{exp_id.upper()} Pass {pass_num} Bootstrap Stats")

            try:
                bootstrap = provider.get_final_bootstrap_stats(exp_id, pass_num)
                add(f"{'Agent':<10} {'Mean':<12} {'Std Dev':<12} {'95% CI Lower':<14} {'95% CI Upper':<14} {'Samples':<8}")
                add("-" * 70)
                for agent_id, stats in bootstrap.items():
                    add(
                        f"{agent_id:<10} "
                        f"{stats['mean_cost']:<12,} "
                        f"{stats['std_dev']:<12,} "
                        f"{stats['ci_lower']:<14,} "
                        f"{stats['ci_upper']:<14,} "
                        f"{stats['num_samples']:<8}"
                    )
            except Exception as e:
                add(f"No bootstrap data available: {e}")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    return output_path
