"""Conclusion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.formatting import format_percent

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_conclusion(provider: DataProvider) -> str:
    """Generate the conclusion section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the conclusion section
    """
    # Get convergence iterations to summarize
    exp1_conv = provider.get_convergence_iteration("exp1", pass_num=1)
    exp2_conv = provider.get_convergence_iteration("exp2", pass_num=1)
    exp3_conv = provider.get_convergence_iteration("exp3", pass_num=1)

    # Get aggregate statistics
    aggregate_stats = provider.get_aggregate_stats()
    convergence_pct = int(aggregate_stats["overall_convergence_rate"] * 100)
    avg_iterations = aggregate_stats["overall_mean_iterations"]

    # Get exp2 data for Finding #3
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp2_all_liqs = [s["bank_a_liquidity"] for s in exp2_summaries] + [
        s["bank_b_liquidity"] for s in exp2_summaries
    ]
    exp2_liq_min = min(exp2_all_liqs)
    exp2_liq_max = max(exp2_all_liqs)

    # Count symmetric passes (ratio < 2x considered symmetric)
    exp2_symmetric_count = sum(
        1
        for s in exp2_summaries
        if max(s["bank_a_liquidity"], s["bank_b_liquidity"])
        / max(min(s["bank_a_liquidity"], s["bank_b_liquidity"]), 0.001)
        < 2.0
    )

    return rf"""
\section{{Conclusion}}
\label{{sec:conclusion}}

We presented SimCash, a framework for discovering equilibrium-like behavior in payment system
liquidity games using LLM-based policy optimization. Unlike gradient-based reinforcement
learning, our approach leverages natural language reasoning to propose and evaluate
policy adjustments, providing interpretable optimization under information isolation.

\subsection{{Summary of Findings}}

Across {aggregate_stats["total_passes"]} independent runs, LLM agents achieved
{convergence_pct}\% convergence to stable policy profiles (mean {avg_iterations:.1f} iterations).
Three key findings emerged:

\textbf{{1. Asymmetric outcomes dominate in our experiments.}} Even in Experiment 3's symmetric game,
agents consistently converged to asymmetric free-rider outcomes rather than the
theoretically predicted symmetric equilibrium. Typically one agent settles on very low liquidity
while the other maintains higher allocation; even in suboptimal outcomes (Exp 1 Pass 3),
the results remain asymmetric.

\textbf{{2. Early dynamics determine equilibrium selection.}} The \textit{{identity}}
of the free-rider was determined by early exploration rather than cost structure.
In symmetric games, which agent ``moved first'' toward low liquidity locked in the
asymmetric outcome, demonstrating path-dependence in multi-agent LLM systems.

\textbf{{3. Stochastic environments produced symmetric outcomes in all passes.}}
While deterministic scenarios (Experiments 1 and 3) exhibited asymmetric free-rider outcomes
with liquidity ratios exceeding 6$\times$, stochastic environments (Experiment 2) produced
symmetric allocations in all {exp2_symmetric_count} passes (ratios below 2$\times$, overall range
{format_percent(exp2_liq_min)}--{format_percent(exp2_liq_max)}). This pattern
is consistent with Castro et al.'s prediction that payment timing uncertainty inhibits
free-riding, though the small sample size (n=3) warrants further validation. The magnitude
({format_percent(exp2_liq_min)}--{format_percent(exp2_liq_max)}) fell below Castro's predicted
10--30\%, suggesting LLM agents discovered lower-liquidity equilibria.

\subsection{{Implications}}

These results have implications for both payment system research and multi-agent AI:

\begin{{itemize}}
    \item \textbf{{For payment systems:}} LLM-based policy optimization can discover
    equilibrium behavior without explicit game-theoretic modeling, potentially aiding
    central banks in understanding how algorithmic liquidity management might evolve.

    \item \textbf{{For multi-agent AI:}} Sequential best-response dynamics in LLM systems
    naturally select among multiple stable outcomes based on exploration history, not payoff
    structure alone. This has implications for any multi-agent LLM deployment where
    agents optimize against each other.
\end{{itemize}}

\subsection{{Limitations and Future Work}}

The most significant limitation is \textbf{{sample size}}: with only {aggregate_stats["total_passes"]}
total runs, our findings are preliminary. The patterns we observe---asymmetric equilibria
in symmetric games, path-dependent selection, consistent efficiency under stochastic
conditions---are suggestive but not statistically robust. Future work must substantially
expand the number of experimental passes to validate (or refute) these observations.

Additionally, our implementation differs from Castro et al.\ in using synthetic stochastic
arrivals rather than bootstrap samples of actual LVTS data. Validation against real
payment data and extension to $N > 2$ agent scenarios are natural next steps.

The interpretability of LLM reasoning also presents opportunities: agents' natural
language deliberations could be analyzed to understand \textit{{why}} particular
equilibria are selected, potentially revealing the implicit heuristics that drive
equilibrium selection in learning systems.
"""
