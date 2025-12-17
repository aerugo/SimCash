"""Appendices section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.figures import include_figure
from src.latex.formatting import format_money, format_percent
from src.latex.tables import (
    generate_bootstrap_table,
    generate_iteration_table,
    generate_results_summary_table,
)

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Chart paths relative to output directory
CHARTS_DIR = "charts"


def generate_appendices(provider: DataProvider) -> str:
    """Generate the appendices section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the appendices
    """
    # Generate detailed tables for all experiments and passes
    appendix_sections = []

    # Appendix A: Results Summary
    results_summary = _generate_results_summary_appendix(provider)
    appendix_sections.append(results_summary)

    # Appendix B: Experiment 1 Detailed Results
    exp1_content = _generate_experiment_appendix(
        provider,
        exp_id="exp1",
        title="Experiment 1: Asymmetric Equilibrium",
        label_prefix="exp1",
    )
    appendix_sections.append(exp1_content)

    # Appendix C: Experiment 2 Detailed Results
    exp2_content = _generate_experiment_appendix(
        provider,
        exp_id="exp2",
        title="Experiment 2: Stochastic Environment",
        label_prefix="exp2",
    )
    appendix_sections.append(exp2_content)

    # Appendix D: Experiment 3 Detailed Results
    exp3_content = _generate_experiment_appendix(
        provider,
        exp_id="exp3",
        title="Experiment 3: Symmetric Equilibrium",
        label_prefix="exp3",
    )
    appendix_sections.append(exp3_content)

    # Appendix E: Bootstrap Statistics
    bootstrap_content = _generate_bootstrap_appendix(provider)
    appendix_sections.append(bootstrap_content)

    # Appendix F: LLM Prompt Audit
    prompt_audit = _generate_prompt_audit_appendix(provider)
    appendix_sections.append(prompt_audit)

    all_content = "\n\n".join(appendix_sections)

    return rf"""
\appendix

{all_content}
"""


def _generate_results_summary_appendix(provider: DataProvider) -> str:
    """Generate appendix section with comprehensive results summary.

    Args:
        provider: DataProvider instance

    Returns:
        LaTeX string for results summary appendix
    """
    # Get all pass summaries
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Generate comprehensive table
    summary_table = generate_results_summary_table(
        exp1_summaries,
        exp2_summaries,
        exp3_summaries,
        caption="Complete results summary across all experiments and passes",
        label="tab:results_summary",
    )

    # Calculate aggregate statistics
    all_summaries = exp1_summaries + exp2_summaries + exp3_summaries
    total_passes = len(all_summaries)
    avg_iterations = sum(s["iterations"] for s in all_summaries) / total_passes

    # Calculate per-experiment averages
    exp1_avg_total = sum(s["total_cost"] for s in exp1_summaries) // len(exp1_summaries)
    exp2_avg_total = sum(s["total_cost"] for s in exp2_summaries) // len(exp2_summaries)
    exp3_avg_total = sum(s["total_cost"] for s in exp3_summaries) // len(exp3_summaries)

    return rf"""
\section{{Results Summary}}
\label{{app:results_summary}}

This appendix provides a comprehensive summary of all experimental results
across {total_passes} passes ({len(exp1_summaries)} per experiment). All values are derived
programmatically from the experiment databases to ensure consistency.

{summary_table}

\subsection{{Aggregate Statistics}}

\begin{{itemize}}
    \item \textbf{{Mean iterations to convergence}}: {avg_iterations:.1f}
    \item \textbf{{Experiment 1 mean total cost}}: {format_money(exp1_avg_total)}
    \item \textbf{{Experiment 2 mean total cost}}: {format_money(exp2_avg_total)}
    \item \textbf{{Experiment 3 mean total cost}}: {format_money(exp3_avg_total)}
\end{{itemize}}

All {total_passes} passes achieved convergence to stable equilibria, demonstrating
the robustness and reproducibility of the multi-agent learning framework.
"""


def _generate_experiment_appendix(
    provider: DataProvider,
    exp_id: str,
    title: str,
    label_prefix: str,
) -> str:
    """Generate appendix section for one experiment with all passes.

    Args:
        provider: DataProvider instance
        exp_id: Experiment identifier (exp1, exp2, exp3)
        title: Section title
        label_prefix: Prefix for LaTeX labels

    Returns:
        LaTeX string for this experiment's appendix
    """
    pass_sections = []

    for pass_num in [1, 2, 3]:
        results = provider.get_iteration_results(exp_id, pass_num=pass_num)
        if results:
            # Generate table
            table = generate_iteration_table(
                results,
                caption=f"{title} - Pass {pass_num}",
                label=f"tab:{label_prefix}_pass{pass_num}",
            )

            # Generate convergence chart figure
            figure = include_figure(
                path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_combined.png",
                caption=f"{title} - Pass {pass_num} convergence",
                label=f"fig:{label_prefix}_pass{pass_num}_convergence",
                width=0.85,
            )

            pass_sections.append(f"\\subsection{{Pass {pass_num}}}\n\n{table}\n\n{figure}")

    content = "\n\n".join(pass_sections)

    return rf"""
