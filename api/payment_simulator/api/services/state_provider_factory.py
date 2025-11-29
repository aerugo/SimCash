"""Factory for creating StateProvider instances for API use.

This factory abstracts the decision of which StateProvider implementation to use:
- OrchestratorStateProvider for live (in-memory) simulations
- DatabaseStateProvider for persisted (database-only) simulations

This enables API endpoints to work uniformly with both live and persisted simulations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from payment_simulator.cli.execution.state_provider import (
    DatabaseStateProvider,
    OrchestratorStateProvider,
    StateProvider,
)

if TYPE_CHECKING:
    from payment_simulator.persistence.connection import DatabaseManager


class SimulationNotFoundError(Exception):
    """Raised when a simulation cannot be found in memory or database."""

    def __init__(self, simulation_id: str) -> None:
        self.simulation_id = simulation_id
        super().__init__(f"Simulation not found: {simulation_id}")


class APIStateProviderFactory:
    """Factory for creating StateProvider instances.

    Determines whether a simulation is live (in-memory) or persisted (database-only)
    and returns the appropriate StateProvider implementation.

    Usage:
        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)
        costs = provider.get_agent_accumulated_costs("BANK_A")
    """

    def create(
        self,
        simulation_id: str,
        db_manager: DatabaseManager | None = None,
        tick: int | None = None,
    ) -> StateProvider:
        """Create a StateProvider for the given simulation.

        Args:
            simulation_id: The simulation ID to get provider for
            db_manager: Optional database manager for persisted simulations
            tick: Optional tick number for database queries (defaults to latest)

        Returns:
            StateProvider instance (either OrchestratorStateProvider or DatabaseStateProvider)

        Raises:
            SimulationNotFoundError: If simulation not found in memory or database
        """
        # First check if simulation is live (in-memory)
        if self._is_live_simulation(simulation_id):
            return self._create_orchestrator_provider(simulation_id)

        # Not live - try database
        if db_manager is not None:
            return self._create_database_provider(simulation_id, db_manager, tick)

        # No live sim and no database - not found
        raise SimulationNotFoundError(simulation_id)

    def _is_live_simulation(self, simulation_id: str) -> bool:
        """Check if simulation is currently live (in-memory).

        Args:
            simulation_id: The simulation ID to check

        Returns:
            True if simulation exists in memory, False otherwise
        """
        from payment_simulator.api.dependencies import container

        return container.simulation_service.has_simulation(simulation_id)

    def _create_orchestrator_provider(self, simulation_id: str) -> OrchestratorStateProvider:
        """Create provider wrapping live orchestrator.

        Args:
            simulation_id: The simulation ID

        Returns:
            OrchestratorStateProvider wrapping the live orchestrator
        """
        from payment_simulator.api.dependencies import container

        orch = container.simulation_service.get_simulation(simulation_id)
        return OrchestratorStateProvider(orch)

    def _create_database_provider(
        self,
        simulation_id: str,
        db_manager: DatabaseManager,
        tick: int | None = None,
    ) -> DatabaseStateProvider:
        """Create provider from database state.

        Args:
            simulation_id: The simulation ID
            db_manager: Database manager for queries
            tick: Optional tick (defaults to latest)

        Returns:
            DatabaseStateProvider with loaded state

        Raises:
            SimulationNotFoundError: If simulation not in database
        """
        conn = db_manager.get_connection()

        # Check if simulation exists in database
        result = conn.execute(
            "SELECT simulation_id FROM simulations WHERE simulation_id = ?",
            [simulation_id],
        ).fetchone()

        if result is None:
            raise SimulationNotFoundError(simulation_id)

        # Determine tick to use
        if tick is None:
            tick = self._get_latest_tick(conn, simulation_id)

        # Load state from database
        tx_cache = self._load_tx_cache(conn, simulation_id)
        agent_states = self._load_agent_states(conn, simulation_id, tick)
        queue_snapshots = self._load_queue_snapshots(conn, simulation_id, tick)

        return DatabaseStateProvider(
            conn=conn,
            simulation_id=simulation_id,
            tick=tick,
            tx_cache=tx_cache,
            agent_states=agent_states,
            queue_snapshots=queue_snapshots,
        )

    def _get_latest_tick(self, conn: Any, simulation_id: str) -> int:
        """Get the latest tick for a simulation.

        Args:
            conn: Database connection
            simulation_id: The simulation ID

        Returns:
            Latest tick number, or 0 if no tick data
        """
        result = conn.execute(
            """
            SELECT MAX(tick) FROM tick_agent_states
            WHERE simulation_id = ?
            """,
            [simulation_id],
        ).fetchone()

        return result[0] if result and result[0] is not None else 0

    def _load_tx_cache(self, conn: Any, simulation_id: str) -> dict[str, dict[str, Any]]:
        """Load transaction cache from database.

        Args:
            conn: Database connection
            simulation_id: The simulation ID

        Returns:
            Dict mapping tx_id -> transaction details
        """
        rows = conn.execute(
            """
            SELECT tx_id, sender_id, receiver_id, amount, priority,
                   deadline_tick, status, is_divisible, arrival_tick,
                   settlement_tick, amount_settled
            FROM transactions
            WHERE simulation_id = ?
            """,
            [simulation_id],
        ).fetchall()

        tx_cache: dict[str, dict[str, Any]] = {}
        for row in rows:
            tx_id = row[0]
            tx_cache[tx_id] = {
                "tx_id": tx_id,
                "sender_id": row[1],
                "receiver_id": row[2],
                "amount": row[3],
                "priority": row[4],
                "deadline_tick": row[5],
                "status": row[6],
                "is_divisible": row[7],
                "arrival_tick": row[8],
                "settlement_tick": row[9],
                "amount_settled": row[10] or 0,
            }

        return tx_cache

    def _load_agent_states(
        self, conn: Any, simulation_id: str, tick: int
    ) -> dict[str, dict[str, Any]]:
        """Load agent states from database at specified tick.

        Args:
            conn: Database connection
            simulation_id: The simulation ID
            tick: Tick number to load state for

        Returns:
            Dict mapping agent_id -> agent state dict
        """
        rows = conn.execute(
            """
            SELECT agent_id, balance, unsecured_cap, posted_collateral,
                   liquidity_cost, delay_cost, collateral_cost, penalty_cost,
                   split_friction_cost
            FROM tick_agent_states
            WHERE simulation_id = ? AND tick = ?
            """,
            [simulation_id, tick],
        ).fetchall()

        agent_states: dict[str, dict[str, Any]] = {}
        for row in rows:
            agent_id = row[0]
            agent_states[agent_id] = {
                "agent_id": agent_id,
                "balance": row[1],
                "unsecured_cap": row[2],
                "posted_collateral": row[3],
                "liquidity_cost": row[4],
                "delay_cost": row[5],
                "collateral_cost": row[6],
                "penalty_cost": row[7],
                "split_friction_cost": row[8],
            }

        return agent_states

    def _load_queue_snapshots(
        self, conn: Any, simulation_id: str, tick: int
    ) -> dict[str, dict[str, Any]]:
        """Load queue snapshots from database at specified tick.

        The tick_queue_snapshots table stores one row per transaction:
        (simulation_id, agent_id, tick, queue_type, position, tx_id)

        Args:
            conn: Database connection
            simulation_id: The simulation ID
            tick: Tick number to load queues for

        Returns:
            Dict mapping agent_id -> queue state dict with queue1 and rtgs lists
        """
        rows = conn.execute(
            """
            SELECT agent_id, queue_type, tx_id, position
            FROM tick_queue_snapshots
            WHERE simulation_id = ? AND tick = ?
            ORDER BY agent_id, queue_type, position
            """,
            [simulation_id, tick],
        ).fetchall()

        queue_snapshots: dict[str, dict[str, Any]] = {}
        for row in rows:
            agent_id = row[0]
            queue_type = row[1]
            tx_id = row[2]

            if agent_id not in queue_snapshots:
                queue_snapshots[agent_id] = {"queue1": [], "rtgs": []}

            # Map queue_type to expected keys
            if queue_type == "queue1":
                queue_snapshots[agent_id]["queue1"].append(tx_id)
            elif queue_type in ("rtgs", "queue2"):
                queue_snapshots[agent_id]["rtgs"].append(tx_id)

        return queue_snapshots


def get_state_provider_factory() -> APIStateProviderFactory:
    """FastAPI dependency for getting the StateProviderFactory.

    Usage:
        @router.get("/simulations/{sim_id}/costs")
        def get_costs(
            sim_id: str,
            factory: APIStateProviderFactory = Depends(get_state_provider_factory)
        ):
            provider = factory.create(sim_id, db_manager)
            ...
    """
    return APIStateProviderFactory()
