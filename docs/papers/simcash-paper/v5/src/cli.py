"""CLI for programmatic paper generation.

Usage:
    python -m src.cli --data-dir data/ --output-dir output/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.paper_builder import build_paper


def main() -> None:
    """Main entry point for paper generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate SimCash paper from experiment databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python -m src.cli --data-dir data/ --output-dir output/

This generates paper.tex from the experiment databases in data/.
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing exp{1,2,3}.db database files",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for generated paper.tex output",
    )

    args = parser.parse_args()

    # Generate paper
    tex_path = build_paper(args.data_dir, args.output_dir)

    print(f"Generated: {tex_path}")


if __name__ == "__main__":
    main()
