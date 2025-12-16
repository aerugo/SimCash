"""Unified repository for experiment persistence.

Provides database operations for experiment runs, iterations, and events.
Supports any experiment type with flexible schema.

Phase 11, Task 11.2: Unified Persistence

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
    from payment_simulator.persistence.simulation_persistence_provider import (
        StandardSimulationPersistenceProvider,
    )


# =============================================================================
# Record Dataclasses
# =============================================================================


@dataclass(frozen=True)
class ExperimentRecord:
    """Stored experiment record.

    Immutable record of experiment metadata.

    Attributes:
        run_id: Unique run identifier
        experiment_name: Name of the experiment
        experiment_type: Type of experiment (e.g., "castro", "custom")
        config: Experiment configuration dict
        created_at: ISO timestamp when experiment started
        completed_at: ISO timestamp when experiment completed (optional)
        num_iterations: Total iterations (optional)
        converged: Whether experiment converged (optional)
        convergence_reason: Reason for stopping (optional)
    """

    run_id: str
    experiment_name: str
    experiment_type: str
    config: dict[str, Any]
    created_at: str
    completed_at: str | None
    num_iterations: int
    converged: bool
    convergence_reason: str | None


@dataclass(frozen=True)
class IterationRecord:
    """Stored iteration record.

    All costs are integer cents (INV-1 compliance).

    Attributes:
        run_id: Run identifier
        iteration: Iteration number (0-indexed)
        costs_per_agent: Dict mapping agent_id to cost in cents
        accepted_changes: Dict mapping agent_id to acceptance status
        policies: Dict mapping agent_id to policy dict
        timestamp: ISO timestamp
    """

    run_id: str
    iteration: int
    costs_per_agent: dict[str, int]
    accepted_changes: dict[str, bool]
    policies: dict[str, Any]
    timestamp: str


@dataclass(frozen=True)
class EventRecord:
    """Stored event record.

    Attributes:
        run_id: Run identifier
        iteration: Iteration number
        event_type: Type of event
        event_data: Event-specific data
        timestamp: ISO timestamp
    """

    run_id: str
    iteration: int
    event_type: str
    event_data: dict[str, Any]
    timestamp: str


@dataclass(frozen=True)
class PolicyEvaluationRecord:
    """Complete record of a policy evaluation.

    All costs in integer cents (INV-1 compliance).

    The interpretation of cost fields depends on evaluation_mode:
    - "deterministic": old_cost/new_cost are from THE configured scenario
    - "bootstrap": old_cost/new_cost are means across N resampled scenarios

    Attributes:
        run_id: Run identifier.
        iteration: Iteration number (0-indexed).
        agent_id: Agent being evaluated.
        evaluation_mode: "deterministic" or "bootstrap".
        proposed_policy: Proposed policy dict.
        old_cost: Cost with old policy (actual, not estimate).
        new_cost: Cost with new policy (actual, not estimate).
        context_simulation_cost: Context simulation cost (for comparison/audit).
        accepted: Whether the policy was accepted.
        acceptance_reason: Reason for acceptance decision.
        delta_sum: Sum of deltas across samples.
        num_samples: Number of samples (1 for deterministic, N for bootstrap).
        sample_details: Bootstrap per-sample details (None for deterministic).
        scenario_seed: Seed for deterministic evaluation (None for bootstrap).
        timestamp: ISO timestamp.

    Extended Statistics (all optional for backward compatibility):
        settlement_rate: System-wide settlement rate (0.0 to 1.0).
        avg_delay: System-wide average delay in ticks.
        cost_breakdown: Total cost by type {delay_cost, overdraft_cost,
            deadline_penalty, eod_penalty} in integer cents.
        cost_std_dev: Standard deviation of costs in cents (bootstrap only).
        confidence_interval_95: 95% CI bounds [lower, upper] in cents (bootstrap only).
        agent_stats: Per-agent metrics keyed by agent_id. Each agent has:
            cost, settlement_rate, avg_delay, cost_breakdown, and optionally
            std_dev, ci_95_lower, ci_95_upper (bootstrap only).
    """

    run_id: str
    iteration: int
    agent_id: str
    evaluation_mode: str
    proposed_policy: dict[str, Any]
    old_cost: int
    new_cost: int
    context_simulation_cost: int
    accepted: bool
    acceptance_reason: str
    delta_sum: int
    num_samples: int
    sample_details: list[dict[str, Any]] | None
    scenario_seed: int | None
    timestamp: str
    # Extended statistics (Phase 1: Extended Policy Evaluation Stats)
    settlement_rate: float | None = None
    avg_delay: float | None = None
    cost_breakdown: dict[str, int] | None = None
    cost_std_dev: int | None = None
    confidence_interval_95: list[int] | None = None
    agent_stats: dict[str, dict[str, Any]] | None = None


# =============================================================================
# Repository Implementation
# =============================================================================


class ExperimentRepository:
    """Unified repository for experiment persistence.

    Supports any experiment type with flexible schema.
    All costs are integer cents (INV-1 compliance).

    Example:
        >>> repo = ExperimentRepository(Path("experiments.db"))
        >>> repo.save_experiment(record)
        >>> loaded = repo.load_experiment("run-123")
        >>> repo.close()

    Or with context manager:
        >>> with ExperimentRepository(Path("experiments.db")) as repo:
        ...     repo.save_experiment(record)
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize repository with database path.

        Creates database file and tables if they don't exist.

        Args:
            db_path: Path to DuckDB database file
        """
        self._db_path = db_path
        self._conn = duckdb.connect(str(db_path))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database tables if they don't exist."""
        # Create experiments table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                run_id VARCHAR PRIMARY KEY,
                experiment_name VARCHAR NOT NULL,
                experiment_type VARCHAR NOT NULL,
                config JSON NOT NULL,
                created_at VARCHAR NOT NULL,
                completed_at VARCHAR,
                num_iterations INTEGER DEFAULT 0,
                converged BOOLEAN DEFAULT FALSE,
                convergence_reason VARCHAR
            )
        """)

        # Create iterations table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_iterations (
                run_id VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                costs_per_agent JSON NOT NULL,
                accepted_changes JSON NOT NULL,
                policies JSON NOT NULL,
                timestamp VARCHAR NOT NULL,
                PRIMARY KEY (run_id, iteration)
            )
        """)

        # Create events table
        # Use a sequence for auto-increment ID
        self._conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS experiment_events_id_seq START 1
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_events (
                id INTEGER DEFAULT nextval('experiment_events_id_seq') PRIMARY KEY,
                run_id VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                event_data JSON NOT NULL,
                timestamp VARCHAR NOT NULL
            )
        """)

        # Create policy_evaluations table
        # Natural primary key is (run_id, iteration, agent_id)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_evaluations (
                run_id VARCHAR NOT NULL,
                iteration INTEGER NOT NULL,
                agent_id VARCHAR NOT NULL,
                evaluation_mode VARCHAR NOT NULL,
                proposed_policy JSON NOT NULL,
                old_cost INTEGER NOT NULL,
                new_cost INTEGER NOT NULL,
                context_simulation_cost INTEGER NOT NULL,
                accepted BOOLEAN NOT NULL,
                acceptance_reason VARCHAR NOT NULL,
                delta_sum INTEGER NOT NULL,
                num_samples INTEGER NOT NULL,
                sample_details JSON,
                scenario_seed INTEGER,
                timestamp VARCHAR NOT NULL,
                PRIMARY KEY (run_id, iteration, agent_id)
            )
        """)

        # Add extended statistics columns (Phase 1: Extended Policy Evaluation Stats)
        # Using ALTER TABLE ADD COLUMN IF NOT EXISTS for backward compatibility
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS settlement_rate DOUBLE
        """)
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS avg_delay DOUBLE
        """)
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS cost_breakdown JSON
        """)
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS cost_std_dev INTEGER
        """)
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS confidence_interval_95 JSON
        """)
        self._conn.execute("""
            ALTER TABLE policy_evaluations
            ADD COLUMN IF NOT EXISTS agent_stats JSON
        """)

        # Create indexes for performance
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_experiments_type
            ON experiments(experiment_type)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_iterations_run
            ON experiment_iterations(run_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_run_iter
            ON experiment_events(run_id, iteration)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_evals_run_agent
            ON policy_evaluations(run_id, agent_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_evals_mode
            ON policy_evaluations(run_id, evaluation_mode)
        """)

        # =====================================================================
        # Simulation Persistence Tables (INV-11: Simulation Persistence Identity)
        # These tables enable `payment-sim replay` for experiment simulations
        # =====================================================================

        # Create simulations table (matches CLI schema)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id VARCHAR PRIMARY KEY,
                config_file VARCHAR,
                config_name VARCHAR,
                description VARCHAR,
                rng_seed BIGINT,
                ticks_per_day INTEGER,
                num_days INTEGER,
                num_agents INTEGER,
                status VARCHAR DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                total_arrivals INTEGER,
                total_settlements INTEGER,
                total_cost_cents BIGINT,
                duration_seconds DOUBLE,
                ticks_per_second DOUBLE,
                config_json TEXT,
                experiment_run_id VARCHAR,
                experiment_iteration INTEGER
            )
        """)

        # Create simulation_events table (matches CLI schema)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS simulation_events (
                event_id VARCHAR PRIMARY KEY,
                simulation_id VARCHAR,
                tick INTEGER,
                day INTEGER,
                event_timestamp TIMESTAMP,
                event_type VARCHAR,
                details TEXT,
                agent_id VARCHAR,
                tx_id VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create agent_state_registers table (for StateRegisterSet dual-write)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_state_registers (
                simulation_id VARCHAR,
                tick INTEGER,
                agent_id VARCHAR,
                register_key VARCHAR,
                register_value DOUBLE,
                PRIMARY KEY (simulation_id, tick, agent_id, register_key)
            )
        """)

        # Create indexes for simulation tables
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_simulations_experiment
            ON simulations(experiment_run_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_simulation_events_sim_tick
            ON simulation_events(simulation_id, tick)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_simulation_events_type
            ON simulation_events(simulation_id, event_type)
        """)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()

    def __enter__(self) -> ExperimentRepository:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    # =========================================================================
    # Simulation Persistence Provider (INV-11)
    # =========================================================================

    def get_simulation_persistence_provider(
        self,
        ticks_per_day: int,
    ) -> StandardSimulationPersistenceProvider:
        """Get SimulationPersistenceProvider for persisting simulation data.

        Returns a provider that writes to the standard simulation tables
        (simulations, simulation_events, agent_state_registers), enabling
        `payment-sim replay` for experiment simulations.

        This ensures INV-11 (Simulation Persistence Identity): simulations
        persisted through experiments use the same schema as CLI-persisted
        simulations.

        Args:
            ticks_per_day: Number of ticks per day (for day calculation)

        Returns:
            StandardSimulationPersistenceProvider instance

        Example:
            >>> with ExperimentRepository(db_path) as repo:
            ...     provider = repo.get_simulation_persistence_provider(100)
            ...     provider.persist_simulation_start(sim_id, config)
            ...     provider.persist_tick_events(sim_id, tick, events)
            ...     provider.persist_simulation_complete(sim_id, metrics)
        """
        from payment_simulator.persistence.simulation_persistence_provider import (
            StandardSimulationPersistenceProvider,
        )

        return StandardSimulationPersistenceProvider(
            conn=self._conn,
            ticks_per_day=ticks_per_day,
        )

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
                run_id, experiment_name, experiment_type, config,
                created_at, completed_at, num_iterations, converged,
                convergence_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.run_id,
                record.experiment_name,
                record.experiment_type,
                config_json,
                record.created_at,
                record.completed_at,
                record.num_iterations,
                record.converged,
                record.convergence_reason,
            ],
        )

    def load_experiment(self, run_id: str) -> ExperimentRecord | None:
        """Load an experiment by run ID.

        Args:
            run_id: Run identifier

        Returns:
            ExperimentRecord if found, None otherwise
        """
        result = self._conn.execute(
            "SELECT * FROM experiments WHERE run_id = ?",
            [run_id],
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
        """Convert database row to ExperimentRecord."""
        config = row[3]
        if isinstance(config, str):
            config = json.loads(config)

        return ExperimentRecord(
            run_id=row[0],
            experiment_name=row[1],
            experiment_type=row[2],
            config=config,
            created_at=row[4],
            completed_at=row[5],
            num_iterations=row[6] or 0,
            converged=bool(row[7]) if row[7] is not None else False,
            convergence_reason=row[8],
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
                run_id, iteration, costs_per_agent, accepted_changes,
                policies, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                record.run_id,
                record.iteration,
                costs_json,
                accepted_json,
                policies_json,
                record.timestamp,
            ],
        )

    def get_iterations(self, run_id: str) -> list[IterationRecord]:
        """Get all iterations for an experiment.

        Args:
            run_id: Run identifier

        Returns:
            List of IterationRecord ordered by iteration number
        """
        results = self._conn.execute(
            """
            SELECT run_id, iteration, costs_per_agent, accepted_changes,
                   policies, timestamp
            FROM experiment_iterations
            WHERE run_id = ?
            ORDER BY iteration
            """,
            [run_id],
        ).fetchall()

        return [self._row_to_iteration_record(row) for row in results]

    def _row_to_iteration_record(self, row: tuple[Any, ...]) -> IterationRecord:
        """Convert database row to IterationRecord."""
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
            run_id=row[0],
            iteration=row[1],
            costs_per_agent=costs,
            accepted_changes=accepted,
            policies=policies,
            timestamp=row[5],
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
                run_id, iteration, event_type, event_data, timestamp
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                event.run_id,
                event.iteration,
                event.event_type,
                event_data_json,
                event.timestamp,
            ],
        )

    def get_events(self, run_id: str, iteration: int) -> list[EventRecord]:
        """Get events for a specific iteration.

        Args:
            run_id: Run identifier
            iteration: Iteration number

        Returns:
            List of EventRecord for the iteration
        """
        results = self._conn.execute(
            """
            SELECT run_id, iteration, event_type, event_data, timestamp
            FROM experiment_events
            WHERE run_id = ? AND iteration = ?
            ORDER BY timestamp
            """,
            [run_id, iteration],
        ).fetchall()

        return [self._row_to_event_record(row) for row in results]

    def get_all_events(self, run_id: str) -> list[EventRecord]:
        """Get all events for an experiment.

        Args:
            run_id: Run identifier

        Returns:
            List of EventRecord ordered by iteration, timestamp
        """
        results = self._conn.execute(
            """
            SELECT run_id, iteration, event_type, event_data, timestamp
            FROM experiment_events
            WHERE run_id = ?
            ORDER BY iteration, timestamp
            """,
            [run_id],
        ).fetchall()

        return [self._row_to_event_record(row) for row in results]

    def _row_to_event_record(self, row: tuple[Any, ...]) -> EventRecord:
        """Convert database row to EventRecord."""
        event_data = row[3]
        if isinstance(event_data, str):
            event_data = json.loads(event_data)

        return EventRecord(
            run_id=row[0],
            iteration=row[1],
            event_type=row[2],
            event_data=event_data,
            timestamp=row[4],
        )

    # =========================================================================
    # Policy Evaluation Operations
    # =========================================================================

    def save_policy_evaluation(self, record: PolicyEvaluationRecord) -> None:
        """Save or update a policy evaluation record.

        Uses INSERT ... ON CONFLICT DO UPDATE for upsert based on
        (run_id, iteration, agent_id) primary key.

        Args:
            record: PolicyEvaluationRecord to persist
        """
        proposed_policy_json = json.dumps(record.proposed_policy)
        sample_details_json = (
            json.dumps(record.sample_details)
            if record.sample_details is not None
            else None
        )
        # Extended stats JSON serialization
        cost_breakdown_json = (
            json.dumps(record.cost_breakdown)
            if record.cost_breakdown is not None
            else None
        )
        confidence_interval_json = (
            json.dumps(record.confidence_interval_95)
            if record.confidence_interval_95 is not None
            else None
        )
        agent_stats_json = (
            json.dumps(record.agent_stats)
            if record.agent_stats is not None
            else None
        )

        # DuckDB INSERT with ON CONFLICT DO UPDATE for upsert
        self._conn.execute(
            """
            INSERT INTO policy_evaluations (
                run_id, iteration, agent_id, evaluation_mode,
                proposed_policy, old_cost, new_cost, context_simulation_cost,
                accepted, acceptance_reason, delta_sum, num_samples,
                sample_details, scenario_seed, timestamp,
                settlement_rate, avg_delay, cost_breakdown,
                cost_std_dev, confidence_interval_95, agent_stats
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, iteration, agent_id) DO UPDATE SET
                evaluation_mode = EXCLUDED.evaluation_mode,
                proposed_policy = EXCLUDED.proposed_policy,
                old_cost = EXCLUDED.old_cost,
                new_cost = EXCLUDED.new_cost,
                context_simulation_cost = EXCLUDED.context_simulation_cost,
                accepted = EXCLUDED.accepted,
                acceptance_reason = EXCLUDED.acceptance_reason,
                delta_sum = EXCLUDED.delta_sum,
                num_samples = EXCLUDED.num_samples,
                sample_details = EXCLUDED.sample_details,
                scenario_seed = EXCLUDED.scenario_seed,
                timestamp = EXCLUDED.timestamp,
                settlement_rate = EXCLUDED.settlement_rate,
                avg_delay = EXCLUDED.avg_delay,
                cost_breakdown = EXCLUDED.cost_breakdown,
                cost_std_dev = EXCLUDED.cost_std_dev,
                confidence_interval_95 = EXCLUDED.confidence_interval_95,
                agent_stats = EXCLUDED.agent_stats
            """,
            [
                record.run_id,
                record.iteration,
                record.agent_id,
                record.evaluation_mode,
                proposed_policy_json,
                record.old_cost,
                record.new_cost,
                record.context_simulation_cost,
                record.accepted,
                record.acceptance_reason,
                record.delta_sum,
                record.num_samples,
                sample_details_json,
                record.scenario_seed,
                record.timestamp,
                record.settlement_rate,
                record.avg_delay,
                cost_breakdown_json,
                record.cost_std_dev,
                confidence_interval_json,
                agent_stats_json,
            ],
        )

    def get_policy_evaluations(
        self, run_id: str, agent_id: str
    ) -> list[PolicyEvaluationRecord]:
        """Get policy evaluations for a specific agent.

        Args:
            run_id: Run identifier.
            agent_id: Agent ID to filter by.

        Returns:
            List of PolicyEvaluationRecord ordered by iteration.
        """
        results = self._conn.execute(
            """
            SELECT run_id, iteration, agent_id, evaluation_mode,
                   proposed_policy, old_cost, new_cost, context_simulation_cost,
                   accepted, acceptance_reason, delta_sum, num_samples,
                   sample_details, scenario_seed, timestamp,
                   settlement_rate, avg_delay, cost_breakdown,
                   cost_std_dev, confidence_interval_95, agent_stats
            FROM policy_evaluations
            WHERE run_id = ? AND agent_id = ?
            ORDER BY iteration
            """,
            [run_id, agent_id],
        ).fetchall()

        return [self._row_to_policy_evaluation_record(row) for row in results]

    def get_all_policy_evaluations(
        self, run_id: str
    ) -> list[PolicyEvaluationRecord]:
        """Get all policy evaluations for a run.

        Args:
            run_id: Run identifier.

        Returns:
            List of PolicyEvaluationRecord ordered by iteration, agent_id.
        """
        results = self._conn.execute(
            """
            SELECT run_id, iteration, agent_id, evaluation_mode,
                   proposed_policy, old_cost, new_cost, context_simulation_cost,
                   accepted, acceptance_reason, delta_sum, num_samples,
                   sample_details, scenario_seed, timestamp,
                   settlement_rate, avg_delay, cost_breakdown,
                   cost_std_dev, confidence_interval_95, agent_stats
            FROM policy_evaluations
            WHERE run_id = ?
            ORDER BY iteration, agent_id
            """,
            [run_id],
        ).fetchall()

        return [self._row_to_policy_evaluation_record(row) for row in results]

    def has_policy_evaluations(self, run_id: str) -> bool:
        """Check if run has policy evaluation records.

        Args:
            run_id: Run identifier.

        Returns:
            True if policy evaluations exist for the run.
        """
        result = self._conn.execute(
            """
            SELECT COUNT(*) FROM policy_evaluations WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()

        return result is not None and result[0] > 0

    def _row_to_policy_evaluation_record(
        self, row: tuple[Any, ...]
    ) -> PolicyEvaluationRecord:
        """Convert database row to PolicyEvaluationRecord.

        Handles both old records (15 columns) and new records (21 columns)
        for backward compatibility.
        """
        proposed_policy = row[4]
        if isinstance(proposed_policy, str):
            proposed_policy = json.loads(proposed_policy)

        sample_details = row[12]
        if sample_details is not None and isinstance(sample_details, str):
            sample_details = json.loads(sample_details)

        # Extended stats (columns 15-20, may not exist in old records)
        settlement_rate: float | None = None
        avg_delay: float | None = None
        cost_breakdown: dict[str, int] | None = None
        cost_std_dev: int | None = None
        confidence_interval_95: list[int] | None = None
        agent_stats: dict[str, dict[str, Any]] | None = None

        if len(row) > 15:
            settlement_rate = row[15]
            avg_delay = row[16]

            cost_breakdown = row[17]
            if cost_breakdown is not None and isinstance(cost_breakdown, str):
                cost_breakdown = json.loads(cost_breakdown)

            cost_std_dev = int(row[18]) if row[18] is not None else None

            confidence_interval_95 = row[19]
            if confidence_interval_95 is not None and isinstance(
                confidence_interval_95, str
            ):
                confidence_interval_95 = json.loads(confidence_interval_95)

            agent_stats = row[20]
            if agent_stats is not None and isinstance(agent_stats, str):
                agent_stats = json.loads(agent_stats)

        return PolicyEvaluationRecord(
            run_id=row[0],
            iteration=row[1],
            agent_id=row[2],
            evaluation_mode=row[3],
            proposed_policy=proposed_policy,
            old_cost=int(row[5]),
            new_cost=int(row[6]),
            context_simulation_cost=int(row[7]),
            accepted=bool(row[8]),
            acceptance_reason=row[9],
            delta_sum=int(row[10]),
            num_samples=int(row[11]),
            sample_details=sample_details,
            scenario_seed=row[13],
            timestamp=row[14],
            settlement_rate=settlement_rate,
            avg_delay=avg_delay,
            cost_breakdown=cost_breakdown,
            cost_std_dev=cost_std_dev,
            confidence_interval_95=confidence_interval_95,
            agent_stats=agent_stats,
        )

    # =========================================================================
    # StateProvider Integration
    # =========================================================================

    def as_state_provider(self, run_id: str) -> ExperimentStateProviderProtocol:
        """Create a StateProvider for replay.

        Returns a DatabaseStateProvider wrapping this repository.

        Args:
            run_id: Run identifier to load

        Returns:
            ExperimentStateProviderProtocol implementation
        """
        from payment_simulator.experiments.runner.state_provider import (
            DatabaseStateProvider,
        )

        return DatabaseStateProvider(self, run_id)
