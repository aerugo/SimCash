"""Results section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.template import var

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Chart paths relative to output directory
CHARTS_DIR = "charts"


def generate_results(provider: DataProvider | None = None) -> str:
    """Generate the results section template.

    Args:
        provider: DataProvider instance (unused, kept for API compatibility)

    Returns:
        LaTeX string with {{variable}} placeholders
    """
    return rf"""
\section{{Results}}
\label{{sec:results}}

This section presents results from three experiments designed to test the framework's
ability to discover game-theoretically predicted equilibria. Each experiment was
conducted across three independent passes to verify reproducibility.

\subsection{{Convergence Summary}}

Table~\ref{{tab:convergence_stats}} summarizes convergence behavior across all experiments.
All passes achieved convergence, with mean iterations ranging from {var('exp3_mean_iterations')}
(Experiment 3) to {var('exp1_mean_iterations')} (Experiment 1).

{var('convergence_table')}

\subsection{{Experiment 1: Asymmetric Equilibrium}}

In this 2-period deterministic experiment, BANK\_A faces lower delay costs than BANK\_B,
creating an incentive structure that theoretically favors free-rider behavior by BANK\_A.

{var('exp1_iteration_table')}

{var('exp1_figure')}

The agents converged after {var('exp1_pass1_iterations')} iterations in Pass 1 to an asymmetric equilibrium:
\begin{{itemize}}
    \item BANK\_A achieved \${var('exp1_pass1_bank_a_cost')} cost with {var('exp1_pass1_bank_a_liquidity_pct')}\% liquidity allocation
    \item BANK\_B achieved \${var('exp1_pass1_bank_b_cost')} cost with {var('exp1_pass1_bank_b_liquidity_pct')}\% liquidity allocation
\end{{itemize}}

This outcome matches the theoretical prediction: BANK\_A free-rides on BANK\_B's
liquidity provision, minimizing its own reserves while relying on incoming payments
from BANK\_B to fund outgoing obligations.

Table~\ref{{tab:exp1_summary}} shows consistent convergence across all three passes.

{var('exp1_summary_table')}

\subsection{{Experiment 2: Stochastic Environment}}

Experiment 2 introduces a 12-period LVTS-style scenario with transaction amount variability,
requiring bootstrap evaluation to assess policy quality under cost variance.
Agents converged after {var('exp2_pass1_iterations')} iterations in Pass 1.

{var('exp2_iteration_table')}

{var('exp2_figure')}

\subsubsection{{Bootstrap Evaluation Methodology}}

To account for stochastic variance, we evaluate final policies using bootstrap
evaluation with {var('exp2_bootstrap_samples')} samples. This provides confidence intervals on expected costs.

{var('exp2_bootstrap_table')}

Bootstrap evaluation reveals:
\begin{{itemize}}
    \item BANK\_A: Mean cost \${var('exp2_bootstrap_a_mean')} ($\pm$ \${var('exp2_bootstrap_a_std')} std dev)
    \item BANK\_B: Mean cost \${var('exp2_bootstrap_b_mean')} ($\pm$ \${var('exp2_bootstrap_b_std')} std dev)
\end{{itemize}}

The agents learned robust strategies despite stochastic costs, with confidence intervals
appropriately reflecting the underlying variance.

{var('exp2_summary_table')}

\subsection{{Experiment 3: Symmetric Equilibrium}}

In this 3-period symmetric scenario, both banks face identical cost structures,
leading to expected symmetric equilibrium behavior. Convergence occurred at
iteration {var('exp3_pass1_iterations')} in Pass 1.

{var('exp3_iteration_table')}

{var('exp3_figure')}

Final equilibrium:
\begin{{itemize}}
    \item BANK\_A: \${var('exp3_pass1_bank_a_cost')} cost, {var('exp3_pass1_bank_a_liquidity_pct')}\% liquidity
    \item BANK\_B: \${var('exp3_pass1_bank_b_cost')} cost, {var('exp3_pass1_bank_b_liquidity_pct')}\% liquidity
\end{{itemize}}

Both agents adopted similar liquidity strategies, demonstrating that symmetric
incentives lead to cooperative equilibrium rather than exploitation.

{var('exp3_summary_table')}

\subsection{{Cross-Experiment Analysis}}

Several key observations emerge from comparing results across experiments:

\begin{{enumerate}}
    \item \textbf{{Convergence Reliability}}: All {var('total_passes')} passes ({var('total_experiments')} experiments $\times$ {var('passes_per_experiment')} passes)
    achieved convergence to stable equilibria, demonstrating framework robustness.

    \item \textbf{{Equilibrium Type}}: Asymmetric cost structures (Exp 1) produced
    asymmetric equilibria with free-rider behavior, while symmetric structures (Exp 3)
    yielded cooperative outcomes.

    \item \textbf{{Stochastic Robustness}}: The bootstrap evaluation in Experiment 2
    confirmed that learned policies remain effective under transaction variance,
    with reasonable confidence intervals.
\end{{enumerate}}
"""
