"""Related work section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_related_work(provider: DataProvider) -> str:
    """Generate the related work section.

    Args:
        provider: DataProvider instance (unused but required for interface consistency)

    Returns:
        LaTeX string for the related work section
    """
    # Provider is unused but kept for interface consistency
    _ = provider

    return r"""
\section{Related Work}
\label{sec:related}

\subsection{Payment System Simulation}

Castro et al.\ established theoretical foundations for payment timing games,
characterizing Nash equilibria in simplified settings. Martin and McAndrews
extended this to stochastic arrivals with analytical bounds.

\subsection{LLMs in Game Theory}

Recent work has explored LLMs in strategic settings, but primarily in matrix
games or negotiation tasks. Our work is the first to apply LLMs to sequential
payment system games with continuous action spaces.
"""
