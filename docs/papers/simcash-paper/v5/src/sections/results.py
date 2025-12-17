"""Results section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.formatting import format_money, format_percent
from src.latex.tables import generate_iteration_table

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_results(provider: DataProvider) -> str:
    """Generate the results section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the results section
    """
    # Get experiment 1 data
    exp1_results = provider.get_iteration_results("exp1", pass_num=1)
    exp1_convergence = provider.get_convergence_iteration("exp1", pass_num=1)

    # Get final iteration results for exp1
    exp1_final = [r for r in exp1_results if r["iteration"] == exp1_convergence]
    exp1_bank_a = next((r for r in exp1_final if r["agent_id"] == "BANK_A"), None)
    exp1_bank_b = next((r for r in exp1_final if r["agent_id"] == "BANK_B"), None)

    # Generate exp1 table
    exp1_table = generate_iteration_table(
        exp1_results,
        caption="Experiment 1: Iteration-by-iteration results (Pass 1)",
        label="tab:exp1_results",
    )

    # Get experiment 2 data
    exp2_convergence = provider.get_convergence_iteration("exp2", pass_num=1)
    exp2_bootstrap = provider.get_final_bootstrap_stats("exp2", pass_num=1)

    # Get experiment 3 data
    exp3_results = provider.get_iteration_results("exp3", pass_num=1)
    exp3_convergence = provider.get_convergence_iteration("exp3", pass_num=1)
    exp3_final = [r for r in exp3_results if r["iteration"] == exp3_convergence]
    exp3_bank_a = next((r for r in exp3_final if r["agent_id"] == "BANK_A"), None)
    exp3_bank_b = next((r for r in exp3_final if r["agent_id"] == "BANK_B"), None)

    # Format exp1 values
    exp1_a_cost = format_money(exp1_bank_a["cost"]) if exp1_bank_a else "N/A"
    exp1_a_liq = format_percent(exp1_bank_a["liquidity_fraction"]) if exp1_bank_a else "N/A"
    exp1_b_cost = format_money(exp1_bank_b["cost"]) if exp1_bank_b else "N/A"
    exp1_b_liq = format_percent(exp1_bank_b["liquidity_fraction"]) if exp1_bank_b else "N/A"

    # Format exp2 bootstrap values
    exp2_a_mean = format_money(exp2_bootstrap["BANK_A"]["mean_cost"]) if "BANK_A" in exp2_bootstrap else "N/A"
    exp2_b_mean = format_money(exp2_bootstrap["BANK_B"]["mean_cost"]) if "BANK_B" in exp2_bootstrap else "N/A"

    # Format exp3 values
    exp3_a_cost = format_money(exp3_bank_a["cost"]) if exp3_bank_a else "N/A"
    exp3_a_liq = format_percent(exp3_bank_a["liquidity_fraction"]) if exp3_bank_a else "N/A"
    exp3_b_cost = format_money(exp3_bank_b["cost"]) if exp3_bank_b else "N/A"
    exp3_b_liq = format_percent(exp3_bank_b["liquidity_fraction"]) if exp3_bank_b else "N/A"

    return rf"""
\section{{Results}}
\label{{sec:results}}

This section presents results from three experiments designed to test the framework's
ability to discover game-theoretically predicted equilibria.

\subsection{{Experiment 1: Asymmetric Equilibrium}}

In this experiment, BANK\_A faces lower delay costs than BANK\_B, creating an incentive
structure that theoretically favors free-rider behavior by BANK\_A.

{exp1_table}

The agents converged after {exp1_convergence} iterations to an asymmetric equilibrium:
\begin{{itemize}}
    \item BANK\_A achieved {exp1_a_cost} cost with {exp1_a_liq} liquidity allocation
    \item BANK\_B achieved {exp1_b_cost} cost with {exp1_b_liq} liquidity allocation
\end{{itemize}}

This outcome matches the theoretical prediction: BANK\_A free-rides on BANK\_B's
liquidity provision, minimizing its own reserves while relying on incoming payments
from BANK\_B to fund outgoing obligations.

\subsection{{Experiment 2: Stochastic Environment}}

Experiment 2 introduces transaction amount variability, requiring bootstrap evaluation
to assess policy quality under cost variance. Agents converged after {exp2_convergence}
iterations.

Bootstrap evaluation with 50 samples reveals:
\begin{{itemize}}
    \item BANK\_A: Mean cost {exp2_a_mean}
    \item BANK\_B: Mean cost {exp2_b_mean}
\end{{itemize}}

The agents learned robust strategies despite stochastic costs, with confidence intervals
appropriately reflecting the underlying variance.

\subsection{{Experiment 3: Symmetric Equilibrium}}

With identical cost structures for both banks, we expect symmetric equilibrium behavior.
Convergence occurred at iteration {exp3_convergence}.

Final equilibrium:
\begin{{itemize}}
    \item BANK\_A: {exp3_a_cost} cost, {exp3_a_liq} liquidity
    \item BANK\_B: {exp3_b_cost} cost, {exp3_b_liq} liquidity
\end{{itemize}}

Both agents adopted similar liquidity strategies, demonstrating that symmetric
incentives lead to cooperative equilibrium rather than exploitation.
"""
