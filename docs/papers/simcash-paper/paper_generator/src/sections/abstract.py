"""Abstract section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_abstract(provider: DataProvider) -> str:
    """Generate the abstract section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the abstract
    """
    # Get aggregate statistics across all experiments
    aggregate_stats = provider.get_aggregate_stats()

    total_experiments = aggregate_stats["total_experiments"]
    total_passes = aggregate_stats["total_passes"]
    avg_iterations = aggregate_stats["overall_mean_iterations"]
    convergence_rate = aggregate_stats["overall_convergence_rate"]

    # Format convergence rate as percentage
    convergence_pct = int(convergence_rate * 100)

    # Calculate passes per experiment for the formula display
    passes_per_exp = total_passes // total_experiments if total_experiments > 0 else 0

    return rf"""
\begin{{abstract}}
We present SimCash, a novel framework for discovering Nash equilibria in payment
system liquidity games using Large Language Models (LLMs). Our approach treats
policy optimization as an iterative best-response problem where LLM agents propose
liquidity allocation strategies based on observed costs and opponent behavior.
Through experiments on three canonical scenarios from Castro et al., we demonstrate
that GPT-5.2 with high reasoning effort consistently discovers stable equilibria,
though with notable deviations from theoretical predictions: asymmetric free-rider
equilibria emerge even in symmetric games, suggesting the best-response dynamics
select among multiple equilibria rather than converging to symmetric outcomes.
Our results across {total_passes} independent runs
({passes_per_exp} passes $\times$ {total_experiments} experiments) show {convergence_pct}\% convergence success with an average
of {avg_iterations:.1f} iterations to stability.
\end{{abstract}}
"""
