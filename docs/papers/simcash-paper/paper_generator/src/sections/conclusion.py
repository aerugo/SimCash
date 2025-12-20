"""Conclusion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_conclusion(provider: DataProvider) -> str:
    """Generate the conclusion section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the conclusion section
    """
    # Get convergence iterations to summarize
    exp1_conv = provider.get_convergence_iteration("exp1", pass_num=1)
    exp2_conv = provider.get_convergence_iteration("exp2", pass_num=1)
    exp3_conv = provider.get_convergence_iteration("exp3", pass_num=1)

    return rf"""
\section{{Conclusion}}
\label{{sec:conclusion}}

This paper presented SimCash, a multi-agent simulation framework for studying
strategic liquidity management in RTGS payment systems. Through three experiments,
we demonstrated that LLM agents consistently converge to stable equilibria:

\begin{{enumerate}}
    \item \textbf{{Asymmetric equilibrium}} ({exp1_conv} iterations): Free-rider behavior
    emerges when agents face different cost structures, with one agent minimizing
    liquidity while depending on counterparty provision.

    \item \textbf{{Robust learning}} ({exp2_conv} iterations): Agents learn effective
    strategies even under transaction stochasticity, as validated through bootstrap
    evaluation methodology.

    \item \textbf{{Equilibrium selection}} ({exp3_conv} iterations): Even in symmetric
    games, LLM agents converge to asymmetric equilibria, suggesting that sequential
    best-response dynamics favor free-rider outcomes over cooperative equilibria.
\end{{enumerate}}

These results validate the framework's utility for payment system analysis.
Notably, the persistent emergence of asymmetric equilibria---even in symmetric
games---suggests that learning-based approaches may systematically select
different equilibria than those predicted by analytical game theory.
"""
