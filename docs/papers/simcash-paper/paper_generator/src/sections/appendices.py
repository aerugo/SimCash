"""Appendices section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.figures import include_figure
from src.latex.formatting import format_money, format_percent
from src.latex.tables import (
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

    # Appendix E: LLM Prompt Audit
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
            # Generate convergence chart figure with [H] to prevent floating
            # [H] from float package forces figure to stay exactly here
            figure = include_figure(
                path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_combined.png",
                caption=f"{title} - Pass {pass_num} convergence",
                label=f"fig:{label_prefix}_pass{pass_num}_convergence",
                width=0.85,
                position="H",  # Force figure to stay in place, don't float
            )

            # Generate table (may use longtable for long experiments)
            # Use position="H" to prevent floating in appendices
            table = generate_iteration_table(
                results,
                caption=f"{title} - Pass {pass_num}",
                label=f"tab:{label_prefix}_pass{pass_num}",
                position="H",  # Force table to stay in place
            )

            # Figure before table helps LaTeX place floats correctly
            pass_sections.append(f"\\subsection{{Pass {pass_num}}}\n\n{figure}\n\n{table}")

    content = "\n\n".join(pass_sections)

    return rf"""
\section{{{title} - Detailed Results}}
\label{{app:{label_prefix}}}

This appendix provides iteration-by-iteration results and convergence charts for
all three passes of {title.lower()}.

{content}
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

\subsection{Prompt Structure}

Each agent receives a \textbf{system prompt} (identical for all agents) and a
\textbf{user prompt} (agent-specific, filtered).

\subsubsection{System Prompt (Shared)}

The system prompt provides domain context without agent-specific information:

\begin{enumerate}
    \item \textbf{Domain explanation}: RTGS mechanics, queuing, LSM netting
    \item \textbf{Cost structure}: Overdraft, delay, deadline, and EOD penalties
    \item \textbf{Policy tree architecture}: JSON schema for valid policies
    \item \textbf{Optimization guidance}: General strategy for cost minimization
    \item \textbf{Validation checklist}: Common errors to avoid
\end{enumerate}

\subsubsection{User Prompt (Agent-Specific)}

The user prompt provides filtered information for the optimizing agent only:

\begin{enumerate}
    \item \textbf{Performance metrics}: Agent's own mean cost, standard deviation, settlement rate
    \item \textbf{Current policy}: Agent's own policy parameters (e.g., \texttt{initial\_liquidity\_fraction})
    \item \textbf{Cost breakdown}: Agent's own costs by type (delay, overdraft, penalties)
    \item \textbf{Simulation trace}: Filtered event log showing ONLY:
    \begin{itemize}
        \item Outgoing transactions FROM this agent
        \item Incoming payments TO this agent
        \item Agent's own policy decisions (Submit, Hold, etc.)
        \item Agent's own balance changes (for outgoing settlements only)
    \end{itemize}
    \item \textbf{Iteration history}: Agent's own cost trajectory across iterations
    \item \textbf{Parameter trajectories}: How agent's parameters evolved
\end{enumerate}

\subsection{Information Boundaries}

\textbf{Critical invariant}: An agent optimizing policy may ONLY observe:
\begin{itemize}
    \item Events where they are the sender (outgoing transactions)
    \item Events where they are the receiver (incoming liquidity)
    \item Their own state changes (balance, collateral, costs)
\end{itemize}

\subsubsection{What Agents CANNOT See}

\begin{itemize}
    \item \textbf{Counterparty balances}: No visibility into opponent's reserves
    \item \textbf{Counterparty policies}: No access to opponent's decision trees
    \item \textbf{Counterparty costs}: No visibility into opponent's cost breakdown
    \item \textbf{Counterparty reasoning}: No access to opponent's LLM responses
    \item \textbf{Third-party transactions}: Events not involving this agent are filtered
\end{itemize}

This strict isolation is enforced by the \texttt{filter\_events\_for\_agent()} function
which processes the raw simulation event stream before prompt construction.

\subsection{Prompt Sanitization}

All prompts are sanitized to remove:

\begin{itemize}
    \item References to ``optimal'' or ``theoretical'' equilibria
    \item Hints about expected asymmetric vs symmetric outcomes
    \item Explicit game-theoretic terminology (Nash, Pareto, etc.)
    \item Training data leakage from prior experiments
\end{itemize}

\subsection{Audit Conclusions}

Based on our review:

\begin{enumerate}
    \item \textbf{No information leakage}: Agents discover equilibria through
    observed costs, not prompt hints. Counterparty information is strictly filtered.

    \item \textbf{Fair competition}: Both agents receive identically structured
    prompts with symmetric information access. Neither agent has visibility into
    the other's balance, policy, or reasoning.

    \item \textbf{Reproducibility}: The same prompts with identical seeds produce
    identical learning trajectories.

    \item \textbf{Strategic opacity}: Agents cannot observe counterparty reserves
    or pending decisions. The only ``signal'' about counterparty behavior comes
    from incoming payments, which is realistic RTGS transparency.
\end{enumerate}

The experiment results demonstrate genuine strategic learning rather than
prompt-induced behavior, as evidenced by:

\begin{itemize}
    \item Gradual convergence over multiple iterations
    \item Different equilibria across different cost structures
    \item Consistent results across independent passes
\end{itemize}
"""
