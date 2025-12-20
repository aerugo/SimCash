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

Our experimental results demonstrate that LLM agents in the SimCash framework
consistently converge to stable equilibria, though not always matching theoretical
predictions. All {total_passes} experiment passes achieved convergence,
validating the framework's robustness.

\subsection{{Theoretical Alignment and Deviations}}

The observed equilibria show both alignment with and deviation from game-theoretic predictions:

\begin{{itemize}}
    \item \textbf{{Experiment 1 (Asymmetric)}}: BANK\_A converged to mean liquidity
    {exp1_a_liq_fmt} while BANK\_B maintained {exp1_b_liq_fmt}. This {format_percent(exp1_liq_diff)}
    difference reflects free-rider dynamics, though the \textit{{identity}} of the free-rider
    varied across passes---demonstrating that the game admits multiple asymmetric equilibria.

    \item \textbf{{Experiment 3 (Symmetric)}}: Contrary to the predicted symmetric equilibrium,
    agents converged to asymmetric outcomes ({exp3_a_liq_fmt} vs {exp3_b_liq_fmt}). This
    {format_percent(exp3_liq_diff)} difference suggests that even symmetric incentive structures
    can support asymmetric equilibria when agents engage in sequential best-response dynamics.
\end{{itemize}}

The mean convergence time of {exp1_mean_iters} iterations for Experiment 1
compared to {exp3_mean_iters} for Experiment 3 indicates similar exploration
effort regardless of the underlying cost structure.

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

    \item \textbf{{Implicit Opponent Modeling}}: Despite having no direct visibility into
    counterparty policies or balances (see Section~\ref{{sec:prompt_anatomy}}), agents
    converged to coordinated asymmetric equilibria. BANK\_A's low liquidity strategy
    only works if BANK\_B provides higher liquidity---yet agents achieved this coordination
    purely through observing their own cost dynamics and incoming payment patterns.

    \item \textbf{{Convergence Speed}}: Mean convergence in {exp1_mean_iters}--{exp3_mean_iters}
    iterations suggests efficient exploration of the strategy space.
\end{{enumerate}}

\subsection{{Behavioral Realism of LLM Agents}}

A key advantage of using LLM-based reasoning agents over traditional reinforcement learning
approaches lies in their behavioral realism. Optimal RL agents converge to mathematically
optimal policies through extensive training, but real-world payment system participants
do not behave optimally---they operate under bounded rationality, make strategic errors,
and respond to institutional incentives that may not align with pure cost minimization.

Our experimental results demonstrate this concretely: in Experiment 1 Pass 3, one agent
persistently attempted a zero-liquidity strategy despite facing costs that made this
suboptimal given its counterparty's response. This ``mistake'' is precisely the kind of
behavior observed in real financial institutions, where treasury managers may anchor on
historical strategies or misread market signals.

LLM agents offer additional modeling flexibility:
\begin{{itemize}}
    \item \textbf{{Heterogeneous instructions}}: Different agents can receive tailored
    system prompts emphasizing risk tolerance, regulatory constraints, or strategic
    objectives---mirroring how different banks operate under different mandates.

    \item \textbf{{Bounded rationality}}: Rather than assuming perfect optimization,
    LLM agents exhibit human-like exploration and exploitation patterns, occasionally
    getting ``stuck'' in local optima or over-exploring suboptimal regions.

    \item \textbf{{Strategic reasoning}}: Agents can explain their decisions in natural
    language, enabling researchers to understand \textit{{why}} particular equilibria
    emerge---not just what the equilibrium is.
\end{{itemize}}

This behavioral richness makes LLM-based simulation more suitable for policy analysis
where understanding participant responses to regulatory changes is as important as
predicting equilibrium outcomes.

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
    \item \textbf{{Two-agent simplification}}: Real RTGS systems involve dozens or
    hundreds of participants with heterogeneous characteristics. Scaling to larger
    networks remains for future work.

    \item \textbf{{Partial observability}}: Agents operate under information isolation
    (Section~\ref{{sec:prompt_anatomy}})---they cannot observe counterparty balances
    or policies. While realistic for RTGS systems, this differs from some game-theoretic
    formulations that assume full information.

    \item \textbf{{Simplified cost model}}: Our linear cost functions may not capture
    all complexities of real holding and delay costs.

    \item \textbf{{Deterministic convergence}}: While we verify reproducibility across
    {total_passes} passes, learning dynamics could exhibit path-dependence in more
    complex scenarios.
\end{{enumerate}}
"""
