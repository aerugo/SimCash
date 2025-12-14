"""Tests for unified database schema.

Phase 2 of database consolidation: Verify that DatabaseManager creates
a unified schema that supports both simulations and experiments.

TDD: These tests are written first, then implementation follows.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb
import pytest


class TestUnifiedSchemaCreation:
    """Tests for unified schema creation by DatabaseManager."""

    @pytest.fixture
    def db_manager(self) -> "DatabaseManager":  # type: ignore[name-defined]
        """Create DatabaseManager with temporary database."""
        from payment_simulator.persistence.connection import DatabaseManager

        # Create a unique temp path without creating the file
        db_path = Path(tempfile.gettempdir()) / f"test_unified_{id(self)}.db"
        db_path.unlink(missing_ok=True)  # Ensure clean start

        manager = DatabaseManager(db_path)
        manager.initialize_schema()
        yield manager
        manager.close()
        db_path.unlink(missing_ok=True)

    def test_experiments_table_created(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify experiments table is created by DatabaseManager."""
        # Check table exists
        result = db_manager.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'experiments'"
        ).fetchone()
        assert result is not None
        assert result[0] == 1, "experiments table should exist"

        # Check required columns
        columns = db_manager.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experiments'"
        ).fetchall()
        column_names = {col[0] for col in columns}

        required_columns = {
            "experiment_id",
            "experiment_name",
            "experiment_type",
            "config",
            "created_at",
            "completed_at",
            "num_iterations",
            "converged",
            "convergence_reason",
        }
        assert required_columns.issubset(column_names), (
            f"Missing columns: {required_columns - column_names}"
        )

    def test_experiment_iterations_table_created(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify experiment_iterations table is created by DatabaseManager."""
        # Check table exists
        result = db_manager.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'experiment_iterations'"
        ).fetchone()
        assert result is not None
        assert result[0] == 1, "experiment_iterations table should exist"

        # Check required columns
        columns = db_manager.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experiment_iterations'"
        ).fetchall()
        column_names = {col[0] for col in columns}

        required_columns = {
            "experiment_id",
            "iteration",
            "costs_per_agent",
            "accepted_changes",
            "policies",
            "timestamp",
            "evaluation_simulation_id",
        }
        assert required_columns.issubset(column_names), (
            f"Missing columns: {required_columns - column_names}"
        )

    def test_experiment_events_table_created(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify experiment_events table is created by DatabaseManager."""
        # Check table exists
        result = db_manager.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'experiment_events'"
        ).fetchone()
        assert result is not None
        assert result[0] == 1, "experiment_events table should exist"

        # Check required columns
        columns = db_manager.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experiment_events'"
        ).fetchall()
        column_names = {col[0] for col in columns}

        required_columns = {
            "experiment_id",
            "iteration",
            "event_type",
            "event_data",
            "timestamp",
        }
        assert required_columns.issubset(column_names), (
            f"Missing columns: {required_columns - column_names}"
        )

    def test_simulation_runs_has_experiment_columns(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify simulation_runs has experiment linkage columns."""
        columns = db_manager.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'simulation_runs'"
        ).fetchall()
        column_names = {col[0] for col in columns}

        # New experiment linkage columns
        experiment_columns = {
            "experiment_id",
            "iteration",
            "sample_index",
            "run_purpose",
        }
        assert experiment_columns.issubset(column_names), (
            f"Missing experiment columns in simulation_runs: {experiment_columns - column_names}"
        )


class TestExperimentSimulationLinkage:
    """Tests for experiment → simulation linking."""

    @pytest.fixture
    def db_manager(self) -> "DatabaseManager":  # type: ignore[name-defined]
        """Create DatabaseManager with temporary database."""
        from payment_simulator.persistence.connection import DatabaseManager

        # Create a unique temp path without creating the file
        db_path = Path(tempfile.gettempdir()) / f"test_unified_{id(self)}.db"
        db_path.unlink(missing_ok=True)  # Ensure clean start

        manager = DatabaseManager(db_path)
        manager.initialize_schema()
        yield manager
        manager.close()
        db_path.unlink(missing_ok=True)

    def test_simulation_can_reference_experiment(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify simulation_runs can link to experiments table."""
        conn = db_manager.conn

        # Insert an experiment (include all required fields)
        conn.execute("""
            INSERT INTO experiments (
                experiment_id, experiment_name, experiment_type, config, created_at,
                master_seed, num_iterations, converged
            )
            VALUES ('exp-123', 'test_exp', 'castro', '{}', '2025-01-01T00:00:00', 12345, 0, false)
        """)

        # Insert a simulation linked to the experiment
        conn.execute("""
            INSERT INTO simulation_runs (
                simulation_id, experiment_id, iteration, run_purpose,
                config_name, config_hash, rng_seed, ticks_per_day, num_days,
                status, start_time, total_transactions
            )
            VALUES (
                'sim-exp-123-iter0-eval', 'exp-123', 0, 'evaluation',
                'test.yaml', 'hash123', 12345, 100, 1, 'completed', '2025-01-01T00:00:00', 0
            )
        """)

        # Query the link
        result = conn.execute("""
            SELECT s.simulation_id, e.experiment_name
            FROM simulation_runs s
            JOIN experiments e ON s.experiment_id = e.experiment_id
            WHERE s.simulation_id = 'sim-exp-123-iter0-eval'
        """).fetchone()

        assert result is not None
        assert result[0] == "sim-exp-123-iter0-eval"
        assert result[1] == "test_exp"

    def test_iteration_can_reference_simulation(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify experiment_iterations can link to simulation_runs."""
        conn = db_manager.conn

        # Insert an experiment (include all required fields)
        conn.execute("""
            INSERT INTO experiments (
                experiment_id, experiment_name, experiment_type, config, created_at,
                master_seed, num_iterations, converged
            )
            VALUES ('exp-456', 'test_exp', 'castro', '{}', '2025-01-01T00:00:00', 12345, 0, false)
        """)

        # Insert a simulation
        conn.execute("""
            INSERT INTO simulation_runs (
                simulation_id, experiment_id, iteration, run_purpose,
                config_name, config_hash, rng_seed, ticks_per_day, num_days,
                status, start_time, total_transactions
            )
            VALUES (
                'sim-exp-456-iter5-eval', 'exp-456', 5, 'evaluation',
                'test.yaml', 'hash456', 12345, 100, 1, 'completed', '2025-01-01T00:00:00', 0
            )
        """)

        # Insert an iteration linked to the simulation
        conn.execute("""
            INSERT INTO experiment_iterations (
                experiment_id, iteration, costs_per_agent, accepted_changes,
                policies, timestamp, evaluation_simulation_id
            )
            VALUES (
                'exp-456', 5, '{"BANK_A": 10000}', '{"BANK_A": true}',
                '{}', '2025-01-01T00:00:00', 'sim-exp-456-iter5-eval'
            )
        """)

        # Query the link
        result = conn.execute("""
            SELECT i.iteration, s.simulation_id
            FROM experiment_iterations i
            JOIN simulation_runs s ON i.evaluation_simulation_id = s.simulation_id
            WHERE i.experiment_id = 'exp-456' AND i.iteration = 5
        """).fetchone()

        assert result is not None
        assert result[0] == 5
        assert result[1] == "sim-exp-456-iter5-eval"


class TestInvariantCompliance:
    """Tests for critical invariants in unified schema."""

    @pytest.fixture
    def db_manager(self) -> "DatabaseManager":  # type: ignore[name-defined]
        """Create DatabaseManager with temporary database."""
        from payment_simulator.persistence.connection import DatabaseManager

        # Create a unique temp path without creating the file
        db_path = Path(tempfile.gettempdir()) / f"test_unified_{id(self)}.db"
        db_path.unlink(missing_ok=True)  # Ensure clean start

        manager = DatabaseManager(db_path)
        manager.initialize_schema()
        yield manager
        manager.close()
        db_path.unlink(missing_ok=True)

    def test_experiment_costs_are_integer_cents_inv1(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """INV-1: Costs in experiments should support integer cents."""
        conn = db_manager.conn

        # Insert experiment with integer cost (include all required fields)
        conn.execute("""
            INSERT INTO experiments (
                experiment_id, experiment_name, experiment_type, config, created_at,
                master_seed, num_iterations, converged, final_cost, best_cost
            )
            VALUES ('exp-inv1', 'test', 'castro', '{}', '2025-01-01T00:00:00', 12345, 0, false, 1234567, 1000000)
        """)

        # Verify costs are stored correctly
        result = conn.execute(
            "SELECT final_cost, best_cost FROM experiments WHERE experiment_id = 'exp-inv1'"
        ).fetchone()

        assert result is not None
        assert result[0] == 1234567, "final_cost should be integer cents"
        assert result[1] == 1000000, "best_cost should be integer cents"

    def test_iteration_costs_json_contains_integers_inv1(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """INV-1: costs_per_agent JSON should contain integer cents."""
        conn = db_manager.conn

        # Insert experiment first (include all required fields)
        conn.execute("""
            INSERT INTO experiments (
                experiment_id, experiment_name, experiment_type, config, created_at,
                master_seed, num_iterations, converged
            )
            VALUES ('exp-iter-inv1', 'test', 'castro', '{}', '2025-01-01T00:00:00', 12345, 0, false)
        """)

        # Insert iteration with integer costs in JSON
        costs = {"BANK_A": 5000000, "BANK_B": 3000000}  # 50000.00 and 30000.00 in cents
        conn.execute(
            """
            INSERT INTO experiment_iterations (
                experiment_id, iteration, costs_per_agent, accepted_changes, policies, timestamp
            )
            VALUES (?, 0, ?, '{}', '{}', '2025-01-01T00:00:00')
            """,
            ["exp-iter-inv1", json.dumps(costs)],
        )

        # Retrieve and verify
        result = conn.execute(
            "SELECT costs_per_agent FROM experiment_iterations WHERE experiment_id = 'exp-iter-inv1'"
        ).fetchone()

        assert result is not None
        loaded_costs = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        assert loaded_costs["BANK_A"] == 5000000
        assert loaded_costs["BANK_B"] == 3000000

    def test_seeds_stored_for_determinism_inv2(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """INV-2: master_seed should be stored in experiments table."""
        # Check column exists
        columns = db_manager.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experiments'"
        ).fetchall()
        column_names = {col[0] for col in columns}

        assert "master_seed" in column_names, "experiments should have master_seed column"

        # Verify we can store and retrieve a seed (all required fields included)
        db_manager.conn.execute("""
            INSERT INTO experiments (
                experiment_id, experiment_name, experiment_type, config, created_at,
                master_seed, num_iterations, converged
            )
            VALUES ('exp-seed', 'test', 'castro', '{}', '2025-01-01T00:00:00', 9876543210, 0, false)
        """)

        result = db_manager.conn.execute(
            "SELECT master_seed FROM experiments WHERE experiment_id = 'exp-seed'"
        ).fetchone()

        assert result is not None
        assert result[0] == 9876543210


class TestExperimentRepositoryWithDatabaseManager:
    """Tests for ExperimentRepository using DatabaseManager.

    Note: These tests are for Phase 2.6 - ExperimentRepository refactoring.
    """

    @pytest.fixture
    def db_manager(self) -> "DatabaseManager":  # type: ignore[name-defined]
        """Create DatabaseManager with temporary database."""
        from payment_simulator.persistence.connection import DatabaseManager

        # Create a unique temp path without creating the file
        db_path = Path(tempfile.gettempdir()) / f"test_unified_{id(self)}.db"
        db_path.unlink(missing_ok=True)  # Ensure clean start

        manager = DatabaseManager(db_path)
        manager.initialize_schema()
        yield manager
        manager.close()
        db_path.unlink(missing_ok=True)

    @pytest.mark.skip(reason="Phase 2.6: ExperimentRepository.from_database_manager not yet implemented")
    def test_experiment_repository_uses_database_manager(self, db_manager: "DatabaseManager") -> None:  # type: ignore[name-defined]
        """Verify ExperimentRepository can use DatabaseManager connection."""
        from payment_simulator.experiments.persistence.repository import (
            ExperimentRecord,
            ExperimentRepository,
        )

        # Create repository with DatabaseManager
        repo = ExperimentRepository.from_database_manager(db_manager)

        # Save an experiment
        record = ExperimentRecord(
            run_id="test-run-123",
            experiment_name="test_experiment",
            experiment_type="castro",
            config={"test": "config"},
            created_at="2025-01-01T00:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repo.save_experiment(record)

        # Load and verify
        loaded = repo.load_experiment("test-run-123")
        assert loaded is not None
        assert loaded.experiment_name == "test_experiment"
        assert loaded.experiment_type == "castro"
