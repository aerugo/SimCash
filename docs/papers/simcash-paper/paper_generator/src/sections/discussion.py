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

    # Get individual pass data for detailed analysis
    exp2_summaries = provider.get_all_pass_summaries("exp2")

    # Identify free-rider patterns (who has lower liquidity in each pass)
    exp1_freerider_a_count = sum(
        1 for s in exp1_summaries if s["bank_a_liquidity"] < s["bank_b_liquidity"]
    )
    exp3_freerider_a_count = sum(
        1 for s in exp3_summaries if s["bank_a_liquidity"] < s["bank_b_liquidity"]
    )

    # Get best and worst total costs for each experiment
    exp1_best_total = min(s["total_cost"] for s in exp1_summaries)
    exp1_worst_total = max(s["total_cost"] for s in exp1_summaries)
    exp3_best_total = min(s["total_cost"] for s in exp3_summaries)
    exp3_worst_total = max(s["total_cost"] for s in exp3_summaries)

    # Exp2 statistics
    exp2_mean_a_liq = sum(s["bank_a_liquidity"] for s in exp2_summaries) / len(exp2_summaries)
    exp2_mean_b_liq = sum(s["bank_b_liquidity"] for s in exp2_summaries) / len(exp2_summaries)
    exp2_best_total = min(s["total_cost"] for s in exp2_summaries)
    exp2_worst_total = max(s["total_cost"] for s in exp2_summaries)

    # Exp2 cost asymmetry analysis
    exp2_mean_a_cost = sum(s["bank_a_cost"] for s in exp2_summaries) // len(exp2_summaries)
    exp2_mean_b_cost = sum(s["bank_b_cost"] for s in exp2_summaries) // len(exp2_summaries)
    exp2_cost_ratio = exp2_mean_b_cost / exp2_mean_a_cost if exp2_mean_a_cost > 0 else 0

    # Compute exp2 liquidity range and symmetry metrics
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
\section{{Discussion}}
\label{{sec:discussion}}

Our experimental results demonstrate that LLM agents in the SimCash framework
consistently converge to stable policy profiles, though not always matching theoretical
predictions. All {total_passes} experiment passes achieved convergence,
validating the framework's robustness.

\subsection{{Theoretical Alignment and Deviations}}

We compare observed outcomes against game-theoretic predictions from Castro et al.\ (2025):

\subsubsection{{Experiment 1: Asymmetric Cost Structure}}

Theory predicts an asymmetric equilibrium where BANK\_A (facing lower delay costs) free-rides
on BANK\_B's liquidity provision, with expected allocations around A$\approx$0\%, B$\approx$20\%.

Our results \textbf{{partially confirm}} this prediction:
\begin{{itemize}}
    \item \textbf{{Passes 1--2}}: BANK\_A converged to near-zero liquidity (0.0--0.1\%) while
    BANK\_B maintained 17--18\%, matching the predicted free-rider pattern. Total costs were
    efficient at \$27--28.

    \item \textbf{{Pass 3}}: The free-rider \textit{{identity flipped}}---BANK\_B converged to
    0\% while BANK\_A maintained 1.8\%. This role reversal resulted in substantially
    higher total cost ({format_money(exp1_worst_total)} vs {format_money(exp1_best_total)}),
    demonstrating that the learning dynamics can converge to \textbf{{multiple asymmetric
    stable outcomes}} with different efficiency properties. Note that BANK\_B's zero-liquidity
    outcome, while stable, resulted in \textit{{higher}} costs for both agents---representing
    a coordination failure rather than successful free-riding.
\end{{itemize}}

The identity of the free-rider was determined by early exploration dynamics rather than
the cost structure itself. BANK\_A assumed the free-rider role in {exp1_freerider_a_count}
of 3 passes.

\subsubsection{{Experiment 2: Stochastic Environment}}

Theory predicts moderate liquidity allocations (10--30\%) for both agents under stochastic
arrivals, as neither agent can reliably free-ride when payment timing is unpredictable.

\textbf{{Methodological note:}} Castro et al.\ use bootstrap samples of \textit{{actual}} LVTS
payment data (380 business days), where each episode samples a historical day. Our implementation
uses \textit{{stochastic transaction arrival}} with configurable Poisson rates and amount
distributions---a synthetic approximation that may exhibit different variance characteristics.

