"""Unit tests for bootstrap data structures.

Phase 1: Data Structures - TDD Tests

Tests for:
- TransactionRecord: Historical transaction with relative timing offsets
- RemappedTransaction: Transaction with absolute ticks after remapping
- BootstrapSample: Collection of remapped transactions for evaluation
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
    TransactionRecord,
)


class TestTransactionRecordCreation:
    """Test TransactionRecord creation and basic properties."""

    def test_transaction_record_creation(self) -> None:
        """TransactionRecord stores transaction with relative timing offsets."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,  # $5,000.00
            priority=5,
            original_arrival_tick=10,
            deadline_offset=5,  # deadline = arrival + 5
            settlement_offset=3,  # settled = arrival + 3
        )

        assert record.tx_id == "tx-001"
        assert record.sender_id == "BANK_A"
        assert record.receiver_id == "BANK_B"
        assert record.amount == 500000
        assert record.priority == 5
        assert record.original_arrival_tick == 10
        assert record.deadline_offset == 5
        assert record.settlement_offset == 3
        assert record.was_settled is True  # settlement_offset is not None

    def test_transaction_record_unsettled(self) -> None:
        """TransactionRecord handles unsettled transactions."""
        record = TransactionRecord(
            tx_id="tx-002",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=3,
            original_arrival_tick=5,
            deadline_offset=10,
            settlement_offset=None,  # Never settled!
        )

        assert record.was_settled is False
        assert record.settlement_offset is None

    def test_transaction_record_immutable(self) -> None:
        """TransactionRecord is immutable (frozen dataclass)."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,
            priority=5,
            original_arrival_tick=10,
            deadline_offset=5,
            settlement_offset=3,
        )

        with pytest.raises(AttributeError):
            record.amount = 1000  # type: ignore[misc]


class TestTransactionRemapping:
    """Test TransactionRecord.remap_to_tick() method."""

    def test_remap_to_new_arrival_tick(self) -> None:
        """Remapping preserves offsets while changing arrival tick."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,
            priority=5,
            original_arrival_tick=10,
            deadline_offset=5,
            settlement_offset=3,
        )

        # Remap to new arrival at tick 2
        remapped = record.remap_to_tick(new_arrival=2, eod_tick=12)

        assert remapped.arrival_tick == 2
        assert remapped.deadline_tick == 7  # 2 + 5
        assert remapped.settlement_tick == 5  # 2 + 3
        assert remapped.amount == 500000  # Unchanged
        assert remapped.priority == 5
        assert remapped.tx_id == "tx-001"
        assert remapped.sender_id == "BANK_A"
        assert remapped.receiver_id == "BANK_B"

    def test_remap_caps_at_eod(self) -> None:
        """Remapping caps deadline and settlement at end-of-day."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,
            priority=5,
            original_arrival_tick=5,
            deadline_offset=10,
            settlement_offset=8,
        )

        # Remap to tick 8, but EoD is tick 12
        remapped = record.remap_to_tick(new_arrival=8, eod_tick=12)

        assert remapped.arrival_tick == 8
        assert remapped.deadline_tick == 12  # Capped: min(8+10, 12)
        assert remapped.settlement_tick == 12  # Capped: min(8+8, 12)

    def test_remap_unsettled_transaction(self) -> None:
        """Remapping unsettled transaction has no settlement_tick."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,
            priority=5,
            original_arrival_tick=5,
            deadline_offset=10,
            settlement_offset=None,
        )

        remapped = record.remap_to_tick(new_arrival=2, eod_tick=12)

        assert remapped.settlement_tick is None
        assert remapped.deadline_tick == 12  # 2 + 10, not capped

    def test_remap_returns_remapped_transaction_type(self) -> None:
        """Remapping returns a RemappedTransaction instance."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            original_arrival_tick=0,
            deadline_offset=10,
            settlement_offset=5,
        )

        remapped = record.remap_to_tick(new_arrival=0, eod_tick=12)

        assert isinstance(remapped, RemappedTransaction)


class TestRemappedTransaction:
    """Test RemappedTransaction dataclass."""

    def test_remapped_transaction_creation(self) -> None:
        """RemappedTransaction stores absolute ticks."""
        remapped = RemappedTransaction(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=2,
            deadline_tick=12,
            settlement_tick=7,
        )

        assert remapped.tx_id == "tx-001"
        assert remapped.arrival_tick == 2
        assert remapped.deadline_tick == 12
        assert remapped.settlement_tick == 7

    def test_remapped_transaction_immutable(self) -> None:
        """RemappedTransaction is immutable (frozen dataclass)."""
        remapped = RemappedTransaction(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=2,
            deadline_tick=12,
            settlement_tick=7,
        )

        with pytest.raises(AttributeError):
            remapped.amount = 1000  # type: ignore[misc]

    def test_remapped_transaction_none_settlement(self) -> None:
        """RemappedTransaction can have None settlement_tick for unsettled."""
        remapped = RemappedTransaction(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=2,
            deadline_tick=12,
            settlement_tick=None,
        )

        assert remapped.settlement_tick is None


class TestBootstrapSampleCreation:
    """Test BootstrapSample creation and basic properties."""

    def test_bootstrap_sample_creation(self) -> None:
        """BootstrapSample holds remapped transactions and metadata."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-1",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=1000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=None,
            ),
        )
        incoming = (
            RemappedTransaction(
                tx_id="tx-2",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=2000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=3,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=incoming,
            total_ticks=12,
        )

        assert sample.agent_id == "BANK_A"
        assert sample.sample_idx == 0
        assert sample.seed == 12345
        assert len(sample.outgoing_txns) == 1
        assert len(sample.incoming_settlements) == 1
        assert sample.total_ticks == 12

    def test_bootstrap_sample_immutable(self) -> None:
        """BootstrapSample is immutable (frozen dataclass)."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=12,
        )

        with pytest.raises(AttributeError):
            sample.seed = 999  # type: ignore[misc]

    def test_bootstrap_sample_empty_tuples(self) -> None:
        """BootstrapSample handles empty transaction tuples."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=12,
        )

        assert len(sample.outgoing_txns) == 0
        assert len(sample.incoming_settlements) == 0


