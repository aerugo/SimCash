"""State provider protocol for unified output functions.

Defines a common interface for accessing simulation state, implemented by
both live Orchestrator (via FFI) and database replay (via queries).
"""

from typing import Any, Protocol, TypedDict, cast, runtime_checkable

from duckdb import DuckDBPyConnection

from payment_simulator._core import Orchestrator


# =============================================================================
# TypedDicts for structured return types
# =============================================================================


class TransactionDetails(TypedDict):
    """Transaction details returned by get_transaction_details."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    remaining_amount: int
    priority: int
    deadline_tick: int
    status: str
    is_divisible: bool


class AccumulatedCosts(TypedDict):
    """Accumulated costs returned by get_agent_accumulated_costs."""

    liquidity_cost: int
    delay_cost: int
    collateral_cost: int
    penalty_cost: int
    split_friction_cost: int
    deadline_penalty: int  # Alias for penalty_cost
    total_cost: int


class NearDeadlineTransaction(TypedDict):
    """Transaction near deadline returned by get_transactions_near_deadline."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    remaining_amount: int
    deadline_tick: int
    ticks_until_deadline: int


class OverdueTransaction(TypedDict):
    """Overdue transaction returned by get_overdue_transactions."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    remaining_amount: int
    deadline_tick: int
    overdue_since_tick: int
    ticks_overdue: int
    deadline_penalty_cost: int
    estimated_delay_cost: int
    total_overdue_cost: int


@runtime_checkable
class StateProvider(Protocol):
    """Protocol for accessing simulation state.

    This interface is implemented by both:
    - OrchestratorStateProvider (live execution via FFI)
    - DatabaseStateProvider (replay from database)

    Enables unified output functions that work identically in both modes.
    """

    def get_transaction_details(self, tx_id: str) -> TransactionDetails | None:
        """Get transaction details by ID.

        Returns:
            TransactionDetails with keys: tx_id, sender_id, receiver_id, amount,
            remaining_amount, priority, deadline_tick, status, is_divisible
            Returns None if transaction not found.
        """
        ...

    def get_agent_balance(self, agent_id: str) -> int:
        """Get agent's current balance in cents."""
        ...

    def get_agent_unsecured_cap(self, agent_id: str) -> int:
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

    def get_agent_accumulated_costs(self, agent_id: str) -> AccumulatedCosts:
        """Get accumulated costs for agent.

        Returns:
            AccumulatedCosts with keys: liquidity_cost, delay_cost, collateral_cost,
            penalty_cost, split_friction_cost, deadline_penalty, total_cost (all in cents)
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

    def get_transactions_near_deadline(self, within_ticks: int) -> list[NearDeadlineTransaction]:
        """Get transactions approaching their deadline.

        Args:
            within_ticks: Number of ticks ahead to check (e.g., 2 for "within 2 ticks")

        Returns:
            List of NearDeadlineTransaction dicts with keys: tx_id, sender_id,
            receiver_id, amount, remaining_amount, deadline_tick, ticks_until_deadline
        """
        ...

    def get_overdue_transactions(self) -> list[OverdueTransaction]:
        """Get all currently overdue transactions with cost data.

        Returns:
            List of OverdueTransaction dicts with keys: tx_id, sender_id, receiver_id,
            amount, remaining_amount, deadline_tick, overdue_since_tick, ticks_overdue,
            deadline_penalty_cost, estimated_delay_cost, total_overdue_cost
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

    def get_transaction_details(self, tx_id: str) -> TransactionDetails | None:
        """Delegate to orchestrator."""
        result = self.orch.get_transaction_details(tx_id)
        return cast(TransactionDetails, result) if result else None

    def get_agent_balance(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        result = self.orch.get_agent_balance(agent_id)
        return result if result is not None else 0

    def get_agent_unsecured_cap(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        result = self.orch.get_agent_unsecured_cap(agent_id)
        return result if result is not None else 0

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_agent_queue1_contents(agent_id)

    def get_rtgs_queue_contents(self) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_rtgs_queue_contents()

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        result = self.orch.get_agent_collateral_posted(agent_id)
        return result if result is not None else 0

    def get_agent_accumulated_costs(self, agent_id: str) -> AccumulatedCosts:
        """Delegate to orchestrator."""
        return cast(AccumulatedCosts, self.orch.get_agent_accumulated_costs(agent_id))

    def get_queue1_size(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_queue1_size(agent_id)

    def get_queue2_size(self, agent_id: str) -> int:
        """Calculate Queue 2 size from RTGS queue contents."""
        rtgs_queue = self.orch.get_rtgs_queue_contents()
        count = 0
        for tx_id in rtgs_queue:
            tx = self.orch.get_transaction_details(tx_id)
            if tx and tx.get("sender_id") == agent_id:
                count += 1
        return count

    def get_transactions_near_deadline(self, within_ticks: int) -> list[NearDeadlineTransaction]:
        """Delegate to orchestrator."""
        return cast(
            list[NearDeadlineTransaction],
            self.orch.get_transactions_near_deadline(within_ticks),
        )

    def get_overdue_transactions(self) -> list[OverdueTransaction]:
        """Delegate to orchestrator."""
        return cast(list[OverdueTransaction], self.orch.get_overdue_transactions())


class DatabaseStateProvider:
    """StateProvider implementation using database state (replay).

    Reads from pre-loaded database state (agent_states, queue_snapshots, tx_cache)
    to provide same interface as Orchestrator without re-execution.
    """

    def __init__(
        self,
        conn: DuckDBPyConnection,
        simulation_id: str,
        tick: int,
        tx_cache: dict[str, dict[str, Any]],
        agent_states: dict[str, dict[str, Any]],
        queue_snapshots: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize with database state.

        Args:
            conn: DuckDB database connection (for future queries if needed)
            simulation_id: Simulation identifier
            tick: Current tick number
            tx_cache: Dict mapping tx_id -> transaction details
            agent_states: Dict mapping agent_id -> agent state dict
            queue_snapshots: Dict mapping agent_id -> queue snapshot dict
        """
        self.conn: DuckDBPyConnection = conn
        self.simulation_id = simulation_id
        self.tick = tick
        self._tx_cache = tx_cache
        self._agent_states = agent_states
        self._queue_snapshots = queue_snapshots

    def get_transaction_details(self, tx_id: str) -> TransactionDetails | None:
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
            amount_settled = int(tx.get("amount_settled", 0))
        # else: Transaction not yet settled at this tick, amount_settled = 0

        # Convert database format to orchestrator format
        return TransactionDetails(
            tx_id=tx["tx_id"],
            sender_id=tx["sender_id"],
            receiver_id=tx["receiver_id"],
            amount=tx["amount"],
            remaining_amount=int(tx.get("amount", 0)) - amount_settled,
            priority=tx["priority"],
            deadline_tick=tx["deadline_tick"],
            status=tx["status"],
            is_divisible=tx.get("is_divisible", False),
        )

    def get_agent_balance(self, agent_id: str) -> int:
        """Get balance from agent_states."""
        # Handle missing agent_id gracefully
        if agent_id not in self._agent_states:
            return 0
        return int(self._agent_states[agent_id].get("balance", 0))

    def get_agent_unsecured_cap(self, agent_id: str) -> int:
        """Get credit limit from agent_states."""
        # Handle missing unsecured_cap gracefully (older databases may not have it)
        if agent_id not in self._agent_states:
            return 0
        return int(self._agent_states[agent_id].get("unsecured_cap", 0))

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get queue1 from queue_snapshots."""
        result = self._queue_snapshots.get(agent_id, {}).get("queue1", [])
        return result if isinstance(result, list) else []

    def get_rtgs_queue_contents(self) -> list[str]:
        """Aggregate RTGS queue from all agent snapshots."""
        rtgs_txs = []
        for agent_id, queues in self._queue_snapshots.items():
            rtgs_txs.extend(queues.get("rtgs", []))
        return rtgs_txs

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral from agent_states."""
        # Database schema uses "posted_collateral" not "collateral_posted"
        return int(self._agent_states.get(agent_id, {}).get("posted_collateral", 0))

    def get_agent_accumulated_costs(self, agent_id: str) -> AccumulatedCosts:
        """Get costs from agent_states."""
        state = self._agent_states.get(agent_id, {})
        liquidity_cost = int(state.get("liquidity_cost", 0))
        delay_cost = int(state.get("delay_cost", 0))
        collateral_cost = int(state.get("collateral_cost", 0))
        penalty_cost = int(state.get("penalty_cost", 0))
        split_friction_cost = int(state.get("split_friction_cost", 0))

        return AccumulatedCosts(
            liquidity_cost=liquidity_cost,
            delay_cost=delay_cost,
            collateral_cost=collateral_cost,
            penalty_cost=penalty_cost,
            split_friction_cost=split_friction_cost,
            deadline_penalty=penalty_cost,  # Alias for compatibility
            total_cost=liquidity_cost + delay_cost + collateral_cost + penalty_cost + split_friction_cost,
        )

    def get_queue1_size(self, agent_id: str) -> int:
        """Get queue1 size."""
        return len(self.get_agent_queue1_contents(agent_id))

    def get_queue2_size(self, agent_id: str) -> int:
        """Get Queue 2 size from queue snapshots.

        Queue 2 consists of transactions in the RTGS queue that belong to this agent.
        """
        rtgs_queue = self.get_rtgs_queue_contents()
        count = 0
        for tx_id in rtgs_queue:
            tx_details = self.get_transaction_details(tx_id)
            if tx_details and tx_details.get("sender_id") == agent_id:
                count += 1
        return count

    def get_transactions_near_deadline(self, within_ticks: int) -> list[NearDeadlineTransaction]:
        """Get transactions approaching deadline from cache.

        CRITICAL FIX (Issue #12):
        Only return transactions that are ACTUALLY in Queue-1 or Queue-2 at
        the current tick. Previously this scanned ALL transactions in cache,
        showing phantom transactions that had already been submitted or settled.
        """
        threshold = self.tick + within_ticks
        near_deadline: list[NearDeadlineTransaction] = []

        # Build set of ALL tx_ids currently in Queue-1 or Queue-2
        queued_tx_ids: set[str] = set()
        for _agent_id, queues in self._queue_snapshots.items():
            queued_tx_ids.update(queues.get("queue1", []))
            queued_tx_ids.update(queues.get("rtgs", []))

        for tx_id, tx in self._tx_cache.items():
            # CRITICAL: Only consider transactions currently in queues
            if tx_id not in queued_tx_ids:
                continue

            # CRITICAL FIX (Discrepancy #1): Don't check status field in replay!
            # In replay, tx_cache contains FINAL state (status='settled' at end of sim),
            # not state at current tick. We must check settlement_tick instead.
            # The old check `if tx.get("status") == "settled": continue` was wrong!

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
                near_deadline.append(NearDeadlineTransaction(
                    tx_id=tx["tx_id"],
                    sender_id=tx["sender_id"],
                    receiver_id=tx["receiver_id"],
                    amount=tx["amount"],
                    remaining_amount=remaining,
                    deadline_tick=deadline,
                    ticks_until_deadline=deadline - self.tick,
                ))

        return near_deadline

    def get_overdue_transactions(self) -> list[OverdueTransaction]:
        """Get overdue transactions by querying simulation_events."""
        import json

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

        overdue_txs: dict[str, OverdueTransaction] = {}

        rows = self.conn.execute(query, [self.simulation_id, self.tick]).fetchall()
        for row in rows:
            event = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # Merge in the separate columns
            tx_id: str = row[1]  # tx_id column
            event["tx_id"] = tx_id
            event["tick"] = row[2]  # tick column
            if row[3]:  # agent_id column (nullable)
                event["agent_id"] = row[3]

            # Check if this transaction has been settled since going overdue
            tx = self._tx_cache.get(tx_id)
            if tx and tx.get("status") == "settled":
                continue  # Skip settled transactions

            # Calculate current overdue status
            overdue_since: int = event["tick"]
            ticks_overdue = self.tick - overdue_since

            # CRITICAL FIX (Discrepancy #7): Get ACTUAL delay costs from CostAccrual events
            # Do NOT recalculate with a formula - use persisted events as single source of truth
            actual_delay_cost = 0
            cost_query = """
                SELECT details FROM simulation_events
                WHERE simulation_id = ?
                    AND tx_id = ?
                    AND event_type = 'CostAccrual'
                    AND tick > ?
                    AND tick <= ?
            """
            cost_rows = self.conn.execute(
                cost_query,
                [self.simulation_id, tx_id, event["deadline_tick"], self.tick]
            ).fetchall()

            for cost_row in cost_rows:
                cost_event = json.loads(cost_row[0]) if isinstance(cost_row[0], str) else cost_row[0]
                # Sum all delay-related costs (overdue transactions accrue delay costs)
                actual_delay_cost += cost_event.get("delay_cost", 0)

            deadline_penalty = int(event.get("deadline_penalty_cost", 0))
            overdue_txs[tx_id] = OverdueTransaction(
                tx_id=tx_id,
                sender_id=event["sender_id"],
                receiver_id=event["receiver_id"],
                amount=event["amount"],
                remaining_amount=event.get("remaining_amount", event["amount"]),
                deadline_tick=event["deadline_tick"],
                overdue_since_tick=overdue_since,
                ticks_overdue=ticks_overdue,
                deadline_penalty_cost=deadline_penalty,
                # Use ACTUAL accumulated delay costs from events, not formula
                estimated_delay_cost=actual_delay_cost,
                total_overdue_cost=deadline_penalty + actual_delay_cost,
            )

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


class BootstrapEventStateProvider:
    """StateProvider adapter for BootstrapEvent lists.

    Provides minimal StateProvider implementation for formatting bootstrap
    events. Only implements methods needed by output formatting functions.

    Since bootstrap events don't include full simulation state (like queue
    contents, agent balances), this adapter returns sensible defaults for
    most queries. The primary use case is to enable pretty-formatting of
    bootstrap event traces for LLM context.

    Attributes:
        _events: List of BootstrapEvent objects.
        _agent_id: Agent ID being evaluated.
        _event_dicts: Cached dict representations of events.
        _balance_cache: Cache of agent balances extracted from events.

    Example:
        >>> from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import BootstrapEvent
        >>> events = [
        ...     BootstrapEvent(tick=0, event_type="Arrival", details={"tx_id": "123", ...}),
        ...     BootstrapEvent(tick=1, event_type="RtgsImmediateSettlement", details={...}),
        ... ]
        >>> provider = BootstrapEventStateProvider(events, "BANK_A")
        >>> balance = provider.get_agent_balance("BANK_A")
    """

    def __init__(
        self,
        events: list[Any],  # List of BootstrapEvent
        agent_id: str,
        opening_balance: int = 0,
    ) -> None:
        """Initialize the state provider.

        Args:
            events: List of BootstrapEvent objects from bootstrap evaluation.
            agent_id: ID of the agent being evaluated.
            opening_balance: Starting balance for the agent (cents).
        """
        self._events = events
        self._agent_id = agent_id
        self._opening_balance = opening_balance
        self._event_dicts = [self._to_dict(e) for e in events]
        self._balance_cache: dict[str, int] = {}
        self._tx_cache: dict[str, TransactionDetails] = {}

        # Pre-populate balance and transaction caches from events
        self._build_caches()

    def _to_dict(self, event: Any) -> dict[str, Any]:
        """Convert a BootstrapEvent to a dict.

        Args:
            event: BootstrapEvent object.

        Returns:
            Dict representation with tick, event_type, and merged details.
        """
        return {
            "tick": event.tick,
            "event_type": event.event_type,
            **event.details,
        }

    def _build_caches(self) -> None:
        """Build caches from events for efficient lookups."""
        # Track balance changes from settlement events
        running_balance: dict[str, int] = {}

        for event in self._event_dicts:
            event_type = event.get("event_type")

            # Track balance from settlement events
            if event_type == "RtgsImmediateSettlement":
                sender = event.get("sender")
                receiver = event.get("receiver")

                # Update sender's balance if we have the data
                if sender == self._agent_id:
                    balance_after = event.get("sender_balance_after")
                    if balance_after is not None:
                        running_balance[sender] = balance_after

                # Receiver gets incoming funds
                if receiver == self._agent_id:
                    amount = event.get("amount", 0)
                    current = running_balance.get(receiver, self._opening_balance)
                    running_balance[receiver] = current + amount

            # Track transactions from arrival events
            if event_type == "Arrival":
                tx_id = event.get("tx_id")
                if tx_id:
                    self._tx_cache[tx_id] = TransactionDetails(
                        tx_id=tx_id,
                        sender_id=event.get("sender_id", ""),
                        receiver_id=event.get("receiver_id", ""),
                        amount=event.get("amount", 0),
                        remaining_amount=event.get("amount", 0),
                        priority=event.get("priority", 5),
                        deadline_tick=event.get("deadline_tick", 0),
                        status="pending",
                        is_divisible=event.get("is_divisible", False),
                    )

        self._balance_cache = running_balance

    def get_transaction_details(self, tx_id: str) -> TransactionDetails | None:
        """Get transaction details by ID.

        Returns cached transaction details if available, None otherwise.
        """
        return self._tx_cache.get(tx_id)

    def get_agent_balance(self, agent_id: str) -> int:
        """Get agent's balance from cached values or opening balance."""
        return self._balance_cache.get(agent_id, self._opening_balance)

    def get_agent_unsecured_cap(self, agent_id: str) -> int:
        """Get agent's credit limit.

        Bootstrap events don't include credit limit data, so return 0.
        """
        return 0

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get list of transaction IDs in agent's internal queue.

        Bootstrap events don't track queue contents, so return empty list.
        """
        return []

    def get_rtgs_queue_contents(self) -> list[str]:
        """Get list of transaction IDs in RTGS central queue.

        Bootstrap events don't track queue contents, so return empty list.
        """
        return []

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral posted by agent.

        Bootstrap events don't track collateral, so return 0.
        """
        return 0

    def get_agent_accumulated_costs(self, agent_id: str) -> AccumulatedCosts:
        """Get accumulated costs for agent from events.

        Scans CostAccrual events to build cost breakdown.
        """
        total_liquidity = 0
        total_delay = 0
        total_collateral = 0
        total_penalty = 0
        total_split_friction = 0

        for event in self._event_dicts:
            if event.get("event_type") == "CostAccrual":
                if event.get("agent_id") == agent_id:
                    costs = event.get("costs", {})
                    total_liquidity += costs.get("liquidity_cost", 0)
                    total_delay += costs.get("delay_cost", 0)
                    total_collateral += costs.get("collateral_cost", 0)
                    total_penalty += costs.get("penalty_cost", 0)
                    total_split_friction += costs.get("split_friction_cost", 0)

        return AccumulatedCosts(
            liquidity_cost=total_liquidity,
            delay_cost=total_delay,
            collateral_cost=total_collateral,
            penalty_cost=total_penalty,
            split_friction_cost=total_split_friction,
            deadline_penalty=total_penalty,
            total_cost=total_liquidity + total_delay + total_collateral + total_penalty + total_split_friction,
        )

    def get_queue1_size(self, agent_id: str) -> int:
        """Get size of agent's internal queue.

        Bootstrap events don't track queue contents, so return 0.
        """
        return 0

    def get_queue2_size(self, agent_id: str) -> int:
        """Get size of agent's RTGS queue.

        Bootstrap events don't track queue contents, so return 0.
        """
        return 0

    def get_transactions_near_deadline(self, within_ticks: int) -> list[NearDeadlineTransaction]:
        """Get transactions approaching their deadline.

        Bootstrap events don't track transaction state, so return empty list.
        """
        return []

    def get_overdue_transactions(self) -> list[OverdueTransaction]:
        """Get all currently overdue transactions.

        Bootstrap events don't track overdue state, so return empty list.
        """
        return []

    def get_event_dicts(self) -> list[dict[str, Any]]:
        """Get the cached list of event dicts.

        Useful for passing to format_events_as_text() after filtering.
        """
        return self._event_dicts
