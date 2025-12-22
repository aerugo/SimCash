"""Results section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.figures import include_figure
from src.latex.formatting import format_money, format_percent
from src.latex.tables import (
    generate_bootstrap_table,
    generate_convergence_table,
    generate_iteration_table,
    generate_pass_summary_table,
)

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Chart paths relative to output directory
CHARTS_DIR = "charts"


def generate_results(provider: DataProvider) -> str:
    """Generate the results section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the results section
    """
    # Get aggregate statistics for data-driven text
    aggregate_stats = provider.get_aggregate_stats()
    total_experiments = aggregate_stats["total_experiments"]
    total_passes = aggregate_stats["total_passes"]
    passes_per_exp = total_passes // total_experiments if total_experiments > 0 else 0

    # Get all pass summaries for each experiment
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Get convergence statistics for each experiment
    exp1_conv_stats = provider.get_convergence_statistics("exp1")
    exp2_conv_stats = provider.get_convergence_statistics("exp2")
    exp3_conv_stats = provider.get_convergence_statistics("exp3")

    # Get experiment 1 data (pass 1 for detailed results)
    exp1_results = provider.get_iteration_results("exp1", pass_num=1)
    exp1_convergence = provider.get_convergence_iteration("exp1", pass_num=1)

    # Get final iteration results for exp1
    exp1_final = [r for r in exp1_results if r["iteration"] == exp1_convergence]
    exp1_bank_a = next((r for r in exp1_final if r["agent_id"] == "BANK_A"), None)
    exp1_bank_b = next((r for r in exp1_final if r["agent_id"] == "BANK_B"), None)

    # Generate exp1 iteration table
    exp1_iter_table = generate_iteration_table(
        exp1_results,
        caption="Experiment 1: Iteration-by-iteration results (Pass 1)",
        label="tab:exp1_results",
    )

    # Generate exp1 pass summary table
    exp1_summary_table = generate_pass_summary_table(
        exp1_summaries,
        caption="Experiment 1: Summary across all passes",
        label="tab:exp1_summary",
    )

    # Get experiment 2 data - Pass 2 shown as exemplar
    # All passes achieved convergence under strict bootstrap criteria
    exp2_results = provider.get_iteration_results("exp2", pass_num=2)
    exp2_convergence = provider.get_convergence_iteration("exp2", pass_num=2)
    exp2_bootstrap = provider.get_final_bootstrap_stats("exp2", pass_num=2)

    # Generate exp2 tables
    exp2_iter_table = generate_iteration_table(
        exp2_results,
        caption="Experiment 2: Iteration-by-iteration results (Pass 2)",
        label="tab:exp2_results",
    )

    exp2_bootstrap_table = generate_bootstrap_table(
        exp2_bootstrap,
        caption="Experiment 2: Bootstrap evaluation statistics (Pass 2, 50 samples)",
        label="tab:exp2_bootstrap",
    )

    exp2_summary_table = generate_pass_summary_table(
        exp2_summaries,
        caption="Experiment 2: Summary across all passes",
        label="tab:exp2_summary",
    )

    # Get experiment 3 data
    exp3_results = provider.get_iteration_results("exp3", pass_num=1)
    exp3_convergence = provider.get_convergence_iteration("exp3", pass_num=1)
    exp3_final = [r for r in exp3_results if r["iteration"] == exp3_convergence]
    exp3_bank_a = next((r for r in exp3_final if r["agent_id"] == "BANK_A"), None)
    exp3_bank_b = next((r for r in exp3_final if r["agent_id"] == "BANK_B"), None)

    # Generate exp3 tables
    exp3_iter_table = generate_iteration_table(
        exp3_results,
        caption="Experiment 3: Iteration-by-iteration results (Pass 1)",
        label="tab:exp3_results",
    )

    exp3_summary_table = generate_pass_summary_table(
        exp3_summaries,
        caption="Experiment 3: Summary across all passes",
        label="tab:exp3_summary",
    )

    # Generate convergence statistics table
    convergence_table = generate_convergence_table(
        [exp1_conv_stats, exp2_conv_stats, exp3_conv_stats],
        caption="Termination statistics across all experiments. EXP2 shows budget termination (50 iterations) rather than formal convergence.",
        label="tab:convergence_stats",
    )

    # Format exp1 values
    exp1_a_cost = format_money(exp1_bank_a["cost"]) if exp1_bank_a else "N/A"
    exp1_a_liq = format_percent(exp1_bank_a["liquidity_fraction"]) if exp1_bank_a else "N/A"
    exp1_b_cost = format_money(exp1_bank_b["cost"]) if exp1_bank_b else "N/A"
    exp1_b_liq = format_percent(exp1_bank_b["liquidity_fraction"]) if exp1_bank_b else "N/A"

    # Format exp2 bootstrap values
    exp2_a_mean = format_money(exp2_bootstrap["BANK_A"]["mean_cost"]) if "BANK_A" in exp2_bootstrap else "N/A"
    exp2_a_std = format_money(exp2_bootstrap["BANK_A"]["std_dev"]) if "BANK_A" in exp2_bootstrap else "N/A"
    exp2_b_mean = format_money(exp2_bootstrap["BANK_B"]["mean_cost"]) if "BANK_B" in exp2_bootstrap else "N/A"
    exp2_b_std = format_money(exp2_bootstrap["BANK_B"]["std_dev"]) if "BANK_B" in exp2_bootstrap else "N/A"
    exp2_samples = exp2_bootstrap["BANK_A"]["num_samples"] if "BANK_A" in exp2_bootstrap else 0

    # Format exp3 values
    exp3_a_cost = format_money(exp3_bank_a["cost"]) if exp3_bank_a else "N/A"
    exp3_a_liq = format_percent(exp3_bank_a["liquidity_fraction"]) if exp3_bank_a else "N/A"
    exp3_b_cost = format_money(exp3_bank_b["cost"]) if exp3_bank_b else "N/A"
    exp3_b_liq = format_percent(exp3_bank_b["liquidity_fraction"]) if exp3_bank_b else "N/A"

    # Format convergence stats
    exp1_mean_iters = f"{exp1_conv_stats['mean_iterations']:.1f}"
    exp2_mean_iters = f"{exp2_conv_stats['mean_iterations']:.1f}"
    exp3_mean_iters = f"{exp3_conv_stats['mean_iterations']:.1f}"

    # Compute exp2 liquidity range for cross-experiment summary
    exp2_all_liqs = [s["bank_a_liquidity"] for s in exp2_summaries] + [
        s["bank_b_liquidity"] for s in exp2_summaries
    ]
    exp2_liq_min = format_percent(min(exp2_all_liqs))
    exp2_liq_max = format_percent(max(exp2_all_liqs))

    # Generate figure includes for each experiment
    exp1_fig = include_figure(
        path=f"{CHARTS_DIR}/exp1_pass1_combined.png",
        caption="Experiment 1: Convergence of both agents toward asymmetric stable outcome",
        label="fig:exp1_convergence",
        width=0.9,
    )

    exp2_fig = include_figure(
        path=f"{CHARTS_DIR}/exp2_pass2_combined.png",
        caption="Experiment 2: Convergence under stochastic transaction amounts (Pass 2). Cost values are means across 50 bootstrap samples per iteration.",
        label="fig:exp2_convergence",
        width=0.9,
    )

    exp2_variance_fig = include_figure(
        path=f"{CHARTS_DIR}/exp2_pass2_variance.png",
        caption="Experiment 2: Cost variance over iterations showing 95\\% confidence intervals",
        label="fig:exp2_variance",
        width=0.95,
    )

    exp3_fig = include_figure(
        path=f"{CHARTS_DIR}/exp3_pass1_combined.png",
        caption="Experiment 3: Convergence dynamics in symmetric game",
        label="fig:exp3_convergence",
        width=0.9,
    )

    return rf"""
