#!/usr/bin/env python3
"""
Run missing experiments from config.yaml.

This script reads the paper generator config.yaml, identifies experiments
with empty run_ids, and runs them automatically. Experiments for the same
database run sequentially (to avoid lock conflicts), while different
experiments run in parallel.

Usage:
    python run_missing_experiments.py config.yaml
    python run_missing_experiments.py --help
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class MissingExperiment:
    """Represents a missing experiment pass."""

    experiment_name: str  # e.g., "exp1"
    pass_number: int  # e.g., 1, 2, 3
    config_path: Path  # Path to experiment config (e.g., configs/exp1.yaml)
    db_path: Path  # Path to database


def load_config(config_path: Path) -> dict:
    """Load and parse config.yaml."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def save_config(config_path: Path, config: dict) -> None:
    """Save config.yaml with proper formatting."""
    # Read original file to preserve comments structure
    with open(config_path) as f:
        original_content = f.read()

    # Update run_ids in the original content using regex
    for exp_name, exp_data in config["experiments"].items():
        for pass_num, run_id in exp_data["passes"].items():
            if run_id:
                # Find and replace the specific pass line
                pattern = rf'(\s+{pass_num}:\s*")[^"]*(".*#{exp_name}.*pass.*{pass_num}|".*#.*|")'
                replacement = rf'\g<1>{run_id}\g<2>'
                # Try to match with comment
                if not re.search(pattern, original_content):
                    # Simple pattern without comment matching
                    pattern = rf'(\s+{pass_num}:\s*")[^"]*(")'
                    replacement = rf'\g<1>{run_id}\g<2>'
                original_content = re.sub(pattern, replacement, original_content)

    with open(config_path, "w") as f:
        f.write(original_content)


def find_missing_experiments(
    config: dict, config_dir: Path
) -> dict[str, list[MissingExperiment]]:
    """
    Find experiments with empty run_ids.

    Returns a dict mapping experiment name to list of missing passes.
    """
    missing: dict[str, list[MissingExperiment]] = {}

    for exp_name, exp_data in config["experiments"].items():
        db_path = config_dir / config["databases"][exp_name]
        config_path = config_dir / "configs" / f"{exp_name}.yaml"

        for pass_num, run_id in exp_data["passes"].items():
            if not run_id:  # Empty string means missing
                if exp_name not in missing:
                    missing[exp_name] = []
                missing[exp_name].append(
                    MissingExperiment(
                        experiment_name=exp_name,
                        pass_number=int(pass_num),
                        config_path=config_path,
                        db_path=db_path,
                    )
                )

    # Sort passes within each experiment
    for exp_name in missing:
        missing[exp_name].sort(key=lambda x: x.pass_number)

    return missing


def run_experiment(
    exp: MissingExperiment,
    api_dir: Path,
    output_prefix: str,
    lock: threading.Lock,
) -> tuple[MissingExperiment, str | None, str]:
    """
    Run a single experiment and return (experiment, run_id, output).

    Returns None for run_id if experiment failed.
    """
    cmd = [
        str(api_dir / ".venv" / "bin" / "payment-sim"),
        "experiment",
        "run",
        "--verbose",
        str(exp.config_path),
        "--db",
        str(exp.db_path),
    ]

    output_lines: list[str] = []
    run_id: str | None = None

    with lock:
        print(f"\n{'='*60}")
        print(f"[{output_prefix}] Starting {exp.experiment_name} pass {exp.pass_number}")
        print(f"{'='*60}")
        sys.stdout.flush()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in iter(process.stdout.readline, ""):
            output_lines.append(line)
            with lock:
                print(f"[{output_prefix}] {line}", end="")
                sys.stdout.flush()

            # Extract run_id from output
            if "Experiment run ID:" in line:
                match = re.search(r"Experiment run ID:\s*(\S+)", line)
                if match:
                    run_id = match.group(1)

        process.wait()

        if process.returncode != 0:
            with lock:
                print(f"\n[{output_prefix}] ERROR: Experiment failed with code {process.returncode}")
            return exp, None, "".join(output_lines)

        # Check if experiment completed successfully
        output_text = "".join(output_lines)
        if "Experiment completed!" not in output_text:
            with lock:
                print(f"\n[{output_prefix}] WARNING: Experiment may not have completed properly")
            return exp, None, output_text

        with lock:
            print(f"\n[{output_prefix}] Completed: {run_id}")

        return exp, run_id, output_text

    except Exception as e:
        with lock:
            print(f"\n[{output_prefix}] ERROR: {e}")
        return exp, None, str(e)


