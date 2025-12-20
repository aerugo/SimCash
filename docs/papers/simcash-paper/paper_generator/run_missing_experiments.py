#!/usr/bin/env python3
"""
Run missing experiments from config.yaml.

This script reads the paper generator config.yaml, validates experiment
configurations, and runs experiments with empty run_ids. Before running,
it displays a validation summary showing:
- Which databases exist and which run_ids are verified
- Which new databases will be created
- Which experiments will be run
- Warnings for referenced run_ids that don't exist in their databases

Experiments for the same database run sequentially (to avoid lock conflicts),
while different experiments run in parallel.

Usage:
    # Validate configuration and run missing experiments
    python run_missing_experiments.py config.yaml

    # Validate only (no confirmation, no running)
    python run_missing_experiments.py config.yaml --validate-only

    # Dry run - show what would happen
    python run_missing_experiments.py config.yaml --dry-run

    # Skip confirmation prompt
    python run_missing_experiments.py config.yaml --yes
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

import duckdb
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
    """Save config.yaml with proper formatting.

    This function preserves the file's comments and formatting by using
    line-by-line replacement within each experiment's section.
    """
    with open(config_path) as f:
        lines = f.readlines()

    # Process line by line, tracking which experiment section we're in
    current_experiment: str | None = None
    in_passes_section = False
    result_lines: list[str] = []

    for line in lines:
        # Check if we're entering a new experiment section (e.g., "  exp1:")
        exp_match = re.match(r'^  (\w+):$', line)
        if exp_match:
            exp_name = exp_match.group(1)
            if exp_name in config["experiments"]:
                current_experiment = exp_name
                in_passes_section = False
            else:
                current_experiment = None
            result_lines.append(line)
            continue

        # Check if we're entering the passes section
        if current_experiment and re.match(r'^\s+passes:\s*$', line):
            in_passes_section = True
            result_lines.append(line)
            continue

        # Check if we're leaving the passes section (new key at same or lower indent)
        if in_passes_section and re.match(r'^\s{0,6}\S', line) and not re.match(r'^\s+\d+:', line):
            in_passes_section = False

        # Update pass lines within the correct experiment section
        if current_experiment and in_passes_section:
            pass_match = re.match(r'^(\s+)(\d+):\s*"[^"]*"(.*)$', line)
            if pass_match:
                indent = pass_match.group(1)
                pass_num = int(pass_match.group(2))
                trailing = pass_match.group(3)  # Preserve any trailing comments
                exp_passes = config["experiments"][current_experiment]["passes"]
                if pass_num in exp_passes and exp_passes[pass_num]:
                    run_id = exp_passes[pass_num]
                    line = f'{indent}{pass_num}: "{run_id}"{trailing}\n'

        result_lines.append(line)

    with open(config_path, "w") as f:
        f.writelines(result_lines)


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


@dataclass
class ExperimentValidation:
    """Result of validating an experiment configuration."""

    experiment_name: str
    pass_number: int
    run_id: str
    db_path: Path
    db_exists: bool
    run_id_exists: bool | None  # None if db doesn't exist


@dataclass
class ValidationSummary:
    """Summary of all validation results."""

    existing_runs: list[ExperimentValidation]  # Populated run_ids that exist
    missing_runs: list[ExperimentValidation]  # Populated run_ids that don't exist
    new_experiments: list[MissingExperiment]  # Empty run_ids (will be created)
    new_databases: set[Path]  # Databases that don't exist yet


def check_run_id_exists(db_path: Path, run_id: str) -> bool:
    """Check if a run_id exists in the experiments table.

    Args:
        db_path: Path to the database file
        run_id: Experiment run ID to check

    Returns:
        True if run_id exists in database
    """
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        result = conn.execute(
            "SELECT 1 FROM experiments WHERE run_id = ? LIMIT 1",
            [run_id],
        ).fetchone()
        conn.close()
        return result is not None
    except duckdb.CatalogException:
        # Table doesn't exist
        return False
    except Exception:
        return False


def validate_experiments(
    config: dict, config_dir: Path
) -> ValidationSummary:
    """Validate all experiment configurations.

    Checks:
    1. Which databases exist
    2. Which referenced run_ids exist in their databases
    3. Which experiments are missing (empty run_id)

    Args:
        config: Loaded config.yaml
        config_dir: Directory containing config.yaml

    Returns:
        ValidationSummary with categorized results
    """
    existing_runs: list[ExperimentValidation] = []
    missing_runs: list[ExperimentValidation] = []
    new_experiments: list[MissingExperiment] = []
    new_databases: set[Path] = set()

    for exp_name, exp_data in config["experiments"].items():
        db_path = config_dir / config["databases"][exp_name]
        config_path = config_dir / "configs" / f"{exp_name}.yaml"
        db_exists = db_path.exists()

        if not db_exists:
            new_databases.add(db_path)

        for pass_num, run_id in exp_data["passes"].items():
            if not run_id:  # Empty string means needs to be run
                new_experiments.append(
                    MissingExperiment(
                        experiment_name=exp_name,
                        pass_number=int(pass_num),
                        config_path=config_path,
                        db_path=db_path,
                    )
                )
            else:
                # Check if the referenced run_id exists
                if db_exists:
                    run_id_exists = check_run_id_exists(db_path, run_id)
                else:
                    run_id_exists = None  # Can't check - DB doesn't exist

                validation = ExperimentValidation(
                    experiment_name=exp_name,
                    pass_number=int(pass_num),
                    run_id=run_id,
                    db_path=db_path,
                    db_exists=db_exists,
                    run_id_exists=run_id_exists,
                )

                if run_id_exists is True:
                    existing_runs.append(validation)
                else:
                    missing_runs.append(validation)

    # Sort for consistent output
    new_experiments.sort(key=lambda x: (x.experiment_name, x.pass_number))
    existing_runs.sort(key=lambda v: (v.experiment_name, v.pass_number))
    missing_runs.sort(key=lambda v: (v.experiment_name, v.pass_number))

    return ValidationSummary(
        existing_runs=existing_runs,
        missing_runs=missing_runs,
        new_experiments=new_experiments,
        new_databases=new_databases,
    )


def print_validation_summary(summary: ValidationSummary) -> bool:
    """Print validation summary and return whether to proceed.

    Args:
        summary: Validation results

    Returns:
        True if there are issues that should block execution
    """
    has_errors = False

    print("\n" + "=" * 70)
    print("EXPERIMENT VALIDATION SUMMARY")
    print("=" * 70)

    # Section 1: Existing databases and verified run_ids
    if summary.existing_runs:
        print(f"\n✓ VERIFIED ({len(summary.existing_runs)} passes):")
        print("  These run_ids exist in their databases:")
        for v in summary.existing_runs:
            print(f"    {v.experiment_name} pass {v.pass_number}: {v.run_id}")
            print(f"      └── {v.db_path}")

    # Section 2: New databases that will be created
    if summary.new_databases:
        print(f"\n📁 NEW DATABASES ({len(summary.new_databases)}):")
        print("  These databases will be created:")
        for db_path in sorted(summary.new_databases):
            print(f"    {db_path}")

    # Section 3: Experiments that will be run
    if summary.new_experiments:
        # Group by experiment name
        by_exp: dict[str, list[MissingExperiment]] = {}
        for exp in summary.new_experiments:
            if exp.experiment_name not in by_exp:
                by_exp[exp.experiment_name] = []
            by_exp[exp.experiment_name].append(exp)

        print(f"\n🔄 TO BE RUN ({len(summary.new_experiments)} passes):")
        for exp_name in sorted(by_exp.keys()):
            passes = by_exp[exp_name]
            db_path = passes[0].db_path
            db_status = "NEW" if db_path in summary.new_databases else "exists"
            pass_nums = ", ".join(str(p.pass_number) for p in passes)
            print(f"    {exp_name} passes [{pass_nums}]")
            print(f"      └── {db_path} ({db_status})")

    # Section 4: WARNINGS - referenced run_ids that don't exist
    if summary.missing_runs:
        has_errors = True
        print(f"\n⚠️  WARNINGS ({len(summary.missing_runs)} issues):")
        print("  These run_ids are referenced but NOT FOUND:")
        for v in summary.missing_runs:
            if v.db_exists:
                print(f"    {v.experiment_name} pass {v.pass_number}: {v.run_id}")
                print(f"      └── NOT FOUND in {v.db_path}")
            else:
                print(f"    {v.experiment_name} pass {v.pass_number}: {v.run_id}")
                print(f"      └── DATABASE DOES NOT EXIST: {v.db_path}")

    print("\n" + "=" * 70)

    # Summary counts
    total_passes = (
        len(summary.existing_runs)
        + len(summary.missing_runs)
        + len(summary.new_experiments)
    )
    print(f"Total: {total_passes} passes configured")
    print(f"  ✓ Verified: {len(summary.existing_runs)}")
    print(f"  🔄 To run: {len(summary.new_experiments)}")
    if summary.missing_runs:
        print(f"  ⚠️  Missing: {len(summary.missing_runs)}")
    print("=" * 70 + "\n")

    return has_errors


def run_experiment(
    exp: MissingExperiment,
    api_dir: Path,
    output_prefix: str,
    lock: threading.Lock,
    verbose: bool = False,
) -> tuple[MissingExperiment, str | None, str]:
    """
    Run a single experiment and return (experiment, run_id, output).

    Args:
        exp: The missing experiment to run.
        api_dir: Path to the api directory containing payment-sim.
        output_prefix: Prefix for output lines (e.g., "exp1:P1").
        lock: Threading lock for synchronized output.
        verbose: If True, enable verbose experiment output.

    Returns None for run_id if experiment failed.
    """
    cmd = [
        str(api_dir / ".venv" / "bin" / "payment-sim"),
        "experiment",
        "run",
        str(exp.config_path),
        "--db",
        str(exp.db_path),
    ]
    if verbose:
        cmd.insert(3, "--verbose")

    output_lines: list[str] = []
    run_id: str | None = None

    with lock:
        print(f"\n{'='*60}")
        print(f"[{output_prefix}] Starting {exp.experiment_name} pass {exp.pass_number}")
        print(f"{'='*60}")
        sys.stdout.flush()

    # Run from project root so Rust can find simulator/policies/ directory
    project_root = api_dir.parent

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=project_root,
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
    verbose: bool = False,
) -> list[tuple[MissingExperiment, str | None]]:
    """
    Run a sequence of experiments for the same database (sequentially).

    Updates config.yaml after each successful run.

    Args:
        experiments: List of experiments for the same database.
        api_dir: Path to the api directory containing payment-sim.
        config_path: Path to config.yaml to update after each run.
        config: The loaded config dict to update.
        config_lock: Threading lock for config file updates.
        output_lock: Threading lock for synchronized output.
        verbose: If True, enable verbose experiment output.
    """
    results: list[tuple[MissingExperiment, str | None]] = []
    exp_name = experiments[0].experiment_name

    for exp in experiments:
        prefix = f"{exp.experiment_name}:P{exp.pass_number}"
        exp_result, run_id, _ = run_experiment(exp, api_dir, prefix, output_lock, verbose)
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
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and proceed automatically",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the configuration, don't run experiments",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose experiment output (shows iteration details, LLM calls, etc.)",
    )

    args = parser.parse_args()

    config_path = args.config.resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 1

    config_dir = config_path.parent

    # Load config and validate all experiments first
    config = load_config(config_path)
    summary = validate_experiments(config, config_dir)

    # Print validation summary
    has_warnings = print_validation_summary(summary)

    # Handle validate-only mode
    if args.validate_only:
        if has_warnings:
            print("Validation completed with warnings.")
            return 1
        print("Validation completed successfully.")
        return 0

    # Check if there's anything to run
    if not summary.new_experiments:
        print("All experiments are complete! Nothing to run.")
        return 0

    # Handle dry-run mode
    if args.dry_run:
        print("[DRY RUN] Would run the above experiments")
        return 0

    # Warn about missing run_ids but allow proceeding
    if has_warnings:
        print("Note: Some referenced run_ids were not found in their databases.")
        print("This may indicate data loss or configuration errors.\n")

    # Confirmation prompt (unless --yes flag is used)
    if not args.yes:
        try:
            response = input(f"Proceed with running {len(summary.new_experiments)} experiment(s)? [y/N] ")
            if response.lower() not in ("y", "yes"):
                print("Aborted.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 0

    # Find api directory - paper_generator is at docs/papers/simcash-paper/paper_generator
    # So api is at ../../../../api relative to config_dir
    api_dir = (config_dir / ".." / ".." / ".." / ".." / "api").resolve()

    # Fallback: search upward for SimCash/api
    if not api_dir.exists():
        search_dir = config_dir
        while search_dir.parent != search_dir:
            if (search_dir / "api" / ".venv" / "bin" / "payment-sim").exists():
                api_dir = search_dir / "api"
                break
            search_dir = search_dir.parent

    payment_sim = api_dir / ".venv" / "bin" / "payment-sim"
    if not payment_sim.exists():
        print(f"Error: payment-sim not found at {payment_sim}", file=sys.stderr)
        print(f"Searched in: {api_dir}", file=sys.stderr)
        print("Make sure you've run 'uv sync' in the api directory", file=sys.stderr)
        return 1

    # Group experiments by experiment name (for parallel execution)
    missing = find_missing_experiments(config, config_dir)

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
                args.verbose,
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
