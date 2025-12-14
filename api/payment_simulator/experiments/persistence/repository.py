"""Unified repository for experiment persistence.

Provides database operations for experiment runs, iterations, and events.
Supports any experiment type with flexible schema.

Phase 11, Task 11.2: Unified Persistence
Phase 2 Database Consolidation: Refactored to use DatabaseManager

All costs are integer cents (INV-1 compliance).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

if TYPE_CHECKING:
    from payment_simulator.experiments.runner.state_provider import (
        ExperimentStateProviderProtocol,
    )
    from payment_simulator.persistence.connection import DatabaseManager


# =============================================================================
# Record Dataclasses
# =============================================================================


@dataclass(frozen=True)
class ExperimentRecord:
    """Stored experiment record.

    Immutable record of experiment metadata.

    Phase 2 Database Consolidation: Uses experiment_id to match unified schema.

    Attributes:
        experiment_id: Unique experiment identifier (was run_id)
        experiment_name: Name of the experiment
        experiment_type: Type of experiment (e.g., "castro", "custom")
        config: Experiment configuration dict
        created_at: ISO timestamp when experiment started
        completed_at: ISO timestamp when experiment completed (optional)
        num_iterations: Total iterations (optional)
        converged: Whether experiment converged (optional)
        convergence_reason: Reason for stopping (optional)
        master_seed: RNG seed for determinism (INV-2)
        final_cost: Final total cost in cents (INV-1)
        best_cost: Best cost found in cents (INV-1)
    """

    experiment_id: str
    experiment_name: str
    experiment_type: str
    config: dict[str, Any]
    created_at: str
    completed_at: str | None
    num_iterations: int
    converged: bool
    convergence_reason: str | None
    master_seed: int = 0  # INV-2: Determinism
    final_cost: int | None = None  # INV-1: Integer cents
    best_cost: int | None = None  # INV-1: Integer cents

    # Backwards compatibility alias
    @property
    def run_id(self) -> str:
        """Alias for experiment_id (backwards compatibility)."""
        return self.experiment_id


@dataclass(frozen=True)
class IterationRecord:
    """Stored iteration record.

    All costs are integer cents (INV-1 compliance).
    Phase 2 Database Consolidation: Uses experiment_id to match unified schema.

    Attributes:
        experiment_id: Experiment identifier (was run_id)
        iteration: Iteration number (0-indexed)
        costs_per_agent: Dict mapping agent_id to cost in cents
        accepted_changes: Dict mapping agent_id to acceptance status
        policies: Dict mapping agent_id to policy dict
        timestamp: ISO timestamp
        evaluation_simulation_id: Link to simulation_runs (optional)
    """

    experiment_id: str
    iteration: int
    costs_per_agent: dict[str, int]
    accepted_changes: dict[str, bool]
    policies: dict[str, Any]
    timestamp: str
    evaluation_simulation_id: str | None = None

    # Backwards compatibility alias
    @property
    def run_id(self) -> str:
        """Alias for experiment_id (backwards compatibility)."""
        return self.experiment_id


@dataclass(frozen=True)
class EventRecord:
    """Stored event record.

    Phase 2 Database Consolidation: Uses experiment_id to match unified schema.

    Attributes:
        experiment_id: Experiment identifier (was run_id)
        iteration: Iteration number
        event_type: Type of event
        event_data: Event-specific data
        timestamp: ISO timestamp
    """

    experiment_id: str
    iteration: int
    event_type: str
    event_data: dict[str, Any]
    timestamp: str

    # Backwards compatibility alias
    @property
    def run_id(self) -> str:
        """Alias for experiment_id (backwards compatibility)."""
        return self.experiment_id


# =============================================================================
# Repository Implementation
# =============================================================================


class ExperimentRepository:
    """Unified repository for experiment persistence.

    Supports any experiment type with flexible schema.
    All costs are integer cents (INV-1 compliance).

    Phase 2 Database Consolidation: Can now be created from DatabaseManager
    to share the unified database schema.

    Example (standalone):
        >>> repo = ExperimentRepository(Path("experiments.db"))
        >>> repo.save_experiment(record)
        >>> loaded = repo.load_experiment("run-123")
        >>> repo.close()

    Example (with DatabaseManager - recommended):
        >>> from payment_simulator.persistence.connection import DatabaseManager
        >>> db_manager = DatabaseManager("unified.db")
        >>> db_manager.setup()
        >>> repo = ExperimentRepository.from_database_manager(db_manager)
        >>> repo.save_experiment(record)

    Or with context manager:
        >>> with ExperimentRepository(Path("experiments.db")) as repo:
        ...     repo.save_experiment(record)
    """

    def __init__(
        self,
        db_path: Path | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
        *,
        skip_schema_init: bool = False,
    ) -> None:
        """Initialize repository with database path or existing connection.

        Creates database file and tables if they don't exist.
        When using from_database_manager(), schema is already created.

        Args:
            db_path: Path to DuckDB database file (required if conn is None)
            conn: Existing DuckDB connection (optional, used by from_database_manager)
            skip_schema_init: Skip schema initialization (True when using DatabaseManager)
        """
        if conn is not None:
            self._conn = conn
            self._db_path = None
            self._owns_connection = False
        elif db_path is not None:
            self._db_path = db_path
            self._conn = duckdb.connect(str(db_path))
            self._owns_connection = True
        else:
            raise ValueError("Either db_path or conn must be provided")

        if not skip_schema_init:
            self._ensure_schema()

    @classmethod
    def from_database_manager(cls, db_manager: DatabaseManager) -> ExperimentRepository:
        """Create repository using DatabaseManager's connection.

        This is the recommended way to create an ExperimentRepository when
        using the unified database schema (Phase 2 Database Consolidation).

        The DatabaseManager is responsible for schema creation, so this
        repository will use the unified experiments/experiment_iterations/
        experiment_events tables.

        Args:
            db_manager: DatabaseManager with initialized schema

        Returns:
            ExperimentRepository using the manager's connection
        """
        return cls(conn=db_manager.conn, skip_schema_init=True)

    def _ensure_schema(self) -> None:
        """Create database tables if they don't exist.

        This creates a standalone schema compatible with the unified schema
        used by DatabaseManager. When using from_database_manager(), this
        method is skipped and DatabaseManager's schema is used instead.
        """
        # Create experiments table (matches unified schema)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id VARCHAR PRIMARY KEY,
                experiment_name VARCHAR NOT NULL,
                experiment_type VARCHAR NOT NULL,
                config JSON NOT NULL,
                scenario_path VARCHAR,
                master_seed BIGINT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                num_iterations INTEGER NOT NULL DEFAULT 0,
                converged BOOLEAN NOT NULL DEFAULT FALSE,
                convergence_reason VARCHAR,
                final_cost BIGINT,
                best_cost BIGINT
            )
        """)

        # Create iterations table (matches unified schema)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_iterations (
                experiment_id VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                costs_per_agent JSON NOT NULL,
                accepted_changes JSON NOT NULL,
                policies JSON NOT NULL,
                timestamp VARCHAR NOT NULL,
                evaluation_simulation_id VARCHAR,
                PRIMARY KEY (experiment_id, iteration)
            )
        """)

        # Create events table (matches unified schema)
        self._conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS experiment_events_id_seq START 1
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_events (
                id INTEGER DEFAULT nextval('experiment_events_id_seq') PRIMARY KEY,
                experiment_id VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                event_data JSON NOT NULL,
                timestamp VARCHAR NOT NULL
            )
        """)

        # Create indexes for performance
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_experiments_type
            ON experiments(experiment_type)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_iterations_exp
            ON experiment_iterations(experiment_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_exp_iter
            ON experiment_events(experiment_id, iteration)
        """)

    def close(self) -> None:
        """Close the database connection if we own it.

        When created from DatabaseManager, the connection is not closed
        here (DatabaseManager manages its lifecycle).
        """
        if self._conn is not None and self._owns_connection:
            self._conn.close()

    def __enter__(self) -> ExperimentRepository:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    # =========================================================================
    # Experiment Operations
    # =========================================================================

    def save_experiment(self, record: ExperimentRecord) -> None:
        """Save or update an experiment record.

        Uses INSERT OR REPLACE to handle both insert and update.

        Args:
            record: ExperimentRecord to persist
        """
        config_json = json.dumps(record.config)

        self._conn.execute(
            """
            INSERT OR REPLACE INTO experiments (
                experiment_id, experiment_name, experiment_type, config,
                master_seed, created_at, completed_at, num_iterations, converged,
                convergence_reason, final_cost, best_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.experiment_id,
                record.experiment_name,
                record.experiment_type,
                config_json,
                record.master_seed,
                record.created_at,
                record.completed_at,
                record.num_iterations,
                record.converged,
                record.convergence_reason,
                record.final_cost,
                record.best_cost,
            ],
        )

    def load_experiment(self, experiment_id: str) -> ExperimentRecord | None:
        """Load an experiment by experiment ID.

        Args:
            experiment_id: Experiment identifier (was run_id)

        Returns:
            ExperimentRecord if found, None otherwise
        """
        result = self._conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?",
            [experiment_id],
        ).fetchone()

        if result is None:
            return None

        return self._row_to_experiment_record(result)

    def list_experiments(
        self,
        experiment_type: str | None = None,
        experiment_name: str | None = None,
        limit: int = 100,
    ) -> list[ExperimentRecord]:
        """List experiments with optional filtering.

        Args:
            experiment_type: Filter by type (optional)
            experiment_name: Filter by name (optional)
            limit: Maximum results to return

        Returns:
            List of ExperimentRecord ordered by created_at descending
        """
        query = "SELECT * FROM experiments WHERE 1=1"
        params: list[Any] = []

        if experiment_type is not None:
            query += " AND experiment_type = ?"
            params.append(experiment_type)

        if experiment_name is not None:
            query += " AND experiment_name = ?"
            params.append(experiment_name)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results = self._conn.execute(query, params).fetchall()
        return [self._row_to_experiment_record(row) for row in results]

    def _row_to_experiment_record(self, row: tuple[Any, ...]) -> ExperimentRecord:
        """Convert database row to ExperimentRecord.

        Row order matches unified schema:
        experiment_id, experiment_name, experiment_type, config,
        scenario_path, master_seed, created_at, completed_at,
        num_iterations, converged, convergence_reason, final_cost, best_cost
        """
        config = row[3]
        if isinstance(config, str):
            config = json.loads(config)

        # Handle timestamp conversion (may be datetime or string)
        created_at = row[6]
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()

        completed_at = row[7]
        if completed_at is not None and hasattr(completed_at, 'isoformat'):
            completed_at = completed_at.isoformat()

        return ExperimentRecord(
            experiment_id=row[0],
            experiment_name=row[1],
            experiment_type=row[2],
            config=config,
            created_at=created_at,
            completed_at=completed_at,
            num_iterations=row[8] or 0,
            converged=bool(row[9]) if row[9] is not None else False,
            convergence_reason=row[10],
            master_seed=row[5] or 0,
            final_cost=row[11],
            best_cost=row[12],
        )

    # =========================================================================
    # Iteration Operations
    # =========================================================================

    def save_iteration(self, record: IterationRecord) -> None:
        """Save an iteration record.

        Args:
            record: IterationRecord to persist
        """
        costs_json = json.dumps(record.costs_per_agent)
        accepted_json = json.dumps(record.accepted_changes)
        policies_json = json.dumps(record.policies)

        self._conn.execute(
            """
            INSERT OR REPLACE INTO experiment_iterations (
                experiment_id, iteration, costs_per_agent, accepted_changes,
                policies, timestamp, evaluation_simulation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.experiment_id,
                record.iteration,
                costs_json,
                accepted_json,
                policies_json,
                record.timestamp,
                record.evaluation_simulation_id,
            ],
        )

    def get_iterations(self, experiment_id: str) -> list[IterationRecord]:
        """Get all iterations for an experiment.

        Args:
            experiment_id: Experiment identifier (was run_id)

        Returns:
            List of IterationRecord ordered by iteration number
        """
        results = self._conn.execute(
            """
            SELECT experiment_id, iteration, costs_per_agent, accepted_changes,
                   policies, timestamp, evaluation_simulation_id
            FROM experiment_iterations
            WHERE experiment_id = ?
            ORDER BY iteration
            """,
            [experiment_id],
        ).fetchall()

        return [self._row_to_iteration_record(row) for row in results]

    def _row_to_iteration_record(self, row: tuple[Any, ...]) -> IterationRecord:
        """Convert database row to IterationRecord.

        Row order: experiment_id, iteration, costs_per_agent, accepted_changes,
                   policies, timestamp, evaluation_simulation_id
        """
        costs = row[2]
        accepted = row[3]
        policies = row[4]

        # Parse JSON if needed
        if isinstance(costs, str):
            costs = json.loads(costs)
        if isinstance(accepted, str):
            accepted = json.loads(accepted)
        if isinstance(policies, str):
            policies = json.loads(policies)

        # Ensure costs are integers (INV-1)
        costs = {k: int(v) for k, v in costs.items()}

        return IterationRecord(
            experiment_id=row[0],
            iteration=row[1],
            costs_per_agent=costs,
            accepted_changes=accepted,
            policies=policies,
            timestamp=row[5],
            evaluation_simulation_id=row[6] if len(row) > 6 else None,
        )

    # =========================================================================
    # Event Operations
    # =========================================================================

    def save_event(self, event: EventRecord) -> None:
        """Save an event record.

        Args:
            event: EventRecord to persist
        """
        event_data_json = json.dumps(event.event_data)

        self._conn.execute(
            """
            INSERT INTO experiment_events (
                experiment_id, iteration, event_type, event_data, timestamp
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                event.experiment_id,
                event.iteration,
                event.event_type,
                event_data_json,
                event.timestamp,
            ],
        )

    def get_events(self, experiment_id: str, iteration: int) -> list[EventRecord]:
        """Get events for a specific iteration.

        Args:
            experiment_id: Experiment identifier (was run_id)
            iteration: Iteration number

        Returns:
            List of EventRecord for the iteration
        """
        results = self._conn.execute(
            """
            SELECT experiment_id, iteration, event_type, event_data, timestamp
            FROM experiment_events
            WHERE experiment_id = ? AND iteration = ?
            ORDER BY timestamp
            """,
            [experiment_id, iteration],
        ).fetchall()

        return [self._row_to_event_record(row) for row in results]

    def get_all_events(self, experiment_id: str) -> list[EventRecord]:
        """Get all events for an experiment.

        Args:
            experiment_id: Experiment identifier (was run_id)

        Returns:
            List of EventRecord ordered by iteration, timestamp
        """
        results = self._conn.execute(
            """
            SELECT experiment_id, iteration, event_type, event_data, timestamp
            FROM experiment_events
            WHERE experiment_id = ?
            ORDER BY iteration, timestamp
            """,
            [experiment_id],
        ).fetchall()

        return [self._row_to_event_record(row) for row in results]

    def _row_to_event_record(self, row: tuple[Any, ...]) -> EventRecord:
        """Convert database row to EventRecord.

        Row order: experiment_id, iteration, event_type, event_data, timestamp
        """
        event_data = row[3]
        if isinstance(event_data, str):
            event_data = json.loads(event_data)

        return EventRecord(
            experiment_id=row[0],
            iteration=row[1],
            event_type=row[2],
            event_data=event_data,
            timestamp=row[4],
        )

    # =========================================================================
    # StateProvider Integration
    # =========================================================================

    def as_state_provider(self, experiment_id: str) -> ExperimentStateProviderProtocol:
        """Create a StateProvider for replay.

        Returns a DatabaseStateProvider wrapping this repository.

        Args:
            experiment_id: Experiment identifier to load (was run_id)

        Returns:
            ExperimentStateProviderProtocol implementation
        """
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        return DatabaseStateProvider(self, experiment_id)
