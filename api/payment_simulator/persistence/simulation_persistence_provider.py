"""Simulation Persistence Provider Protocol and Implementation.

Defines a common interface for persisting simulation data, ensuring identical
persistence behavior across all code paths (CLI and experiments).

INV-11 (Simulation Persistence Identity):
For any simulation S, persistence MUST produce identical database records
regardless of which code path executes the simulation.

This module follows the StateProvider pattern (INV-5):
- Protocol defines the interface
- StandardSimulationPersistenceProvider provides the implementation
- All code paths (CLI, experiments) use the same provider
"""

import json
import uuid
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

import duckdb


@runtime_checkable
class SimulationPersistenceProvider(Protocol):
    """Protocol for persisting simulation data.

    This interface is used by both:
    - CLI runner (`payment-sim run --persist`)
    - Experiment runner (`payment-sim experiment run --persist-bootstrap`)

    Ensures identical persistence behavior across all execution contexts (INV-11).

    Methods:
        persist_simulation_start: Create initial simulation record
        persist_tick_events: Write events to simulation_events table
        persist_simulation_complete: Update simulation with final metrics
    """

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        *,
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        """Create simulation record at start of run.

        Args:
            simulation_id: Unique identifier for this simulation
            config: Simulation configuration dict (contains seed, num_days, etc.)
            experiment_run_id: Optional experiment run ID for cross-referencing
            experiment_iteration: Optional iteration number within experiment
        """
        ...

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> int:
        """Persist events from a single tick to simulation_events table.

        Args:
            simulation_id: Simulation ID to associate events with
            tick: Tick number
            events: List of event dicts from Rust FFI

        Returns:
            Number of events written
        """
        ...

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Update simulation record with final metrics.

        Args:
            simulation_id: Simulation ID to update
            metrics: Final metrics dict containing:
                - total_arrivals: int
                - total_settlements: int
                - total_cost_cents: int (INV-1: integer cents)
                - duration_seconds: float
        """
        ...


class StandardSimulationPersistenceProvider:
    """Standard implementation of SimulationPersistenceProvider.

    Uses DuckDB connection to persist simulation data to standard tables:
    - simulations: Simulation metadata and summary
    - simulation_events: All events with details JSON
    - agent_state_registers: Dual-write for StateRegisterSet events

    This implementation wraps the existing write_events_batch() functionality
    to ensure identical behavior with the CLI persistence path.

    Usage:
        provider = StandardSimulationPersistenceProvider(conn, ticks_per_day=100)
        provider.persist_simulation_start(sim_id, config)
        for tick, events in tick_events:
            provider.persist_tick_events(sim_id, tick, events)
        provider.persist_simulation_complete(sim_id, metrics)
    """

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        ticks_per_day: int,
    ) -> None:
        """Initialize with database connection.

        Args:
            conn: DuckDB connection
            ticks_per_day: Number of ticks per day (for day calculation)
        """
        self._conn = conn
        self._ticks_per_day = ticks_per_day

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        *,
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None:
        """Create simulation record at start of run.

        Creates a record in the simulations table with status='running'.
        Extracts configuration values for structured columns and stores
        the full config as JSON.

        Args:
            simulation_id: Unique identifier for this simulation
            config: Simulation configuration dict
            experiment_run_id: Optional experiment run ID for cross-referencing
            experiment_iteration: Optional iteration number within experiment
        """
        # Extract config values
        seed = config.get("seed", config.get("rng_seed", 0))
        num_days = config.get("num_days", 1)
        num_agents = len(config.get("agents", []))

        # Store full config as JSON
        config_json = json.dumps(config, default=str)

        self._conn.execute(
            """
            INSERT INTO simulations (
                simulation_id,
                rng_seed,
                ticks_per_day,
                num_days,
                num_agents,
                status,
                started_at,
                config_json,
                experiment_run_id,
                experiment_iteration
            ) VALUES (?, ?, ?, ?, ?, 'running', CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            [
                simulation_id,
                seed,
                self._ticks_per_day,
                num_days,
                num_agents,
                config_json,
                experiment_run_id,
                experiment_iteration,
            ],
        )

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> int:
        """Persist events from a single tick to simulation_events table.

        Transforms Rust FFI events into database records:
        - Common fields (event_type, tick, agent_id, tx_id) go to dedicated columns
        - All other fields go to details JSON column
        - StateRegisterSet events are dual-written to agent_state_registers

        This replicates the behavior of write_events_batch() from event_writer.py
        to ensure persistence identity (INV-11).

        Args:
            simulation_id: Simulation ID to associate events with
            tick: Tick number (events may override this in their data)
            events: List of event dicts from Rust FFI

        Returns:
            Number of events written
        """
        if not events:
            return 0

        # Prepare batch insert data for simulation_events
        records: list[tuple[Any, ...]] = []
        # Prepare batch insert data for agent_state_registers (dual-write)
        state_register_records: list[tuple[Any, ...]] = []

        for event in events:
            # Use event's tick if present, otherwise use passed tick
            event_tick = event.get("tick", tick)
            day = event_tick // self._ticks_per_day
            event_type = event["event_type"]

            # Extract common fields (from flat structure)
            agent_id = event.get("agent_id")
            tx_id = event.get("tx_id")

            # Build details dict from all fields except common ones
            details = {
                k: v
                for k, v in event.items()
                if k not in ("event_type", "tick", "agent_id", "tx_id")
            }

            # Create record tuple for simulation_events
            record = (
                str(uuid.uuid4()),  # event_id
                simulation_id,  # simulation_id
                event_tick,  # tick
                day,  # day
                datetime.now(),  # event_timestamp
                event_type,  # event_type
                json.dumps(details),  # details (JSON)
                agent_id,  # agent_id (nullable)
                tx_id,  # tx_id (nullable)
                datetime.now(),  # created_at
            )
            records.append(record)

            # Dual-write StateRegisterSet events to agent_state_registers
            if event_type == "StateRegisterSet":
                state_register_record = (
                    simulation_id,  # simulation_id
                    event_tick,  # tick
                    agent_id,  # agent_id
                    event.get("register_key"),  # register_key
                    event.get("new_value"),  # register_value (store new_value)
                )
                state_register_records.append(state_register_record)

        # Batch insert into simulation_events
        self._conn.executemany(
            """
            INSERT INTO simulation_events (
                event_id,
                simulation_id,
                tick,
                day,
                event_timestamp,
                event_type,
                details,
                agent_id,
                tx_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        # Batch insert into agent_state_registers (if any StateRegisterSet events)
        # Handle duplicate register updates in same tick (keep only final value)
        if state_register_records:
            merged_records = self._merge_state_register_updates(state_register_records)
            self._conn.executemany(
                """
                INSERT INTO agent_state_registers (
                    simulation_id,
                    tick,
                    agent_id,
                    register_key,
                    register_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                merged_records,
            )

        return len(records)

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Update simulation record with final metrics.

        Updates the simulations table with status='completed' and final metrics.

        Args:
            simulation_id: Simulation ID to update
            metrics: Final metrics dict containing:
                - total_arrivals: int
                - total_settlements: int
                - total_cost_cents: int (INV-1: integer cents)
                - duration_seconds: float
        """
        self._conn.execute(
            """
            UPDATE simulations SET
                status = 'completed',
                ended_at = CURRENT_TIMESTAMP,
                total_arrivals = ?,
                total_settlements = ?,
                total_cost_cents = ?,
                duration_seconds = ?,
                ticks_per_second = ?
            WHERE simulation_id = ?
            """,
            [
                metrics.get("total_arrivals", 0),
                metrics.get("total_settlements", 0),
                metrics.get("total_cost_cents", 0),  # Integer cents (INV-1)
                metrics.get("duration_seconds", 0.0),
                (
                    metrics.get("total_arrivals", 0) / metrics.get("duration_seconds", 1.0)
                    if metrics.get("duration_seconds", 0.0) > 0
                    else 0.0
                ),
                simulation_id,
            ],
        )

    @staticmethod
    def _merge_state_register_updates(
        records: list[tuple[Any, ...]],
    ) -> list[tuple[Any, ...]]:
        """Merge duplicate state register updates in same tick, keeping only final value.

        When multiple SetState operations occur on same register in same tick
        (e.g., policy update + EOD reset), we store only the FINAL value to avoid
        duplicate key constraint violation.

        Args:
            records: List of tuples (simulation_id, tick, agent_id, register_key, register_value)

        Returns:
            List of tuples with duplicates removed (only final value kept for each key)
        """
        # Use dict with composite key to track final value for each register
        # Key: (simulation_id, tick, agent_id, register_key)
        # Value: full tuple (including register_value)
        final_values: dict[tuple[Any, ...], tuple[Any, ...]] = {}

        for record in records:
            simulation_id, tick, agent_id, register_key, _register_value = record
            key = (simulation_id, tick, agent_id, register_key)

            # Overwrite previous value - this keeps the LAST value encountered
            final_values[key] = record

        # Convert back to list
        return list(final_values.values())
