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
We present SimCash, a framework for discovering Nash equilibria in payment system
liquidity games using Large Language Models (LLMs) as strategic agents. Unlike
gradient-based reinforcement learning, our approach uses LLM reasoning to propose
policy adjustments through natural language deliberation, enabling interpretable
optimization under information isolation---agents observe only their own costs and
transaction history, not counterparty strategies.

Through {total_passes} independent runs across {total_experiments} canonical scenarios
from Castro et al., we find that LLM agents reliably converge to stable equilibria
({convergence_pct}\% success, mean {avg_iterations:.1f} iterations), but with notable
deviations from game-theoretic predictions. Most strikingly, symmetric cost structures
yield asymmetric free-rider equilibria: one agent minimizes liquidity while the other
compensates. The specific equilibrium selected depends on early exploration dynamics
rather than payoff structure alone, and different runs find equilibria with substantially
different efficiency---total costs vary by up to 4$\times$ across independent passes.

These results suggest that sequential best-response dynamics in multi-agent LLM systems
naturally select among multiple equilibria rather than converging to theoretically
predicted symmetric outcomes, with implications for using LLMs to model strategic
behavior in financial infrastructure.
\end{{abstract}}
"""
