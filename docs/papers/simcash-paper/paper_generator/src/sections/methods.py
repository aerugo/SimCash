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
    # Provider not used for static methods text
    _ = provider

    return r"""
\section{The SimCash Framework}
\label{sec:methods}

\subsection{Simulation Engine}

SimCash uses a discrete-time simulation where:
\begin{itemize}
    \item Time proceeds in \textbf{ticks} (atomic time units)
    \item Banks hold \textbf{balances} in settlement accounts
    \item \textbf{Transactions} arrive with amounts, counterparties, and deadlines
    \item Settlement follows RTGS (Real-Time Gross Settlement) rules
\end{itemize}

\subsection{Cost Function}

Agent costs comprise:
\begin{itemize}
    \item \textbf{Liquidity opportunity cost}: Proportional to allocated reserves
    \item \textbf{Delay penalty}: Accumulated per tick for pending transactions
    \item \textbf{Deadline penalty}: Incurred when transactions become overdue
    \item \textbf{End-of-day penalty}: Large cost for unsettled transactions at day end
\end{itemize}

\subsection{LLM Policy Optimization}

The key innovation is using LLMs to propose policy parameters. At each iteration:

\begin{enumerate}
    \item \textbf{Context Construction}: Current policy, recent costs, opponent summary
    \item \textbf{LLM Proposal}: Agent proposes new \texttt{initial\_liquidity\_fraction} parameter
    \item \textbf{Paired Evaluation}: Run sandboxed simulations with proposed vs. current policy
    \item \textbf{Acceptance Decision}: Accept if cost improves (cost delta $> 0$)
    \item \textbf{Convergence Check}: Stable for 5 consecutive iterations
\end{enumerate}

\subsection{Evaluation Modes}

\begin{itemize}
    \item \textbf{Deterministic}: Single simulation per evaluation (fixed payments)
    \item \textbf{Bootstrap}: 50 resampled transaction histories (stochastic payments)
\end{itemize}

\subsection{Experimental Setup}

We implement three canonical scenarios:

\textbf{Experiment 1: 2-Period Deterministic}
\begin{itemize}
    \item 2 ticks per day
    \item Fixed payment arrivals at tick 0: BANK\_A sends 0.2, BANK\_B sends 0.2
    \item Expected equilibrium: Asymmetric (A=0\%, B=20\%)
\end{itemize}

\textbf{Experiment 2: 12-Period Stochastic}
\begin{itemize}
    \item 12 ticks per day
    \item Poisson arrivals ($\lambda$=0.5/tick), LogNormal amounts
    \item Expected equilibrium: Both agents in 10-30\% range
\end{itemize}

\textbf{Experiment 3: 3-Period Symmetric}
\begin{itemize}
    \item 3 ticks per day
    \item Fixed symmetric payment demands (0.2, 0.2, 0)
    \item Expected equilibrium: Symmetric ($\sim$20\%)
\end{itemize}

\subsection{LLM Configuration}

\begin{itemize}
    \item Model: \texttt{openai:gpt-5.2}
    \item Reasoning effort: \texttt{high}
    \item Temperature: 0.5
    \item Convergence: 5-iteration stability window, 5\% threshold
\end{itemize}

Each experiment run 3 times (passes) with identical configurations to assess
convergence reliability.
"""
