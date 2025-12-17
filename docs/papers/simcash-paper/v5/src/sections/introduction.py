"""Introduction section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.template import var

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_introduction(provider: DataProvider | None = None) -> str:
    """Generate the introduction section template.

    Args:
        provider: DataProvider instance (unused, kept for API compatibility)

    Returns:
        LaTeX string with {{variable}} placeholders
    """
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
    \item \textbf{{Empirical Validation}}: Successful recovery of Castro et al.'s
    theoretical equilibria
    \item \textbf{{Reproducibility Analysis}}: {var('total_passes')} independent runs demonstrating consistent
    convergence
    \item \textbf{{Bootstrap Evaluation}}: Methodology for handling stochastic payment
    arrivals
\end{{enumerate}}
"""
