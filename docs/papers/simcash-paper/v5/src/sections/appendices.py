"""Appendices section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.latex.tables import generate_bootstrap_table, generate_iteration_table

if TYPE_CHECKING:
    from src.data_provider import DataProvider


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
    tables = []

    for pass_num in [1, 2, 3]:
        results = provider.get_iteration_results(exp_id, pass_num=pass_num)
        if results:
            table = generate_iteration_table(
                results,
                caption=f"{title} - Pass {pass_num}",
                label=f"tab:{label_prefix}_pass{pass_num}",
            )
            tables.append(table)

    tables_content = "\n\n".join(tables)

    return rf"""
\section{{{title} - Detailed Results}}
\label{{app:{label_prefix}}}

This appendix provides iteration-by-iteration results for all three passes of
{title.lower()}.

{tables_content}
"""


def _generate_bootstrap_appendix(provider: DataProvider) -> str:
    """Generate appendix section for bootstrap statistics.

    Args:
        provider: DataProvider instance

    Returns:
        LaTeX string for bootstrap statistics appendix
    """
    tables = []

    for exp_id, exp_name in [("exp1", "Experiment 1"), ("exp2", "Experiment 2"), ("exp3", "Experiment 3")]:
        for pass_num in [1, 2, 3]:
            stats = provider.get_final_bootstrap_stats(exp_id, pass_num=pass_num)
            if stats:
                table = generate_bootstrap_table(
                    stats,
                    caption=f"{exp_name} Bootstrap Statistics - Pass {pass_num}",
                    label=f"tab:{exp_id}_bootstrap_pass{pass_num}",
                )
                tables.append(table)

    tables_content = "\n\n".join(tables)

    return rf"""
\section{{Bootstrap Evaluation Statistics}}
\label{{app:bootstrap}}

This appendix provides bootstrap evaluation statistics for all experiments and passes.
Bootstrap evaluation assesses policy quality by running multiple simulations with
different random seeds, computing mean costs and confidence intervals.

{tables_content}
"""
