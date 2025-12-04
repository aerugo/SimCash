"""Unit tests for EventFilter class.

Tests event filtering logic for CLI --filter-* flags.
"""

import pytest

from payment_simulator.cli.filters import EventFilter


def test_event_filter_no_filters_matches_all():
    """Test that EventFilter with no filters matches all events."""
    filter = EventFilter()

    event = {"event_type": "Arrival", "tx_id": "tx1"}
    assert filter.matches(event, tick=10)

    event = {"event_type": "Settlement", "tx_id": "tx2"}
    assert filter.matches(event, tick=20)


def test_event_filter_event_type_single():
    """Test filtering by a single event type."""
    filter = EventFilter(event_types=["Arrival"])

    arrival_event = {"event_type": "Arrival", "tx_id": "tx1"}
    assert filter.matches(arrival_event, tick=10)

    settlement_event = {"event_type": "Settlement", "tx_id": "tx2"}
    assert not filter.matches(settlement_event, tick=10)


def test_event_filter_event_type_multiple():
    """Test filtering by multiple event types."""
    filter = EventFilter(event_types=["Arrival", "Settlement"])

    arrival_event = {"event_type": "Arrival", "tx_id": "tx1"}
    assert filter.matches(arrival_event, tick=10)

    settlement_event = {"event_type": "Settlement", "tx_id": "tx2"}
    assert filter.matches(settlement_event, tick=10)

    policy_event = {"event_type": "PolicySubmit", "tx_id": "tx3"}
    assert not filter.matches(policy_event, tick=10)


def test_event_filter_agent_via_agent_id():
    """Test filtering by agent via agent_id field."""
    filter = EventFilter(agent_id="BANK_A")

    # Match via agent_id field (policy events)
    policy_event = {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx1"}
    assert filter.matches(policy_event, tick=10)

    # No match
    other_event = {"event_type": "PolicySubmit", "agent_id": "BANK_B", "tx_id": "tx2"}
    assert not filter.matches(other_event, tick=10)


def test_event_filter_agent_via_sender_id():
    """Test filtering by agent via sender_id field."""
    filter = EventFilter(agent_id="BANK_A")

    # Match via sender_id field (arrival/settlement events)
    arrival_event = {"event_type": "Arrival", "sender_id": "BANK_A", "tx_id": "tx1"}
    assert filter.matches(arrival_event, tick=10)

    # No match
    other_event = {"event_type": "Arrival", "sender_id": "BANK_B", "tx_id": "tx2"}
    assert not filter.matches(other_event, tick=10)


def test_event_filter_agent_no_agent_field():
    """Test agent filter when event has no agent_id or sender_id."""
    filter = EventFilter(agent_id="BANK_A")

    # Event with no agent fields should not match
    event = {"event_type": "EndOfDay", "day": 0}
    assert not filter.matches(event, tick=99)


def test_event_filter_transaction_id():
    """Test filtering by transaction ID."""
    filter = EventFilter(tx_id="tx123")

    matching_event = {"event_type": "Arrival", "tx_id": "tx123"}
    assert filter.matches(matching_event, tick=10)

    non_matching_event = {"event_type": "Arrival", "tx_id": "tx456"}
    assert not filter.matches(non_matching_event, tick=10)


def test_event_filter_transaction_id_missing():
    """Test transaction filter when event has no tx_id."""
    filter = EventFilter(tx_id="tx123")

    # Event with no tx_id should not match
    event = {"event_type": "EndOfDay", "day": 0}
    assert not filter.matches(event, tick=99)


def test_event_filter_tick_range_min_only():
    """Test filtering by minimum tick."""
    filter = EventFilter(tick_min=10)

    event = {"event_type": "Arrival"}
    assert not filter.matches(event, tick=5)   # Before min
    assert filter.matches(event, tick=10)      # At min
    assert filter.matches(event, tick=15)      # After min


def test_event_filter_tick_range_max_only():
    """Test filtering by maximum tick."""
    filter = EventFilter(tick_max=20)

    event = {"event_type": "Arrival"}
    assert filter.matches(event, tick=15)      # Before max
    assert filter.matches(event, tick=20)      # At max
    assert not filter.matches(event, tick=25)  # After max


def test_event_filter_tick_range_both():
    """Test filtering by tick range (min and max)."""
    filter = EventFilter(tick_min=10, tick_max=20)

    event = {"event_type": "Arrival"}
    assert not filter.matches(event, tick=5)   # Before range
    assert filter.matches(event, tick=10)      # Start of range
    assert filter.matches(event, tick=15)      # Middle of range
    assert filter.matches(event, tick=20)      # End of range
    assert not filter.matches(event, tick=25)  # After range


def test_event_filter_multiple_filters_and_logic():
    """Test that multiple filters use AND logic (all must match)."""
    filter = EventFilter(
        event_types=["Arrival", "Settlement"],
        agent_id="BANK_A",
        tick_min=10,
        tick_max=20,
    )

    # All criteria match
    event1 = {"event_type": "Arrival", "sender_id": "BANK_A"}
    assert filter.matches(event1, tick=15)

    # Wrong event type
    event2 = {"event_type": "PolicySubmit", "agent_id": "BANK_A"}
    assert not filter.matches(event2, tick=15)

    # Wrong agent
    event3 = {"event_type": "Arrival", "sender_id": "BANK_B"}
    assert not filter.matches(event3, tick=15)

    # Wrong tick
    event4 = {"event_type": "Arrival", "sender_id": "BANK_A"}
    assert not filter.matches(event4, tick=25)


def test_event_filter_from_cli_args_all_none():
    """Test creating filter from CLI args when all are None."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent=None,
        filter_tx=None,
        filter_tick_range=None,
    )

    assert filter.event_types is None
    assert filter.agent_id is None
    assert filter.tx_id is None
    assert filter.tick_min is None
    assert filter.tick_max is None

    # Should match everything
    event = {"event_type": "Arrival", "tx_id": "tx1"}
    assert filter.matches(event, tick=10)


def test_event_filter_from_cli_args_event_types_single():
    """Test parsing single event type from CLI."""
    filter = EventFilter.from_cli_args(
        filter_event_type="Arrival",
        filter_agent=None,
        filter_tx=None,
        filter_tick_range=None,
    )

    assert filter.event_types == ["Arrival"]


def test_event_filter_from_cli_args_event_types_multiple():
    """Test parsing comma-separated event types from CLI."""
    filter = EventFilter.from_cli_args(
        filter_event_type="Arrival,Settlement,PolicySubmit",
        filter_agent=None,
        filter_tx=None,
        filter_tick_range=None,
    )

    assert filter.event_types == ["Arrival", "Settlement", "PolicySubmit"]


def test_event_filter_from_cli_args_event_types_with_spaces():
    """Test parsing event types with spaces around commas."""
    filter = EventFilter.from_cli_args(
        filter_event_type="Arrival, Settlement , PolicySubmit",
        filter_agent=None,
        filter_tx=None,
        filter_tick_range=None,
    )

    # Should strip spaces
    assert filter.event_types == ["Arrival", "Settlement", "PolicySubmit"]


def test_event_filter_from_cli_args_agent():
    """Test parsing agent ID from CLI."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent="BANK_A",
        filter_tx=None,
        filter_tick_range=None,
    )

    assert filter.agent_id == "BANK_A"


