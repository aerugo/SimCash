"""Introduction section for web version."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_introduction(provider: DataProvider) -> str:
    """Generate the introduction section in blog style."""
    _ = provider

    return """## What is SimCash?

Payment systems are where banks settle debts with each other in real-time. Every day,
trillions of dollars flow through systems like Fedwire (US), TARGET2 (EU), and Lynx
(Canada). Banks face a fundamental tradeoff: hold enough cash reserves to settle payments
quickly, or minimize idle capital and risk delays.

This is a game-theoretic problem. Your optimal strategy depends on what the other banks
do — if everyone holds plenty of cash, the system runs smoothly. If your counterparty
is cash-rich, you can free-ride with minimal reserves since their payments to you will
fund your outgoing obligations.

Traditional approaches use analytical game theory or reinforcement learning with neural
networks. We tried something different: **LLM agents that reason in natural language**
about their liquidity strategy, adjusting it iteration by iteration based on observed
costs — just like a human treasury manager would.

## Key Contributions

1. **SimCash Framework** — A hybrid Rust/Python simulator with LLM-based policy
   optimization under strict information isolation between agents

2. **Empirical Comparison** — Side-by-side comparison with game-theoretic predictions
   from Castro et al., revealing both alignment and systematic deviations

3. **Coordination Failure Analysis** — Demonstration that greedy, non-communicating
   LLM agents converge to stable but Pareto-dominated outcomes in symmetric games

4. **Bootstrap Evaluation** — A methodology for policy evaluation under stochastic
   transaction arrivals with fixed-environment assumptions
"""
