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
    return r"""
\section{Introduction}

Real-time gross settlement (RTGS) systems form the backbone of modern financial
infrastructure, processing trillions of dollars in interbank payments daily.
Banks participating in these systems face a fundamental tension: holding sufficient
liquidity reserves ensures timely settlement but incurs opportunity costs, while
minimizing reserves risks settlement delays and penalty fees.

This strategic interdependence creates a complex multi-agent environment where each
bank's optimal liquidity strategy depends on the behavior of others. Game-theoretic
analysis predicts various equilibria depending on system parameters, but validating
these predictions empirically has remained challenging due to the opacity of real-world
payment systems and the difficulty of conducting controlled experiments.

We address this gap by developing SimCash, a multi-agent simulation framework that
models RTGS payment dynamics with reinforcement learning agents. Our framework enables
controlled experiments to study how strategic agents learn to manage liquidity under
various cost structures and information conditions.

\subsection{Contributions}

This paper makes the following contributions:

\begin{enumerate}
    \item \textbf{Simulation Framework}: We present SimCash, an open-source payment
    system simulator with configurable cost structures, transaction patterns, and
    settlement mechanisms including liquidity-saving mechanisms (LSM).

    \item \textbf{Learning Agents}: We implement adaptive agents using policy gradient
    methods that learn liquidity strategies through repeated interaction, demonstrating
    convergence to game-theoretic equilibria.

    \item \textbf{Experimental Validation}: Through three experiments with varying
    asymmetry and stochasticity, we show that learned strategies match theoretical
    predictions, including free-rider equilibria and cooperative outcomes.

    \item \textbf{Methodological Contribution}: We introduce bootstrap evaluation
    for stochastic scenarios, enabling statistically rigorous comparison of agent
    strategies under cost variance.
\end{enumerate}

The remainder of this paper is organized as follows: Section~\ref{sec:methods}
describes the simulation framework and learning algorithm. Section~\ref{sec:results}
presents experimental results across three scenarios. Section~\ref{sec:discussion}
discusses implications and limitations. Section~\ref{sec:conclusion} concludes
with directions for future work.
"""
