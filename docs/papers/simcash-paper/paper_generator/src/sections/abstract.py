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
Can Large Language Models discover stable policy profiles through strategic reasoning alone?
We explore this question using payment system liquidity management---a domain where
banks must balance the cost of holding reserves against settlement delays, and where
game-theoretic equilibria are well-characterized but difficult to find without explicit
modeling.

We present SimCash, a framework where LLM agents optimize liquidity policies through
natural language deliberation under information isolation: each agent observes only
its own costs and transaction history, never counterparty strategies. Through {total_passes}
independent runs across {total_experiments} scenarios adapted from Castro et al., agents
reliably converge to stable policy profiles in deterministic scenarios (mean {avg_iterations:.1f}
iterations), while stochastic scenarios achieved practical stability but terminated at iteration
budget without meeting strict statistical convergence criteria. However, \textbf{{stability does not imply optimality}}: in symmetric deterministic
games, agents consistently converge to \textit{{coordination failures}}---Pareto-dominated
profiles where both agents are worse off than baseline---with the identity of the
free-rider determined by early aggressive moves. In contrast, stochastic environments with
bootstrap policy evaluation produced near-symmetric allocations without coordination collapse.

These preliminary findings suggest that LLM-based policy optimization can discover
stable profiles without explicit game-theoretic modeling, but also demonstrates that
greedy, non-communicating agents can reliably converge to coordination traps.
Our small sample ({total_passes} runs) requires validation through expanded
experimentation before drawing strong conclusions.
\end{{abstract}}

\tableofcontents
\newpage
"""
