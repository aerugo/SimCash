"""State provider protocol for unified output functions.

Defines a common interface for accessing simulation state, implemented by
both live Orchestrator (via FFI) and database replay (via queries).
"""

from typing import Protocol, runtime_checkable
from payment_simulator._core import Orchestrator


@runtime_checkable
class StateProvider(Protocol):
    """Protocol for accessing simulation state.

    This interface is implemented by both:
    - OrchestratorStateProvider (live execution via FFI)
    - DatabaseStateProvider (replay from database)

    Enables unified output functions that work identically in both modes.
    """

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Get transaction details by ID.

        Returns:
            Transaction dict with keys: tx_id, sender_id, receiver_id, amount,
            remaining_amount, priority, deadline_tick, status, is_divisible
            Returns None if transaction not found.
        """
        ...

    def get_agent_balance(self, agent_id: str) -> int:
        """Get agent's current balance in cents."""
        ...

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Get agent's credit limit in cents."""
        ...

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get list of transaction IDs in agent's internal queue."""
        ...

    def get_rtgs_queue_contents(self) -> list[str]:
        """Get list of transaction IDs in RTGS central queue."""
        ...

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral posted by agent in cents."""
        ...

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Get accumulated costs for agent.

        Returns:
            Dict with keys: liquidity_cost, delay_cost, collateral_cost,
            penalty_cost, split_friction_cost (all in cents)
        """
        ...

    def get_queue1_size(self, agent_id: str) -> int:
        """Get size of agent's internal queue."""
        ...


class OrchestratorStateProvider:
    """StateProvider implementation wrapping live Orchestrator (FFI).

    Thin wrapper that delegates all calls to the Rust Orchestrator via PyO3.
    """

    def __init__(self, orch: Orchestrator):
        """Initialize with orchestrator.

        Args:
            orch: Orchestrator instance from Rust FFI
        """
        self.orch = orch

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Delegate to orchestrator."""
        return self.orch.get_transaction_details(tx_id)

    def get_agent_balance(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_balance(agent_id)

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_credit_limit(agent_id)

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_agent_queue1_contents(agent_id)

    def get_rtgs_queue_contents(self) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_rtgs_queue_contents()

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_collateral_posted(agent_id)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Delegate to orchestrator."""
        return self.orch.get_agent_accumulated_costs(agent_id)

    def get_queue1_size(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_queue1_size(agent_id)


class DatabaseStateProvider:
    """StateProvider implementation using database state (replay).

    Reads from pre-loaded database state (agent_states, queue_snapshots, tx_cache)
    to provide same interface as Orchestrator without re-execution.
    """

    def __init__(
        self,
        conn,
        simulation_id: str,
        tick: int,
        tx_cache: dict[str, dict],
        agent_states: dict[str, dict],
        queue_snapshots: dict[str, dict],
    ):
        """Initialize with database state.

        Args:
            conn: Database connection (for future queries if needed)
            simulation_id: Simulation identifier
            tick: Current tick number
            tx_cache: Dict mapping tx_id -> transaction details
            agent_states: Dict mapping agent_id -> agent state dict
            queue_snapshots: Dict mapping agent_id -> queue snapshot dict
        """
        self.conn = conn
        self.simulation_id = simulation_id
        self.tick = tick
        self._tx_cache = tx_cache
        self._agent_states = agent_states
        self._queue_snapshots = queue_snapshots

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Get transaction from cache."""
        tx = self._tx_cache.get(tx_id)
        if not tx:
            return None

        # Convert database format to orchestrator format
        return {
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount"],
            "remaining_amount": tx.get("amount", 0) - tx.get("amount_settled", 0),
            "priority": tx["priority"],
            "deadline_tick": tx["deadline_tick"],
            "status": tx["status"],
            "is_divisible": tx.get("is_divisible", False),
        }

    def get_agent_balance(self, agent_id: str) -> int:
        """Get balance from agent_states."""
        # Handle missing agent_id gracefully
        if agent_id not in self._agent_states:
            return 0
        return self._agent_states[agent_id].get("balance", 0)

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Get credit limit from agent_states."""
        # Handle missing credit_limit gracefully (older databases may not have it)
        if agent_id not in self._agent_states:
            return 0
        return self._agent_states[agent_id].get("credit_limit", 0)

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get queue1 from queue_snapshots."""
        return self._queue_snapshots.get(agent_id, {}).get("queue1", [])

    def get_rtgs_queue_contents(self) -> list[str]:
        """Aggregate RTGS queue from all agent snapshots."""
        rtgs_txs = []
        for agent_id, queues in self._queue_snapshots.items():
            rtgs_txs.extend(queues.get("rtgs", []))
        return rtgs_txs

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral from agent_states."""
        return self._agent_states.get(agent_id, {}).get("collateral_posted", 0)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Get costs from agent_states."""
        state = self._agent_states.get(agent_id, {})
        return {
            "liquidity_cost": state.get("liquidity_cost", 0),
            "delay_cost": state.get("delay_cost", 0),
            "collateral_cost": state.get("collateral_cost", 0),
            "penalty_cost": state.get("penalty_cost", 0),
            "split_friction_cost": state.get("split_friction_cost", 0),
        }

    def get_queue1_size(self, agent_id: str) -> int:
        """Get queue1 size."""
        return len(self.get_agent_queue1_contents(agent_id))