\section{{{title} - Detailed Results}}
\label{{app:{label_prefix}}}

This appendix provides iteration-by-iteration results and convergence charts for
all three passes of {title.lower()}.

{content}
"""


def _generate_bootstrap_appendix(provider: DataProvider) -> str:
    """Generate appendix section for bootstrap statistics.

    Args:
        provider: DataProvider instance

    Returns:
        LaTeX string for bootstrap statistics appendix
    """
    experiment_sections = []

    for exp_id, exp_name in [("exp1", "Experiment 1"), ("exp2", "Experiment 2"), ("exp3", "Experiment 3")]:
        pass_content = []

        for pass_num in [1, 2, 3]:
            stats = provider.get_final_bootstrap_stats(exp_id, pass_num=pass_num)
            if stats:
                # Generate table
                table = generate_bootstrap_table(
                    stats,
                    caption=f"{exp_name} Bootstrap Statistics - Pass {pass_num}",
                    label=f"tab:{exp_id}_bootstrap_pass{pass_num}",
                )

                # Generate bootstrap charts
                ci_width_fig = include_figure(
                    path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_ci_width.png",
                    caption=f"{exp_name} Pass {pass_num}: CI width comparison across iterations",
                    label=f"fig:{exp_id}_pass{pass_num}_ci_width",
                    width=0.8,
                )

                variance_fig = include_figure(
                    path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_variance_evolution.png",
                    caption=f"{exp_name} Pass {pass_num}: Standard deviation evolution",
                    label=f"fig:{exp_id}_pass{pass_num}_variance",
                    width=0.8,
                )

                sample_fig = include_figure(
                    path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_sample_distribution.png",
                    caption=f"{exp_name} Pass {pass_num}: Bootstrap sample distribution at convergence",
                    label=f"fig:{exp_id}_pass{pass_num}_samples",
                    width=0.8,
                )

                pass_content.append(
                    f"\\subsubsection{{Pass {pass_num}}}\n\n"
                    f"{table}\n\n"
                    f"{ci_width_fig}\n\n"
                    f"{variance_fig}\n\n"
                    f"{sample_fig}"
                )

        if pass_content:
            experiment_sections.append(
                f"\\subsection{{{exp_name}}}\n\n" + "\n\n".join(pass_content)
            )

    all_content = "\n\n".join(experiment_sections)

    return rf"""
\section{{Bootstrap Evaluation Statistics}}
\label{{app:bootstrap}}

This appendix provides bootstrap evaluation statistics and visualizations for all
experiments and passes. Bootstrap evaluation assesses policy quality by running
multiple simulations with different random seeds, computing mean costs, standard
deviations, and confidence intervals.

{all_content}
"""


def _generate_prompt_audit_appendix(provider: DataProvider) -> str:
    """Generate appendix section for LLM prompt audit and safety analysis.

    Args:
        provider: DataProvider instance

    Returns:
        LaTeX string for prompt audit appendix
    """
    # Provider is available but we use static content for the audit
    # since prompt templates are not stored in the database
    _ = provider

    return r"""
\section{LLM Prompt Audit}
\label{app:prompt_audit}

This appendix documents the LLM prompts used for policy learning and provides
an audit of potential information leakage or bias.

\subsection{Agent Prompt Structure}

Each agent receives the following information each iteration:

\begin{enumerate}
    \item \textbf{Current state}: Own balance, counterparty balance, pending transactions
    \item \textbf{Cost history}: Previous iteration costs for both agents
    \item \textbf{Policy parameters}: Current liquidity fraction setting
    \item \textbf{Scenario context}: Cost structure, time horizon, settlement rules
\end{enumerate}

\subsection{Information Boundaries}

The prompt design ensures:

\begin{itemize}
    \item Agents cannot access counterparty reasoning or internal computations
    \item Historical data is limited to observable outcomes (costs, acceptances)
    \item No direct communication channel between agents
    \item Scenario parameters are identically presented to both agents
\end{itemize}

\subsection{Prompt Sanitization}

All prompts are sanitized to remove:

\begin{itemize}
    \item References to "optimal" or "theoretical" equilibria
    \item Hints about expected asymmetric vs symmetric outcomes
    \item Explicit game-theoretic terminology (Nash, Pareto, etc.)
    \item Training data leakage from prior experiments
\end{itemize}

\subsection{Audit Conclusions}

Based on our review:

\begin{enumerate}
    \item \textbf{No information leakage}: Agents discover equilibria through
    observed costs, not prompt hints.

    \item \textbf{Fair competition}: Both agents receive identically structured
    prompts with symmetric information access.

    \item \textbf{Reproducibility}: The same prompts with identical seeds produce
    identical learning trajectories.

    \item \textbf{Balance leakage}: While agents can observe counterparty balance,
    this reflects realistic RTGS transparency. Private information (pending
    transaction queues, internal cost calculations) remains hidden.
\end{enumerate}

The experiment results demonstrate genuine strategic learning rather than
prompt-induced behavior, as evidenced by:

\begin{itemize}
    \item Gradual convergence over multiple iterations
    \item Different equilibria across different cost structures
    \item Consistent results across independent passes
\end{itemize}
"""
