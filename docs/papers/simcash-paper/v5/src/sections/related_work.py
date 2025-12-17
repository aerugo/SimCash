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
characterizing Nash equilibria in simplified settings with deterministic payment
arrivals \cite{castro2013}. Their analysis of two-period games predicts asymmetric
equilibria where one bank can free-ride on another's liquidity provision when
payment timing creates sequential dependencies.

Martin and McAndrews extended this framework to stochastic arrivals with
analytical bounds on equilibrium liquidity levels \cite{martin2010}. Their work
on liquidity-saving mechanisms (LSM) demonstrated how multilateral netting can
reduce aggregate liquidity requirements while preserving settlement finality.

Simulation-based approaches have modeled RTGS dynamics with fixed or rule-based
agent behavior, but typically lack the adaptive learning that characterizes
real strategic interactions between banks.

\subsection{LLMs in Game Theory}

Recent work has explored Large Language Models in strategic settings, primarily
in matrix games, negotiation tasks, and auction mechanisms. Studies have shown
that LLMs can exhibit sophisticated strategic reasoning, including recognizing
dominant strategies, anticipating opponent behavior, and converging to Nash
equilibria in repeated games.

However, prior work has focused on discrete action spaces and single-shot or
short-horizon interactions. Our work is the first to apply LLMs to sequential
payment system games with continuous action spaces (liquidity fractions) and
multi-day time horizons.

\subsection{Multi-Agent Reinforcement Learning}

Multi-agent reinforcement learning (MARL) provides theoretical foundations for
understanding convergence in competitive and cooperative settings. Independent
learners using policy gradient methods can converge to Nash equilibria in
certain game classes, though convergence guarantees are weaker than in single-agent
settings.

Our framework applies these principles to a novel domain---interbank payment
systems---where the strategic complexity arises from the interaction between
liquidity costs, settlement timing, and counterparty dependencies.
"""
