"""Experiment Simulation Persister.

Phase 3 Database Consolidation: Persists simulation runs executed during
experiments with proper experiment linkage.

Provides:
- Structured simulation ID generation
- Simulation run record persistence with experiment linkage
- Policy-aware persistence decisions
- Event persistence for replay capability
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from payment_simulator.experiments.persistence.policy import (
    ExperimentPersistencePolicy,
    SimulationPersistenceLevel,
)
from payment_simulator.experiments.simulation_id import (
    generate_experiment_simulation_id,
)
from payment_simulator.persistence.models import SimulationRunPurpose

if TYPE_CHECKING:
    from payment_simulator.persistence.connection import DatabaseManager


class ExperimentSimulationPersister:
    """Persists simulation runs executed during experiments.

    This class handles:
    - Generation of structured simulation IDs for experiment runs
    - Persistence of simulation_runs records with experiment linkage
    - Policy-aware decisions about what to persist
    - Integration with the unified database schema

    All costs are stored as integer cents (INV-1 compliance).
    Seeds are stored for deterministic replay (INV-2 compliance).

    Example:
        >>> from payment_simulator.persistence.connection import DatabaseManager
        >>> db = DatabaseManager("experiment.db")
        >>> policy = ExperimentPersistencePolicy()
        >>> persister = ExperimentSimulationPersister(db, "exp-123", policy)
        >>>
        >>> sim_id = persister.generate_simulation_id(
        ...     iteration=5,
        ...     purpose=SimulationRunPurpose.EVALUATION,
        ... )
        >>> persister.persist_simulation_run(
        ...     simulation_id=sim_id,
        ...     iteration=5,
        ...     purpose=SimulationRunPurpose.EVALUATION,
        ...     seed=12345,
        ...     config_name="scenario.yaml",
        ...     total_ticks=100,
        ...     total_transactions=50,
        ...     total_settlements=45,
        ...     total_cost=10000,  # Integer cents
        ...     duration_seconds=2.5,
        ... )
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        experiment_id: str,
        policy: ExperimentPersistencePolicy,
    ) -> None:
        """Initialize the simulation persister.

        Args:
            db_manager: DatabaseManager for database operations.
            experiment_id: Parent experiment ID to link simulations to.
            policy: Persistence policy controlling what gets persisted.
        """
        self._db_manager = db_manager
        self._experiment_id = experiment_id
        self._policy = policy

    @property
    def experiment_id(self) -> str:
        """Get the parent experiment ID."""
        return self._experiment_id

    @property
    def policy(self) -> ExperimentPersistencePolicy:
        """Get the persistence policy."""
        return self._policy

    def generate_simulation_id(
        self,
        iteration: int,
        purpose: SimulationRunPurpose,
        sample_index: int | None = None,
    ) -> str:
        """Generate a structured simulation ID for an experiment run.

        Format: {experiment_id}-iter{N}-{purpose}[-sample{M}]

        Args:
            iteration: Iteration number (0-indexed).
            purpose: Simulation purpose (evaluation, bootstrap, etc.).
            sample_index: Bootstrap sample index (only for BOOTSTRAP purpose).

        Returns:
            Structured simulation ID.
        """
        return generate_experiment_simulation_id(
            experiment_id=self._experiment_id,
            iteration=iteration,
            purpose=purpose,
            sample_index=sample_index,
        )

    def should_persist_simulation(
        self,
        purpose: SimulationRunPurpose,
    ) -> bool:
        """Check if a simulation should be persisted based on policy.

        Args:
            purpose: Simulation purpose.

        Returns:
            True if simulation should be persisted.
        """
        # Final evaluation is always persisted if configured
        if purpose == SimulationRunPurpose.FINAL and self._policy.persist_final_evaluation:
            return True

        # Check persistence level
        if self._policy.simulation_persistence == SimulationPersistenceLevel.NONE:
            return False

        # Bootstrap samples have their own flag
        if purpose == SimulationRunPurpose.BOOTSTRAP:
            return self._policy.persist_bootstrap_transactions

        # For other purposes (EVALUATION, INITIAL, BEST), respect the level
        return True

    def persist_simulation_run(
        self,
        simulation_id: str,
        iteration: int,
        purpose: SimulationRunPurpose,
        seed: int,
        config_name: str,
        total_ticks: int,
        total_transactions: int,
        total_settlements: int,
        total_cost: int,
        duration_seconds: float,
        sample_index: int | None = None,
        config_hash: str | None = None,
        ticks_per_day: int = 100,
        num_days: int = 1,
    ) -> None:
        """Persist a simulation run record to the database.

        All costs must be integer cents (INV-1 compliance).

        Args:
            simulation_id: Structured simulation ID.
            iteration: Iteration number (0-indexed).
            purpose: Simulation purpose.
            seed: RNG seed for replay (INV-2 compliance).
            config_name: Name of the scenario config.
            total_ticks: Total ticks executed.
            total_transactions: Total transactions processed.
            total_settlements: Total settlements completed.
            total_cost: Total cost in integer cents (INV-1).
            duration_seconds: Simulation duration in seconds.
            sample_index: Bootstrap sample index (optional).
            config_hash: SHA256 hash of config (optional).
            ticks_per_day: Ticks per day in simulation config.
            num_days: Number of simulation days.
        """
        now = datetime.now()

        self._db_manager.conn.execute(
            """
            INSERT INTO simulation_runs (
                simulation_id,
                config_name,
                config_hash,
                start_time,
                end_time,
                ticks_per_day,
                num_days,
                rng_seed,
                status,
                total_transactions,
                total_settlements,
                total_cost,
                duration_seconds,
                experiment_id,
                iteration,
                sample_index,
                run_purpose
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                simulation_id,
                config_name,
                config_hash or "",
                now,
                now,
                ticks_per_day,
                num_days,
                seed,
                "completed",
                total_transactions,
                total_settlements,
                total_cost,
                duration_seconds,
                self._experiment_id,
                iteration,
                sample_index,
                purpose.value,
            ],
        )

    def persist_simulation_events(
        self,
        simulation_id: str,
        events: list[dict[str, Any]],
        ticks_per_day: int,
    ) -> int:
        """Persist simulation events for replay capability.

        Uses the existing event_writer infrastructure for consistency.

        Args:
            simulation_id: Simulation ID to associate events with.
            events: List of event dicts from simulation.
            ticks_per_day: Ticks per day for day calculation.

        Returns:
            Number of events written.
        """
        from payment_simulator.persistence.event_writer import write_events_batch

        return write_events_batch(
            conn=self._db_manager.conn,
            simulation_id=simulation_id,
            events=events,
            ticks_per_day=ticks_per_day,
        )

    def get_simulations_for_experiment(self) -> list[dict[str, Any]]:
        """Query all simulations linked to this experiment.

        Returns:
            List of simulation records for this experiment.
        """
        result = self._db_manager.conn.execute(
            """
            SELECT
                simulation_id,
                config_name,
                seed,
                total_ticks,
                total_transactions,
                total_settlements,
                total_cost,
                duration_seconds,
                iteration,
                sample_index,
                run_purpose,
                started_at,
                completed_at
            FROM simulation_runs
            WHERE experiment_id = ?
            ORDER BY iteration, sample_index
            """,
            [self._experiment_id],
        ).fetchall()

        simulations = []
        for row in result:
            simulations.append({
                "simulation_id": row[0],
                "config_name": row[1],
                "seed": row[2],
                "total_ticks": row[3],
                "total_transactions": row[4],
                "total_settlements": row[5],
                "total_cost": row[6],
                "duration_seconds": row[7],
                "iteration": row[8],
                "sample_index": row[9],
                "run_purpose": row[10],
                "started_at": row[11],
                "completed_at": row[12],
            })

        return simulations
