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

We presented SimCash, a framework for discovering stable policy profiles in payment system
liquidity games using LLM-based policy optimization. Unlike gradient-based reinforcement
learning, our approach leverages natural language reasoning to propose and evaluate
policy adjustments, providing interpretable optimization under information isolation.

\subsection{{Summary of Findings}}

Across {aggregate_stats["total_passes"]} independent runs, LLM agents achieved
policy stability in deterministic scenarios (mean {avg_iterations:.1f} iterations),
while stochastic scenarios achieved practical stability but terminated at iteration budget
without meeting strict statistical convergence thresholds (the CV $<$ 3\% requirement
proved overly conservative for environments with inherent cost variance).
Three key findings emerged:

\textbf{{1. Stability does not imply optimality.}} In Experiment 3's symmetric game,
agents consistently converged to \textit{{coordination failures}}---stable profiles where
both agents incur higher costs than the Pareto-efficient baseline. The unconditional
acceptance mechanism in deterministic mode allows agents to follow locally-improving
gradients into globally-worse outcomes. This demonstrates that LLM agents exhibit the
same coordination failures as any greedy, non-communicating optimizers.

\textbf{{2. Early dynamics determine outcome selection.}} The \textit{{identity}}
of the free-rider was determined by early aggressive moves rather than cost structure.
In symmetric games, which agent ``moved first'' toward low liquidity trapped both
agents in an asymmetric profile, demonstrating path-dependence in multi-agent LLM systems.

\textbf{{3. Stochastic environments with bootstrap evaluation avoided coordination collapse.}}
While deterministic scenarios (Experiments 1 and 3) exhibited coordination failures
with liquidity ratios exceeding 6$\times$, stochastic environments (Experiment 2) produced
near-symmetric allocations in all {exp2_symmetric_count} passes (ratios below 2$\times$, overall range
{format_percent(exp2_liq_min)}--{format_percent(exp2_liq_max)}). The bootstrap evaluation
mechanism---which tests candidate policies before acceptance---may help agents avoid
aggressive moves that trigger coordination traps. However, Experiment 2 terminated at
iteration budget rather than achieving formal convergence, and the small sample size (n=3)
warrants further validation.

\subsection{{Implications}}

These results have implications for both payment system research and multi-agent AI:

\begin{{itemize}}
    \item \textbf{{For payment systems:}} LLM-based policy optimization can discover
    stable profiles without explicit game-theoretic modeling, but stability alone does
    not guarantee efficiency. Central banks studying algorithmic liquidity management
    should anticipate that decentralized optimizers may converge to coordination traps.

    \item \textbf{{For multi-agent AI:}} Sequential optimization in LLM systems can
    produce coordination failures where all agents are worse off. This has implications
    for any multi-agent LLM deployment: without mechanisms for coordination (communication,
    commitment devices, or external guidance), agents may reliably converge to suboptimal
    outcomes.
\end{{itemize}}

\subsection{{Limitations and Future Work}}

The most significant limitation is \textbf{{sample size}}: with only {aggregate_stats["total_passes"]}
total runs, our findings are preliminary. The patterns we observe---coordination failures
in symmetric games, path-dependent selection, near-symmetric outcomes under stochastic
conditions---are suggestive but not statistically robust. Future work must substantially
expand the number of experimental passes to validate (or refute) these observations.

Additionally, our implementation differs from Castro et al.\ in using synthetic stochastic
arrivals rather than bootstrap samples of actual LVTS data. Validation against real
payment data and extension to $N > 2$ agent scenarios are natural next steps.

The bootstrap evaluation methodology also warrants refinement. Transaction-level resampling
with settlement offsets can create non-physical correlations that potentially amplify tail
events beyond what the original generative process would produce. For real RTGS data with
intra-day variability, \textbf{{block bootstrap}} (resampling contiguous time windows) or
\textbf{{day-level bootstrap}} (resampling entire business days) would better preserve temporal
dependencies. Alternatively, evaluating final policies on held-out stochastic seeds would
measure true cross-day variance rather than resampling sensitivity.

The coordination failures in Experiment 3 suggest a promising research direction:
\textbf{{mechanisms that help non-communicating agents escape suboptimal profiles}}.
Regulatory nudges, commitment devices, and cost-aware acceptance criteria could be
tested within SimCash to identify minimal interventions that improve coordination
while preserving realistic information constraints.
"""
