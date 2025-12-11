"""Tests for experiment state provider pattern.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import duckdb
import pytest


class TestExperimentStateProviderProtocol:
    """Test ExperimentStateProvider protocol compliance."""

    def test_protocol_defined(self) -> None:
        """ExperimentStateProvider protocol is defined."""
        from castro.state_provider import ExperimentStateProvider

        # Should be importable
        assert ExperimentStateProvider is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """ExperimentStateProvider can be used with isinstance()."""
        from castro.state_provider import (
            DatabaseExperimentProvider,
            ExperimentStateProvider,
            LiveExperimentProvider,
        )

        # Both implementations should satisfy the protocol
        # We'll test this more fully when we have instances


class TestLiveExperimentProvider:
    """Test LiveExperimentProvider (wraps live runner)."""

    def test_live_provider_creation(self) -> None:
        """LiveExperimentProvider can be created."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test experiment",
            model="anthropic:claude-sonnet-4-5",
            max_iterations=25,
            num_samples=5,
        )

        assert provider.run_id == "exp1-20251209-143022-a1b2c3"

    def test_live_provider_get_run_metadata(self) -> None:
        """LiveExperimentProvider.get_run_metadata returns metadata."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test experiment",
            model="anthropic:claude-sonnet-4-5",
            max_iterations=25,
            num_samples=5,
        )

        metadata = provider.get_run_metadata()

        assert metadata["run_id"] == "exp1-20251209-143022-a1b2c3"
        assert metadata["experiment_name"] == "exp1"
        assert metadata["description"] == "Test experiment"
        assert metadata["model"] == "anthropic:claude-sonnet-4-5"

    def test_live_provider_capture_event(self) -> None:
        """LiveExperimentProvider.capture_event stores events."""
        from castro.event_compat import CastroEvent as ExperimentEvent
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test",
            model="test",
            max_iterations=25,
            num_samples=5,
        )

        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={"total_cost": 15000},
        )

        provider.capture_event(event)

        events = list(provider.get_all_events())
        assert len(events) == 1
        assert events[0].event_type == "iteration_start"

    def test_live_provider_get_events_for_iteration(self) -> None:
        """LiveExperimentProvider.get_events_for_iteration filters by iteration."""
        from castro.event_compat import CastroEvent as ExperimentEvent
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test",
            model="test",
            max_iterations=25,
            num_samples=5,
        )

        # Add events for multiple iterations
        for iteration in range(3):
            event = ExperimentEvent(
                event_type="iteration_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=iteration,
                timestamp=datetime.now(),
                details={},
            )
            provider.capture_event(event)

        iter1_events = provider.get_events_for_iteration(1)
        assert len(iter1_events) == 1
        assert iter1_events[0].iteration == 1

    def test_live_provider_set_final_result(self) -> None:
        """LiveExperimentProvider.set_final_result stores result."""
        from castro.state_provider import LiveExperimentProvider

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test",
            model="test",
            max_iterations=25,
            num_samples=5,
        )

        provider.set_final_result(
            final_cost=12000,
            best_cost=11500,
            converged=True,
            convergence_reason="stability_reached",
            num_iterations=10,
            duration_seconds=120.5,
        )

        result = provider.get_final_result()
        assert result["final_cost"] == 12000
        assert result["best_cost"] == 11500
        assert result["converged"] is True


class TestDatabaseExperimentProvider:
    """Test DatabaseExperimentProvider (wraps database)."""

    @pytest.fixture
    def db_conn(self) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DuckDB connection."""
        return duckdb.connect(":memory:")

    @pytest.fixture
    def repo_with_data(self, db_conn: duckdb.DuckDBPyConnection) -> Any:
        """Create a repository with test data."""
        from castro.event_compat import CastroEvent as ExperimentEvent
        from castro.persistence import ExperimentEventRepository, ExperimentRunRecord

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()

        # Save a run record
        record = ExperimentRunRecord(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            started_at=datetime(2025, 12, 9, 14, 30, 22),
            status="completed",
            final_cost=12000,
            best_cost=11500,
            num_iterations=10,
            converged=True,
            convergence_reason="stability_reached",
            model="anthropic:claude-sonnet-4-5",
        )
        repo.save_run_record(record)

        # Save events
        for i in range(3):
            event = ExperimentEvent(
                event_type="iteration_start",
                run_id="exp1-20251209-143022-a1b2c3",
                iteration=i,
                timestamp=datetime(2025, 12, 9, 14, 30, 22 + i),
                details={"total_cost": 15000 - i * 1000},
            )
            repo.save_event(event)

        return repo

    def test_database_provider_creation(
        self, db_conn: duckdb.DuckDBPyConnection, repo_with_data: Any
    ) -> None:
        """DatabaseExperimentProvider can be created."""
        from castro.state_provider import DatabaseExperimentProvider

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="exp1-20251209-143022-a1b2c3",
        )

        assert provider.run_id == "exp1-20251209-143022-a1b2c3"

    def test_database_provider_get_run_metadata(
        self, db_conn: duckdb.DuckDBPyConnection, repo_with_data: Any
    ) -> None:
        """DatabaseExperimentProvider.get_run_metadata queries database."""
        from castro.state_provider import DatabaseExperimentProvider

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="exp1-20251209-143022-a1b2c3",
        )

        metadata = provider.get_run_metadata()

        assert metadata["run_id"] == "exp1-20251209-143022-a1b2c3"
        assert metadata["experiment_name"] == "exp1"
        assert metadata["model"] == "anthropic:claude-sonnet-4-5"

    def test_database_provider_get_all_events(
        self, db_conn: duckdb.DuckDBPyConnection, repo_with_data: Any
    ) -> None:
        """DatabaseExperimentProvider.get_all_events returns events from database."""
        from castro.state_provider import DatabaseExperimentProvider

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="exp1-20251209-143022-a1b2c3",
        )

        events = list(provider.get_all_events())

        assert len(events) == 3
        # Should be ordered by iteration
        for i, event in enumerate(events):
            assert event.iteration == i

    def test_database_provider_get_events_for_iteration(
        self, db_conn: duckdb.DuckDBPyConnection, repo_with_data: Any
    ) -> None:
        """DatabaseExperimentProvider.get_events_for_iteration filters correctly."""
        from castro.state_provider import DatabaseExperimentProvider

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="exp1-20251209-143022-a1b2c3",
        )

        events = provider.get_events_for_iteration(1)

        assert len(events) == 1
        assert events[0].iteration == 1

    def test_database_provider_get_final_result(
        self, db_conn: duckdb.DuckDBPyConnection, repo_with_data: Any
    ) -> None:
        """DatabaseExperimentProvider.get_final_result returns result from database."""
        from castro.state_provider import DatabaseExperimentProvider

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="exp1-20251209-143022-a1b2c3",
        )

        result = provider.get_final_result()

        assert result["final_cost"] == 12000
        assert result["best_cost"] == 11500
        assert result["converged"] is True
        assert result["convergence_reason"] == "stability_reached"

    def test_database_provider_run_not_found(
        self, db_conn: duckdb.DuckDBPyConnection
    ) -> None:
        """DatabaseExperimentProvider raises error for nonexistent run."""
        from castro.persistence import ExperimentEventRepository
        from castro.state_provider import DatabaseExperimentProvider

        # Initialize schema but don't add any data
        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()

        provider = DatabaseExperimentProvider(
            conn=db_conn,
            run_id="nonexistent-run",
        )

        # Should return None for metadata when run doesn't exist
        metadata = provider.get_run_metadata()
        assert metadata is None


