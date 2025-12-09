"""Repository for experiment event persistence.

Provides database operations for experiment runs and events.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb

from castro.events import ExperimentEvent
from castro.persistence.models import ExperimentRunRecord


class ExperimentEventRepository:
    """Repository for experiment event database operations.

    Provides CRUD operations for experiment runs and events.

    Example:
        >>> conn = duckdb.connect("experiments.db")
        >>> repo = ExperimentEventRepository(conn)
        >>> repo.initialize_schema()
        >>> repo.save_event(event)
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Initialize repository with database connection.

        Args:
            conn: DuckDB connection
        """
        self._conn = conn

    def initialize_schema(self) -> None:
        """Initialize database tables for experiment persistence.

        Creates experiment_runs and experiment_events tables if they don't exist.
        Safe to call multiple times.
        """
        # Create experiment_runs table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_runs (
                run_id VARCHAR PRIMARY KEY,
                experiment_name VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                status VARCHAR NOT NULL,
                final_cost INTEGER,
                best_cost INTEGER,
                num_iterations INTEGER,
                converged BOOLEAN,
                convergence_reason VARCHAR,
                model VARCHAR,
                master_seed BIGINT,
                config_json VARCHAR
            )
        """)

        # Create experiment_events table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_events (
                event_id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                details JSON NOT NULL
            )
        """)

        # Create indexes
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_experiment
            ON experiment_runs(experiment_name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_started_at
            ON experiment_runs(started_at)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_run_id
            ON experiment_events(run_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_iteration
            ON experiment_events(run_id, iteration)
        """)

    # =========================================================================
    # Run Record Operations
    # =========================================================================

    def save_run_record(self, record: ExperimentRunRecord) -> None:
        """Save or update an experiment run record.

        Args:
            record: ExperimentRunRecord to persist
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO experiment_runs (
                run_id, experiment_name, started_at, completed_at, status,
                final_cost, best_cost, num_iterations, converged,
                convergence_reason, model, master_seed, config_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.run_id,
                record.experiment_name,
                record.started_at,
                record.completed_at,
                record.status,
                record.final_cost,
                record.best_cost,
                record.num_iterations,
                record.converged,
                record.convergence_reason,
                record.model,
                record.master_seed,
                record.config_json,
            ],
        )

    def get_run_record(self, run_id: str) -> ExperimentRunRecord | None:
        """Retrieve an experiment run by ID.

        Args:
            run_id: Run identifier

        Returns:
            ExperimentRunRecord if found, None otherwise
        """
        result = self._conn.execute(
            "SELECT * FROM experiment_runs WHERE run_id = ?",
            [run_id],
        ).fetchone()

        if result is None:
            return None

        return self._row_to_run_record(result)

    def update_run_status(
        self,
        run_id: str,
        status: str,
        completed_at: datetime | None = None,
        final_cost: int | None = None,
        best_cost: int | None = None,
        num_iterations: int | None = None,
        converged: bool | None = None,
        convergence_reason: str | None = None,
    ) -> None:
        """Update run status and completion fields.

        Args:
            run_id: Run identifier
            status: New status value
            completed_at: Completion timestamp (optional)
            final_cost: Final cost (optional)
            best_cost: Best cost (optional)
            num_iterations: Total iterations (optional)
            converged: Whether converged (optional)
            convergence_reason: Reason for stopping (optional)
        """
        updates = ["status = ?"]
        params: list[Any] = [status]

        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)

        if final_cost is not None:
            updates.append("final_cost = ?")
            params.append(final_cost)

        if best_cost is not None:
            updates.append("best_cost = ?")
            params.append(best_cost)

        if num_iterations is not None:
            updates.append("num_iterations = ?")
            params.append(num_iterations)

        if converged is not None:
            updates.append("converged = ?")
            params.append(converged)

        if convergence_reason is not None:
            updates.append("convergence_reason = ?")
            params.append(convergence_reason)

        params.append(run_id)

        # Field names are hardcoded above, not from user input
        self._conn.execute(
            f"UPDATE experiment_runs SET {', '.join(updates)} WHERE run_id = ?",  # noqa: S608
            params,
        )

    def list_runs(
        self,
        experiment_filter: str | None = None,
        limit: int = 100,
    ) -> list[ExperimentRunRecord]:
        """List experiment runs with optional filtering.

        Args:
            experiment_filter: Filter by experiment name (optional)
            limit: Maximum results to return

        Returns:
            List of ExperimentRunRecord ordered by started_at descending
        """
        query = "SELECT * FROM experiment_runs WHERE 1=1"
        params: list[Any] = []

        if experiment_filter is not None:
            query += " AND experiment_name = ?"
            params.append(experiment_filter)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        results = self._conn.execute(query, params).fetchall()
        return [self._row_to_run_record(row) for row in results]

    def _row_to_run_record(self, row: tuple[Any, ...]) -> ExperimentRunRecord:
        """Convert database row to ExperimentRunRecord."""
        return ExperimentRunRecord(
            run_id=row[0],
            experiment_name=row[1],
            started_at=row[2],
            completed_at=row[3],
            status=row[4],
            final_cost=row[5],
            best_cost=row[6],
            num_iterations=row[7],
            converged=row[8],
            convergence_reason=row[9],
            model=row[10],
            master_seed=row[11],
            config_json=row[12],
        )

    # =========================================================================
    # Event Operations
    # =========================================================================

    def save_event(self, event: ExperimentEvent) -> None:
        """Save an experiment event.

        Args:
            event: ExperimentEvent to persist
        """
        event_id = str(uuid.uuid4())
        details_json = json.dumps(event.details)

        self._conn.execute(
            """
            INSERT INTO experiment_events (
                event_id, run_id, event_type, iteration, timestamp, details
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                event.run_id,
                event.event_type,
                event.iteration,
                event.timestamp,
                details_json,
            ],
        )

    def save_events_batch(self, events: list[ExperimentEvent]) -> None:
        """Save multiple events efficiently.

        Args:
            events: List of ExperimentEvent to persist
        """
        for event in events:
            self.save_event(event)

    def get_events_for_run(self, run_id: str) -> Iterator[ExperimentEvent]:
        """Get all events for a run.

        Args:
            run_id: Run identifier

        Yields:
            ExperimentEvent instances ordered by iteration, timestamp
        """
        query = """
            SELECT event_type, run_id, iteration, timestamp, details
            FROM experiment_events
            WHERE run_id = ?
            ORDER BY iteration, timestamp
        """

        results = self._conn.execute(query, [run_id]).fetchall()
        for row in results:
            yield self._row_to_event(row)

    def get_events_for_iteration(
        self,
        run_id: str,
        iteration: int,
    ) -> Iterator[ExperimentEvent]:
        """Get events for a specific iteration.

        Args:
            run_id: Run identifier
            iteration: Iteration number

        Yields:
            ExperimentEvent instances for the specified iteration
        """
        query = """
            SELECT event_type, run_id, iteration, timestamp, details
            FROM experiment_events
            WHERE run_id = ? AND iteration = ?
            ORDER BY timestamp
        """

        results = self._conn.execute(query, [run_id, iteration]).fetchall()
        for row in results:
            yield self._row_to_event(row)

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
