"""Appendices section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.figures import include_figure
from src.latex.tables import generate_bootstrap_table, generate_iteration_table

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

    # Appendix A: Experiment 1 Detailed Results
    exp1_content = _generate_experiment_appendix(
        provider,
        exp_id="exp1",
        title="Experiment 1: Asymmetric Equilibrium",
        label_prefix="exp1",
    )
    appendix_sections.append(exp1_content)

    # Appendix B: Experiment 2 Detailed Results
    exp2_content = _generate_experiment_appendix(
        provider,
        exp_id="exp2",
        title="Experiment 2: Stochastic Environment",
        label_prefix="exp2",
    )
    appendix_sections.append(exp2_content)

    # Appendix C: Experiment 3 Detailed Results
    exp3_content = _generate_experiment_appendix(
        provider,
        exp_id="exp3",
        title="Experiment 3: Symmetric Equilibrium",
        label_prefix="exp3",
    )
    appendix_sections.append(exp3_content)

    # Appendix D: Bootstrap Statistics
    bootstrap_content = _generate_bootstrap_appendix(provider)
    appendix_sections.append(bootstrap_content)

    all_content = "\n\n".join(appendix_sections)

    return rf"""
\appendix

{all_content}
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
