"""Methods section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_methods(provider: DataProvider) -> str:
    """Generate the methods/framework section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the methods section
    """
    return r"""
\section{Framework and Methods}
\label{sec:methods}

This section describes the SimCash simulation framework, including the payment
system model, cost structure, and reinforcement learning approach.

\subsection{Payment System Model}

We model an RTGS system with $N$ banks (agents) processing payments over discrete
time steps (ticks). Each bank $i$ maintains:
\begin{itemize}
    \item \textbf{Balance} $b_i(t)$: Current settlement account balance
    \item \textbf{Liquidity fraction} $\lambda_i \in [0,1]$: Proportion of assets
    held as liquid reserves
    \item \textbf{Payment queue} $Q_i(t)$: Pending outgoing payments awaiting settlement
\end{itemize}

Payments arrive according to configurable arrival processes with specified amount
distributions. Each payment has a deadline; payments settled after their deadline
incur increased costs.

\subsection{Cost Structure}

Bank $i$'s total cost comprises several components:

\begin{equation}
C_i = C_i^{hold} + C_i^{delay} + C_i^{deadline} + C_i^{EOD}
\end{equation}

where:
\begin{itemize}
    \item $C_i^{hold}$: Opportunity cost of holding liquid reserves
    \item $C_i^{delay}$: Per-tick delay cost for queued payments
    \item $C_i^{deadline}$: Penalty when payments become overdue
    \item $C_i^{EOD}$: End-of-day penalty for unsettled payments
\end{itemize}

The specific parameterization varies by experiment to create different strategic
incentives (asymmetric vs. symmetric).

\subsection{Settlement Mechanisms}

The simulation supports two settlement modes:
\begin{enumerate}
    \item \textbf{RTGS}: Immediate gross settlement when sender has sufficient balance
    \item \textbf{LSM}: Liquidity-saving mechanism that identifies bilateral and
    multilateral netting opportunities to reduce liquidity requirements
\end{enumerate}

\subsection{Reinforcement Learning Agents}

Each agent learns a policy $\pi_i(\lambda | s)$ mapping observations to liquidity
fraction choices. We use a policy gradient approach where agents:

\begin{enumerate}
    \item Observe end-of-period costs and counterparty behavior
    \item Update policy parameters via gradient descent on expected cost
    \item Propose new liquidity fractions for the next iteration
\end{enumerate}

The learning process continues until policy changes fall below a convergence
threshold or a maximum iteration count is reached.

\subsection{Experimental Design}

We conduct three experiments with varying parameters:

\begin{description}
    \item[Experiment 1 (Asymmetric)] Different delay costs create incentive for
    free-riding behavior
    \item[Experiment 2 (Stochastic)] Transaction amounts drawn from distributions
    require bootstrap evaluation
    \item[Experiment 3 (Symmetric)] Identical cost structures encourage cooperative
    equilibrium
\end{description}

Each experiment runs multiple passes to verify reproducibility of convergence.
"""
