"""Web markdown builder — orchestrates blog-style page generation.

Produces 4 markdown files from experiment data:
- paper-introduction.md (abstract + intro + methods)
- paper-results.md (all results)
- paper-discussion.md (discussion + conclusion)
- paper-appendix.md (detailed per-experiment per-pass data)
"""

from __future__ import annotations

from pathlib import Path

from src.config import load_config, validate_runs_completed
from src.data_provider import DatabaseDataProvider
from src.markdown.figures import include_figure
from src.markdown.tables import (
    generate_iteration_table,
    generate_pass_summary_table,
    generate_results_summary_table,
)
from src.web_sections import (
    generate_abstract,
    generate_discussion,
    generate_introduction,
    generate_methods,
    generate_results,
)

CHARTS_DIR = "charts"


def _generate_appendix(provider: DatabaseDataProvider) -> str:
    """Generate the appendix markdown with detailed per-pass data and charts."""
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    summary_table = generate_results_summary_table(exp1_summaries, exp2_summaries, exp3_summaries)

    sections = [f"""# Detailed Data

## Complete Results Summary

{summary_table}

---
"""]

    experiments = [
        ("exp1", "Experiment 1: Asymmetric (2-Period Deterministic)"),
        ("exp2", "Experiment 2: Stochastic (12-Period)"),
        ("exp3", "Experiment 3: Symmetric (3-Period Deterministic)"),
    ]

    for exp_id, title in experiments:
        num_passes = provider.get_num_passes(exp_id)
        sections.append(f"\n## {title}\n")

        for pass_num in range(1, num_passes + 1):
            results = provider.get_iteration_results(exp_id, pass_num=pass_num)
            if not results:
                continue

            combined_fig = include_figure(
                f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_combined.png",
                f"{title} — Pass {pass_num} convergence",
            )
            bank_a_fig = include_figure(
                f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_bankA.png",
                f"{title} — Pass {pass_num} Bank A detail",
            )
            bank_b_fig = include_figure(
                f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_bankB.png",
                f"{title} — Pass {pass_num} Bank B detail",
            )

            iter_table = generate_iteration_table(results)

            # Check for variance chart (exp2 only)
            variance_section = ""
            if exp_id == "exp2":
                var_fig = include_figure(
                    f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_variance.png",
                    f"{title} — Pass {pass_num} cost variance",
                )
                variance_section = f"\n{var_fig}\n"

            sections.append(f"""### Pass {pass_num}

{combined_fig}

{bank_a_fig}

{bank_b_fig}
{variance_section}
<details>
<summary>📊 View iteration-by-iteration data</summary>

{iter_table}

</details>

---
""")

    return "\n".join(sections)


def build_web(
    data_dir: Path,
    output_dir: Path,
    config: dict,
) -> list[Path]:
    """Build web markdown files from experiment databases.

    Args:
        data_dir: Directory containing exp{1,2,3}.db files
        output_dir: Directory for output markdown files

    Returns:
        List of paths to generated markdown files
    """
    base_dir = data_dir.parent
    validate_runs_completed(config, base_dir)

    provider = DatabaseDataProvider(data_dir, config=config)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate sections
    abstract = generate_abstract(provider)
    intro = generate_introduction(provider)
    methods = generate_methods(provider)
    results = generate_results(provider)
    discussion = generate_discussion(provider)
    appendix = _generate_appendix(provider)

    # Compose files
    files = {
        "paper-introduction.md": f"{abstract}\n{intro}\n{methods}",
        "paper-results.md": results,
        "paper-discussion.md": discussion,
        "paper-appendix.md": appendix,
    }

    paths = []
    for filename, content in files.items():
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        paths.append(path)
        print(f"  Generated: {path}")

    return paths
