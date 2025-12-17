"""Paper builder - compose sections into complete LaTeX document.

This module provides functions for generating the complete paper from
experiment data via the DataProvider protocol.

Generates two files:
- paper_src.tex: LaTeX with {{variable}} placeholders visible
- paper.tex: LaTeX with actual values substituted

A config.yaml file is REQUIRED for paper generation to ensure reproducible
run_id selection. The config explicitly maps experiment passes to specific
run_ids, preventing issues with database ordering or incomplete runs.

Example:
    >>> from pathlib import Path
    >>> from src.config import load_config
    >>> from src.paper_builder import build_paper
    >>> config = load_config(Path("config.yaml"))
    >>> tex_path, src_path = build_paper(Path("data/"), Path("output/"), config=config)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from src.charts.generators import generate_all_paper_charts
from src.data_provider import DatabaseDataProvider
from src.sections import (
    generate_abstract,
    generate_appendices,
    generate_conclusion,
    generate_discussion,
    generate_introduction,
    generate_methods,
    generate_references,
    generate_related_work,
    generate_results,
)
from src.template import collect_template_context, render_template

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Type alias for section generator functions (provider is optional now)
SectionGenerator = Callable[["DataProvider | None"], str]

# Template sections (use {{placeholders}})
TEMPLATE_SECTIONS: list[SectionGenerator] = [
    generate_abstract,
    generate_introduction,
    generate_related_work,
    generate_methods,
    generate_results,
    generate_discussion,
    generate_conclusion,
    generate_references,
]

# Data-driven sections (need provider for complex tables)
DATA_SECTIONS: list[SectionGenerator] = [
    generate_appendices,
]


def wrap_document(
    content: str,
    title: str = "SimCash: Multi-Agent Simulation of Strategic Liquidity Management in Payment Systems",
    author: str = "Anonymous",
) -> str:
    """Wrap content in a complete LaTeX document structure.

    Args:
        content: LaTeX content for the document body
        title: Document title
        author: Document author

    Returns:
        Complete LaTeX document string
    """
    return rf"""\documentclass[11pt]{{article}}

% Page layout
\usepackage[margin=1in]{{geometry}}

% Typography
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{microtype}}

% Math
\usepackage{{amsmath}}
\usepackage{{amssymb}}

% Tables and figures
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{float}}

% Lists
\usepackage{{enumitem}}

% Hyperlinks
\usepackage{{hyperref}}
\hypersetup{{
    colorlinks=true,
    linkcolor=blue,
    citecolor=blue,
    urlcolor=blue
}}

% Title and author
\title{{{title}}}
\author{{{author}}}
\date{{\today}}

\begin{{document}}

\maketitle

{content}

\end{{document}}
"""


def generate_paper(
    provider: DataProvider,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Generate both paper files from data provider.

    Generates:
    - paper_src.tex: Template with {{variable}} placeholders visible
    - paper.tex: Rendered with actual values substituted

    Args:
        provider: DataProvider instance for accessing experiment data
        output_dir: Directory to write output files

    Returns:
        Tuple of (paper.tex path, paper_src.tex path)
    """
    # Collect template context from data
    context = collect_template_context(provider)

    # Generate template sections (with {{placeholders}})
    template_contents = [section(None) for section in TEMPLATE_SECTIONS]

    # Generate data-driven sections (appendices need provider)
    data_contents = [section(provider) for section in DATA_SECTIONS]

    # Add appendices content to context for rendering
    appendices_template = "\n\n".join(data_contents)
    context["appendices"] = appendices_template

    # Combine template sections
    body_template = "\n\n".join(template_contents)

    # Add appendices placeholder to template
    body_template += "\n\n{{appendices}}"

    # Wrap in document structure
    src_document = wrap_document(body_template)

    # Render with values
    rendered_document = render_template(src_document, context)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write both files
    src_path = output_dir / "paper_src.tex"
    tex_path = output_dir / "paper.tex"

    src_path.write_text(src_document)
    tex_path.write_text(rendered_document)

    return tex_path, src_path


def build_paper(
    data_dir: Path,
    output_dir: Path,
    config: dict,
    generate_charts: bool = True,
) -> tuple[Path, Path]:
    """Build complete paper from experiment databases.

    This is the main entry point for paper generation. It creates a
    DatabaseDataProvider from the data directory and generates the paper.

    Generates two files:
    - paper_src.tex: LaTeX with {{variable}} placeholders visible
    - paper.tex: LaTeX with actual values substituted

    A config file is REQUIRED to ensure reproducible paper generation.
    The config explicitly maps experiment passes to specific run_ids.

    Args:
        data_dir: Directory containing exp{1,2,3}.db files
        output_dir: Directory for output files (created if needed)
        config: Paper config with explicit run_id mappings (required)
        generate_charts: Whether to generate chart images (default: True)

    Returns:
        Tuple of (paper.tex path, paper_src.tex path)

    Raises:
        IncompleteExperimentError: If any experiment run in config is not completed
        FileNotFoundError: If database files don't exist
        ValueError: If run_ids in config don't exist in database

    Example:
        >>> from pathlib import Path
        >>> from src.config import load_config
        >>> config = load_config(Path("config.yaml"))
        >>> tex_path, src_path = build_paper(Path("data/"), Path("output/"), config=config)
        >>> print(f"Paper generated at: {tex_path}")
    """
    from src.config import validate_runs_completed

    # Validate all experiment runs are completed
    # base_dir is parent of data_dir (data_dir is v5/data, base_dir is v5)
    base_dir = data_dir.parent
    validate_runs_completed(config, base_dir)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate charts if requested
    if generate_charts:
        charts_dir = output_dir / "charts"
        generate_all_paper_charts(data_dir, charts_dir, config)

    # Create data provider with config for explicit run_id lookup
    provider = DatabaseDataProvider(data_dir, config=config)

    # Generate both paper files
    return generate_paper(provider, output_dir)
