"""CLI for programmatic paper generation.

Usage:
    python -m src.cli --data-dir data/ --output-dir output/
    python -m src.cli --config config.yaml --output-dir output/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import load_config
from src.paper_builder import build_paper


def main() -> None:
    """Main entry point for paper generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate SimCash paper from experiment databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Using config file (recommended):
    python -m src.cli --config config.yaml --output-dir output/

    # Legacy mode (infers run_ids from database):
    python -m src.cli --data-dir data/ --output-dir output/

The config file specifies explicit run_ids for each experiment pass,
ensuring reproducible paper generation regardless of database contents.
        """,
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config.yaml with explicit run_id mappings (recommended)",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Directory containing exp{1,2,3}.db database files (legacy mode)",
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

    args = parser.parse_args()

    # Determine data_dir and config
    config = None
    if args.config:
        config = load_config(args.config)
        # Data dir is relative to config file location
        data_dir = args.config.parent / "data"
    elif args.data_dir:
        data_dir = args.data_dir
    else:
        parser.error("Either --config or --data-dir must be specified")

    # Generate paper (with or without charts)
    tex_path = build_paper(
        data_dir,
        args.output_dir,
        generate_charts=not args.skip_charts,
        config=config,
    )

    print(f"Generated: {tex_path}")


if __name__ == "__main__":
    main()
