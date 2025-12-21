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

    return rf"""
\section{{Discussion}}
\label{{sec:discussion}}

Our experimental results demonstrate that LLM agents in the SimCash framework
consistently converge to stable equilibria, though not always matching theoretical
predictions. All {total_passes} experiment passes achieved convergence,
validating the framework's robustness.

\subsection{{Theoretical Alignment and Deviations}}

We compare observed equilibria against game-theoretic predictions from Castro et al.\ (2025):

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
    demonstrating that the game admits \textbf{{multiple asymmetric equilibria}} with
    different efficiency properties.
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
    \item Final liquidity allocations ranged from {format_percent(exp2_mean_a_liq)} (BANK\_A mean)
    to {format_percent(exp2_mean_b_liq)} (BANK\_B mean). BANK\_A's allocation falls \textit{{below}}
    the expected 10--30\% range, suggesting possible free-riding even under stochastic conditions.

    \item Unlike Experiments 1 and 3, equilibrium \textbf{{efficiency was remarkably consistent}}:
    total costs ranged from {format_money(exp2_best_total)} to {format_money(exp2_worst_total)}---only
    $\sim$1\% variance compared to 2--4$\times$ variation in deterministic scenarios.

    \item The bootstrap convergence criterion (CV $<$ 3\%, no trend, regret $<$ 10\%)
    identified stable policies that, despite different liquidity allocations, achieved similar
    total costs.
\end{{itemize}}

\subsubsection{{Experiment 3: Symmetric Cost Structure}}

Theory predicts a \textbf{{symmetric equilibrium}} where both agents allocate similar
liquidity fractions ($\sim$20\% each), as neither has a structural advantage.

Our results show a \textbf{{systematic deviation}} from this prediction:
\begin{{itemize}}
    \item \textbf{{Passes 1--2}}: Despite symmetric costs, BANK\_A converged to low liquidity
    (1--5\%) while BANK\_B maintained high liquidity (29--30\%). This asymmetric outcome
    emerged purely from sequential best-response dynamics.

    \item \textbf{{Pass 3}}: Roles flipped---BANK\_B became the free-rider (0.9\%) while
    BANK\_A maintained 10\%. Total cost was {format_money(exp3_worst_total)}, more than
    double the efficient equilibrium ({format_money(exp3_best_total)}).

    \item BANK\_A assumed the free-rider role in {exp3_freerider_a_count} of 3 passes.
\end{{itemize}}

This finding suggests that \textbf{{symmetric games can support asymmetric equilibria}}
when agents optimize sequentially. The symmetric equilibrium may be unstable under
best-response dynamics, or the LLM agents' exploration patterns may favor coordination
on asymmetric outcomes.

\subsubsection{{Summary of Theoretical Alignment}}

\begin{{center}}
\begin{{tabular}}{{lccc}}
\hline
Experiment & Predicted & Observed & Alignment \\
\hline
Exp 1 (Asymmetric) & Asymmetric & Asymmetric (role varies) & Partial \\
Exp 2 (Stochastic) & Moderate (10--30\%) & 6--20\% & Good \\
Exp 3 (Symmetric) & Symmetric & Asymmetric & Deviation \\
\hline
\end{{tabular}}
\end{{center}}

The key insight is that while agents consistently find \textit{{stable}} equilibria,
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

    \item \textbf{{Few-shot adaptation}}: Agents adjust policies in 7--29 iterations
    rather than requiring thousands of training episodes, enabling rapid exploration
    of scenario variations.
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

    \item \textbf{{Partial observability}}: Agents operate under information isolation
    (Section~\ref{{sec:prompt_anatomy}})---they cannot observe counterparty balances
    or policies. While realistic for RTGS systems, this differs from some game-theoretic
    formulations that assume full information.

    \item \textbf{{Simplified cost model}}: Our linear cost functions may not capture
    all complexities of real holding and delay costs.

    \item \textbf{{Equilibrium variability}}: While all passes converged to \textit{{some}}
    stable equilibrium, the specific equilibrium varied across runs---different passes
    found different free-rider assignments and efficiency levels. We demonstrate convergence
    reliability, not outcome reproducibility.
\end{{enumerate}}
"""
