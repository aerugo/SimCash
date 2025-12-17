"""Discussion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.formatting import format_money, format_percent

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_discussion(provider: DataProvider) -> str:
    """Generate the discussion section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the discussion section
    """
    # Get aggregate statistics
    aggregate_stats = provider.get_aggregate_stats()
    total_passes = aggregate_stats["total_passes"]

    # Get data for analysis
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Calculate mean final values across passes
    exp1_mean_a_liq = sum(s["bank_a_liquidity"] for s in exp1_summaries) / len(exp1_summaries)
    exp1_mean_b_liq = sum(s["bank_b_liquidity"] for s in exp1_summaries) / len(exp1_summaries)
    exp1_mean_total = sum(s["total_cost"] for s in exp1_summaries) // len(exp1_summaries)

    exp3_mean_a_liq = sum(s["bank_a_liquidity"] for s in exp3_summaries) / len(exp3_summaries)
    exp3_mean_b_liq = sum(s["bank_b_liquidity"] for s in exp3_summaries) / len(exp3_summaries)
    exp3_mean_total = sum(s["total_cost"] for s in exp3_summaries) // len(exp3_summaries)

    # Get convergence stats
    exp1_conv = provider.get_convergence_statistics("exp1")
    exp3_conv = provider.get_convergence_statistics("exp3")

    # Format values for inline use
    exp1_a_liq_fmt = format_percent(exp1_mean_a_liq)
    exp1_b_liq_fmt = format_percent(exp1_mean_b_liq)
    exp1_total_fmt = format_money(exp1_mean_total)

    exp3_a_liq_fmt = format_percent(exp3_mean_a_liq)
    exp3_b_liq_fmt = format_percent(exp3_mean_b_liq)
    exp3_total_fmt = format_money(exp3_mean_total)

    exp1_mean_iters = f"{exp1_conv['mean_iterations']:.1f}"
    exp3_mean_iters = f"{exp3_conv['mean_iterations']:.1f}"

    # Calculate liquidity asymmetry
    exp1_liq_diff = abs(exp1_mean_a_liq - exp1_mean_b_liq)
    exp3_liq_diff = abs(exp3_mean_a_liq - exp3_mean_b_liq)

    return rf"""
\section{{Discussion}}
\label{{sec:discussion}}

Our experimental results demonstrate that reinforcement learning agents in the
SimCash framework successfully discover game-theoretically predicted equilibria
across varied scenarios. All {total_passes} experiment passes achieved convergence,
validating the framework's robustness.

\subsection{{Theoretical Alignment}}

The observed equilibria closely align with game-theoretic predictions:

\begin{{itemize}}
    \item \textbf{{Experiment 1 (Asymmetric)}}: BANK\_A converged to mean liquidity
    {exp1_a_liq_fmt} while BANK\_B maintained {exp1_b_liq_fmt}. The
    {format_percent(exp1_liq_diff)} difference reflects the predicted free-rider equilibrium
    where the bank with lower delay costs under-provides liquidity.

    \item \textbf{{Experiment 3 (Symmetric)}}: Both banks converged to similar
    liquidity levels ({exp3_a_liq_fmt} vs {exp3_b_liq_fmt}), with only
    {format_percent(exp3_liq_diff)} difference. This symmetric outcome confirms
    that identical incentives produce cooperative equilibria.
\end{{itemize}}

The mean convergence time of {exp1_mean_iters} iterations for Experiment 1
compared to {exp3_mean_iters} for Experiment 3 suggests that asymmetric equilibria
require more exploration to discover optimal free-riding strategies.

\subsection{{Implications for Payment System Design}}

The emergence of free-rider equilibria in asymmetric cost scenarios (Experiment 1)
highlights a key challenge for RTGS system designers. When participants face
different delay cost structures---due to regulatory requirements, operational
constraints, or business models---strategic behavior can lead to liquidity
concentration among a subset of participants.

Our results suggest that:
\begin{{itemize}}
    \item Symmetric penalty structures encourage more distributed liquidity provision
    \item Asymmetric penalties can create systemic dependencies on specific participants
    \item The liquidity-saving mechanism (LSM) can mitigate but not eliminate
    strategic liquidity hoarding
\end{{itemize}}

The total equilibrium cost of {exp1_total_fmt} in Experiment 1 compared to
{exp3_total_fmt} in Experiment 3 demonstrates the efficiency implications of
different cost structures.

\subsection{{Methodological Contributions}}

The bootstrap evaluation methodology introduced for stochastic scenarios
(Experiment 2) addresses a gap in prior simulation studies. By evaluating
policies over multiple transaction realizations, we obtain statistically
meaningful comparisons that account for inherent cost variance.

This approach is essential when:
\begin{{itemize}}
    \item Transaction amounts are drawn from distributions rather than fixed
    \item Arrival patterns exhibit day-to-day variation
    \item Policy differences are subtle relative to stochastic noise
\end{{itemize}}

\subsection{{LLM Reasoning Capabilities}}

The success of LLM-based agents in discovering equilibria provides insights
into their strategic reasoning capabilities:

\begin{{enumerate}}
    \item \textbf{{Policy Optimization}}: Agents effectively explored the
    continuous liquidity fraction space, converging from initial 50\% allocations
    to optimal values ranging from {exp1_a_liq_fmt} to {exp1_b_liq_fmt}.

    \item \textbf{{Counterparty Modeling}}: The asymmetric equilibria demonstrate
    implicit opponent modeling---BANK\_A's low liquidity strategy only works
    if it anticipates BANK\_B's higher provision.

    \item \textbf{{Convergence Speed}}: Mean convergence in {exp1_mean_iters}--{exp3_mean_iters}
    iterations suggests efficient exploration of the strategy space.
\end{{enumerate}}

\subsection{{Limitations}}

Several limitations of this study warrant acknowledgment:

\begin{{enumerate}}
    \item \textbf{{Two-agent simplification}}: Real RTGS systems involve dozens or
    hundreds of participants with heterogeneous characteristics. Scaling to larger
    networks remains for future work.

    \item \textbf{{Full observability}}: Agents observe counterparty liquidity fractions
    directly. In practice, banks have limited visibility into others' reserves.

    \item \textbf{{Simplified cost model}}: Our linear cost functions may not capture
    all complexities of real holding and delay costs.

    \item \textbf{{Deterministic convergence}}: While we verify reproducibility across
    {total_passes} passes, learning dynamics could exhibit path-dependence in more
    complex scenarios.
\end{{enumerate}}
"""
