"""Abstract / hero section for web version."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_abstract(provider: DataProvider) -> str:
    """Generate title + abstract as blog intro."""
    agg = provider.get_aggregate_stats()
    total_passes = agg["total_passes"]
    total_experiments = agg["total_experiments"]
    avg_iters = agg["overall_mean_iterations"]

    return f"""# Discovering Equilibrium-like Behavior with LLM Agents

*A Payment Systems Case Study* — **Hugi Aegisberg**

---

Can Large Language Models discover stable strategies through reasoning alone — without
knowing they're playing a game?

We gave LLM agents a real problem: manage liquidity in a payment system where holding
cash is expensive but running out causes settlement delays. Each agent sees only its own
costs and transactions — never what the other side is doing. Through {total_passes}
independent runs across {total_experiments} scenarios, these agents reliably converged to
stable policy profiles in an average of {avg_iters:.1f} iterations.

But here's the twist: **stability doesn't mean optimality**. In symmetric games, agents
consistently fell into coordination traps — Pareto-dominated outcomes where both sides
ended up worse off than where they started. The identity of the "free-rider" was determined
by whoever made the first aggressive move, not by any structural advantage.

Stochastic environments told a different story. With uncertain payment timing and bootstrap
policy evaluation, agents found near-symmetric allocations without the coordination
collapse seen in deterministic settings.

These results suggest LLM-based optimization can discover stable strategies without
explicit game theory, but also show that greedy, non-communicating agents reliably
converge to coordination traps — exactly what theory predicts for rational agents
without coordination mechanisms.
"""
