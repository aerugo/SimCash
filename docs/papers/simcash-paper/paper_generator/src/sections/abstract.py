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
Can Large Language Models discover equilibrium-like behavior through strategic reasoning alone?
We explore this question using payment system liquidity management---a domain where
banks must balance the cost of holding reserves against settlement delays, and where
game-theoretic equilibria are well-characterized but difficult to find without explicit
modeling.

We present SimCash, a framework where LLM agents optimize liquidity policies through
natural language deliberation under information isolation: each agent observes only
its own costs and transaction history, never counterparty strategies. Through {total_passes}
independent runs across {total_experiments} scenarios adapted from Castro et al., agents
reliably converge to stable policy profiles ({convergence_pct}\% success in {total_passes}
preliminary runs, mean {avg_iterations:.1f} iterations). However, outcome selection exhibits
path-dependence: in deterministic scenarios, agents consistently converge to \textit{{asymmetric}}
free-rider outcomes---even when the cost structure is symmetric---with the identity of the
free-rider determined by early exploration. In contrast, stochastic environments produced
near-symmetric equilibria with no free-rider emergence.

These preliminary findings suggest that LLM-based policy optimization can discover
equilibrium-like behavior without explicit game-theoretic modeling---though we do not
formally verify the Nash condition. They also reveal that sequential best-response 
dynamics in multi-agent LLM systems may systematically favor asymmetric outcomes. 
Our small sample ({total_passes} runs) requires validation through expanded 
experimentation before drawing strong conclusions.
\end{{abstract}}
"""
