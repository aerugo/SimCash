"""Configuration loader for paper generation.

Loads explicit run_id mappings from config.yaml to ensure reproducible
paper generation without relying on database ordering.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import duckdb
import yaml


class ExperimentConfig(TypedDict):
    """Configuration for a single experiment."""

    name: str
    passes: dict[int, str]  # pass_num -> run_id


class OutputConfig(TypedDict):
    """Output configuration."""

    paper_filename: str
    charts_dir: str


class PaperConfig(TypedDict):
    """Complete paper generation configuration."""

    databases: dict[str, str]  # exp_id -> relative path
    experiments: dict[str, ExperimentConfig]
    output: OutputConfig


def load_config(config_path: Path | None = None) -> PaperConfig:
    """Load paper generation configuration.

    Args:
        config_path: Path to config.yaml. If None, uses default location.

    Returns:
        PaperConfig with database paths and run_id mappings

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    if config_path is None:
        # Default to config.yaml in v5 directory
        config_path = Path(__file__).parent.parent / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config


def get_run_id(config: PaperConfig, exp_id: str, pass_num: int) -> str:
    """Get run_id for a specific experiment pass from config.

    Args:
        config: Loaded paper configuration
        exp_id: Experiment identifier (exp1, exp2, exp3)
        pass_num: Pass number (1, 2, or 3)

    Returns:
        Run ID string

    Raises:
        KeyError: If exp_id or pass_num not found in config
    """
    if exp_id not in config["experiments"]:
        raise KeyError(f"Experiment {exp_id} not found in config")

    passes = config["experiments"][exp_id]["passes"]
    if pass_num not in passes:
        raise KeyError(
            f"Pass {pass_num} not found for {exp_id}. "
            f"Available: {list(passes.keys())}"
        )

    return passes[pass_num]


def get_db_path(config: PaperConfig, exp_id: str, base_dir: Path) -> Path:
    """Get database path for an experiment.

    Args:
        config: Loaded paper configuration
        exp_id: Experiment identifier
        base_dir: Base directory (v5/ directory)

    Returns:
        Absolute path to database file

    Raises:
        KeyError: If exp_id not found in config
    """
    if exp_id not in config["databases"]:
        raise KeyError(f"Database for {exp_id} not found in config")

    return base_dir / config["databases"][exp_id]


def get_experiment_ids(config: PaperConfig) -> list[str]:
    """Get list of experiment IDs from config.

    Args:
        config: Loaded paper configuration

    Returns:
        List of experiment IDs (e.g., ["exp1", "exp2", "exp3"])
    """
    return list(config["experiments"].keys())


def get_pass_numbers(config: PaperConfig, exp_id: str) -> list[int]:
    """Get list of pass numbers for an experiment.

    Args:
        config: Loaded paper configuration
        exp_id: Experiment identifier

    Returns:
        List of pass numbers (e.g., [1, 2, 3])
    """
    return list(config["experiments"][exp_id]["passes"].keys())


class IncompleteExperimentError(Exception):
    """Raised when an experiment run referenced in config is not completed."""

    pass


def validate_runs_completed(config: PaperConfig, base_dir: Path) -> None:
    """Validate that all experiment runs in config have completed status.

    Checks each run_id in the config against the database to ensure
    it has a completed_at timestamp set.

    Args:
        config: Loaded paper configuration
        base_dir: Base directory containing database files (v5/ directory)

    Raises:
        IncompleteExperimentError: If any run_id is not completed
        FileNotFoundError: If a database file doesn't exist
        ValueError: If a run_id doesn't exist in the database
    """
    incomplete_runs: list[str] = []

    for exp_id in get_experiment_ids(config):
        db_path = get_db_path(config, exp_id, base_dir)

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            for pass_num in get_pass_numbers(config, exp_id):
                run_id = get_run_id(config, exp_id, pass_num)

                result = conn.execute(
                    """
                    SELECT completed_at
                    FROM experiments
                    WHERE run_id = ?
                    """,
                    [run_id],
                ).fetchone()

                if result is None:
                    raise ValueError(
                        f"Run {run_id} not found in database {db_path}. "
                        f"Check that the run_id in config.yaml is correct."
                    )

                completed_at = result[0]
                if completed_at is None:
                    incomplete_runs.append(
                        f"  - {exp_id} pass {pass_num}: {run_id}"
                    )
        finally:
            conn.close()

    if incomplete_runs:
        runs_list = "\n".join(incomplete_runs)
        raise IncompleteExperimentError(
            f"Cannot generate paper: the following experiment runs are not completed:\n"
            f"{runs_list}\n\n"
            f"Please wait for all experiments to complete before generating the paper, "
            f"or update config.yaml to reference completed runs."
        )
