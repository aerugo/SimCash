"""State provider protocol for experiment replay identity.

Defines a common interface for accessing experiment state, implemented by:
- LiveExperimentProvider (wraps live execution)
- DatabaseExperimentProvider (wraps database for replay)

This enables unified display functions that work identically in both modes.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import duckdb

from castro.events import ExperimentEvent


# =============================================================================
# Protocol Definition
# =============================================================================


@runtime_checkable
class ExperimentStateProvider(Protocol):
    """Protocol for accessing experiment state.

    This interface is implemented by both:
    - LiveExperimentProvider (live execution)
    - DatabaseExperimentProvider (replay from database)

    Enables unified display functions that work identically in both modes.
    """

    @property
    def run_id(self) -> str:
        """Get the run ID."""
        ...

    def get_run_metadata(self) -> dict[str, Any] | None:
        """Get run metadata.

        Returns:
            Dict with keys: run_id, experiment_name, description, model, etc.
            Returns None if run not found.
        """
        ...

    def get_all_events(self) -> Iterator[ExperimentEvent]:
        """Get all events in order.

        Yields:
            ExperimentEvent instances ordered by iteration, timestamp
        """
        ...

    def get_events_for_iteration(self, iteration: int) -> list[ExperimentEvent]:
        """Get events for a specific iteration.

        Args:
            iteration: Iteration number

        Returns:
            List of ExperimentEvent for the iteration
        """
        ...

    def get_final_result(self) -> dict[str, Any]:
        """Get final experiment result.

        Returns:
            Dict with keys: final_cost, best_cost, converged, etc.
        """
        ...


# =============================================================================
# Live Implementation
# =============================================================================


class LiveExperimentProvider:
    """StateProvider wrapping live experiment execution.

    Captures events during execution for both:
    - Live display (immediate feedback)
    - Database persistence (for replay)
    """

    def __init__(
        self,
        run_id: str,
        experiment_name: str,
        description: str,
        model: str,
        max_iterations: int,
        num_samples: int,
    ) -> None:
        """Initialize live provider.

        Args:
            run_id: Unique run identifier
            experiment_name: Name of experiment
            description: Human-readable description
            model: LLM model string
            max_iterations: Maximum iterations
            num_samples: Monte Carlo sample count
        """
        self._run_id = run_id
        self._experiment_name = experiment_name
        self._description = description
        self._model = model
        self._max_iterations = max_iterations
        self._num_samples = num_samples
        self._events: list[ExperimentEvent] = []
        self._final_result: dict[str, Any] = {}

    @property
    def run_id(self) -> str:
        """Get the run ID."""
        return self._run_id

    def get_run_metadata(self) -> dict[str, Any]:
        """Get run metadata."""
        return {
            "run_id": self._run_id,
            "experiment_name": self._experiment_name,
            "description": self._description,
            "model": self._model,
            "max_iterations": self._max_iterations,
            "num_samples": self._num_samples,
        }

    def capture_event(self, event: ExperimentEvent) -> None:
        """Capture an event during execution.

        Args:
            event: Event to capture
        """
        self._events.append(event)

    def get_all_events(self) -> Iterator[ExperimentEvent]:
        """Get all captured events."""
        return iter(self._events)

    def get_events_for_iteration(self, iteration: int) -> list[ExperimentEvent]:
        """Get events for a specific iteration."""
        return [e for e in self._events if e.iteration == iteration]

    def set_final_result(
        self,
        final_cost: int,
        best_cost: int,
        converged: bool,
        convergence_reason: str,
        num_iterations: int,
        duration_seconds: float,
    ) -> None:
        """Set the final experiment result.

        Args:
            final_cost: Final cost (cents)
            best_cost: Best cost achieved (cents)
            converged: Whether experiment converged
            convergence_reason: Reason for stopping
            num_iterations: Total iterations
            duration_seconds: Total duration
        """
        self._final_result = {
            "final_cost": final_cost,
            "best_cost": best_cost,
            "converged": converged,
            "convergence_reason": convergence_reason,
            "num_iterations": num_iterations,
            "duration_seconds": duration_seconds,
        }

    def get_final_result(self) -> dict[str, Any]:
        """Get the final result."""
        return self._final_result


# =============================================================================
# Database Implementation
# =============================================================================


class DatabaseExperimentProvider:
    """StateProvider wrapping database queries for replay.

    Reads from pre-persisted experiment data to provide the same
    interface as LiveExperimentProvider.
    """

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        run_id: str,
    ) -> None:
        """Initialize database provider.

        Args:
            conn: DuckDB database connection
            run_id: Run identifier to load
        """
        self._conn = conn
        self._run_id = run_id
        self._run_record: dict[str, Any] | None = None
        self._load_run_record()

    def _load_run_record(self) -> None:
        """Load run record from database."""
        result = self._conn.execute(
            "SELECT * FROM experiment_runs WHERE run_id = ?",
            [self._run_id],
        ).fetchone()

        if result is None:
            self._run_record = None
            return

        self._run_record = {
            "run_id": result[0],
            "experiment_name": result[1],
            "started_at": result[2],
            "completed_at": result[3],
            "status": result[4],
            "final_cost": result[5],
            "best_cost": result[6],
            "num_iterations": result[7],
            "converged": result[8],
            "convergence_reason": result[9],
            "model": result[10],
            "master_seed": result[11],
            "config_json": result[12],
        }

    @property
    def run_id(self) -> str:
        """Get the run ID."""
        return self._run_id

    def get_run_metadata(self) -> dict[str, Any] | None:
        """Get run metadata from database."""
        if self._run_record is None:
            return None

        return {
            "run_id": self._run_record["run_id"],
            "experiment_name": self._run_record["experiment_name"],
            "model": self._run_record["model"],
            "started_at": self._run_record["started_at"],
            "status": self._run_record["status"],
        }

    def get_all_events(self) -> Iterator[ExperimentEvent]:
        """Get all events from database."""
        query = """
            SELECT event_type, run_id, iteration, timestamp, details
            FROM experiment_events
            WHERE run_id = ?
            ORDER BY iteration, timestamp
        """

        results = self._conn.execute(query, [self._run_id]).fetchall()
        for row in results:
            yield self._row_to_event(row)

    def get_events_for_iteration(self, iteration: int) -> list[ExperimentEvent]:
        """Get events for a specific iteration from database."""
        query = """
            SELECT event_type, run_id, iteration, timestamp, details
            FROM experiment_events
            WHERE run_id = ? AND iteration = ?
            ORDER BY timestamp
        """

        results = self._conn.execute(query, [self._run_id, iteration]).fetchall()
        return [self._row_to_event(row) for row in results]

    def get_final_result(self) -> dict[str, Any]:
        """Get final result from database."""
        if self._run_record is None:
            return {}

        return {
            "final_cost": self._run_record["final_cost"],
            "best_cost": self._run_record["best_cost"],
            "converged": self._run_record["converged"],
            "convergence_reason": self._run_record["convergence_reason"],
            "num_iterations": self._run_record["num_iterations"],
        }

    def _row_to_event(self, row: tuple[Any, ...]) -> ExperimentEvent:
        """Convert database row to ExperimentEvent."""
        details = row[4]
        if isinstance(details, str):
            details = json.loads(details)

        return ExperimentEvent(
            event_type=row[0],
            run_id=row[1],
            iteration=row[2],
            timestamp=row[3],
            details=details,
        )


# =============================================================================
# Event Emitter (bridges capture and persistence)
# =============================================================================


class EventEmitter:
    """Emits events to both provider (for display) and database (for replay).

    This is the bridge between live execution and persistence.
    When an event is emitted:
    1. It's captured in the provider (for immediate display)
    2. It's persisted to the database (for future replay)
    """

    def __init__(
        self,
        provider: LiveExperimentProvider,
        repo: Any,  # ExperimentEventRepository
    ) -> None:
        """Initialize event emitter.

        Args:
            provider: Live provider to capture events
            repo: Repository for database persistence
        """
        self._provider = provider
        self._repo = repo

    def emit(self, event: ExperimentEvent) -> None:
        """Emit an event.

        Captures in provider and persists to database.

        Args:
            event: Event to emit
        """
        # Capture for live display
        self._provider.capture_event(event)

        # Persist for replay
        self._repo.save_event(event)
