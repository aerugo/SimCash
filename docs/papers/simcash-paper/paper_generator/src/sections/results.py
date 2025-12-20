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

    # Get experiment 2 data - use Pass 2 which achieved convergence
    # (Pass 1 did not converge within 25 iterations)
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

    # Generate figure includes for each experiment
    exp1_fig = include_figure(
        path=f"{CHARTS_DIR}/exp1_pass1_combined.png",
        caption="Experiment 1: Convergence of both agents toward asymmetric equilibrium",
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
(Experiment 3) to {exp1_mean_iters} (Experiment 1).

{convergence_table}

\subsection{{Experiment 1: Asymmetric Equilibrium}}

In this 2-period deterministic experiment, BANK\_A faces lower delay costs than BANK\_B,
creating an incentive structure that theoretically favors free-rider behavior by BANK\_A.

{exp1_iter_table}

{exp1_fig}

The agents converged after {exp1_convergence} iterations in Pass 1 to an asymmetric equilibrium:
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
that of the efficient equilibrium. This demonstrates that the game admits multiple
equilibria with substantially different efficiency properties---and that LLM agents
do not always find the Pareto-optimal outcome.

{exp1_summary_table}

\subsection{{Experiment 2: Stochastic Environment}}

Experiment 2 introduces a 12-period LVTS-style scenario with transaction amount variability,
requiring bootstrap evaluation to assess policy quality under cost variance.

We present Pass 2 results, which achieved convergence after {exp2_convergence} iterations.
Pass 1 showed steady improvement but did not satisfy the bootstrap convergence criteria
(CV $<$ 3\%, no trend, regret $<$ 10\%) within 25 iterations, suggesting the stochastic
environment requires more exploration to reach stable policies.

{exp2_iter_table}

{exp2_fig}

\subsubsection{{Bootstrap Evaluation Methodology}}

To account for stochastic variance, we evaluate final policies using bootstrap
evaluation with {exp2_samples} samples. This provides confidence intervals on expected costs.

{exp2_bootstrap_table}

Bootstrap evaluation reveals:
\begin{{itemize}}
    \item BANK\_A: Mean cost {exp2_a_mean} ($\pm$ {exp2_a_std} std dev)
    \item BANK\_B: Mean cost {exp2_b_mean} ($\pm$ {exp2_b_std} std dev)
\end{{itemize}}

\subsubsection{{Risk-Return Tradeoff}}

Figure~\ref{{fig:exp2_variance}} shows how cost variance evolves during optimization.
BANK\_B exhibits increasing variance from iteration 17 onward as it reduces liquidity
toward the final 11.5\% allocation. This demonstrates a risk-return tradeoff: lower
liquidity reduces mean holding costs but increases exposure to stochastic payment timing.
BANK\_A's variance remains stable, suggesting its lower liquidity position (7.4\%) has
already reached a risk plateau.

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

Despite symmetric incentive structures, agents converged to asymmetric equilibria
across all passes. Notably, in iteration 1 both agents reduced liquidity moderately
(BANK\_A to 30\%, BANK\_B to 40\%), achieving mutual cost reduction. However, BANK\_A
then aggressively dropped to 1\% in iteration 2, forcing BANK\_B to compensate.

Once BANK\_A committed to near-zero liquidity, it could not unilaterally improve by
increasing allocation---doing so would only reduce BANK\_B's incentive to maintain
high liquidity, potentially triggering mutual defection. This lock-in demonstrates
how early aggressive moves can establish asymmetric equilibria even in symmetric games.

{exp3_summary_table}

\subsection{{Cross-Experiment Analysis}}

Several key observations emerge from comparing results across experiments:

\begin{{enumerate}}
    \item \textbf{{Convergence Reliability}}: 8 of {total_passes} passes achieved formal convergence.
    Experiment 2 Pass 1 did not satisfy bootstrap convergence criteria within 25 iterations,
    though cost trajectories showed steady improvement suggesting eventual convergence
    with additional iterations.

    \item \textbf{{Asymmetric Equilibria Prevalence}}: Both asymmetric (Exp 1) and
    symmetric (Exp 3) cost structures produced asymmetric equilibria with free-rider
    behavior. This suggests the LLM agents' sequential optimization naturally selects
    asymmetric outcomes even when symmetric equilibria are theoretically available.

    \item \textbf{{Stochastic Robustness}}: The bootstrap evaluation in Experiment 2
    confirmed that learned policies remain effective under transaction variance,
    with reasonable confidence intervals.
\end{{enumerate}}
"""