class TestBootstrapSampleLiquidityMethods:
    """Test BootstrapSample helper methods for liquidity calculations."""

    def test_get_incoming_liquidity_at_tick(self) -> None:
        """BootstrapSample computes incoming liquidity at specific tick."""
        incoming = (
            RemappedTransaction(
                tx_id="tx-1",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=5000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=3,
            ),
            RemappedTransaction(
                tx_id="tx-2",
                sender_id="BANK_C",
                receiver_id="BANK_A",
                amount=3000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=3,  # Same tick!
            ),
            RemappedTransaction(
                tx_id="tx-3",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=2000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=7,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=incoming,
            total_ticks=12,
        )

        assert sample.get_incoming_liquidity_at_tick(3) == 8000  # 5000 + 3000
        assert sample.get_incoming_liquidity_at_tick(7) == 2000
        assert sample.get_incoming_liquidity_at_tick(5) == 0  # No settlements at tick 5

    def test_get_incoming_liquidity_at_tick_no_settlements(self) -> None:
        """get_incoming_liquidity_at_tick returns 0 when no settlements."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=12,
        )

        assert sample.get_incoming_liquidity_at_tick(0) == 0
        assert sample.get_incoming_liquidity_at_tick(5) == 0

    def test_get_incoming_liquidity_skips_unsettled(self) -> None:
        """get_incoming_liquidity_at_tick skips unsettled transactions."""
        incoming = (
            RemappedTransaction(
                tx_id="tx-1",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=5000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=3,
            ),
            RemappedTransaction(
                tx_id="tx-2",
                sender_id="BANK_C",
                receiver_id="BANK_A",
                amount=3000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=None,  # Unsettled!
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=incoming,
            total_ticks=12,
        )

        # Only tx-1 at tick 3, tx-2 is unsettled (None != 3)
        assert sample.get_incoming_liquidity_at_tick(3) == 5000


class TestBootstrapSampleOutgoingArrivals:
    """Test BootstrapSample.get_outgoing_arrivals_at_tick method."""

    def test_get_outgoing_arrivals_at_tick(self) -> None:
        """get_outgoing_arrivals_at_tick returns transactions arriving at tick."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-1",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=1000,
                priority=5,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=None,
            ),
            RemappedTransaction(
                tx_id="tx-2",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=2000,
                priority=7,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=None,
            ),
            RemappedTransaction(
                tx_id="tx-3",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=3000,
                priority=3,
                arrival_tick=5,
                deadline_tick=10,
                settlement_tick=None,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=(),
            total_ticks=12,
        )

        arrivals_at_0 = sample.get_outgoing_arrivals_at_tick(0)
        assert len(arrivals_at_0) == 2
        assert arrivals_at_0[0].tx_id == "tx-1"
        assert arrivals_at_0[1].tx_id == "tx-2"

        arrivals_at_5 = sample.get_outgoing_arrivals_at_tick(5)
        assert len(arrivals_at_5) == 1
        assert arrivals_at_5[0].tx_id == "tx-3"

        arrivals_at_10 = sample.get_outgoing_arrivals_at_tick(10)
        assert len(arrivals_at_10) == 0

    def test_get_outgoing_arrivals_empty(self) -> None:
        """get_outgoing_arrivals_at_tick returns empty tuple when no arrivals."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=12,
        )

        arrivals = sample.get_outgoing_arrivals_at_tick(0)
        assert arrivals == ()


class TestInvariantMoneyIsInteger:
    """Test that all money-related fields are integers (project invariant)."""

    def test_transaction_record_amount_is_int(self) -> None:
        """TransactionRecord.amount must be an integer."""
        record = TransactionRecord(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=500000,  # Integer cents
            priority=5,
            original_arrival_tick=10,
            deadline_offset=5,
            settlement_offset=3,
        )

        assert isinstance(record.amount, int)

    def test_remapped_transaction_amount_is_int(self) -> None:
        """RemappedTransaction.amount must be an integer."""
        remapped = RemappedTransaction(
            tx_id="tx-001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,  # Integer cents
            priority=5,
            arrival_tick=2,
            deadline_tick=12,
            settlement_tick=7,
        )

        assert isinstance(remapped.amount, int)

    def test_liquidity_calculation_returns_int(self) -> None:
        """get_incoming_liquidity_at_tick returns an integer."""
        incoming = (
            RemappedTransaction(
                tx_id="tx-1",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=5000,
                priority=5,
                arrival_tick=0,
                deadline_tick=5,
                settlement_tick=3,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=incoming,
            total_ticks=12,
        )

        liquidity = sample.get_incoming_liquidity_at_tick(3)
        assert isinstance(liquidity, int)