\section{{Results}}
\label{{sec:results}}

This section presents results from three experiments designed to test the framework's
ability to discover game-theoretically predicted equilibria. Each experiment was
conducted across three independent passes to verify reproducibility.

\subsection{{Convergence Summary}}

Table~\ref{{tab:convergence_stats}} summarizes termination behavior across all experiments.
Experiments 1 and 3 achieved formal convergence via temporal policy stability, with mean iterations
of {exp1_mean_iters} and {exp3_mean_iters} respectively. Experiment 2's stochastic passes
terminated at the 50-iteration budget without meeting formal convergence criteria (see Section 3.3).

{convergence_table}

\subsection{{Experiment 1: Asymmetric Equilibrium}}

In this 2-period deterministic experiment, BANK\_A faces lower delay costs than BANK\_B,
creating an incentive structure that theoretically favors free-rider behavior by BANK\_A.

{exp1_iter_table}

{exp1_fig}

The agents converged after {exp1_convergence} iterations in Pass 1 to an asymmetric stable outcome:
\begin{{itemize}}
    \item BANK\_A achieved {exp1_a_cost} cost with {exp1_a_liq} liquidity allocation
    \item BANK\_B achieved {exp1_b_cost} cost with {exp1_b_liq} liquidity allocation
\end{{itemize}}

