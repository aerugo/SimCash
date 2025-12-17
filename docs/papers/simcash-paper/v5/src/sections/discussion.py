"""Discussion section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.template import var

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_discussion(provider: DataProvider | None = None) -> str:
    """Generate the discussion section template.

    Args:
        provider: DataProvider instance (unused, kept for API compatibility)

    Returns:
        LaTeX string with {{variable}} placeholders
    """
    return rf"""
\section{{Discussion}}
\label{{sec:discussion}}

Our experimental results demonstrate that reinforcement learning agents in the
SimCash framework successfully discover game-theoretically predicted equilibria
across varied scenarios. All {var('total_passes')} experiment passes achieved convergence,
validating the framework's robustness.

\subsection{{Theoretical Alignment}}

The observed equilibria closely align with game-theoretic predictions:

\begin{{itemize}}
    \item \textbf{{Experiment 1 (Asymmetric)}}: BANK\_A converged to mean liquidity
    {var('exp1_avg_bank_a_liquidity_pct')}\% while BANK\_B maintained {var('exp1_avg_bank_b_liquidity_pct')}\%. The
    {var('exp1_liquidity_diff_pct')}\% difference reflects the predicted free-rider equilibrium
    where the bank with lower delay costs under-provides liquidity.

    \item \textbf{{Experiment 3 (Symmetric)}}: Both banks converged to similar
    liquidity levels ({var('exp3_avg_bank_a_liquidity_pct')}\% vs {var('exp3_avg_bank_b_liquidity_pct')}\%), with only
    {var('exp3_liquidity_diff_pct')}\% difference. This symmetric outcome confirms
    that identical incentives produce cooperative equilibria.
\end{{itemize}}

The mean convergence time of {var('exp1_mean_iterations')} iterations for Experiment 1
compared to {var('exp3_mean_iterations')} for Experiment 3 suggests that asymmetric equilibria
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

The total equilibrium cost of \${var('exp1_avg_total_cost')} in Experiment 1 compared to
\${var('exp3_avg_total_cost')} in Experiment 3 demonstrates the efficiency implications of
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
    to optimal values ranging from {var('exp1_avg_bank_a_liquidity_pct')}\% to {var('exp1_avg_bank_b_liquidity_pct')}\%.

    \item \textbf{{Counterparty Modeling}}: The asymmetric equilibria demonstrate
    implicit opponent modeling---BANK\_A's low liquidity strategy only works
    if it anticipates BANK\_B's higher provision.

    \item \textbf{{Convergence Speed}}: Mean convergence in {var('exp1_mean_iterations')}--{var('exp3_mean_iterations')}
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
    {var('total_passes')} passes, learning dynamics could exhibit path-dependence in more
    complex scenarios.
\end{{enumerate}}
"""
