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
        title="Experiment 1: Asymmetric Scenario",
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
        title="Experiment 3: Symmetric Scenario",
        label_prefix="exp3",
    )
    appendix_sections.append(exp3_content)

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

    # Calculate total passes for summary text
    total_passes = len(exp1_summaries) + len(exp2_summaries) + len(exp3_summaries)

    return rf"""
\section{{Results Summary}}
\label{{app:results_summary}}

This appendix provides a comprehensive summary of all experimental results
across {total_passes} passes ({len(exp1_summaries)} per experiment). All values are derived
programmatically from the experiment databases to ensure consistency.

{summary_table}
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


