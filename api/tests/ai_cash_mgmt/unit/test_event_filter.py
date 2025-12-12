"""Tests for event filtering with agent isolation.

CRITICAL INVARIANT: An LLM optimizing for Agent X may ONLY see:
- Outgoing transactions FROM Agent X
- Incoming liquidity events TO Agent X balance
- Agent X's own policy and state changes
"""

from __future__ import annotations

from typing import Any

import pytest

# Import the functions we'll implement (TDD - tests written first)
from payment_simulator.ai_cash_mgmt.prompts.event_filter import (
    filter_events_for_agent,
    format_filtered_output,
)


# =============================================================================
# Test Group 1: Event Filtering - Outgoing
# =============================================================================


class TestEventFilterOutgoing:
    """Tests for filtering outgoing transaction events."""

    def test_filters_arrival_by_sender(self) -> None:
        """Arrivals where agent is sender are included."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "tick": 2, "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            {"event_type": "Arrival", "tick": 3, "sender_id": "BANK_A", "receiver_id": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A sends 2 (outgoing) + receives 1 (incoming notification) = 3
        assert len(filtered) == 3

    def test_filters_policy_submit(self) -> None:
        """PolicySubmit decisions only for target agent."""
        events: list[dict[str, Any]] = [
            {"event_type": "PolicySubmit", "tick": 1, "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicySubmit", "tick": 2, "agent_id": "BANK_B", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["agent_id"] == "BANK_A"

    def test_filters_policy_hold(self) -> None:
        """PolicyHold decisions only for target agent."""
        events: list[dict[str, Any]] = [
            {"event_type": "PolicyHold", "tick": 1, "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicyHold", "tick": 2, "agent_id": "BANK_B", "tx_id": "tx2"},
            {"event_type": "PolicyHold", "tick": 3, "agent_id": "BANK_A", "tx_id": "tx3"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 2
        assert all(e["agent_id"] == "BANK_A" for e in filtered)

    def test_filters_policy_drop(self) -> None:
        """PolicyDrop decisions only for target agent."""
        events: list[dict[str, Any]] = [
            {"event_type": "PolicyDrop", "tick": 1, "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicyDrop", "tick": 2, "agent_id": "BANK_B", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_filters_policy_split(self) -> None:
        """PolicySplit decisions only for target agent."""
        events: list[dict[str, Any]] = [
            {"event_type": "PolicySplit", "tick": 1, "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicySplit", "tick": 2, "agent_id": "BANK_B", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_filters_rtgs_immediate_by_sender(self) -> None:
        """RtgsImmediateSettlement where agent is sender (outgoing)."""
        events: list[dict[str, Any]] = [
            {"event_type": "RtgsImmediateSettlement", "tick": 1, "sender": "BANK_A", "receiver": "BANK_B"},
            {"event_type": "RtgsImmediateSettlement", "tick": 2, "sender": "BANK_B", "receiver": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["sender"] == "BANK_A"

    def test_filters_rtgs_submission_by_sender(self) -> None:
        """RtgsSubmission where agent is sender."""
        events: list[dict[str, Any]] = [
            {"event_type": "RtgsSubmission", "tick": 1, "sender": "BANK_A", "receiver": "BANK_B"},
            {"event_type": "RtgsSubmission", "tick": 2, "sender": "BANK_B", "receiver": "BANK_A"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A as sender + BANK_A as receiver = 2
        assert len(filtered) == 2

    def test_filters_transaction_went_overdue_by_sender(self) -> None:
        """TransactionWentOverdue where agent is sender."""
        events: list[dict[str, Any]] = [
            {"event_type": "TransactionWentOverdue", "tick": 10, "sender_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "TransactionWentOverdue", "tick": 11, "sender_id": "BANK_B", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["sender_id"] == "BANK_A"

    def test_filters_overdue_settled_by_sender(self) -> None:
        """OverdueTransactionSettled where agent is sender."""
        events: list[dict[str, Any]] = [
            {"event_type": "OverdueTransactionSettled", "tick": 15, "sender_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "OverdueTransactionSettled", "tick": 16, "sender_id": "BANK_B", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1


# =============================================================================
# Test Group 2: Event Filtering - Incoming Liquidity
# =============================================================================


class TestEventFilterIncoming:
    """Tests for filtering incoming liquidity events."""

    def test_includes_arrival_as_receiver(self) -> None:
        """Arrivals where agent is receiver (incoming payment notification)."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            {"event_type": "Arrival", "tick": 2, "sender_id": "BANK_C", "receiver_id": "BANK_A"},
            {"event_type": "Arrival", "tick": 3, "sender_id": "BANK_B", "receiver_id": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A receives 2 arrivals
        assert len(filtered) == 2

    def test_includes_rtgs_settlement_as_receiver(self) -> None:
        """Settlements to agent included as incoming liquidity."""
        events: list[dict[str, Any]] = [
            {"event_type": "RtgsImmediateSettlement", "tick": 1, "sender": "BANK_B", "receiver": "BANK_A", "amount": 1000},
            {"event_type": "RtgsImmediateSettlement", "tick": 2, "sender": "BANK_C", "receiver": "BANK_A", "amount": 2000},
            {"event_type": "RtgsImmediateSettlement", "tick": 3, "sender": "BANK_B", "receiver": "BANK_C", "amount": 3000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A receives 2 settlements
        assert len(filtered) == 2
        assert all(e["receiver"] == "BANK_A" for e in filtered)

    def test_includes_queue2_release_as_receiver(self) -> None:
        """Queue2LiquidityRelease where agent receives liquidity."""
        events: list[dict[str, Any]] = [
            {"event_type": "Queue2LiquidityRelease", "tick": 5, "sender": "BANK_B", "receiver": "BANK_A"},
            {"event_type": "Queue2LiquidityRelease", "tick": 6, "sender": "BANK_A", "receiver": "BANK_C"},
            {"event_type": "Queue2LiquidityRelease", "tick": 7, "sender": "BANK_D", "receiver": "BANK_E"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A as receiver (1) + BANK_A as sender (1) = 2
        assert len(filtered) == 2

    def test_includes_lsm_bilateral_if_involved(self) -> None:
        """LSM bilateral offsets included if agent is involved."""
        events: list[dict[str, Any]] = [
            {"event_type": "LsmBilateralOffset", "tick": 3, "agent_a": "BANK_A", "agent_b": "BANK_B"},
            {"event_type": "LsmBilateralOffset", "tick": 4, "agent_a": "BANK_B", "agent_b": "BANK_A"},
            {"event_type": "LsmBilateralOffset", "tick": 5, "agent_a": "BANK_C", "agent_b": "BANK_D"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A is in both first and second bilateral
        assert len(filtered) == 2

    def test_includes_lsm_cycle_if_involved(self) -> None:
        """LSM cycle settlements included if agent is in cycle."""
        events: list[dict[str, Any]] = [
            {"event_type": "LsmCycleSettlement", "tick": 3, "agents": ["BANK_A", "BANK_B", "BANK_C"]},
            {"event_type": "LsmCycleSettlement", "tick": 4, "agents": ["BANK_D", "BANK_E"]},
            {"event_type": "LsmCycleSettlement", "tick": 5, "agents": ["BANK_C", "BANK_A", "BANK_E"]},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A is in first and third cycle
        assert len(filtered) == 2
        for event in filtered:
            assert "BANK_A" in event["agents"]


# =============================================================================
# Test Group 3: Event Filtering - Agent State
# =============================================================================


class TestEventFilterAgentState:
    """Tests for filtering agent state events."""

    def test_includes_own_collateral_post(self) -> None:
        """CollateralPost events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "CollateralPost", "tick": 0, "agent_id": "BANK_A", "amount": 10000},
            {"event_type": "CollateralPost", "tick": 0, "agent_id": "BANK_B", "amount": 20000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["agent_id"] == "BANK_A"

    def test_includes_own_collateral_withdraw(self) -> None:
        """CollateralWithdraw events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "CollateralWithdraw", "tick": 5, "agent_id": "BANK_A", "amount": 5000},
            {"event_type": "CollateralWithdraw", "tick": 6, "agent_id": "BANK_B", "amount": 8000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_includes_own_collateral_timer_withdrawn(self) -> None:
        """CollateralTimerWithdrawn events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "CollateralTimerWithdrawn", "tick": 10, "agent_id": "BANK_A", "amount": 5000},
            {"event_type": "CollateralTimerWithdrawn", "tick": 11, "agent_id": "BANK_B", "amount": 3000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_includes_own_cost_accrual(self) -> None:
        """CostAccrual events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "CostAccrual", "tick": 1, "agent_id": "BANK_A", "costs": {"delay": 100}},
            {"event_type": "CostAccrual", "tick": 1, "agent_id": "BANK_B", "costs": {"delay": 200}},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_includes_own_bank_budget(self) -> None:
        """BankBudgetSet events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "BankBudgetSet", "tick": 0, "agent_id": "BANK_A", "max_value": 50000},
            {"event_type": "BankBudgetSet", "tick": 0, "agent_id": "BANK_B", "max_value": 100000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_includes_own_state_register_set(self) -> None:
        """StateRegisterSet events for target agent only."""
        events: list[dict[str, Any]] = [
            {"event_type": "StateRegisterSet", "tick": 5, "agent_id": "BANK_A", "register_key": "counter"},
            {"event_type": "StateRegisterSet", "tick": 5, "agent_id": "BANK_B", "register_key": "counter"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1


# =============================================================================
# Test Group 4: Event Filtering - Strict Isolation
# =============================================================================


class TestEventFilterIsolation:
    """Tests for strict agent isolation."""

    def test_never_shows_other_agent_policy(self) -> None:
        """Other agents' policy decisions are never visible."""
        events: list[dict[str, Any]] = [
            {"event_type": "PolicySubmit", "tick": 1, "agent_id": "BANK_B", "tx_id": "tx1"},
            {"event_type": "PolicyHold", "tick": 2, "agent_id": "BANK_C", "tx_id": "tx2"},
            {"event_type": "PolicyDrop", "tick": 3, "agent_id": "BANK_D", "tx_id": "tx3"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_never_shows_other_agent_collateral(self) -> None:
        """Other agents' collateral events are never visible."""
        events: list[dict[str, Any]] = [
            {"event_type": "CollateralPost", "tick": 0, "agent_id": "BANK_B", "amount": 50000},
            {"event_type": "CollateralWithdraw", "tick": 5, "agent_id": "BANK_C", "amount": 30000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_never_shows_other_agent_costs(self) -> None:
        """Other agents' cost accruals are never visible."""
        events: list[dict[str, Any]] = [
            {"event_type": "CostAccrual", "tick": 1, "agent_id": "BANK_B", "costs": {"delay": 9999}},
            {"event_type": "CostAccrual", "tick": 2, "agent_id": "BANK_C", "costs": {"overdraft": 5000}},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_never_shows_other_agent_budget(self) -> None:
        """Other agents' budget settings are never visible."""
        events: list[dict[str, Any]] = [
            {"event_type": "BankBudgetSet", "tick": 0, "agent_id": "BANK_B", "max_value": 99999},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_isolation_comprehensive(self) -> None:
        """Comprehensive test of agent isolation."""
        events: list[dict[str, Any]] = [
            # BANK_A should see (5 events)
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "tick": 2, "sender_id": "BANK_C", "receiver_id": "BANK_A"},
            {"event_type": "RtgsImmediateSettlement", "tick": 3, "sender": "BANK_B", "receiver": "BANK_A"},
            {"event_type": "CostAccrual", "tick": 4, "agent_id": "BANK_A", "costs": {}},
            {"event_type": "PolicySubmit", "tick": 5, "agent_id": "BANK_A", "tx_id": "tx1"},
            # BANK_A should NOT see (5 events)
            {"event_type": "Arrival", "tick": 6, "sender_id": "BANK_B", "receiver_id": "BANK_C"},
            {"event_type": "CostAccrual", "tick": 7, "agent_id": "BANK_B", "costs": {}},
            {"event_type": "PolicyHold", "tick": 8, "agent_id": "BANK_B", "tx_id": "tx2"},
            {"event_type": "CollateralPost", "tick": 9, "agent_id": "BANK_C", "amount": 10000},
            {"event_type": "RtgsImmediateSettlement", "tick": 10, "sender": "BANK_B", "receiver": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 5


# =============================================================================
# Test Group 5: Event Filtering - Edge Cases
# =============================================================================


class TestEventFilterEdgeCases:
    """Tests for edge cases in event filtering."""

    def test_empty_events_list(self) -> None:
        """Empty events list returns empty list."""
        filtered = filter_events_for_agent("BANK_A", [])
        assert filtered == []

    def test_unknown_event_type_excluded(self) -> None:
        """Unknown event types are excluded."""
        events: list[dict[str, Any]] = [
            {"event_type": "UnknownEvent", "tick": 1, "data": "whatever"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_preserves_event_order(self) -> None:
        """Filtered events preserve original order."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "CostAccrual", "tick": 2, "agent_id": "BANK_A"},
            {"event_type": "PolicySubmit", "tick": 3, "agent_id": "BANK_A", "tx_id": "tx1"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 3
        assert filtered[0]["tick"] == 1
        assert filtered[1]["tick"] == 2
        assert filtered[2]["tick"] == 3

    def test_handles_missing_fields_gracefully(self) -> None:
        """Missing fields don't cause crashes."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival"},  # Missing sender_id, receiver_id
            {"event_type": "RtgsImmediateSettlement"},  # Missing sender, receiver
        ]
        # Should not raise, just skip invalid events
        filtered = filter_events_for_agent("BANK_A", events)
        assert isinstance(filtered, list)

    def test_end_of_day_events(self) -> None:
        """EndOfDay events are included (general info)."""
        events: list[dict[str, Any]] = [
            {"event_type": "EndOfDay", "tick": 100, "day": 1, "unsettled_count": 5},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # EndOfDay is general info, should be included
        assert len(filtered) == 1


# =============================================================================
# Test Group 6: Output Formatting
# =============================================================================


class TestOutputFormatting:
    """Tests for formatting filtered output as text."""

    def test_format_returns_string(self) -> None:
        """format_filtered_output returns a string."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
        ]
        output = format_filtered_output("BANK_A", events)
        assert isinstance(output, str)

    def test_format_includes_tick_info(self) -> None:
        """Output includes tick information."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 5, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
        ]
        output = format_filtered_output("BANK_A", events)
        # Should mention tick somewhere
        assert "5" in output or "Tick" in output

    def test_format_arrival_event(self) -> None:
        """Arrival event formatted with key details."""
        events: list[dict[str, Any]] = [
            {
                "event_type": "Arrival",
                "tick": 1,
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "deadline": 10,
            },
        ]
        output = format_filtered_output("BANK_A", events)
        # Should include agent names
        assert "BANK_A" in output
        assert "BANK_B" in output

    def test_format_settlement_event(self) -> None:
        """Settlement event formatted with balance info."""
        events: list[dict[str, Any]] = [
            {
                "event_type": "RtgsImmediateSettlement",
                "tick": 3,
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 50000,
                "sender_balance_before": 100000,
                "sender_balance_after": 50000,
            },
        ]
        output = format_filtered_output("BANK_A", events)
        # Should include some settlement info
        assert len(output) > 0

    def test_format_empty_events(self) -> None:
        """Empty events list produces meaningful output."""
        output = format_filtered_output("BANK_A", [])
        # Should not crash, may return empty or placeholder
        assert isinstance(output, str)

    def test_format_multiple_ticks(self) -> None:
        """Multiple ticks formatted with separators."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "tick": 5, "sender_id": "BANK_A", "receiver_id": "BANK_C"},
            {"event_type": "CostAccrual", "tick": 5, "agent_id": "BANK_A"},
        ]
        output = format_filtered_output("BANK_A", events)
        # Should have some structure for different ticks
        assert "1" in output
        assert "5" in output

    def test_format_groups_by_tick(self) -> None:
        """Events grouped by tick in output."""
        events: list[dict[str, Any]] = [
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_C"},
            {"event_type": "CostAccrual", "tick": 2, "agent_id": "BANK_A"},
        ]
        output = format_filtered_output("BANK_A", events)
        # Tick 1 should appear before tick 2
        tick1_pos = output.find("1")
        tick2_pos = output.find("2")
        if tick1_pos >= 0 and tick2_pos >= 0:
            assert tick1_pos < tick2_pos


# =============================================================================
# Test Group 7: Integration with Real Event Types
# =============================================================================


class TestRealEventTypes:
    """Tests with realistic event structures."""

    def test_realistic_scenario(self) -> None:
        """Test with a realistic mix of events."""
        events: list[dict[str, Any]] = [
            # Tick 0: Collateral posted
            {"event_type": "CollateralPost", "tick": 0, "agent_id": "BANK_A", "amount": 100000},
            {"event_type": "CollateralPost", "tick": 0, "agent_id": "BANK_B", "amount": 150000},
            # Tick 1: Transactions arrive
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_A", "receiver_id": "BANK_B", "amount": 50000},
            {"event_type": "Arrival", "tick": 1, "sender_id": "BANK_B", "receiver_id": "BANK_A", "amount": 30000},
            # Tick 1: Policy decisions
            {"event_type": "PolicySubmit", "tick": 1, "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicyHold", "tick": 1, "agent_id": "BANK_B", "tx_id": "tx2"},
            # Tick 1: Settlements
            {"event_type": "RtgsImmediateSettlement", "tick": 1, "sender": "BANK_A", "receiver": "BANK_B", "amount": 50000},
            # Tick 1: Costs
            {"event_type": "CostAccrual", "tick": 1, "agent_id": "BANK_A", "costs": {"delay": 0}},
            {"event_type": "CostAccrual", "tick": 1, "agent_id": "BANK_B", "costs": {"delay": 100}},
        ]

        filtered = filter_events_for_agent("BANK_A", events)

        # BANK_A should see:
        # - Own CollateralPost (1)
        # - Own Arrival as sender (1)
        # - Arrival as receiver (1)
        # - Own PolicySubmit (1)
        # - Own RtgsImmediateSettlement (1)
        # - Own CostAccrual (1)
        # Total: 6 events

        assert len(filtered) == 6

        # Verify no BANK_B-only events leaked
        for event in filtered:
            if event["event_type"] == "CollateralPost":
                assert event["agent_id"] == "BANK_A"
            if event["event_type"] == "CostAccrual":
                assert event["agent_id"] == "BANK_A"
            if event["event_type"] in ("PolicySubmit", "PolicyHold", "PolicyDrop"):
                assert event["agent_id"] == "BANK_A"

    def test_lsm_events(self) -> None:
        """Test LSM event filtering."""
        events: list[dict[str, Any]] = [
            {
                "event_type": "LsmBilateralOffset",
                "tick": 5,
                "agent_a": "BANK_A",
                "agent_b": "BANK_B",
                "amount_a": 1000,
                "amount_b": 1000,
            },
            {
                "event_type": "LsmCycleSettlement",
                "tick": 6,
                "agents": ["BANK_B", "BANK_C", "BANK_D"],
                "total_value": 5000,
            },
        ]

        filtered = filter_events_for_agent("BANK_A", events)

        # BANK_A is in bilateral, not in cycle
        assert len(filtered) == 1
        assert filtered[0]["event_type"] == "LsmBilateralOffset"