class TestEventEmitter:
    """Test EventEmitter for capturing events during run."""

    @pytest.fixture
    def db_conn(self) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DuckDB connection."""
        return duckdb.connect(":memory:")

    def test_event_emitter_creation(self, db_conn: duckdb.DuckDBPyConnection) -> None:
        """EventEmitter can be created."""
        from castro.persistence import ExperimentEventRepository
        from castro.state_provider import EventEmitter, LiveExperimentProvider

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test",
            model="test",
            max_iterations=25,
            num_samples=5,
        )

        emitter = EventEmitter(
            provider=provider,
            repo=repo,
        )

        assert emitter is not None

    def test_event_emitter_emit_captures_and_persists(
        self, db_conn: duckdb.DuckDBPyConnection
    ) -> None:
        """EventEmitter.emit captures event and persists to database."""
        from castro.event_compat import CastroEvent as ExperimentEvent
        from castro.persistence import ExperimentEventRepository
        from castro.state_provider import EventEmitter, LiveExperimentProvider

        repo = ExperimentEventRepository(db_conn)
        repo.initialize_schema()

        provider = LiveExperimentProvider(
            run_id="exp1-20251209-143022-a1b2c3",
            experiment_name="exp1",
            description="Test",
            model="test",
            max_iterations=25,
            num_samples=5,
        )

        emitter = EventEmitter(provider=provider, repo=repo)

        event = ExperimentEvent(
            event_type="iteration_start",
            run_id="exp1-20251209-143022-a1b2c3",
            iteration=1,
            timestamp=datetime.now(),
            details={"total_cost": 15000},
        )

        emitter.emit(event)

        # Should be in provider (for live display)
        events_in_provider = list(provider.get_all_events())
        assert len(events_in_provider) == 1

        # Should be in database (for replay)
        events_in_db = list(repo.get_events_for_run("exp1-20251209-143022-a1b2c3"))
        assert len(events_in_db) == 1