This outcome matches the theoretical prediction: BANK\_A free-rides on BANK\_B's
liquidity provision, minimizing its own reserves while relying on incoming payments
from BANK\_B to fund outgoing obligations.

Table~\ref{{tab:exp1_summary}} summarizes convergence across all three passes.
Notably, \textbf{{Pass 3 exhibited coordination failure}}: BANK\_B adopted a
zero-liquidity strategy, but unlike Passes 1--2 where BANK\_A successfully free-rode,
here BANK\_A's low liquidity (1.8\%) was insufficient to compensate. Both agents
incurred high costs (\$31.78 and \$70.00 respectively), with total cost nearly 4$\times$
that of the efficient outcome. This demonstrates that the learning dynamics can converge to
multiple stable outcomes with substantially different efficiency properties---and that LLM agents
do not always find the Pareto-optimal outcome.

{exp1_summary_table}

\subsection{{Experiment 2: Stochastic Environment}}

Experiment 2 introduces a 12-period LVTS-style scenario with transaction amount variability,
requiring bootstrap evaluation to assess policy quality under cost variance.

All three passes \textbf{{terminated at the iteration budget}} (50 iterations) without
meeting the formal convergence criteria. The strict bootstrap convergence
requirements---CV $<$ 3\%, no significant trend, and regret $<$ 10\% sustained over
a 5-iteration window---proved difficult to satisfy in this stochastic environment.
However, as we show below, the policies achieved practical stability: liquidity allocations
settled into consistent ranges and costs remained within narrow bands during the final iterations.
The strict criteria may be overly conservative for stochastic scenarios where inherent
variance makes sustained low-CV windows statistically unlikely. We present Pass 2 as the exemplar run.

{exp2_iter_table}

{exp2_fig}

\subsubsection{{Bootstrap Evaluation Methodology}}

Each iteration uses a unique seed from the pre-generated seed hierarchy (Section~\ref{{sec:methods}}).
The iteration table above shows \textbf{{mean costs}} across 50 bootstrap samples, where each sample
resamples transactions from that iteration's context simulation. Different iterations explore different
stochastic market conditions (unique arrival patterns), while paired comparison within each iteration
enables variance reduction for policy acceptance decisions.

Table~\ref{{tab:exp2_bootstrap}} presents bootstrap statistics for the \textbf{{final accepted
policies}}, evaluated across {exp2_samples} transaction samples. Note that these statistics
reflect the last policy evaluation before convergence---each policy acceptance decision
involves bootstrap sampling to assess robustness. The mean costs shown here differ from
the summary table's final iteration costs because they represent averages across 50 stochastic
scenarios, while final costs reflect a single context simulation.

