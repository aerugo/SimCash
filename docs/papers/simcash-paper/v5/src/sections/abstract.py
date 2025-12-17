"""Abstract section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.template import var

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_abstract(provider: DataProvider | None = None) -> str:
    """Generate the abstract section template.

    Args:
        provider: DataProvider instance (unused, kept for API compatibility)

    Returns:
        LaTeX string with {{variable}} placeholders
    """
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
in twelve-period LVTS-style scenarios. Our results across {var('total_passes')} independent runs
({var('passes_per_experiment')} passes $\times$ {var('total_experiments')} experiments) show {var('overall_convergence_pct')}\% convergence success with an average
of {var('overall_mean_iterations')} iterations to stability.
\end{{abstract}}
"""
