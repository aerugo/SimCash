"""Transaction history collector for bootstrap sampling.

This module collects transaction histories from simulation events,
converting them to TransactionRecord objects for bootstrap resampling.

Key responsibilities:
1. Parse arrival events to create pending records
2. Match settlement events to update settlement_offset
3. Track incoming vs outgoing transactions per agent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord

# Type alias for event dictionaries from FFI layer
# Events are dicts with string keys and various value types
EventDict = dict[str, Any]


@dataclass
class AgentTransactionHistory:
    """Transaction history for a single agent.

    Contains both outgoing (agent sends) and incoming (agent receives)
    transaction records.

    Attributes:
        agent_id: The agent this history belongs to.
        outgoing: Transactions sent by this agent.
        incoming: Transactions received by this agent.
    """

    agent_id: str
    outgoing: tuple[TransactionRecord, ...]
    incoming: tuple[TransactionRecord, ...]


@dataclass
class _PendingRecord:
    """Mutable record during collection phase.

    Internal class used during event processing. Gets converted to
    immutable TransactionRecord after all events are processed.
    """

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int
    priority: int
    original_arrival_tick: int
    deadline_offset: int
    settlement_offset: int | None = None

    def to_transaction_record(self) -> TransactionRecord:
        """Convert to immutable TransactionRecord."""
        return TransactionRecord(
            tx_id=self.tx_id,
            sender_id=self.sender_id,
            receiver_id=self.receiver_id,
            amount=self.amount,
            priority=self.priority,
            original_arrival_tick=self.original_arrival_tick,
            deadline_offset=self.deadline_offset,
            settlement_offset=self.settlement_offset,
        )


@dataclass
class _AgentPendingHistory:
    """Mutable history during collection phase."""

    outgoing: list[_PendingRecord] = field(default_factory=list)
    incoming: list[_PendingRecord] = field(default_factory=list)


class TransactionHistoryCollector:
    """Collects transaction history from simulation events.

    Processes simulation events to build a complete transaction history
    for each agent. Handles:
    - Arrival events (creates pending records)
    - Settlement events (updates settlement_offset)
        - rtgs_immediate_settlement
        - queue2_liquidity_release
        - lsm_bilateral_offset
        - lsm_cycle_settlement

    Example usage:
        ```python
        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        print(f"Outgoing: {len(history.outgoing)}")
        print(f"Incoming: {len(history.incoming)}")
        ```
    """

    def __init__(self) -> None:
        """Initialize the collector."""
        # tx_id -> pending record (for settlement matching)
        self._records_by_tx_id: dict[str, _PendingRecord] = {}
        # agent_id -> pending history
        self._histories: dict[str, _AgentPendingHistory] = {}
        # Track all agent IDs seen
        self._agent_ids: set[str] = set()

    def process_events(self, events: list[EventDict]) -> None:
        """Process simulation events to build transaction history.

        Args:
            events: List of event dictionaries from simulation.
        """
        for event in events:
            event_type = event.get("event_type")

            if event_type == "arrival":
                self._process_arrival(event)
            elif event_type == "rtgs_immediate_settlement":
                self._process_rtgs_settlement(event)
            elif event_type == "queue2_liquidity_release":
                self._process_queue2_release(event)
            elif event_type == "lsm_bilateral_offset":
                self._process_lsm_bilateral(event)
            elif event_type == "lsm_cycle_settlement":
                self._process_lsm_cycle(event)
            # Ignore other event types

    def _process_arrival(self, event: EventDict) -> None:
        """Process an arrival event."""
        tx_id = str(event["tx_id"])
        sender_id = str(event["sender_id"])
        receiver_id = str(event["receiver_id"])
        tick = int(event["tick"])
        deadline_tick = int(event["deadline_tick"])

        record = _PendingRecord(
            tx_id=tx_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=int(event["amount"]),
            priority=int(event["priority"]),
            original_arrival_tick=tick,
            deadline_offset=deadline_tick - tick,
        )

        # Store for settlement matching
        self._records_by_tx_id[tx_id] = record

        # Track agents
        self._agent_ids.add(sender_id)
        self._agent_ids.add(receiver_id)

        # Add to sender's outgoing
        self._get_history(sender_id).outgoing.append(record)
        # Add to receiver's incoming
        self._get_history(receiver_id).incoming.append(record)

    def _process_rtgs_settlement(self, event: EventDict) -> None:
        """Process RTGS immediate settlement event."""
        tx_id = str(event["tx_id"])
        tick = int(event["tick"])
        self._mark_settled(tx_id, tick)

    def _process_queue2_release(self, event: EventDict) -> None:
        """Process Queue2 liquidity release event."""
        tx_id = str(event["tx_id"])
        tick = int(event["tick"])
        self._mark_settled(tx_id, tick)

    def _process_lsm_bilateral(self, event: EventDict) -> None:
        """Process LSM bilateral offset event."""
        tick = int(event["tick"])
        tx_ids = event.get("tx_ids", [])
        if isinstance(tx_ids, list):
            for tx_id in tx_ids:
                self._mark_settled(str(tx_id), tick)

    def _process_lsm_cycle(self, event: EventDict) -> None:
        """Process LSM cycle settlement event."""
        tick = int(event["tick"])
        tx_ids = event.get("tx_ids", [])
        if isinstance(tx_ids, list):
            for tx_id in tx_ids:
                self._mark_settled(str(tx_id), tick)

    def _mark_settled(self, tx_id: str, settlement_tick: int) -> None:
        """Mark a transaction as settled at the given tick."""
        record = self._records_by_tx_id.get(tx_id)
        if record is not None:
            record.settlement_offset = settlement_tick - record.original_arrival_tick

    def _get_history(self, agent_id: str) -> _AgentPendingHistory:
        """Get or create pending history for an agent."""
        if agent_id not in self._histories:
            self._histories[agent_id] = _AgentPendingHistory()
        return self._histories[agent_id]

    def get_agent_history(self, agent_id: str) -> AgentTransactionHistory:
        """Get finalized transaction history for an agent.

        Args:
            agent_id: The agent to get history for.

        Returns:
            AgentTransactionHistory with immutable TransactionRecords.
        """
        pending = self._histories.get(agent_id)
        if pending is None:
            return AgentTransactionHistory(
                agent_id=agent_id,
                outgoing=(),
                incoming=(),
            )

        return AgentTransactionHistory(
            agent_id=agent_id,
            outgoing=tuple(r.to_transaction_record() for r in pending.outgoing),
            incoming=tuple(r.to_transaction_record() for r in pending.incoming),
        )

    def get_all_agent_ids(self) -> set[str]:
        """Get all agent IDs seen in events.

        Returns:
            Set of all agent IDs (senders and receivers).
        """
        return self._agent_ids.copy()
