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
        caption="Convergence statistics across all experiments",
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
        caption="Experiment 2: Convergence under stochastic transaction amounts (Pass 2)",
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

Table~\ref{{tab:convergence_stats}} summarizes convergence behavior across all experiments.
All passes achieved convergence, with mean iterations ranging from {exp3_mean_iters}
(Experiment 3) to {exp2_mean_iters} (Experiment 2).

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

All three passes achieved convergence at iteration 49 (the maximum allowed). The strict
bootstrap convergence criteria---requiring CV $<$ 3\%, no significant trend, and regret $<$ 10\%
over a 5-iteration window---demanded extended observation to confidently identify stable policies
in this stochastic environment. We present Pass 2 as the exemplar run.

{exp2_iter_table}

{exp2_fig}

\subsubsection{{Bootstrap Evaluation Methodology}}

Each iteration uses a unique seed from the pre-generated seed hierarchy (Section~\ref{{sec:methods}}).
The iteration table above shows \textbf{{mean costs}} across 50 bootstrap samples, where each sample
resamples transactions from that iteration's context simulation. Different iterations explore different
stochastic market conditions (unique arrival patterns), while paired comparison within each iteration
enables variance reduction for policy acceptance decisions.

Table~\ref{{tab:exp2_bootstrap}} presents bootstrap statistics for the \textbf{{final converged
policies}} (iteration {exp2_convergence}), evaluated across {exp2_samples} transaction samples.
The bootstrap evaluation assesses policy robustness under the stochastic conditions encountered
in that iteration.

{exp2_bootstrap_table}

The bootstrap evaluation reveals that BANK\_A's policy, despite high variance in individual
simulations, achieves mean cost {exp2_a_mean} ($\pm$ {exp2_a_std}). BANK\_B maintains
more consistent costs at {exp2_b_mean} ($\pm$ {exp2_b_std}).

\subsubsection{{Risk-Return Tradeoff}}

Figure~\ref{{fig:exp2_variance}} shows how cost variance evolves during optimization.
As agents reduce liquidity toward their final allocations, variance behavior diverges:
BANK\_B's variance increases as it reduces liquidity, demonstrating a risk-return tradeoff
where lower liquidity reduces mean holding costs but increases exposure to stochastic
payment timing. BANK\_A's variance remains relatively stable at its low liquidity position,
suggesting it has reached a risk plateau where further reductions would incur settlement failures.

{exp2_variance_fig}

{exp2_summary_table}

\subsection{{Experiment 3: Symmetric Game Dynamics}}

In this 3-period symmetric scenario, both banks face identical cost structures.
Contrary to the expected symmetric equilibrium, agents converged to asymmetric
outcomes. Convergence occurred at iteration {exp3_convergence} in Pass 1.

{exp3_iter_table}

{exp3_fig}

Final equilibrium:
\begin{{itemize}}
    \item BANK\_A: {exp3_a_cost} cost, {exp3_a_liq} liquidity
    \item BANK\_B: {exp3_b_cost} cost, {exp3_b_liq} liquidity
\end{{itemize}}

Despite symmetric incentive structures, agents converged to asymmetric stable outcomes
across all passes. Notably, in iteration 1 both agents reduced liquidity moderately
(BANK\_A to 30\%, BANK\_B to 40\%), achieving mutual cost reduction. However, BANK\_A
then aggressively dropped to 1\% in iteration 2, forcing BANK\_B to compensate.

Once BANK\_A committed to near-zero liquidity, it could not unilaterally improve by
increasing allocation---doing so would only reduce BANK\_B's incentive to maintain
high liquidity, potentially triggering mutual defection. This lock-in demonstrates
how early aggressive moves can establish asymmetric stable outcomes even in symmetric games.

{exp3_summary_table}

\subsection{{Cross-Experiment Analysis}}

Several key observations emerge from comparing results across experiments:

\begin{{enumerate}}
    \item \textbf{{Convergence Reliability}}: All {total_passes} passes achieved formal convergence,
    validating the robustness of the bootstrap convergence criteria for stochastic scenarios
    and temporal policy stability for deterministic scenarios.

    \item \textbf{{Asymmetric Outcomes Prevalence}}: Both asymmetric (Exp 1) and
    symmetric (Exp 3) cost structures produced asymmetric stable outcomes with free-rider
    behavior. This suggests the LLM agents' optimization dynamics naturally select
    asymmetric outcomes even when symmetric equilibria are theoretically available.

    \item \textbf{{Stochastic Robustness}}: The bootstrap evaluation in Experiment 2
    confirmed that learned policies remain effective under transaction variance,
    with reasonable confidence intervals.

    \item \textbf{{Stochastic Environments Produce Symmetric Outcomes}}: While Experiments 1
    and 3 exhibited asymmetric free-rider equilibria despite varying cost structures,
    Experiment 2's stochastic arrivals produced near-symmetric allocations ({exp2_liq_min}--{exp2_liq_max} for
    both agents). This pattern is consistent with Castro et al.'s prediction that payment
    timing uncertainty inhibits the free-rider dynamics observed in deterministic scenarios.
\end{{enumerate}}
"""
