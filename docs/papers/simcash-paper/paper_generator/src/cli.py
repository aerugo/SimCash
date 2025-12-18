"""CLI for programmatic paper generation.

Usage:
    python -m src.cli --config config.yaml --output-dir output/

A config.yaml file is REQUIRED. The config explicitly maps experiment passes
to specific run_ids, ensuring reproducible paper generation.

By default, the CLI generates paper.tex and compiles it to PDF using tectonic
(lightweight, ~70MB) with pdflatex as fallback.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from src.config import load_config
from src.paper_builder import build_paper


def compile_pdf_tectonic(tex_path: Path) -> Path | None:
    """Compile LaTeX file to PDF using tectonic.

    Tectonic is a modern, lightweight TeX engine (~70MB) that automatically
    downloads required packages on first use.

    Args:
        tex_path: Path to .tex file

    Returns:
        Path to generated PDF, or None if compilation failed
    """
    output_dir = tex_path.parent
    pdf_path = tex_path.with_suffix(".pdf")

    result = subprocess.run(
        ["tectonic", "-o", str(output_dir), str(tex_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("tectonic compilation failed:")
        # Show stderr (tectonic outputs errors there)
        if result.stderr:
            for line in result.stderr.split("\n")[-20:]:
                print(f"  {line}")
        return None

    if pdf_path.exists():
        return pdf_path
    return None


def compile_pdf_pdflatex(tex_path: Path) -> Path | None:
    """Compile LaTeX file to PDF using pdflatex (fallback).

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


def compile_pdf(tex_path: Path) -> Path | None:
    """Compile LaTeX file to PDF using tectonic or pdflatex.

    Tries tectonic first (lightweight, ~70MB), falls back to pdflatex.

    Args:
        tex_path: Path to .tex file

    Returns:
        Path to generated PDF, or None if compilation failed
    """
    # Try tectonic first (faster, smaller dependency)
    if shutil.which("tectonic"):
        print("Compiling PDF with tectonic...")
        pdf_path = compile_pdf_tectonic(tex_path)
        if pdf_path:
            return pdf_path
        print("tectonic failed, trying pdflatex...")

    # Fall back to pdflatex
    if shutil.which("pdflatex"):
        print("Compiling PDF with pdflatex...")
        return compile_pdf_pdflatex(tex_path)

    # Neither available
    print("Error: No LaTeX compiler found.")
    print("")
    print("Install tectonic (recommended, lightweight ~70MB):")
    print("  curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh")
    print("")
    print("Or install via cargo:")
    print("  cargo install tectonic")
    print("")
    print("Alternatively, install pdflatex (larger, ~2-4GB):")
    print("  See generate_paper.sh for platform-specific instructions")
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

    # Compile PDF unless skipped
    if not args.skip_pdf:
        pdf_path = compile_pdf(tex_path)
        if pdf_path:
            print(f"Compiled:  {pdf_path}")
        else:
            print("PDF compilation failed (see errors above)")


if __name__ == "__main__":
    main()
