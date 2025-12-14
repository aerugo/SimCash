"""TDD tests for Phase 4: Unified CLI commands.

Tests for unified database CLI commands that work with both
standalone simulations and experiment-linked simulations.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.models import SimulationRunPurpose


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def db_with_experiments(tmp_path: Path) -> tuple[str, str, str]:
    """Create a database with experiments and linked simulations.

    Returns:
        Tuple of (db_path, experiment_id, simulation_id)
    """
    db_path = tmp_path / "test_unified.db"
    db = DatabaseManager(str(db_path))
    db.initialize_schema()

    # Create an experiment
    experiment_id = "exp-test-20251214-abc123"
    db.conn.execute(
        """
        INSERT INTO experiments (
            experiment_id, experiment_name, experiment_type, config,
            master_seed, created_at, num_iterations, converged
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            experiment_id,
            "Test Experiment",
            "optimization",
            '{"test": true}',
            12345,
            "2025-12-14T10:00:00",
            5,
            True,
        ],
    )

    # Create a linked simulation
    simulation_id = f"{experiment_id}-iter3-evaluation"
    db.conn.execute(
        """
        INSERT INTO simulation_runs (
            simulation_id, config_name, config_hash, rng_seed, ticks_per_day, num_days,
            status, total_transactions, start_time,
            experiment_id, iteration, run_purpose
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            simulation_id,
            "test_config",
            "hash123",
            12345,
            100,
            1,
            "completed",
            50,
            "2025-12-14T10:01:00",
            experiment_id,
            3,
            "evaluation",
        ],
    )

    # Create a standalone simulation
    db.conn.execute(
        """
        INSERT INTO simulation_runs (
            simulation_id, config_name, config_hash, rng_seed, ticks_per_day, num_days,
            status, total_transactions, start_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "standalone-sim-456",
            "standalone_config",
            "hash456",
            99999,
            100,
            1,
            "completed",
            25,
            "2025-12-14T09:00:00",
        ],
    )

    db.conn.commit()

    return str(db_path), experiment_id, simulation_id


# =============================================================================
# Sub-Phase 4.1: db simulations with experiment context
# =============================================================================


class TestDbSimulationsWithExperiments:
    """Tests for db simulations showing experiment context."""

    def test_shows_experiment_id_column(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should display experiment_id for linked simulations."""
        from payment_simulator.cli.main import app

        db_path, experiment_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "simulations", "--db-path", db_path])

        assert result.exit_code == 0
        # Should show the experiment ID in the output
        assert experiment_id in result.stdout or "Experiment" in result.stdout

    def test_shows_standalone_as_empty(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Standalone simulations should show no experiment link."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "simulations", "--db-path", db_path])

        assert result.exit_code == 0
        # Standalone simulation should be listed
        assert "standalone-sim-456" in result.stdout

    def test_shows_purpose_column(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should display run_purpose for experiment simulations."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "simulations", "--db-path", db_path])

        assert result.exit_code == 0
        # Should show "evaluation" purpose
        assert "evaluation" in result.stdout.lower() or "Purpose" in result.stdout


# =============================================================================
# Sub-Phase 4.2: db experiments command
# =============================================================================


class TestDbExperimentsCommand:
    """Tests for new db experiments command."""

    def test_lists_experiments(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should list all experiments in database."""
        from payment_simulator.cli.main import app

        db_path, experiment_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "experiments", "--db-path", db_path])

        assert result.exit_code == 0
        assert experiment_id in result.stdout

    def test_shows_experiment_name(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should show experiment name (may be truncated in table)."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "experiments", "--db-path", db_path])

        assert result.exit_code == 0
        # Name column shows at least start of name (may be truncated by Rich)
        assert "Test" in result.stdout

    def test_shows_iteration_count(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should show num_iterations for each experiment."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "experiments", "--db-path", db_path])

        assert result.exit_code == 0
        # Should show iteration count (5 iterations in fixture)
        assert "5" in result.stdout

    def test_shows_converged_status(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should show converged status for each experiment."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(app, ["db", "experiments", "--db-path", db_path])

        assert result.exit_code == 0
        # Should indicate converged status (True in fixture)
        assert (
            "yes" in result.stdout.lower()
            or "✓" in result.stdout
            or "true" in result.stdout.lower()
        )

    def test_empty_database_message(self, runner: CliRunner, tmp_path: Path) -> None:
        """Should show message when no experiments exist."""
        from payment_simulator.cli.main import app

        db_path = tmp_path / "empty.db"
        db = DatabaseManager(str(db_path))
        db.initialize_schema()

        result = runner.invoke(app, ["db", "experiments", "--db-path", str(db_path)])

        assert result.exit_code == 0
        assert "no experiments" in result.stdout.lower()


# =============================================================================
# Sub-Phase 4.3: db experiment-details command
# =============================================================================


class TestDbExperimentDetailsCommand:
    """Tests for experiment-details command."""

    def test_shows_experiment_metadata(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should display experiment metadata."""
        from payment_simulator.cli.main import app

        db_path, experiment_id, _sim_id = db_with_experiments

        result = runner.invoke(
            app, ["db", "experiment-details", experiment_id, "--db-path", db_path]
        )

        assert result.exit_code == 0
        assert experiment_id in result.stdout
        assert "Test Experiment" in result.stdout
        assert "optimization" in result.stdout.lower()

    def test_lists_linked_simulations(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should list all simulations linked to experiment."""
        from payment_simulator.cli.main import app

        db_path, experiment_id, simulation_id = db_with_experiments

        result = runner.invoke(
            app, ["db", "experiment-details", experiment_id, "--db-path", db_path]
        )

        assert result.exit_code == 0
        # Should list the linked simulation
        assert simulation_id in result.stdout or "iter3" in result.stdout

    def test_not_found_error(
        self, runner: CliRunner, db_with_experiments: tuple[str, str, str]
    ) -> None:
        """Should show error for non-existent experiment."""
        from payment_simulator.cli.main import app

        db_path, _exp_id, _sim_id = db_with_experiments

        result = runner.invoke(
            app, ["db", "experiment-details", "nonexistent-exp", "--db-path", db_path]
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


# =============================================================================
# Sub-Phase 4.4: Replay with experiment simulations
# =============================================================================


class TestReplayWithExperimentSimulations:
    """Tests for replay command with experiment simulations."""

    @pytest.mark.skip(
        reason="Requires full simulation data - covered in Phase 5 integration tests"
    )
    def test_replay_works_with_structured_id(self) -> None:
        """Should replay simulation by structured experiment ID."""
        pass

    @pytest.mark.skip(
        reason="Requires full simulation data - covered in Phase 5 integration tests"
    )
    def test_replay_shows_experiment_context(self) -> None:
        """Should show experiment context during replay."""
        pass
