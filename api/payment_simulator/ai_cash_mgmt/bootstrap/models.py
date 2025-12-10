"""Data structures for bootstrap-based policy evaluation.

This module defines immutable data structures for:
1. Historical transactions with relative timing offsets (TransactionRecord)
2. Remapped transactions with absolute ticks (RemappedTransaction)
3. Bootstrap samples for Monte Carlo evaluation (BootstrapSample)

All money amounts are integers representing cents (project invariant).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionRecord:
    """Historical transaction with relative timing offsets.

    Stores offsets (not absolute ticks) so the transaction can be
    remapped to different arrival times while preserving relative timing.
    This is central to the bootstrap methodology - we preserve the
    transaction's characteristics (amount, priority) and relative timing
    (deadline_offset, settlement_offset) while varying when it arrives.

    Attributes:
        tx_id: Unique transaction identifier.
        sender_id: ID of the sending agent.
        receiver_id: ID of the receiving agent.
        amount: Payment amount in cents (integer, never float).
        priority: Transaction priority (0-10, higher = more urgent).
        original_arrival_tick: When transaction arrived in the original simulation.
        deadline_offset: Ticks from arrival to deadline.
        settlement_offset: Ticks from arrival to settlement (None if unsettled).
    """

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents (i64 equivalent, project invariant)
    priority: int
    original_arrival_tick: int
    deadline_offset: int  # ticks from arrival to deadline
    settlement_offset: int | None  # ticks from arrival to settlement (None if unsettled)

    @property
    def was_settled(self) -> bool:
        """Whether this transaction was settled in the original simulation."""
        return self.settlement_offset is not None

    def remap_to_tick(self, new_arrival: int, eod_tick: int) -> RemappedTransaction:
        """Remap this transaction to a new arrival tick.

        Creates a RemappedTransaction with absolute ticks based on the new
        arrival time. Deadline and settlement are capped at end-of-day (eod_tick).

        Args:
            new_arrival: The new arrival tick for this transaction.
            eod_tick: End-of-day tick (caps deadline and settlement).

        Returns:
            RemappedTransaction with absolute ticks.
        """
        settlement_tick: int | None = None
        if self.settlement_offset is not None:
            settlement_tick = min(new_arrival + self.settlement_offset, eod_tick)

        return RemappedTransaction(
            tx_id=self.tx_id,
            sender_id=self.sender_id,
            receiver_id=self.receiver_id,
            amount=self.amount,
            priority=self.priority,
            arrival_tick=new_arrival,
            deadline_tick=min(new_arrival + self.deadline_offset, eod_tick),
            settlement_tick=settlement_tick,
        )


@dataclass(frozen=True)
class RemappedTransaction:
    """Transaction with absolute ticks after bootstrap remapping.

    This represents a transaction that has been remapped to a specific
    arrival tick in a bootstrap sample. All timing is now absolute.

    For outgoing transactions: Used to schedule when payment obligations arrive.
    For incoming transactions: settlement_tick is when liquidity arrives ("beat").

    Attributes:
        tx_id: Unique transaction identifier.
        sender_id: ID of the sending agent.
        receiver_id: ID of the receiving agent.
        amount: Payment amount in cents (integer, never float).
        priority: Transaction priority (0-10, higher = more urgent).
        arrival_tick: When transaction arrives in the bootstrap day.
        deadline_tick: Absolute tick for settlement deadline.
        settlement_tick: When settled (for incoming: when liquidity arrives).
                        None for unsettled transactions.
    """

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents (i64 equivalent, project invariant)
    priority: int
    arrival_tick: int
    deadline_tick: int
    settlement_tick: int | None  # For incoming: when liquidity arrives


@dataclass(frozen=True)
class BootstrapSample:
    """One bootstrap sample with remapped transactions for evaluation.

    Holds all the remapped transactions for a single bootstrap sample.
    This is the input to the sandbox evaluator.

    The sample contains:
    - outgoing_txns: Payment obligations the agent must settle
    - incoming_settlements: "Liquidity beats" - when the agent receives liquidity

    Attributes:
        agent_id: The agent being evaluated.
        sample_idx: Index in the Monte Carlo sequence (for tracking).
        seed: Seed used to generate this sample (for reproducibility).
        outgoing_txns: Tuple of remapped outgoing transactions.
        incoming_settlements: Tuple of remapped incoming transactions ("beats").
        total_ticks: Number of ticks in the simulated day.
    """

    agent_id: str
    sample_idx: int
    seed: int
    outgoing_txns: tuple[RemappedTransaction, ...]
    incoming_settlements: tuple[RemappedTransaction, ...]
    total_ticks: int

    def get_incoming_liquidity_at_tick(self, tick: int) -> int:
        """Get total incoming liquidity settling at this tick.

        Sums the amounts of all incoming settlements where settlement_tick
        equals the specified tick. Unsettled transactions (settlement_tick=None)
        are skipped.

        Args:
            tick: The tick to query.

        Returns:
            Total incoming liquidity in cents at this tick.
        """
        return sum(
            tx.amount
            for tx in self.incoming_settlements
            if tx.settlement_tick == tick
        )

    def get_outgoing_arrivals_at_tick(self, tick: int) -> tuple[RemappedTransaction, ...]:
        """Get outgoing transactions arriving at this tick.

        Returns all outgoing transactions whose arrival_tick equals the
        specified tick.

        Args:
            tick: The tick to query.

        Returns:
            Tuple of RemappedTransaction instances arriving at this tick.
        """
        return tuple(tx for tx in self.outgoing_txns if tx.arrival_tick == tick)
