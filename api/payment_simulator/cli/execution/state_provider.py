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

    def get_queue2_size(self, agent_id: str) -> int:
        """Get size of agent's RTGS queue (Queue 2).

        Queue 2 consists of transactions in the RTGS central queue that
        belong to this agent (where agent is the sender).
        """
        ...

    def get_transactions_near_deadline(self, within_ticks: int) -> list[dict]:
        """Get transactions approaching their deadline.

        Args:
            within_ticks: Number of ticks ahead to check (e.g., 2 for "within 2 ticks")

        Returns:
            List of transaction dicts with keys: tx_id, sender_id, receiver_id,
            amount, remaining_amount, deadline_tick, ticks_until_deadline
        """
        ...

    def get_overdue_transactions(self) -> list[dict]:
        """Get all currently overdue transactions with cost data.

        Returns:
            List of overdue transaction dicts with keys: tx_id, sender_id, receiver_id,
            amount, remaining_amount, deadline_tick, overdue_since_tick, ticks_overdue,
            estimated_delay_cost, deadline_penalty_cost, total_overdue_cost
        """
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

    def get_queue2_size(self, agent_id: str) -> int:
        """Calculate Queue 2 size from RTGS queue contents."""
        rtgs_queue = self.orch.get_rtgs_queue_contents()
        return sum(
            1
            for tx_id in rtgs_queue
            if self.orch.get_transaction_details(tx_id)
            and self.orch.get_transaction_details(tx_id).get("sender_id") == agent_id
        )

    def get_transactions_near_deadline(self, within_ticks: int) -> list[dict]:
        """Delegate to orchestrator."""
        return self.orch.get_transactions_near_deadline(within_ticks)

    def get_overdue_transactions(self) -> list[dict]:
        """Delegate to orchestrator."""
        return self.orch.get_overdue_transactions()


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
        """Get transaction from cache with tick-aware remaining_amount.

        CRITICAL FIX (Issue #3):
        Only count amount_settled if the transaction was settled BY the current tick.
        This prevents future settlements from affecting past tick displays.
        """
        tx = self._tx_cache.get(tx_id)
        if not tx:
            return None

        # Calculate remaining_amount based on settlement status AT current tick
        amount_settled = 0
        settlement_tick = tx.get("settlement_tick")
        if settlement_tick is not None and settlement_tick <= self.tick:
            # Transaction was settled by this tick, so amount_settled counts
            amount_settled = tx.get("amount_settled", 0)
        # else: Transaction not yet settled at this tick, amount_settled = 0

        # Convert database format to orchestrator format
        return {
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount"],
            "remaining_amount": tx.get("amount", 0) - amount_settled,
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
        # Database schema uses "posted_collateral" not "collateral_posted"
        return self._agent_states.get(agent_id, {}).get("posted_collateral", 0)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Get costs from agent_states."""
        state = self._agent_states.get(agent_id, {})
        liquidity_cost = state.get("liquidity_cost", 0)
        delay_cost = state.get("delay_cost", 0)
        collateral_cost = state.get("collateral_cost", 0)
        penalty_cost = state.get("penalty_cost", 0)
        split_friction_cost = state.get("split_friction_cost", 0)

        return {
            "liquidity_cost": liquidity_cost,
            "delay_cost": delay_cost,
            "collateral_cost": collateral_cost,
            "penalty_cost": penalty_cost,
            "split_friction_cost": split_friction_cost,
            # Display code expects total_cost
            "deadline_penalty": penalty_cost,  # Alias for compatibility
            "total_cost": liquidity_cost + delay_cost + collateral_cost + penalty_cost + split_friction_cost,
        }

    def get_queue1_size(self, agent_id: str) -> int:
        """Get queue1 size."""
        return len(self.get_agent_queue1_contents(agent_id))

    def get_queue2_size(self, agent_id: str) -> int:
        """Get Queue 2 size from queue snapshots.

        Queue 2 consists of transactions in the RTGS queue that belong to this agent.
        """
        rtgs_queue = self.get_rtgs_queue_contents()
        return sum(
            1
            for tx_id in rtgs_queue
            if self.get_transaction_details(tx_id)
            and self.get_transaction_details(tx_id).get("sender_id") == agent_id
        )

    def get_transactions_near_deadline(self, within_ticks: int) -> list[dict]:
        """Get transactions approaching deadline from cache.

        CRITICAL FIX (Issue #12):
        Only return transactions that are ACTUALLY in Queue-1 or Queue-2 at
        the current tick. Previously this scanned ALL transactions in cache,
        showing phantom transactions that had already been submitted or settled.
        """
        threshold = self.tick + within_ticks
        near_deadline = []

        # Build set of ALL tx_ids currently in Queue-1 or Queue-2
        queued_tx_ids = set()
        for agent_id, queues in self._queue_snapshots.items():
            queued_tx_ids.update(queues.get("queue1", []))
            queued_tx_ids.update(queues.get("rtgs", []))

        for tx_id, tx in self._tx_cache.items():
            # CRITICAL: Only consider transactions currently in queues
            if tx_id not in queued_tx_ids:
                continue

            # Skip settled transactions
            if tx.get("status") == "settled":
                continue

            # Calculate remaining amount with tick-awareness (Issue #3 fix)
            # Only count amount_settled if settlement happened BY current tick
            amount_settled = 0
            settlement_tick = tx.get("settlement_tick")
            if settlement_tick is not None and settlement_tick <= self.tick:
                amount_settled = tx.get("amount_settled", 0)

            remaining = tx["amount"] - amount_settled
            if remaining <= 0:
                continue

            # Check if near deadline (within threshold but not past)
            deadline = tx["deadline_tick"]
            if self.tick < deadline <= threshold:
                near_deadline.append({
                    "tx_id": tx["tx_id"],
                    "sender_id": tx["sender_id"],
                    "receiver_id": tx["receiver_id"],
                    "amount": tx["amount"],
                    "remaining_amount": remaining,
                    "deadline_tick": deadline,
                    "ticks_until_deadline": deadline - self.tick,
                })

        return near_deadline

    def get_overdue_transactions(self) -> list[dict]:
        """Get overdue transactions by querying simulation_events."""
        # Query for TransactionWentOverdue events up to current tick
        # to find which transactions are currently overdue
        query = """
            SELECT details, tx_id, tick, agent_id
            FROM simulation_events
            WHERE simulation_id = ?
                AND event_type = 'TransactionWentOverdue'
                AND tick <= ?
            ORDER BY tick ASC
        """

        import json
        overdue_txs = {}  # Map tx_id -> overdue event details

        rows = self.conn.execute(query, [self.simulation_id, self.tick]).fetchall()
        for row in rows:
            event = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # Merge in the separate columns
            tx_id = row[1]  # tx_id column
            event["tx_id"] = tx_id
            event["tick"] = row[2]  # tick column
            if row[3]:  # agent_id column (nullable)
                event["agent_id"] = row[3]

            # Check if this transaction has been settled since going overdue
            tx = self._tx_cache.get(tx_id)
            if tx and tx.get("status") == "settled":
                continue  # Skip settled transactions

            # Calculate current overdue status
            overdue_since = event["tick"]
            ticks_overdue = self.tick - overdue_since

            overdue_txs[tx_id] = {
                "tx_id": tx_id,
                "sender_id": event["sender_id"],
                "receiver_id": event["receiver_id"],
                "amount": event["amount"],
                "remaining_amount": event.get("remaining_amount", event["amount"]),
                "deadline_tick": event["deadline_tick"],
                "overdue_since_tick": overdue_since,
                "ticks_overdue": ticks_overdue,
                "deadline_penalty_cost": event.get("deadline_penalty_cost", 0),
                # Estimate current delay cost
                # Note: This is a simplified calculation
                "estimated_delay_cost": event.get("deadline_penalty_cost", 0) // 10 * ticks_overdue,
                "total_overdue_cost": event.get("deadline_penalty_cost", 0) + (event.get("deadline_penalty_cost", 0) // 10 * ticks_overdue),
            }

        return list(overdue_txs.values())

    def get_agent_state_registers(self, agent_id: str, tick: int) -> dict[str, float]:
        """Get all state registers for an agent at a specific tick.

        Returns the most recent value for each register up to and including tick.

        Phase 4.5: Policy micro-memory support for replay.

        Args:
            agent_id: Agent ID
            tick: Tick number to query

        Returns:
            Dict mapping register_key -> register_value (float)
            Empty dict if agent has no registers

        Examples:
            >>> provider.get_agent_state_registers("BANK_A", 10)
            {"bank_state_cooldown": 42.0, "bank_state_counter": 5.0}
        """
        # Query agent_state_registers table for most recent value of each register
        # up to and including the specified tick
        query = """
            SELECT register_key, register_value
            FROM (
                SELECT
                    register_key,
                    register_value,
                    tick,
                    ROW_NUMBER() OVER (
                        PARTITION BY register_key
                        ORDER BY tick DESC
                    ) as row_num
                FROM agent_state_registers
                WHERE simulation_id = ?
                  AND agent_id = ?
                  AND tick <= ?
            ) subquery
            WHERE row_num = 1
        """

        rows = self.conn.execute(query, [self.simulation_id, agent_id, tick]).fetchall()

        # Convert to dict
        registers = {}
        for row in rows:
            register_key = row[0]
            register_value = row[1]
            registers[register_key] = register_value

        return registers