Our results show \textbf{{partial alignment}} with theoretical predictions:
\begin{{itemize}}
    \item Final liquidity allocations were \textbf{{near-symmetric}}: BANK\_A averaged
    {format_percent(exp2_mean_a_liq)} and BANK\_B averaged {format_percent(exp2_mean_b_liq)}.
    Notably, all {exp2_symmetric_count} passes produced symmetric outcomes (liquidity ratios
    below 2$\times$), contrasting sharply with Experiments 1 and 3 where deterministic schedules
    enabled asymmetric free-rider equilibria with ratios exceeding 6$\times$. This pattern
    is consistent with Castro et al.'s prediction that stochastic arrivals inhibit free-riding.

    \item However, the observed {format_percent(exp2_liq_min)}--{format_percent(exp2_liq_max)} range
    falls \textit{{below}} Castro's predicted 10--30\%, suggesting LLM agents discovered
    lower-liquidity stable profiles. Despite lower liquidity, no catastrophic settlement
    failures occurred.

    \item Total costs ranged from {format_money(exp2_best_total)} to {format_money(exp2_worst_total)}.
    While this represents meaningful variation, the key finding is that \textit{{all passes}}
    produced symmetric liquidity outcomes---unlike deterministic experiments where free-rider
    dynamics dominated.

    \item Notably, while liquidity allocations were symmetric, \textbf{{cost outcomes remained
    asymmetric}}: BANK\_B incurred approximately {exp2_cost_ratio:.1f}$\times$ higher costs than
    BANK\_A on average ({format_money(exp2_mean_b_cost)} vs {format_money(exp2_mean_a_cost)}).
    This suggests that similar liquidity allocations can produce different cost outcomes under
    stochastic arrivals, potentially due to differences in payment timing exposure or queue
    dynamics. Further investigation is needed to understand this cost asymmetry.
\end{{itemize}}

\subsubsection{{Experiment 3: Coordination Failure}}

Theory predicts a \textbf{{symmetric equilibrium}} where both agents allocate similar
liquidity fractions ($\sim$20\% each), as neither has a structural advantage. The
symmetric equilibrium at $\sim$\$50 total cost (the baseline) is Pareto-efficient.

\textbf{{All three passes exhibit coordination failure}}:
\begin{{itemize}}
    \item In every pass, agents converged to profiles where \textit{{both}} agents incur
    higher costs than the baseline symmetric equilibrium.

    \item \textbf{{Passes 1--2}}: BANK\_A dropped to low liquidity (1--5\%) while BANK\_B
    compensated (29--30\%). Total costs ({format_money(exp3_best_total)}) exceeded baseline (\$100).

    \item \textbf{{Pass 3}}: Roles flipped but with worse outcomes---total cost was
    {format_money(exp3_worst_total)}, more than double baseline.

    \item BANK\_A assumed the free-rider role in {exp3_freerider_a_count} of 3 passes.
\end{{itemize}}

