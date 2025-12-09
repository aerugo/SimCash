"""Tests for experiment event persistence.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest


class TestExperimentRunRecord:
    """Test ExperimentRunRecord model."""

    def test_run_record_creation(self) -> None:
        """ExperimentRunRecord can be created with required fields."""
        from castro.persistence import ExperimentRunRecord

        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime.now(),
            status="running",
        )

        assert record.run_id == "exp1-20251209-143022-a1b2c3"
        assert record.experiment_name == "exp1"
        assert record.status == "running"

    def test_run_record_optional_fields_default_to_none(self) -> None:
        """ExperimentRunRecord optional fields default to None."""
        from castro.persistence import ExperimentRunRecord

        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime.now(),
            status="running",
        )

        assert record.completed_at is None
        assert record.final_cost is None
        assert record.best_cost is None
        assert record.num_iterations is None
        assert record.converged is None
        assert record.convergence_reason is None


class TestExperimentEventRepository:
    """Test ExperimentEventRepository database operations."""

    @pytest.fixture
    def db_conn(self) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DuckDB connection."""
        return duckdb.connect(":memory:")

    @pytest.fixture
    def repo(self, db_conn: duckdb.DuckDBPyConnection) -> Any:
        """Create a repository with initialized schema."""
        from castro.persistence import ExperimentEventRepository

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()
        return repo

    def test_initialize_schema_creates_tables(
        self, db_conn: duckdb.DuckDBPyConnection
    ) -> None:
        """initialize_schema creates required tables."""
        from castro.persistence import ExperimentEventRepository

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()

        # Check tables exist
        tables = db_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "experiment_runs" in table_names
        assert "experiment_events" in table_names

    def test_save_run_record(self, repo: Any) -> None:
        """save_run_record persists a run record."""
        from castro.persistence import ExperimentRunRecord

        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 14, 30, 22),
            status="running",
            model="anthropic:claude-sonnet-4-5",
            master_seed=42,
        )

        repo.save_run_record(record)

        # Verify it was saved
        result = repo._conn.execute(
            "SELECT * FROM experiment_runs WHERE run_id = ?",
            ["exp1-20251209-143022-a1b2c3"],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp1-20251209-143022-a1b2c3"
        assert result[1] == "exp1"

    def test_get_run_record(self, repo: Any) -> None:
        """get_run_record retrieves a run record."""
        from castro.persistence import ExperimentRunRecord

        # Save a record
        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 14, 30, 22),
            status="running",
            model="anthropic:claude-sonnet-4-5",
            master_seed=42,
        )
        repo.save_run_record(record)

        # Retrieve it
        retrieved = repo.get_run_record("exp1-20251209-143022-a1b2c3")

        assert retrieved is not None
        assert retrieved.run_id == "exp1-20251209-143022-a1b2c3"
        assert retrieved.experiment_name == "exp1"
        assert retrieved.model == "anthropic:claude-sonnet-4-5"
        assert retrieved.master_seed == 42

    def test_get_run_record_not_found_returns_none(self, repo: Any) -> None:
        """get_run_record returns None for nonexistent run."""
        retrieved = repo.get_run_record("nonexistent-run-id")
        assert retrieved is None

    def test_update_run_status(self, repo: Any) -> None:
        """update_run_status updates run completion fields."""
        from castro.persistence import ExperimentRunRecord

        # Save initial record
        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 14, 30, 22),
            status="running",
        )
        repo.save_run_record(record)

        # Update status
        completed_at = datetime(2025, 12, 9, 14, 35, 0)
        repo.update_run_status(
            run_id="exp1-20251209-143022-a1b2c3",
            status="converged",
            completed_at=completed_at,
            final_cost=12000,
            best_cost=11500,
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
        )

        # Verify update
        retrieved = repo.get_run_record("exp1-20251209-143022-a1b2c3")
        assert retrieved is not None
        assert retrieved.status == "converged"
        assert retrieved.completed_at == completed_at
        assert retrieved.final_cost == 12000
        assert retrieved.best_cost == 11500
        assert retrieved.num_iterations == 10
        assert retrieved.converged is True
        assert retrieved.convergence_reason == "stability_reached"

    def test_list_runs(self, repo: Any) -> None:
        """list_runs returns all runs ordered by started_at."""
        from castro.persistence import ExperimentRunRecord

        # Save multiple records
        for i in range(3):
            record = ExperimentRunRecord(
                run_id=f"exp1-2025120{i}-143022-abc{i}",
                experiment_name="exp1",
                started_at=datetime(2025, 12, i + 1, 14, 30, 22),
                status="completed",
            )
            repo.save_run_record(record)

        runs = repo.list_runs()

        assert len(runs) == 3
        # Should be ordered by started_at descending
        assert runs[0].run_id == "exp1-20251202-143022-abc2"
        assert runs[1].run_id == "exp1-20251201-143022-abc1"
        assert runs[2].run_id == "exp1-20251200-143022-abc0"

    def test_list_runs_filter_by_experiment(self, repo: Any) -> None:
        """list_runs can filter by experiment name."""
        from castro.persistence import ExperimentRunRecord

        # Save records for different experiments with unique run_ids
        records = [
            ("exp1", "exp1-20251209-143022-aaa111"),
            ("exp2", "exp2-20251209-143022-bbb222"),
            ("exp1", "exp1-20251209-143023-ccc333"),  # Second exp1 run
        ]
        for exp, run_id in records:
            record = ExperimentRunRecord(
                run_id=run_id,
                experiment_name=exp,
                started_at=datetime.now(),
                status="completed",
            )
            repo.save_run_record(record)

        exp1_runs = repo.list_runs(experiment_filter="exp1")

        assert len(exp1_runs) == 2
        assert all(r.experiment_name == "exp1" for r in exp1_runs)


