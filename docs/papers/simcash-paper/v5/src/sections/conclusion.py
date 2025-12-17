"""Conclusion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.template import var

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_conclusion(provider: DataProvider | None = None) -> str:
    """Generate the conclusion section template.

    Args:
        provider: DataProvider instance (unused, kept for API compatibility)

    Returns:
        LaTeX string with {{variable}} placeholders
    """
    return rf"""
\section{{Conclusion}}
\label{{sec:conclusion}}

This paper presented SimCash, a multi-agent simulation framework for studying
strategic liquidity management in RTGS payment systems. Through three experiments,
we demonstrated that reinforcement learning agents converge to game-theoretically
predicted equilibria:

\begin{{enumerate}}
    \item \textbf{{Asymmetric equilibrium}} ({var('exp1_pass1_iterations')} iterations): Free-rider behavior
    emerges when agents face different cost structures, with one agent minimizing
    liquidity while depending on counterparty provision.

    \item \textbf{{Robust learning}} ({var('exp2_pass1_iterations')} iterations): Agents learn effective
    strategies even under transaction stochasticity, as validated through bootstrap
    evaluation methodology.

    \item \textbf{{Cooperative equilibrium}} ({var('exp3_pass1_iterations')} iterations): Symmetric cost
    structures lead to balanced liquidity provision across participants.
\end{{enumerate}}

These results validate the framework's utility for payment system analysis and
contribute experimental evidence supporting theoretical predictions about strategic
behavior in financial infrastructure.

\subsection{{Future Work}}

Several directions merit further investigation:

\begin{{itemize}}
    \item \textbf{{Network scaling}}: Extending to N-agent scenarios with diverse
    participant types (large, medium, small banks)

    \item \textbf{{Partial observability}}: Modeling realistic information constraints
    where agents cannot directly observe counterparty reserves

    \item \textbf{{Regulatory intervention}}: Testing policy interventions such as
    minimum liquidity requirements, tiered penalty structures, or central bank
    credit facilities

    \item \textbf{{Dynamic environments}}: Incorporating non-stationary elements such
    as changing transaction volumes or participant entry/exit

    \item \textbf{{Alternative learning algorithms}}: Comparing policy gradient methods
    with Q-learning, actor-critic, or model-based approaches
\end{{itemize}}

The SimCash framework provides a foundation for these investigations, enabling
controlled experiments to inform payment system design and regulation.
"""
