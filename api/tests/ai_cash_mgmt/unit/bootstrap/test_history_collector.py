"""Unit tests for TransactionHistoryCollector.

Phase 2: History Collector - TDD Tests

Tests for:
- Parsing arrival events to create pending TransactionRecords
- Matching settlement events to update settlement_offset
- Handling various settlement types (RTGS, LSM bilateral, LSM cycle, Queue2)
- Incoming vs outgoing classification
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
    AgentTransactionHistory,
    TransactionHistoryCollector,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord


class TestParseArrivalEvents:
    """Test collecting arrival events."""

    def test_collect_arrival_creates_pending_record(self) -> None:
        """Arrival event creates pending TransactionRecord."""
        events = [
            {
                "event_type": "arrival",
                "tick": 5,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 7,
                "deadline_tick": 15,
            }
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        assert len(history.outgoing) == 1

        record = history.outgoing[0]
        assert record.tx_id == "tx-001"
        assert record.original_arrival_tick == 5
        assert record.deadline_offset == 10  # 15 - 5
        assert record.settlement_offset is None  # Not yet settled
        assert record.amount == 100000
        assert record.priority == 7

    def test_multiple_arrivals_same_agent(self) -> None:
        """Multiple arrivals from same agent are collected."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 50000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 3,
                "tx_id": "tx-002",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_C",
                "amount": 75000,
                "priority": 8,
                "deadline_tick": 8,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        assert len(history.outgoing) == 2

    def test_arrivals_from_different_agents(self) -> None:
        """Arrivals from different agents are tracked separately."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 50000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 1,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 30000,
                "priority": 5,
                "deadline_tick": 10,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history_a = collector.get_agent_history("BANK_A")
        history_b = collector.get_agent_history("BANK_B")

        assert len(history_a.outgoing) == 1
        assert len(history_b.outgoing) == 1


class TestSettlementMatching:
    """Test matching settlement events to arrivals."""

    def test_rtgs_settlement_updates_offset(self) -> None:
        """RTGS settlement event updates settlement_offset on matching arrival."""
        events = [
            {
                "event_type": "arrival",
                "tick": 5,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 7,
                "deadline_tick": 15,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 8,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        record = history.outgoing[0]

        assert record.settlement_offset == 3  # 8 - 5
        assert record.was_settled is True

    def test_queue2_release_updates_settlement(self) -> None:
        """Queue2 liquidity release updates settlement_offset."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "queue2_liquidity_release",
                "tick": 7,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "queue_wait_ticks": 7,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        assert history.outgoing[0].settlement_offset == 7  # Released at tick 7

    def test_lsm_bilateral_updates_both_transactions(self) -> None:
        """LSM bilateral offset events update settlement_offset for both transactions."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 5000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 1,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 3000,
                "priority": 5,
                "deadline_tick": 10,
            },
            # LSM finds bilateral offset
            {
                "event_type": "lsm_bilateral_offset",
                "tick": 5,
                "agent_a": "BANK_A",
                "agent_b": "BANK_B",
                "tx_ids": ["tx-001", "tx-002"],
                "amount_a": 5000,
                "amount_b": 3000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history_a = collector.get_agent_history("BANK_A")
        history_b = collector.get_agent_history("BANK_B")

        # tx-001: arrived at 0, settled at 5 -> offset = 5
        assert history_a.outgoing[0].settlement_offset == 5
        # tx-002: arrived at 1, settled at 5 -> offset = 4
        assert history_b.outgoing[0].settlement_offset == 4

    def test_lsm_cycle_updates_all_transactions(self) -> None:
        """LSM cycle settlement updates all transactions in the cycle."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_C",
                "amount": 2000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 1,
                "tx_id": "tx-003",
                "sender_id": "BANK_C",
                "receiver_id": "BANK_A",
                "amount": 3000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "lsm_cycle_settlement",
                "tick": 6,
                "agents": ["BANK_A", "BANK_B", "BANK_C"],
                "tx_ids": ["tx-001", "tx-002", "tx-003"],
                "tx_amounts": [1000, 2000, 3000],
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history_a = collector.get_agent_history("BANK_A")
        history_b = collector.get_agent_history("BANK_B")
        history_c = collector.get_agent_history("BANK_C")

        assert history_a.outgoing[0].settlement_offset == 6  # tx-001: 6 - 0
        assert history_b.outgoing[0].settlement_offset == 6  # tx-002: 6 - 0
        assert history_c.outgoing[0].settlement_offset == 5  # tx-003: 6 - 1