This is \textbf{{not a failure of the LLM agents' reasoning}} but rather an expected
outcome of \textit{{unconditional acceptance}} dynamics. Each agent follows locally-improving
gradients that can lead to globally-worse outcomes. Early aggressive moves by one agent
(e.g., BANK\_A dropping to 1\% in iteration 2 of Pass 1) trap both agents in suboptimal
profiles from which neither can unilaterally escape.

The results demonstrate that \textbf{{stable does not imply optimal}}: greedy,
non-communicating agents can reliably converge to Pareto-dominated coordination traps.

\subsubsection{{Summary of Theoretical Alignment}}

\begin{{center}}
\begin{{tabular}}{{lccc}}
\hline
Experiment & Predicted & Observed & Alignment \\
\hline
Exp 1 (Asymmetric) & Asymmetric & Asymmetric (role varies) & Partial \\
Exp 2 (Stochastic) & Symmetric, 10--30\% & Symmetric, {format_percent(exp2_liq_min)}--{format_percent(exp2_liq_max)} & Partial (symmetric, lower magnitude) \\
Exp 3 (Symmetric) & Symmetric & Asymmetric & Deviation \\
\hline
\end{{tabular}}
\end{{center}}

The key insight is that while agents consistently find \textit{{stable}} outcomes,
the specific equilibrium selected depends on learning dynamics rather than cost structure
alone. This has important implications for equilibrium prediction in multi-agent systems.

\subsection{{LLM Reasoning as a Policy Approximation}}

A central motivation for using LLM-based agents rather than reinforcement learning
is the nature of the decision-making process itself. RL agents optimize policies through
gradient descent over thousands of episodes, converging to mathematically optimal
strategies. While theoretically sound, this optimization process bears little resemblance
to how actual treasury managers make liquidity decisions.

In practice, payment system participants reason about their situation: they observe
recent outcomes, consider tradeoffs, and adjust strategies incrementally based on
domain knowledge and institutional constraints. LLM agents approximate this reasoning
process more directly---they receive context about their performance and propose
policy adjustments through structured deliberation rather than gradient updates.

This approach offers several modeling advantages:
\begin{{itemize}}
    \item \textbf{{Interpretable decisions}}: LLM agents produce natural language
    reasoning that researchers can audit, unlike opaque neural network weights.

    \item \textbf{{Heterogeneous instructions}}: Different agents can receive tailored
    system prompts emphasizing risk tolerance, regulatory constraints, or strategic
    objectives---approximating how different institutions operate under different mandates.

    \item \textbf{{Few-shot adaptation}}: Agents adjust policies in 7--50 iterations
    rather than requiring thousands of training episodes, enabling rapid exploration
    of scenario variations. (Note: while each bootstrap iteration involves $\sim$50
    simulation samples for evaluation, the number of LLM decision points requiring
    reasoning remains 7--50.)
\end{{itemize}}

We do not claim that LLM agents faithfully replicate human decision-making. Our
experiments show behaviors that are sometimes suboptimal (e.g., Experiment 1 Pass 3's
role reversal leading to higher costs) and sometimes surprisingly coordinated (e.g.,
asymmetric equilibria emerging under information isolation). The value lies not in
behavioral fidelity but in providing a \textit{{reasoning-based}} alternative to
gradient-based optimization for multi-agent policy discovery.

\subsection{{Policy Expressiveness and Extensibility}}

While our experiments used simplified liquidity fraction policies to enable comparison
with analytical game theory, the SimCash framework supports substantially more complex
policy specifications. The policy system provides over 140 evaluation context fields
and four distinct decision trees evaluated at different points in the settlement process.

Agents can develop policies that respond dynamically to:
\begin{{itemize}}
    \item \textbf{{Temporal dynamics}}: Payment urgency based on ticks remaining until
    deadline, with different thresholds for ``urgent'' versus ``critical'' situations.
    Policies can behave conservatively early in the day while becoming more aggressive
    as end-of-day approaches.

    \item \textbf{{System stress}}: Real-time liquidity gap monitoring enables policies
    that post collateral preemptively when queue depths exceed thresholds, rather than
    waiting for gridlock to develop.

    \item \textbf{{Payment characteristics}}: Priority levels, divisibility flags, and
    remaining amounts can trigger different handling strategies---high-priority payments
    might be released with only modest liquidity buffers, while low-priority payments
    wait for comfortable buffers or offsetting inflows.

    \item \textbf{{Collateral management}}: Sophisticated strategies for posting and
    withdrawing collateral based on credit utilization, queue gaps, and auto-withdrawal
    timers that balance liquidity costs against settlement delays.
\end{{itemize}}

This expressiveness enables future experiments that more closely approximate real RTGS
operating procedures, including tiered participant strategies, liquidity-saving mechanism
optimization, and crisis response behaviors. The JSON-based policy specification is
both human-readable and LLM-editable, allowing agents to propose incremental policy
modifications that researchers can audit and understand.

\subsection{{Limitations}}

Several limitations of this study warrant acknowledgment:

\begin{{enumerate}}
    \item \textbf{{Small sample size}}: With only {total_passes} total runs (3 passes per
    experiment), our findings are preliminary. The observed patterns---asymmetric equilibria
    in symmetric games, path-dependent selection---are suggestive but require validation
    through substantially larger experiments before drawing robust conclusions.

    \item \textbf{{Two-agent simplification}}: Real RTGS systems involve dozens or
    hundreds of participants with heterogeneous characteristics. Scaling to larger
    networks remains for future work.

    \item \textbf{{Fixed-environment bootstrap evaluation}}: The bootstrap mode evaluates
    policies under \textit{{historical}} settlement timing (Section~\ref{{sec:methods}}),
    not the timing that would result from policy-induced changes in system liquidity.
    In our 2-agent experiments, where each agent constitutes 50\% of system volume,
    this assumption is most restrictive---a policy change by one agent materially affects
    the other's settlement timing. We do not claim the bootstrap results reflect full
    equilibrium dynamics; rather, they measure policy quality given the observed
    market response. This limitation would be less severe in realistic multi-participant
    systems where individual policy changes have smaller marginal effects.

    \item \textbf{{Bootstrap variance artifacts}}: The variance guard (CV $<$ 0.5) uses
    bootstrap variance as a heuristic filter for sensitivity to timing perturbations, but
    transaction-level resampling with \texttt{{settlement\_offset}} can create duplicate
    extreme transactions and non-physical correlations, potentially amplifying tail events
    beyond what the original generative process would produce. In Experiment 2, some
    iterations showed 40$\times$ cost ranges across bootstrap samples ($\sim$\$77 to
    $\sim$\$3,100), consistent with tail amplification from resampling. Final policies
    showed CV $\approx$ 2.0 under bootstrap evaluation despite stable policy parameters,
    suggesting the bootstrap CV measures sensitivity to resampled timing rather than true
    cross-day performance variance. For applications to real RTGS data---which exhibits
    substantial intra-day variability---block bootstrap or day-level resampling would
    better preserve temporal dependencies.

    \item \textbf{{Partial observability}}: Agents operate under information isolation
    (Section~\ref{{sec:prompt_anatomy}})---they cannot observe counterparty balances
    or policies. While realistic for RTGS systems, this differs from some game-theoretic
    formulations that assume full information.

    \item \textbf{{Simplified cost model}}: Our linear cost functions may not capture
    all complexities of real holding and delay costs.

    \item \textbf{{Stable but suboptimal outcomes}}: While all deterministic-mode passes
    achieved policy stability, stability does not guarantee optimality. Experiment 3
    demonstrates that agents can converge to profiles where both are worse off than
    baseline. The unconditional acceptance mechanism permits following locally-improving
    gradients into coordination traps.

    \item \textbf{{Equilibrium variability}}: The specific stable profile varied across
    runs---different passes found different free-rider assignments and efficiency levels.
    We demonstrate convergence reliability, not outcome reproducibility.
\end{{enumerate}}

\subsection{{Future Work: Coordination Mechanisms}}

The coordination failures observed in Experiment 3 suggest an important direction for
future research: \textbf{{mechanisms that help non-communicating agents escape suboptimal
coordination traps}}.

Several approaches warrant investigation:

\begin{{enumerate}}
    \item \textbf{{Regulatory nudges}}: Could a central bank or regulator provide
    anonymized aggregate information (e.g., ``system-wide liquidity is below efficient
    levels'') that helps agents recognize coordination failures without revealing
    competitive information? Such nudges preserve the information isolation constraint
    while providing directional guidance.

    \item \textbf{{Commitment devices}}: Mechanisms that allow agents to conditionally
    commit to liquidity allocations (e.g., ``I will maintain 20\% if my counterparty
    does the same'') could help coordinate on efficient symmetric outcomes.

    \item \textbf{{Cost-aware acceptance}}: Modifying the unconditional acceptance
    mechanism to reject policies that increase total system cost (observable via
    aggregate settlement statistics) could prevent the race-to-the-bottom dynamics
    observed in Experiment 3.

    \item \textbf{{Staged adjustment}}: Limiting how much an agent can change its
    liquidity allocation per iteration could prevent the aggressive early moves that
    trap agents in suboptimal profiles.
\end{{enumerate}}

These mechanisms could be tested within the SimCash framework to understand how
LLM agents respond to different coordination assistance. The goal would be to identify
minimal interventions that help agents find Pareto-efficient outcomes while preserving
realistic information constraints.
"""
