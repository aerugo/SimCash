"""Introduction section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_introduction(provider: DataProvider) -> str:
    """Generate the introduction section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the introduction section
    """
    # Get aggregate statistics for data-driven text
    aggregate_stats = provider.get_aggregate_stats()
    total_passes = aggregate_stats["total_passes"]

    return rf"""
\section{{Introduction}}

Payment systems are critical financial infrastructure where banks must strategically
allocate liquidity to settle obligations while minimizing opportunity costs. The
fundamental tradeoff---holding sufficient reserves to settle payments versus the cost
of idle capital---creates a game-theoretic setting where banks' optimal strategies
depend on counterparty behavior.

Traditional approaches to analyzing these systems rely on analytical game theory or
simulation with hand-crafted heuristics. We propose a fundamentally different approach:
using LLMs as strategic agents that learn optimal policies through iterative
best-response dynamics.

\subsection{{Contributions}}

\begin{{enumerate}}
    \item \textbf{{SimCash Framework}}: A hybrid Rust-Python simulator with LLM-based
    policy optimization
    \item \textbf{{Empirical Comparison}}: Comparison with Castro et al.'s theoretical
    predictions, showing partial alignment and systematic deviations
    \item \textbf{{Reproducibility Analysis}}: {total_passes} independent runs demonstrating consistent
    convergence
    \item \textbf{{Bootstrap Evaluation}}: Methodology for handling stochastic payment
    arrivals
\end{{enumerate}}
"""
