"""Tests for config loading and validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import (
    IncompleteExperimentError,
    get_experiment_ids,
    get_pass_numbers,
    get_run_id,
    load_config,
    validate_runs_completed,
)


# =============================================================================
# Test config loading
# =============================================================================


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        """Should load config from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
databases:
  exp1: data/exp1.db
experiments:
  exp1:
    name: Test Experiment
    passes:
      1: run-id-1
      2: run-id-2
output:
  paper_filename: paper.tex
  charts_dir: charts
"""
        )

        config = load_config(config_file)

        assert "databases" in config
        assert "experiments" in config
        assert config["databases"]["exp1"] == "data/exp1.db"

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing config."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")


# =============================================================================
# Test config accessors
# =============================================================================


class TestConfigAccessors:
    """Tests for config accessor functions."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Create a sample config for testing."""
        return {
            "databases": {
                "exp1": "data/exp1.db",
                "exp2": "data/exp2.db",
            },
            "experiments": {
                "exp1": {
                    "name": "Experiment 1",
                    "passes": {
                        1: "exp1-run-1",
                        2: "exp1-run-2",
                        3: "exp1-run-3",
                    },
                },
                "exp2": {
                    "name": "Experiment 2",
                    "passes": {
                        1: "exp2-run-1",
                        2: "exp2-run-2",
                    },
                },
            },
        }

    def test_get_experiment_ids(self, sample_config: dict) -> None:
        """Should return list of experiment IDs."""
        ids = get_experiment_ids(sample_config)
        assert ids == ["exp1", "exp2"]

    def test_get_pass_numbers(self, sample_config: dict) -> None:
        """Should return list of pass numbers for experiment."""
        passes = get_pass_numbers(sample_config, "exp1")
        assert passes == [1, 2, 3]

        passes = get_pass_numbers(sample_config, "exp2")
        assert passes == [1, 2]

    def test_get_run_id(self, sample_config: dict) -> None:
        """Should return run_id for experiment pass."""
        assert get_run_id(sample_config, "exp1", 1) == "exp1-run-1"
        assert get_run_id(sample_config, "exp1", 2) == "exp1-run-2"
        assert get_run_id(sample_config, "exp2", 1) == "exp2-run-1"

    def test_get_run_id_invalid_experiment(self, sample_config: dict) -> None:
        """Should raise KeyError for invalid experiment."""
        with pytest.raises(KeyError, match="Experiment exp3 not found"):
            get_run_id(sample_config, "exp3", 1)

    def test_get_run_id_invalid_pass(self, sample_config: dict) -> None:
        """Should raise KeyError for invalid pass number."""
        with pytest.raises(KeyError, match="Pass 99 not found for exp1"):
            get_run_id(sample_config, "exp1", 99)


# =============================================================================
# Test validation
# =============================================================================


class TestValidateRunsCompleted:
    """Tests for validate_runs_completed()."""

    @pytest.fixture
    def sample_config(self) -> dict:
        """Create a sample config for testing."""
        return {
            "databases": {
                "exp1": "data/exp1.db",
            },
            "experiments": {
                "exp1": {
                    "name": "Experiment 1",
                    "passes": {
                        1: "run-completed",
                    },
                },
            },
        }

    def test_validate_completed_runs_pass(
        self, sample_config: dict, tmp_path: Path
    ) -> None:
        """Should pass validation when all runs are completed."""
        # Create mock database
        import duckdb

        db_dir = tmp_path / "data"
        db_dir.mkdir()
        db_path = db_dir / "exp1.db"

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE experiments (
                run_id VARCHAR PRIMARY KEY,
                completed_at VARCHAR
            )
        """
        )
        conn.execute(
            "INSERT INTO experiments VALUES ('run-completed', '2025-01-01T12:00:00')"
        )
        conn.close()

        # Should not raise
        validate_runs_completed(sample_config, tmp_path)

    def test_validate_incomplete_run_raises(
        self, sample_config: dict, tmp_path: Path
    ) -> None:
        """Should raise IncompleteExperimentError for incomplete runs."""
        # Create mock database with NULL completed_at
        import duckdb

        db_dir = tmp_path / "data"
        db_dir.mkdir()
        db_path = db_dir / "exp1.db"

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE experiments (
                run_id VARCHAR PRIMARY KEY,
                completed_at VARCHAR
            )
        """
        )
        conn.execute("INSERT INTO experiments VALUES ('run-completed', NULL)")
        conn.close()

        with pytest.raises(IncompleteExperimentError) as exc_info:
            validate_runs_completed(sample_config, tmp_path)

        assert "not completed" in str(exc_info.value)
        assert "run-completed" in str(exc_info.value)

    def test_validate_missing_run_raises(
        self, sample_config: dict, tmp_path: Path
    ) -> None:
        """Should raise ValueError for run_id not in database."""
        # Create mock database without the expected run_id
        import duckdb

        db_dir = tmp_path / "data"
        db_dir.mkdir()
        db_path = db_dir / "exp1.db"

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE experiments (
                run_id VARCHAR PRIMARY KEY,
                completed_at VARCHAR
            )
        """
        )
        conn.execute(
            "INSERT INTO experiments VALUES ('different-run', '2025-01-01T12:00:00')"
        )
        conn.close()

        with pytest.raises(ValueError) as exc_info:
            validate_runs_completed(sample_config, tmp_path)

        assert "not found in database" in str(exc_info.value)

    def test_validate_missing_database_raises(
        self, sample_config: dict, tmp_path: Path
    ) -> None:
        """Should raise FileNotFoundError for missing database."""
        # Don't create the database directory

        with pytest.raises(FileNotFoundError):
            validate_runs_completed(sample_config, tmp_path)


# =============================================================================
# Integration test with real config
# =============================================================================


class TestRealConfigValidation:
    """Integration tests using the real config.yaml."""

    @pytest.fixture
    def v5_dir(self) -> Path:
        """Get the v5 directory path."""
        return Path(__file__).parent.parent

    def test_real_config_loads(self, v5_dir: Path) -> None:
        """Real config.yaml should load successfully."""
        config_path = v5_dir / "config.yaml"
        if not config_path.exists():
            pytest.skip("config.yaml not found")

        config = load_config(config_path)

        assert "databases" in config
        assert "experiments" in config
        assert "exp1" in config["experiments"]
        assert "exp2" in config["experiments"]
        assert "exp3" in config["experiments"]

    def test_real_config_validation_passes(self, v5_dir: Path) -> None:
        """Real config should pass validation against real databases."""
        config_path = v5_dir / "config.yaml"
        data_dir = v5_dir / "data"

        if not config_path.exists():
            pytest.skip("config.yaml not found")
        if not (data_dir / "exp1.db").exists():
            pytest.skip("exp1.db not found")

        config = load_config(config_path)

        # Should not raise
        validate_runs_completed(config, v5_dir)
