"""Discussion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_discussion(provider: DataProvider) -> str:
    """Generate the discussion section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the discussion section
    """
    return r"""
\section{Discussion}
\label{sec:discussion}

Our experimental results demonstrate that reinforcement learning agents in the
SimCash framework successfully discover game-theoretically predicted equilibria
across varied scenarios. This section discusses implications, limitations, and
connections to related work.

\subsection{Implications for Payment System Design}

The emergence of free-rider equilibria in asymmetric cost scenarios (Experiment 1)
highlights a key challenge for RTGS system designers. When participants face
different delay cost structures---due to regulatory requirements, operational
constraints, or business models---strategic behavior can lead to liquidity
concentration among a subset of participants.

Our results suggest that:
\begin{itemize}
    \item Symmetric penalty structures encourage more distributed liquidity provision
    \item Asymmetric penalties can create systemic dependencies on specific participants
    \item The liquidity-saving mechanism (LSM) can mitigate but not eliminate
    strategic liquidity hoarding
\end{itemize}

\subsection{Methodological Contributions}

The bootstrap evaluation methodology introduced for stochastic scenarios
(Experiment 2) addresses a gap in prior simulation studies. By evaluating
policies over multiple transaction realizations, we obtain statistically
meaningful comparisons that account for inherent cost variance.

This approach is essential when:
\begin{itemize}
    \item Transaction amounts are drawn from distributions rather than fixed
    \item Arrival patterns exhibit day-to-day variation
    \item Policy differences are subtle relative to stochastic noise
\end{itemize}

\subsection{Limitations}

Several limitations of this study warrant acknowledgment:

\begin{enumerate}
    \item \textbf{Two-agent simplification}: Real RTGS systems involve dozens or
    hundreds of participants with heterogeneous characteristics. Scaling to larger
    networks remains for future work.

    \item \textbf{Full observability}: Agents observe counterparty liquidity fractions
    directly. In practice, banks have limited visibility into others' reserves.

    \item \textbf{Simplified cost model}: Our linear cost functions may not capture
    all complexities of real holding and delay costs.

    \item \textbf{Deterministic convergence}: While we verify reproducibility across
    passes, learning dynamics could exhibit path-dependence in more complex scenarios.
\end{enumerate}

\subsection{Related Work}

Our work builds on several research streams:

\textbf{Payment system simulation}: Prior simulators have modeled RTGS dynamics but
typically used fixed or rule-based agent behavior rather than learning agents.

\textbf{Multi-agent reinforcement learning}: We apply established policy gradient
methods to a new domain, contributing experimental evidence of equilibrium discovery
in strategic payment environments.

\textbf{Liquidity management}: Economic theory predicts free-rider and coordination
equilibria in interbank markets; our simulations validate these predictions experimentally.
"""
