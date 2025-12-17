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
    # Get convergence data to summarize results
    exp1_convergence = provider.get_convergence_iteration("exp1", pass_num=1)
    exp2_convergence = provider.get_convergence_iteration("exp2", pass_num=1)
    exp3_convergence = provider.get_convergence_iteration("exp3", pass_num=1)

    return rf"""
\begin{{abstract}}
This paper presents SimCash, a multi-agent simulation framework for studying
strategic liquidity management in real-time gross settlement (RTGS) payment systems.
We employ reinforcement learning agents that adaptively adjust their intraday
liquidity reserves based on observed costs and counterparty behavior.

Through three experiments, we demonstrate that agents converge to game-theoretically
predicted equilibria. In asymmetric scenarios, agents achieve convergence within
{exp1_convergence} iterations, discovering free-rider equilibria where one bank provides
liquidity while others minimize reserves. In stochastic environments requiring bootstrap
evaluation ({exp2_convergence} iterations to convergence), agents exhibit robust learning
despite cost variance. Symmetric scenarios with identical penalty structures lead to
cooperative equilibria ({exp3_convergence} iterations).

Our results validate the simulation framework's ability to reproduce theoretical
predictions and provide insights into emergent strategic behavior in payment systems.
The framework enables exploration of regulatory interventions and mechanism design
for financial stability.
\end{{abstract}}
"""
