"""Paper builder - compose sections into complete LaTeX document.

This module provides functions for generating the complete paper from
experiment data via the DataProvider protocol.

A config.yaml file is REQUIRED for paper generation to ensure reproducible
run_id selection. The config explicitly maps experiment passes to specific
run_ids, preventing issues with database ordering or incomplete runs.

Example:
    >>> from pathlib import Path
    >>> from src.config import load_config
    >>> from src.paper_builder import build_paper
    >>> config = load_config(Path("config.yaml"))
    >>> tex_path = build_paper(Path("data/"), Path("output/"), config=config)
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
    generate_results,
)

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Type alias for section generator functions
SectionGenerator = Callable[["DataProvider"], str]

# Default sections in paper order
DEFAULT_SECTIONS: list[SectionGenerator] = [
    generate_abstract,
    generate_introduction,
    generate_methods,
    generate_results,
    generate_discussion,
    generate_conclusion,
    generate_appendices,
]


def wrap_document(
    content: str,
    title: str = "Discovering Equilibrium-like Behavior with LLM Agents: A Payment Systems Case Study",
    author: str = "Hugi Aegisberg",
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
\usepackage{{longtable}}

% Lists
\usepackage{{enumitem}}

% Colors for notice box
\usepackage{{xcolor}}

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

\vspace{{1em}}
\begin{{center}}
\colorbox{{red!90}}{{\parbox{{0.92\textwidth}}{{\color{{white}}\centering
\textbf{{\Large DO NOT CIRCULATE}}\\[0.5em]
\normalsize
This is a working document and is not intended for distribution.\\[0.3em]
This paper and the accompanying SimCash codebase were developed with assistance from\\
\textbf{{Claude 4.5 Opus}} (Anthropic) and \textbf{{GPT-5.2}} (OpenAI) as coding and\\
writing tools. All experimental design, analysis, and interpretation are the author's own.
}}}}
\end{{center}}

\vspace{{0.5em}}
\begin{{center}}
\colorbox{{green!70!black}}{{\parbox{{0.92\textwidth}}{{\color{{white}}
\textbf{{About This Document}}\\[0.3em]
This is a \textbf{{research proposal}} presenting methodology and preliminary findings
to potential collaborators. All tables, figures, and statistics are programmatically
generated from experiment databases (DuckDB $\to$ DataProvider $\to$ LaTeX/charts),
eliminating manual transcription. The accompanying text is written by an AI assistant
(Claude) following author guidance on structure and conclusions.\\[0.3em]
SimCash is a hybrid Rust/Python payment system simulator with deterministic replay,
configurable policies, and multiple settlement mechanisms (RTGS, queues, LSM). The
experiment runner uses LLM agents to iteratively optimize policies through natural
language reasoning, enabling research into multi-agent coordination in financial infrastructure.
}}}}
\end{{center}}
\vspace{{1em}}

{content}

\end{{document}}
"""


def generate_paper(
    provider: DataProvider,
    output_dir: Path,
    sections: list[SectionGenerator] | None = None,
    filename: str = "paper.tex",
) -> Path:
    """Generate paper LaTeX file from data provider.

    Args:
        provider: DataProvider instance for accessing experiment data
        output_dir: Directory to write output file
        sections: Optional list of section generators (defaults to all sections)
        filename: Output filename (default: paper.tex)

    Returns:
        Path to generated .tex file
    """
    # Use default sections if not specified
    if sections is None:
        sections = DEFAULT_SECTIONS

    # Generate all sections
    section_contents = [section(provider) for section in sections]
    body_content = "\n\n".join(section_contents)

    # Wrap in document structure
    full_document = wrap_document(body_content)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write to file
    tex_path = output_dir / filename
    tex_path.write_text(full_document)

    return tex_path


def build_paper(
    data_dir: Path,
    output_dir: Path,
    config: dict,
    sections: list[SectionGenerator] | None = None,
    generate_charts: bool = True,
) -> Path:
    """Build complete paper from experiment databases.

    This is the main entry point for paper generation. It creates a
    DatabaseDataProvider from the data directory and generates the paper.

    A config file is REQUIRED to ensure reproducible paper generation.
    The config explicitly maps experiment passes to specific run_ids.

    Args:
        data_dir: Directory containing exp{1,2,3}.db files
        output_dir: Directory for output files (created if needed)
        config: Paper config with explicit run_id mappings (required)
        sections: Optional list of section generators
        generate_charts: Whether to generate chart images (default: True)

    Returns:
        Path to generated .tex file

    Raises:
        IncompleteExperimentError: If any experiment run in config is not completed
        FileNotFoundError: If database files don't exist
        ValueError: If run_ids in config don't exist in database

    Example:
        >>> from pathlib import Path
        >>> from src.config import load_config
        >>> config = load_config(Path("config.yaml"))
        >>> tex_path = build_paper(Path("data/"), Path("output/"), config=config)
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

    # Generate paper
    return generate_paper(provider, output_dir, sections)
