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
