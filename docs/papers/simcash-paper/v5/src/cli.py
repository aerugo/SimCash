"""CLI for programmatic paper generation.

Usage:
    python -m src.cli --config config.yaml --output-dir output/

A config.yaml file is REQUIRED. The config explicitly maps experiment passes
to specific run_ids, ensuring reproducible paper generation.
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


if __name__ == "__main__":
    main()
