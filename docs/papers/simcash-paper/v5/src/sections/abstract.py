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
    # Get convergence statistics across all experiments
    exp1_stats = provider.get_convergence_statistics("exp1")
    exp2_stats = provider.get_convergence_statistics("exp2")
    exp3_stats = provider.get_convergence_statistics("exp3")

    # Calculate overall average iterations
    all_iterations = [exp1_stats["mean_iterations"], exp2_stats["mean_iterations"], exp3_stats["mean_iterations"]]
    avg_iterations = sum(all_iterations) / len(all_iterations)

    return rf"""
\begin{{abstract}}
We present SimCash, a novel framework for discovering Nash equilibria in payment
system liquidity games using Large Language Models (LLMs). Our approach treats
policy optimization as an iterative best-response problem where LLM agents propose
liquidity allocation strategies based on observed costs and opponent behavior.
Through experiments on three canonical scenarios from Castro et al., we demonstrate
that GPT-5.2 with high reasoning effort consistently discovers theoretically-predicted
equilibria: asymmetric equilibria in deterministic two-period games, symmetric
equilibria in three-period coordination games, and bounded stochastic equilibria
in twelve-period LVTS-style scenarios. Our results across 9 independent runs
(3 passes $\times$ 3 experiments) show 100\% convergence success with an average
of {avg_iterations:.1f} iterations to stability.
\end{{abstract}}
"""