class TestEventPersistence:
    """Test event persistence operations."""

    @pytest.fixture
    def db_conn(self) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DuckDB connection."""
        return duckdb.connect(":memory:")

    @pytest.fixture
    def repo(self, db_conn: duckdb.DuckDBPyConnection) -> Any:
        """Create a repository with initialized schema."""
        from castro.persistence import ExperimentEventRepository

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()
        return repo

    def test_save_event(self, repo: Any) -> None:
        """save_event persists an event."""
        from castro.events import ExperimentEvent

        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime(2025, 12, 9, 14, 30, 22),
            details={"total_cost": 15000},
        )

        repo.save_event(event)

        # Verify it was saved
        result = repo._conn.execute(
            "SELECT COUNT(*) FROM experiment_events WHERE run_id = ?",
            ["exp1-20251209-143022-a1b2c3"],
        ).fetchone()

        assert result is not None
        assert result[0] == 1

    def test_save_events_batch(self, repo: Any) -> None:
        """save_events_batch persists multiple events efficiently."""
        from castro.events import ExperimentEvent

        events = [
            ExperimentEvent(
                event_type="iteration_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=i,
                timestamp=datetime(2025, 12, 9, 14, 30, 22 + i),
                details={"total_cost": 15000 - i * 100},
            )
            for i in range(10)
        ]

        repo.save_events_batch(events)

        # Verify all were saved
        result = repo._conn.execute(
            "SELECT COUNT(*) FROM experiment_events WHERE run_id = ?",
            ["exp1-20251209-143022-a1b2c3"],
        ).fetchone()

        assert result is not None
        assert result[0] == 10

    def test_get_events_for_run(self, repo: Any) -> None:
        """get_events_for_run retrieves all events for a run."""
        from castro.events import ExperimentEvent

        # Save events
        for i in range(5):
            event = ExperimentEvent(
                event_type="iteration_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=i,
                timestamp=datetime(2025, 12, 9, 14, 30, 22 + i),
                details={"total_cost": 15000 - i * 100},
            )
            repo.save_event(event)

        events = list(repo.get_events_for_run("exp1-20251209-143022-a1b2c3"))

        assert len(events) == 5
        # Should be ordered by iteration, timestamp
        for i, event in enumerate(events):
            assert event.iteration == i

    def test_get_events_for_iteration(self, repo: Any) -> None:
        """get_events_for_iteration retrieves events for specific iteration."""
        from castro.events import ExperimentEvent

        # Save events for multiple iterations
        for iteration in range(3):
            for event_type in ["iteration_start", "llm_call", "policy_change"]:
                event = ExperimentEvent(
                    event_type=event_type,
                    run_id="exp1-20251209-143022-a1b2c3",
                    iteration=iteration,
                    timestamp=datetime.now(),
                    details={},
                )
                repo.save_event(event)

        events = list(repo.get_events_for_iteration("exp1-20251209-143022-a1b2c3", 1))

        assert len(events) == 3
        assert all(e.iteration == 1 for e in events)

    def test_event_details_serialization(self, repo: Any) -> None:
        """Complex event details serialize and deserialize correctly."""
        from castro.events import ExperimentEvent

        complex_details = {
            "seed_results": [
                {"seed": 42, "cost": 15000, "nested": {"a": 1, "b": [1, 2, 3]}},
                {"seed": 43, "cost": 16000, "nested": {"a": 2, "b": [4, 5, 6]}},
            ],
            "mean_cost": 15500,
            "policy": {"parameters": {"threshold": 3.0}},
        }

        event = ExperimentEvent(
            event_type="monte_carlo_evaluation",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime(2025, 12, 9, 14, 30, 22),
            details=complex_details,
        )

        repo.save_event(event)

        # Retrieve and verify
        events = list(repo.get_events_for_run("exp1-20251209-143022-a1b2c3"))
        assert len(events) == 1

        retrieved = events[0]
        assert retrieved.details["seed_results"] == complex_details["seed_results"]
        assert retrieved.details["mean_cost"] == 15500
        assert retrieved.details["policy"]["parameters"]["threshold"] == 3.0