def test_event_filter_from_cli_args_tx():
    """Test parsing transaction ID from CLI."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent=None,
        filter_tx="abc123def456",
        filter_tick_range=None,
    )

    assert filter.tx_id == "abc123def456"


def test_event_filter_from_cli_args_tick_range_both():
    """Test parsing tick range with min and max."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent=None,
        filter_tx=None,
        filter_tick_range="10-50",
    )

    assert filter.tick_min == 10
    assert filter.tick_max == 50


def test_event_filter_from_cli_args_tick_range_min_only():
    """Test parsing tick range with only min (e.g., '10-')."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent=None,
        filter_tx=None,
        filter_tick_range="10-",
    )

    assert filter.tick_min == 10
    assert filter.tick_max is None


def test_event_filter_from_cli_args_tick_range_max_only():
    """Test parsing tick range with only max (e.g., '-50')."""
    filter = EventFilter.from_cli_args(
        filter_event_type=None,
        filter_agent=None,
        filter_tx=None,
        filter_tick_range="-50",
    )

    assert filter.tick_min is None
    assert filter.tick_max == 50


def test_event_filter_from_cli_args_all_filters():
    """Test parsing all filters from CLI args."""
    filter = EventFilter.from_cli_args(
        filter_event_type="Arrival,Settlement",
        filter_agent="BANK_A",
        filter_tx="tx123",
        filter_tick_range="10-50",
    )

    assert filter.event_types == ["Arrival", "Settlement"]
    assert filter.agent_id == "BANK_A"
    assert filter.tx_id == "tx123"
    assert filter.tick_min == 10
    assert filter.tick_max == 50


def test_event_filter_none_is_permissive():
    """Test that EventFilter(None, None, None, None, None) matches everything."""
    filter = EventFilter(
        event_types=None,
        agent_id=None,
        tx_id=None,
        tick_min=None,
        tick_max=None,
    )

    # Should match all event types
    assert filter.matches({"event_type": "Arrival"}, tick=10)
    assert filter.matches({"event_type": "Settlement"}, tick=20)
    assert filter.matches({"event_type": "PolicySubmit"}, tick=30)

    # Should match all agents
    assert filter.matches({"event_type": "Arrival", "sender_id": "BANK_A"}, tick=10)
    assert filter.matches({"event_type": "Arrival", "sender_id": "BANK_B"}, tick=10)

    # Should match all ticks
    assert filter.matches({"event_type": "Arrival"}, tick=0)
    assert filter.matches({"event_type": "Arrival"}, tick=999)


def test_event_filter_empty_lists_vs_none():
    """Test difference between None (match all) and empty list (match none)."""
    # None means "no filter applied, match all"
    filter_none = EventFilter(event_types=None)
    assert filter_none.matches({"event_type": "Arrival"}, tick=10)

    # Empty list means "match no event types"
    filter_empty = EventFilter(event_types=[])
    assert not filter_empty.matches({"event_type": "Arrival"}, tick=10)


# =============================================================================
# Tests for sender field variants (Problem 1 from feature request)
# =============================================================================


def test_filter_matches_sender_field_not_sender_id():
    """Filter matches events using 'sender' field (not just 'sender_id').

    Several events use 'sender' instead of 'sender_id':
    - RtgsImmediateSettlement
    - RtgsSubmission
    - RtgsWithdrawal
    - RtgsResubmission
    - Queue2LiquidityRelease
    """
    f = EventFilter(agent_id="BANK_A")

    # Should match: uses 'sender' (not 'sender_id')
    assert f.matches(
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_A", "receiver": "BANK_B"},
        tick=1
    )

    # Should match: RtgsSubmission uses 'sender'
    assert f.matches(
        {"event_type": "RtgsSubmission", "sender": "BANK_A", "receiver": "BANK_B"},
        tick=1
    )

    # Should ALSO match: BANK_A is receiver of this settlement
    # (New behavior: settlements match if filtered agent is receiver)
    assert f.matches(
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A"},
        tick=1
    )

    # Should NOT match: BANK_A not involved at all
    assert not f.matches(
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_C"},
        tick=1
    )


def test_filter_matches_both_sender_and_sender_id():
    """Filter matches events with either 'sender' or 'sender_id'."""
    f = EventFilter(agent_id="BANK_A")

    # Match via sender_id (Arrival events)
    assert f.matches({"event_type": "Arrival", "sender_id": "BANK_A"}, tick=1)

    # Match via sender (RTGS events)
    assert f.matches({"event_type": "RtgsImmediateSettlement", "sender": "BANK_A"}, tick=1)


# =============================================================================
# Tests for LSM agent matching (Problem 1 from feature request)
# =============================================================================


def test_filter_matches_lsm_bilateral_agent_a():
    """Filter matches LsmBilateralOffset via agent_a field."""
    f = EventFilter(agent_id="BANK_A")

    assert f.matches(
        {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_matches_lsm_bilateral_agent_b():
    """Filter matches LsmBilateralOffset via agent_b field."""
    f = EventFilter(agent_id="BANK_A")

    assert f.matches(
        {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_B",
            "agent_b": "BANK_A",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_matches_lsm_bilateral_not_involved():
    """Filter does NOT match LsmBilateralOffset when agent not involved."""
    f = EventFilter(agent_id="BANK_A")

    assert not f.matches(
        {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_B",
            "agent_b": "BANK_C",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_matches_lsm_cycle_via_agents_array():
    """Filter matches LsmCycleSettlement via agents array field."""
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is in the agents array
    assert f.matches(
        {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_B", "BANK_A", "BANK_C"],
            "tx_ids": ["tx1", "tx2", "tx3"],
        },
        tick=1
    )


def test_filter_matches_lsm_cycle_not_in_agents():
    """Filter does NOT match LsmCycleSettlement when agent not in cycle."""
    f = EventFilter(agent_id="BANK_A")

    assert not f.matches(
        {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_B", "BANK_C", "BANK_D"],
            "tx_ids": ["tx1", "tx2", "tx3"],
        },
        tick=1
    )


# =============================================================================
# Tests for receiver matching on settlement events only (Problem 2 from feature request)
# =============================================================================


def test_filter_matches_receiver_for_rtgs_immediate_settlement():
    """Filter matches receiver on RtgsImmediateSettlement events."""
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is the receiver - should match for settlement events
    assert f.matches(
        {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_matches_receiver_for_queue2_release():
    """Filter matches receiver on Queue2LiquidityRelease events."""
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is the receiver - should match for settlement events
    assert f.matches(
        {
            "event_type": "Queue2LiquidityRelease",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_matches_receiver_for_overdue_transaction_settled():
    """Filter matches receiver on OverdueTransactionSettled events."""
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is the receiver - should match for settlement events
    assert f.matches(
        {
            "event_type": "OverdueTransactionSettled",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 10000,
        },
        tick=1
    )


def test_filter_does_not_match_receiver_for_arrival():
    """Filter does NOT match receiver for non-settlement events like Arrival."""
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is the receiver but this is NOT a settlement event
    # (Arrival is the sender's event, not receiver's)
    assert not f.matches(
        {
            "event_type": "Arrival",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
        },
        tick=1
    )


def test_filter_does_not_match_receiver_for_policy_submit():
    """Filter does NOT match receiver for PolicySubmit events."""
    f = EventFilter(agent_id="BANK_A")

    # Even if receiver_id were present, PolicySubmit is not a settlement
    assert not f.matches(
        {
            "event_type": "PolicySubmit",
            "agent_id": "BANK_B",
            "receiver_id": "BANK_A",  # Not normally present, but testing edge case
        },
        tick=1
    )


def test_filter_does_not_match_receiver_for_queued_rtgs():
    """Filter does NOT match receiver for QueuedRtgs events."""
    f = EventFilter(agent_id="BANK_A")

    # QueuedRtgs is about the sender queuing a payment, not settlement
    assert not f.matches(
        {
            "event_type": "QueuedRtgs",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
        },
        tick=1
    )


def test_filter_matches_receiver_id_variant():
    """Filter matches receiver_id (not just receiver) for settlements."""
    f = EventFilter(agent_id="BANK_A")

    # OverdueTransactionSettled uses receiver_id
    assert f.matches(
        {
            "event_type": "OverdueTransactionSettled",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
        },
        tick=1
    )


# =============================================================================
# Combined tests - verify complete agent filtering behavior
# =============================================================================


def test_filter_complete_outbound_lifecycle():
    """Filter captures complete lifecycle for outbound transactions.

    When filtering for BANK_A, should see:
    - Arrival (as sender)
    - PolicySubmit (as agent)
    - RtgsSubmission (as sender)
    - QueuedRtgs (as sender)
    - RtgsImmediateSettlement (as sender)
    - LsmBilateralOffset (as participant)
    """
    f = EventFilter(agent_id="BANK_A")

    # All these should match for BANK_A's outbound transaction
    events = [
        {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
        {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx1"},
        {"event_type": "RtgsSubmission", "sender": "BANK_A", "receiver": "BANK_B"},
        {"event_type": "QueuedRtgs", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_A", "receiver": "BANK_B"},
        {"event_type": "LsmBilateralOffset", "agent_a": "BANK_A", "agent_b": "BANK_B"},
    ]

    for event in events:
        assert f.matches(event, tick=1), f"Should match {event['event_type']}"


def test_filter_incoming_settlements_only():
    """Filter shows incoming settlements but not other banks' decisions.

    When filtering for BANK_A (as receiver), should see:
    - Settlements where BANK_A receives money
    - NOT: Other bank's policy decisions, arrivals, queueing
    """
    f = EventFilter(agent_id="BANK_A")

    # Should match: Settlement where BANK_A receives
    assert f.matches(
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A"},
        tick=1
    )

    # Should NOT match: BANK_B's arrival (not BANK_A's business)
    assert not f.matches(
        {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A"},
        tick=1
    )

    # Should NOT match: BANK_B's policy decision (not BANK_A's business)
    assert not f.matches(
        {"event_type": "PolicySubmit", "agent_id": "BANK_B", "tx_id": "tx1"},
        tick=1
    )


def test_filter_with_lsm_bilateral_as_receiver():
    """LsmBilateralOffset is matched for both participants regardless of sender/receiver.

    In bilateral offsets, both agents are effectively sender and receiver.
    """
    f = EventFilter(agent_id="BANK_A")

    # BANK_A is agent_a (sender of one transaction, receiver of other)
    assert f.matches(
        {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 10000,
            "amount_b": 8000,
        },
        tick=1
    )

    # BANK_A is agent_b (receiver of one transaction, sender of other)
    assert f.matches(
        {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_B",
            "agent_b": "BANK_A",
            "amount_a": 8000,
            "amount_b": 10000,
        },
        tick=1
    )