def run_experiment_sequence(
    experiments: list[MissingExperiment],
    api_dir: Path,
    config_path: Path,
    config: dict,
    config_lock: threading.Lock,
    output_lock: threading.Lock,
) -> list[tuple[MissingExperiment, str | None]]:
    """
    Run a sequence of experiments for the same database (sequentially).

    Updates config.yaml after each successful run.
    """
    results: list[tuple[MissingExperiment, str | None]] = []
    exp_name = experiments[0].experiment_name

    for exp in experiments:
        prefix = f"{exp.experiment_name}:P{exp.pass_number}"
        exp_result, run_id, _ = run_experiment(exp, api_dir, prefix, output_lock)
        results.append((exp_result, run_id))

        if run_id:
            # Update config.yaml with the new run_id
            with config_lock:
                config["experiments"][exp_name]["passes"][exp.pass_number] = run_id
                save_config(config_path, config)
                with output_lock:
                    print(f"\n[{prefix}] Updated config.yaml with {run_id}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run missing experiments from config.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all missing experiments
    python run_missing_experiments.py config.yaml

    # From the paper_generator directory
    cd docs/papers/simcash-paper/paper_generator
    python run_missing_experiments.py config.yaml
        """,
    )
    parser.add_argument(
        "config",
        type=Path,
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without actually running",
    )

    args = parser.parse_args()

    config_path = args.config.resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 1

    config_dir = config_path.parent

    # Find api directory (navigate up to find it)
    api_dir = config_dir
    while api_dir.name != "SimCash" and api_dir.parent != api_dir:
        api_dir = api_dir.parent
    api_dir = api_dir / "api"

    if not (api_dir / ".venv" / "bin" / "payment-sim").exists():
        print(f"Error: payment-sim not found at {api_dir}", file=sys.stderr)
        print("Make sure you've run 'uv sync' in the api directory", file=sys.stderr)
        return 1

    # Load config and find missing experiments
    config = load_config(config_path)
    missing = find_missing_experiments(config, config_dir)

    if not missing:
        print("All experiments are complete! Nothing to run.")
        return 0

    print("Missing experiments:")
    for exp_name, passes in missing.items():
        pass_nums = [str(p.pass_number) for p in passes]
        print(f"  {exp_name}: passes {', '.join(pass_nums)}")

    if args.dry_run:
        print("\n[DRY RUN] Would run the above experiments")
        return 0

    print(f"\nRunning {sum(len(p) for p in missing.values())} experiment(s)...")
    print("Different experiments run in parallel, same experiment passes run sequentially.\n")

    # Locks for thread safety
    config_lock = threading.Lock()
    output_lock = threading.Lock()

    # Run experiments in parallel (different experiments) but sequential (same experiment passes)
    all_results: list[tuple[MissingExperiment, str | None]] = []

    with ThreadPoolExecutor(max_workers=len(missing)) as executor:
        futures = {
            executor.submit(
                run_experiment_sequence,
                passes,
                api_dir,
                config_path,
                config,
                config_lock,
                output_lock,
            ): exp_name
            for exp_name, passes in missing.items()
        }

        for future in as_completed(futures):
            exp_name = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                print(f"\nError running {exp_name}: {e}", file=sys.stderr)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [(exp, rid) for exp, rid in all_results if rid]
    failed = [(exp, rid) for exp, rid in all_results if not rid]

    if successful:
        print(f"\nCompleted ({len(successful)}):")
        for exp, run_id in successful:
            print(f"  {exp.experiment_name} pass {exp.pass_number}: {run_id}")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for exp, _ in failed:
            print(f"  {exp.experiment_name} pass {exp.pass_number}")
        return 1

    print("\nAll experiments completed successfully!")
    print(f"Config updated: {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
