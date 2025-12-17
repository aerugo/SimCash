"""CLI for programmatic paper generation.

Usage:
    python -m src.cli --config config.yaml --output-dir output/

A config.yaml file is REQUIRED. The config explicitly maps experiment passes
to specific run_ids, ensuring reproducible paper generation.

By default, the CLI generates paper.tex and compiles it to PDF using pdflatex.
It also generates paper_data.txt with all computed values in plain text.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from src.config import load_config
from src.data_provider import DatabaseDataProvider
from src.data_summary import generate_data_summary
from src.paper_builder import build_paper


def compile_pdf(tex_path: Path) -> Path | None:
    """Compile LaTeX file to PDF using pdflatex.

    Runs pdflatex twice to resolve cross-references.

    Args:
        tex_path: Path to .tex file

    Returns:
        Path to generated PDF, or None if compilation failed
    """
    output_dir = tex_path.parent
    pdf_path = tex_path.with_suffix(".pdf")

    # Run pdflatex twice to resolve references
    for pass_num in range(2):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            cwd=output_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"pdflatex pass {pass_num + 1} failed:")
            # Show last 20 lines of output for debugging
            lines = result.stdout.split("\n")
            for line in lines[-20:]:
                print(f"  {line}")
            return None

    if pdf_path.exists():
        return pdf_path
    return None


def main() -> None:
    """Main entry point for paper generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate SimCash paper from experiment databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python -m src.cli --config config.yaml --output-dir output/

The config file specifies explicit run_ids for each experiment pass,
ensuring reproducible paper generation. All referenced experiment runs
must be completed before paper generation.
        """,
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to config.yaml with explicit run_id mappings (required)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for generated paper.tex and charts/ output",
    )

    parser.add_argument(
        "--skip-charts",
        action="store_true",
        help="Skip chart generation (use existing charts)",
    )

    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF compilation (generate .tex only)",
    )

    args = parser.parse_args()

    # Load config (required)
    config = load_config(args.config)

    # Data dir is relative to config file location
    data_dir = args.config.parent / "data"

    # Generate paper (with or without charts)
    tex_path = build_paper(
        data_dir,
        args.output_dir,
        config=config,
        generate_charts=not args.skip_charts,
    )

    print(f"Generated: {tex_path}")

    # Generate data summary (plain text with all values)
    provider = DatabaseDataProvider(data_dir, config=config)
    data_path = args.output_dir / "paper_data.txt"
    generate_data_summary(provider, data_path)
    print(f"Generated: {data_path}")

    # Compile PDF unless skipped
    if not args.skip_pdf:
        pdf_path = compile_pdf(tex_path)
        if pdf_path:
            print(f"Compiled:  {pdf_path}")
        else:
            print("PDF compilation failed (see errors above)")


if __name__ == "__main__":
    main()