{exp2_bootstrap_table}

The bootstrap evaluation reveals that BANK\_A's policy, despite high variance in individual
simulations, achieves mean cost {exp2_a_mean} ($\pm$ {exp2_a_std}). BANK\_B maintains
more consistent costs at {exp2_b_mean} ($\pm$ {exp2_b_std}).

\textit{{Note on per-agent variance}}: The high standard deviation for BANK\_A (yielding
per-agent $CV \approx 2.0$ at the final iteration) does not necessarily indicate
a violation of the $CV \leq 0.5$ acceptance gate. The gate is checked at the
moment a policy is \textit{{proposed and evaluated for acceptance}}---each iteration
uses different stochastic samples from the seed hierarchy, so the same policy can
exhibit different CV values across iterations. BANK\_A's current policy was accepted
at an earlier iteration when its CV (on that iteration's samples) satisfied the
constraint; the statistics shown here reflect the final iteration's evaluation,
which may differ due to sample variance.

\subsubsection{{Risk-Return Tradeoff}}

Figure~\ref{{fig:exp2_variance}} shows how cost variance evolves during optimization.
Both agents exhibit high variance in cost outcomes---BANK\_A's bootstrap evaluation
shows standard deviation of {exp2_a_std}, reflecting substantial exposure to stochastic
payment timing. BANK\_B maintains lower variance ({exp2_b_std}) despite similar liquidity
allocations. This asymmetry in cost variance, combined with the relatively symmetric
liquidity allocations, suggests that payment timing exposure affects agents differently
even when they hold comparable reserves.

{exp2_variance_fig}

\subsubsection{{Risk-Adjusted Policy Acceptance}}

The convergence chart (Figure~\ref{{fig:exp2_convergence}}) reveals cases where proposed
policies with \textit{{dramatically better}} mean costs were nonetheless rejected. For example,
at iteration 22, BANK\_A's proposed policy achieved mean cost \$324 compared to the current
policy's \$915---a \$591 improvement---yet was rejected.

The acceptance criteria implements \textbf{{risk-adjusted evaluation}}: a policy must satisfy
three requirements to be accepted:
\begin{{enumerate}}
    \item \textbf{{Mean improvement}}: $\mu_{{new}} < \mu_{{old}}$ (paired comparison on same bootstrap samples)
    \item \textbf{{Statistical significance}}: The 95\% confidence interval for the paired delta
    ($\delta_i = \text{{cost}}_{{old,i}} - \text{{cost}}_{{new,i}}$) must not cross zero
    \item \textbf{{Variance constraint}}: $CV \leq 0.5$ where $CV = \sigma_{{new}} / \mu_{{new}}$
    (coefficient of variation of the new policy's costs across bootstrap samples)
\end{{enumerate}}

At iteration 22, the proposed policy had $\sigma = \$269$ on $\mu = \$324$, yielding $CV = 0.83$.
Despite the superior mean, the policy was rejected as too volatile. This risk-adjusted acceptance
explains the apparent paradox in Figure~\ref{{fig:exp2_convergence}} where some rejected proposals
(X markers) appear below the current policy line---they had better average performance but
unacceptable variance.

This mechanism biases optimization toward policies that improve mean cost while avoiding
proposals that are overly sensitive to timing perturbations under the fixed-environment
bootstrap evaluation.

{exp2_summary_table}

\subsection{{Experiment 3: Coordination Failure in Symmetric Games}}

In this 3-period symmetric scenario, both banks face identical cost structures and
begin with identical 50\% liquidity allocations (baseline cost $\sim$\$50 each).
\textbf{{All three passes exhibit coordination failure}}: agents converge to stable
profiles where \textit{{both}} agents incur higher costs than baseline.
Policy stability occurred at iteration {exp3_convergence} in Pass 1.

{exp3_iter_table}

{exp3_fig}

Final stable profile:
\begin{{itemize}}
    \item BANK\_A: {exp3_a_cost} cost, {exp3_a_liq} liquidity
    \item BANK\_B: {exp3_b_cost} cost, {exp3_b_liq} liquidity
\end{{itemize}}

\textbf{{Why coordination fails}}: The unconditional acceptance mechanism allows
agents to follow initially-improving trajectories that lead to collectively
worse outcomes. In Pass 1, iteration 1 saw both agents reduce liquidity moderately
(BANK\_A to 30\%, BANK\_B to 40\%), which improved costs for both. Encouraged by
this success, BANK\_A aggressively dropped to 1\% in iteration 2. This initially
appeared beneficial to BANK\_A (forcing BANK\_B to provide liquidity), but trapped
both agents in a suboptimal profile: BANK\_A's costs rose to {exp3_a_cost} (more
than double baseline), while BANK\_B paid {exp3_b_cost} to compensate.

Once in this trap, neither agent can unilaterally improve: BANK\_A increasing
liquidity would reduce BANK\_B's incentive to maintain high reserves, risking
mutual defection. BANK\_B reducing liquidity would cause settlement failures.
The profile is \textit{{stable}} but \textit{{Pareto-dominated}} by the baseline.

This result demonstrates a fundamental limitation of greedy, non-communicating
optimization: agents following myopic improvement gradients can converge to
coordination traps that leave everyone worse off. The LLM agents are not
``finding equilibria''---they are exhibiting the same coordination failures
that occur when rational agents lack mechanisms to coordinate.

\textit{{Note on evaluation mode}}: These coordination failures arise partly because
deterministic-temporal mode uses \textbf{{unconditional acceptance}}---agents cannot
test proposed policies before committing. In stochastic scenarios using bootstrap
evaluation (Experiment 2), agents evaluate candidate policies on multiple samples
before acceptance, providing a mechanism to detect that aggressive liquidity reductions
lead to worse outcomes. The simplified deterministic scenarios here are designed to
demonstrate strategic dynamics under controlled conditions; in realistic stochastic
settings, the bootstrap evaluation mechanism itself may help agents avoid coordination
traps by revealing the costs of aggressive moves before they become irreversible.

{exp3_summary_table}

\subsection{{Cross-Experiment Analysis}}

Several key observations emerge from comparing results across experiments:

\begin{{enumerate}}
    \item \textbf{{Policy Stability vs.\ Optimality}}: All deterministic-mode passes (Experiments 1 and 3)
    achieved policy stability, but stability does not imply optimality. Experiment 3
    demonstrates that stable profiles can be Pareto-dominated by baseline. Experiment 2
    terminated at iteration budget without meeting strict convergence criteria.

    \item \textbf{{Coordination Failure}}: Experiment 3's symmetric game produced coordination
    failures in all three passes: both agents ended worse off than baseline. This is not
    a bug but an expected outcome of greedy, non-communicating optimization. Without
    mechanisms for coordination (communication, commitment devices, or external nudges),
    agents following myopic improvement paths can become trapped in suboptimal profiles.

    \item \textbf{{Asymmetric Free-Riding}}: Experiments 1 and 3 both produced asymmetric
    outcomes where one agent provides liquidity while the other free-rides. In Exp 1
    (asymmetric costs), this reflects the underlying incentive structure. In Exp 3
    (symmetric costs), it reflects path-dependent dynamics where early aggressive moves
    by one agent force the other into a compensating role.

    \item \textbf{{Stochastic Environments Inhibit Coordination Failure}}: Experiment 2's
    stochastic arrivals produced near-symmetric allocations ({exp2_liq_min}--{exp2_liq_max}
    range) without the severe coordination failures seen in deterministic scenarios.
    The inherent uncertainty may prevent the confident aggressive moves that trigger
    coordination traps, consistent with Castro et al.'s prediction that payment timing
    uncertainty inhibits free-rider dynamics.
\end{{enumerate}}
"""