class TestIncomingOutgoingClassification:
    """Test classification of transactions by direction."""

    def test_incoming_outgoing_classification(self) -> None:
        """Transactions are classified by direction relative to agent."""
        events = [
            # BANK_A sends to BANK_B
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
                "priority": 5,
                "deadline_tick": 10,
            },
            # BANK_B sends to BANK_A
            {
                "event_type": "arrival",
                "tick": 2,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 2000,
                "priority": 5,
                "deadline_tick": 12,
            },
            # Settlements
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 1,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 5,
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 2000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        # From BANK_A's perspective
        history_a = collector.get_agent_history("BANK_A")
        assert len(history_a.outgoing) == 1  # tx-001 (A sends)
        assert len(history_a.incoming) == 1  # tx-002 (A receives)
        assert history_a.outgoing[0].tx_id == "tx-001"
        assert history_a.incoming[0].tx_id == "tx-002"

        # From BANK_B's perspective
        history_b = collector.get_agent_history("BANK_B")
        assert len(history_b.outgoing) == 1  # tx-002 (B sends)
        assert len(history_b.incoming) == 1  # tx-001 (B receives)
        assert history_b.outgoing[0].tx_id == "tx-002"
        assert history_b.incoming[0].tx_id == "tx-001"

    def test_incoming_settlement_offset(self) -> None:
        """Incoming transactions have correct settlement_offset."""
        events = [
            {
                "event_type": "arrival",
                "tick": 2,
                "tx_id": "tx-001",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 5000,
                "priority": 5,
                "deadline_tick": 12,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 7,
                "tx_id": "tx-001",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 5000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history_a = collector.get_agent_history("BANK_A")
        # tx-001 is incoming to A (B sends to A)
        assert len(history_a.incoming) == 1
        incoming_record = history_a.incoming[0]
        assert incoming_record.settlement_offset == 5  # 7 - 2


class TestAgentTransactionHistory:
    """Test AgentTransactionHistory dataclass."""

    def test_empty_history(self) -> None:
        """Empty history for unknown agent."""
        collector = TransactionHistoryCollector()
        history = collector.get_agent_history("UNKNOWN_BANK")

        assert history.agent_id == "UNKNOWN_BANK"
        assert len(history.outgoing) == 0
        assert len(history.incoming) == 0

    def test_history_has_all_agents(self) -> None:
        """get_all_agent_ids returns all agents seen."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
                "priority": 5,
                "deadline_tick": 10,
            },
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-002",
                "sender_id": "BANK_C",
                "receiver_id": "BANK_A",
                "amount": 2000,
                "priority": 5,
                "deadline_tick": 10,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        agent_ids = collector.get_all_agent_ids()
        assert "BANK_A" in agent_ids
        assert "BANK_B" in agent_ids
        assert "BANK_C" in agent_ids


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unsettled_transactions(self) -> None:
        """Unsettled transactions have None settlement_offset."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline_tick": 10,
            },
            # No settlement event for tx-001
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        assert history.outgoing[0].settlement_offset is None
        assert history.outgoing[0].was_settled is False

    def test_zero_tick_arrival(self) -> None:
        """Transaction arriving at tick 0."""
        events = [
            {
                "event_type": "arrival",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 50000,
                "priority": 5,
                "deadline_tick": 5,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 0,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 50000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")
        record = history.outgoing[0]
        assert record.original_arrival_tick == 0
        assert record.settlement_offset == 0  # Instant settlement
        assert record.deadline_offset == 5

    def test_ignore_unrecognized_events(self) -> None:
        """Unrecognized event types are ignored."""
        events = [
            {
                "event_type": "some_unknown_event",
                "tick": 0,
                "data": "whatever",
            },
            {
                "event_type": "arrival",
                "tick": 1,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
                "priority": 5,
                "deadline_tick": 10,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)  # Should not raise

        history = collector.get_agent_history("BANK_A")
        assert len(history.outgoing) == 1

    def test_settlement_without_arrival(self) -> None:
        """Settlement event for unknown transaction is ignored."""
        events = [
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 5,
                "tx_id": "tx-unknown",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)  # Should not raise

        # No crash, just nothing to show
        history = collector.get_agent_history("BANK_A")
        assert len(history.outgoing) == 0


class TestFinalize:
    """Test finalize method for creating immutable records."""

    def test_finalize_creates_immutable_records(self) -> None:
        """Finalize converts pending records to immutable TransactionRecords."""
        events = [
            {
                "event_type": "arrival",
                "tick": 5,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 7,
                "deadline_tick": 15,
            },
            {
                "event_type": "rtgs_immediate_settlement",
                "tick": 8,
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            },
        ]

        collector = TransactionHistoryCollector()
        collector.process_events(events)

        history = collector.get_agent_history("BANK_A")

        # Records should be TransactionRecord instances
        assert isinstance(history.outgoing[0], TransactionRecord)
        # And immutable
        with pytest.raises(AttributeError):
            history.outgoing[0].amount = 999  # type: ignore[misc]
