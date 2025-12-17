"""Paper builder - compose sections into complete LaTeX document.

This module provides functions for generating the complete paper from
experiment data via the DataProvider protocol.

Example:
    >>> from pathlib import Path
    >>> from src.paper_builder import build_paper
    >>> tex_path = build_paper(Path("data/"), Path("output/"))
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

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Type alias for section generator functions
SectionGenerator = Callable[["DataProvider"], str]

# Default sections in paper order
DEFAULT_SECTIONS: list[SectionGenerator] = [
    generate_abstract,
    generate_introduction,
    generate_related_work,
    generate_methods,
    generate_results,
    generate_discussion,
    generate_conclusion,
    generate_references,
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
    sections: list[SectionGenerator] | None = None,
    generate_charts: bool = True,
) -> Path:
    """Build complete paper from experiment databases.

    This is the main entry point for paper generation. It creates a
    DatabaseDataProvider from the data directory and generates the paper.

    Args:
        data_dir: Directory containing exp{1,2,3}.db files
        output_dir: Directory for output files (created if needed)
        sections: Optional list of section generators
        generate_charts: Whether to generate chart images (default: True)

    Returns:
        Path to generated .tex file

    Example:
        >>> from pathlib import Path
        >>> tex_path = build_paper(Path("data/"), Path("output/"))
        >>> print(f"Paper generated at: {tex_path}")
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate charts if requested
    if generate_charts:
        charts_dir = output_dir / "charts"
        generate_all_paper_charts(data_dir, charts_dir)

    # Create data provider
    provider = DatabaseDataProvider(data_dir)

    # Generate paper
    return generate_paper(provider, output_dir, sections)
