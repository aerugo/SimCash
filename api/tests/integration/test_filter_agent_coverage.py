"""Integration tests for comprehensive bank-centric event filtering.

Tests verify that --filter-agent BANK_A shows:
1. All events for transactions where the bank is the sender
2. Settlement events where the bank is the receiver (incoming liquidity)
"""

import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter


class TestFilterAgentCompleteCoverage:
    """Test that filter-agent provides complete event coverage for a bank."""

    @pytest.fixture
    def orchestrator_with_arrivals(self):
        """Create an orchestrator where BANK_A sends to BANK_B and BANK_B sends to BANK_A."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,  # $10,000.00
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,  # 1 tx per tick expected
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 1000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 10, "max": 50},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,  # $10,000.00
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,  # 1 tx per tick expected
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 1000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 10, "max": 50},
                    },
                },
            ],
        }
        return Orchestrator.new(config)

    def test_filter_matches_sender_with_sender_field(self, orchestrator_with_arrivals):
        """Filter matches events using 'sender' field (RTGS events)."""
        orch = orchestrator_with_arrivals
        filter = EventFilter(agent_id="BANK_A")

        # Run several ticks to ensure we have transactions
        for _ in range(10):
            orch.tick()

        # Collect all events
        all_events = []
        for tick in range(10):
            all_events.extend(orch.get_tick_events(tick))

        # Find RTGS settlement events
        rtgs_settlements = [e for e in all_events if e.get("event_type") == "RtgsImmediateSettlement"]

        # Skip if no settlements occurred
        if not rtgs_settlements:
            pytest.skip("No RTGS settlements occurred in this run")

        # Find settlements where BANK_A is sender
        bank_a_sender = [e for e in rtgs_settlements if e.get("sender") == "BANK_A"]

        # Verify filter matches these
        for event in bank_a_sender:
            assert filter.matches(event, tick=0), \
                f"Filter should match RTGS settlement with sender=BANK_A: {event}"

    def test_filter_matches_incoming_settlements(self, orchestrator_with_arrivals):
        """Filter for BANK_A shows settlements where BANK_A receives money."""
        orch = orchestrator_with_arrivals
        filter_a = EventFilter(agent_id="BANK_A")

        # Run several ticks
        for _ in range(10):
            orch.tick()

        # Collect all events
        all_events = []
        for tick in range(10):
            all_events.extend(orch.get_tick_events(tick))

        # Find settlement events
        settlements = [e for e in all_events if e.get("event_type") in [
            "RtgsImmediateSettlement",
            "Queue2LiquidityRelease",
        ]]

        if not settlements:
            pytest.skip("No settlements occurred in this run")

        # BANK_A should see settlements where it is the receiver
        incoming_settlements = [
            e for e in settlements
            if (e.get("receiver") or e.get("receiver_id")) == "BANK_A"
        ]

        for event in incoming_settlements:
            assert filter_a.matches(event, tick=0), \
                f"BANK_A filter should match settlement where BANK_A is receiver: {event}"

    def test_filter_does_not_match_arrivals_for_receiver(self, orchestrator_with_arrivals):
        """Filter for BANK_A should NOT show arrivals where BANK_A is only receiver."""
        orch = orchestrator_with_arrivals
        filter_a = EventFilter(agent_id="BANK_A")

        # Run several ticks
        for _ in range(10):
            orch.tick()

        # Collect all events
        all_events = []
        for tick in range(10):
            all_events.extend(orch.get_tick_events(tick))

        # Find arrival events where BANK_B sends to BANK_A
        arrivals_to_bank_a = [
            e for e in all_events
            if e.get("event_type") == "Arrival"
            and e.get("sender_id") == "BANK_B"
            and e.get("receiver_id") == "BANK_A"
        ]

        if not arrivals_to_bank_a:
            pytest.skip("No arrivals from BANK_B to BANK_A in this run")

        # Filter should NOT match these arrivals (they're BANK_B's arrivals)
        for event in arrivals_to_bank_a:
            assert not filter_a.matches(event, tick=0), \
                f"BANK_A filter should NOT match arrivals where BANK_A is only receiver: {event}"

    def test_filter_shows_complete_outbound_lifecycle(self, orchestrator_with_arrivals):
        """Filter captures complete lifecycle of outbound transactions."""
        orch = orchestrator_with_arrivals
        filter = EventFilter(agent_id="BANK_A")

        # Run a tick
        orch.tick()

        # Collect filtered events
        events = orch.get_tick_events(0)
        matched_events = [e for e in events if filter.matches(e, tick=0)]

        # Should have at least some events (arrivals, policy, maybe settlements)
        # (Exact events depend on whether arrivals occurred)
        arrivals_from_a = [e for e in matched_events if e.get("event_type") == "Arrival"]
        for arr in arrivals_from_a:
            assert arr.get("sender_id") == "BANK_A", "Arrival should be from BANK_A"


class TestFilterAgentWithLsmEvents:
    """Test filter behavior with LSM events."""

    def test_filter_matches_lsm_bilateral_both_participants(self):
        """Filter matches LsmBilateralOffset for both participating banks."""
        # Create a synthetic bilateral offset event for testing
        event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 8000,
            "amount_b": 10000,
            "tx_ids": ["tx1", "tx2"],
        }

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")
        filter_c = EventFilter(agent_id="BANK_C")

        assert filter_a.matches(event, tick=1), "BANK_A filter should match bilateral as agent_a"
        assert filter_b.matches(event, tick=1), "BANK_B filter should match bilateral as agent_b"
        assert not filter_c.matches(event, tick=1), "BANK_C filter should not match (not involved)"

    def test_filter_matches_lsm_cycle_all_participants(self):
        """Filter matches LsmCycleSettlement for all cycle participants."""
        event = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            "net_positions": [-5000, 2000, 3000],
            "tx_ids": ["tx1", "tx2", "tx3"],
        }

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")
        filter_c = EventFilter(agent_id="BANK_C")
        filter_d = EventFilter(agent_id="BANK_D")

        assert filter_a.matches(event, tick=1), "BANK_A should match cycle"
        assert filter_b.matches(event, tick=1), "BANK_B should match cycle"
        assert filter_c.matches(event, tick=1), "BANK_C should match cycle"
        assert not filter_d.matches(event, tick=1), "BANK_D should not match (not in cycle)"


class TestFilterAgentEventFieldConsistency:
    """Test that filter handles all event field naming conventions."""

    def test_all_sender_field_variants(self):
        """Filter handles all sender field naming conventions."""
        filter = EventFilter(agent_id="BANK_A")

        # sender_id field
        assert filter.matches(
            {"event_type": "Arrival", "sender_id": "BANK_A"},
            tick=1
        )

        # sender field
        assert filter.matches(
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_A"},
            tick=1
        )

        # agent_id field
        assert filter.matches(
            {"event_type": "PolicySubmit", "agent_id": "BANK_A"},
            tick=1
        )

    def test_settlement_receiver_field_variants(self):
        """Filter handles receiver field variants for settlements only."""
        filter = EventFilter(agent_id="BANK_A")

        # receiver field (RTGS)
        assert filter.matches(
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A"},
            tick=1
        )

        # receiver_id field (OverdueTransactionSettled)
        assert filter.matches(
            {"event_type": "OverdueTransactionSettled", "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            tick=1
        )

        # But NOT for non-settlements
        assert not filter.matches(
            {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            tick=1
        )

    def test_lsm_bilateral_uses_agent_fields(self):
        """Filter matches LSM bilateral using agent_a/agent_b fields."""
        filter = EventFilter(agent_id="BANK_A")

        # Match via agent_a
        assert filter.matches(
            {"event_type": "LsmBilateralOffset", "agent_a": "BANK_A", "agent_b": "BANK_B"},
            tick=1
        )

        # Match via agent_b
        assert filter.matches(
            {"event_type": "LsmBilateralOffset", "agent_a": "BANK_B", "agent_b": "BANK_A"},
            tick=1
        )

    def test_lsm_cycle_uses_agents_array(self):
        """Filter matches LSM cycle using agents array."""
        filter = EventFilter(agent_id="BANK_A")

        # agents field
        assert filter.matches(
            {"event_type": "LsmCycleSettlement", "agents": ["BANK_A", "BANK_B", "BANK_C"]},
            tick=1
        )

        # agent_ids field (Rust FFI format)
        assert filter.matches(
            {"event_type": "LsmCycleSettlement", "agent_ids": ["BANK_A", "BANK_B", "BANK_C"]},
            tick=1
        )


class TestFilterAgentReplayIdentity:
    """Test that filter-agent works identically in run and replay modes.

    This ensures the Replay Identity principle is maintained when using filters.
    Both run and replay should produce identical filtered output.
    """

    def test_event_filter_from_cli_args_for_replay(self):
        """EventFilter.from_cli_args works with all replay filter options."""
        # Test agent filter
        filter = EventFilter.from_cli_args(filter_agent="BANK_A")
        assert filter.agent_id == "BANK_A"
        assert filter.event_types is None
        assert filter.tx_id is None

        # Test event type filter
        filter = EventFilter.from_cli_args(filter_event_type="Arrival,Settlement")
        assert filter.event_types == ["Arrival", "Settlement"]

        # Test transaction filter
        filter = EventFilter.from_cli_args(filter_tx="tx-123")
        assert filter.tx_id == "tx-123"

        # Test tick range filter
        filter = EventFilter.from_cli_args(filter_tick_range="10-50")
        assert filter.tick_min == 10
        assert filter.tick_max == 50

        # Test combined filters (should all work together)
        filter = EventFilter.from_cli_args(
            filter_agent="BANK_B",
            filter_event_type="RtgsImmediateSettlement",
            filter_tick_range="0-100",
        )
        assert filter.agent_id == "BANK_B"
        assert filter.event_types == ["RtgsImmediateSettlement"]
        assert filter.tick_min == 0
        assert filter.tick_max == 100

    def test_filter_applies_to_settlement_receiver(self):
        """Filter correctly includes settlements where the filtered bank is receiver.

        This tests the key feature: --filter-agent BANK_A shows settlements
        where BANK_A receives incoming liquidity.
        """
        filter = EventFilter(agent_id="BANK_A")

        # Settlement where BANK_A receives money (from BANK_B)
        incoming_settlement = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 100000,
        }

        # Filter should match (BANK_A is receiver of a settlement)
        assert filter.matches(incoming_settlement, tick=5), \
            "Filter should match settlement where filtered agent is receiver"

    def test_filter_excludes_non_settlement_receiver_events(self):
        """Filter does NOT include non-settlement events where agent is only receiver.

        Arrivals and policy events should NOT match when the filtered agent
        is only the receiver, not the sender/actor.
        """
        filter = EventFilter(agent_id="BANK_A")

        # Arrival where BANK_A is only the receiver (sent by BANK_B)
        arrival_to_bank_a = {
            "event_type": "Arrival",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 100000,
        }

        # Filter should NOT match (this is BANK_B's arrival, not BANK_A's)
        assert not filter.matches(arrival_to_bank_a, tick=5), \
            "Filter should NOT match arrival where filtered agent is only receiver"

    def test_filter_comprehensive_sender_field_coverage(self):
        """Filter matches all sender field naming conventions used across event types."""
        filter = EventFilter(agent_id="BANK_A")

        # sender_id (arrivals, queued events)
        assert filter.matches({"event_type": "Arrival", "sender_id": "BANK_A"}, tick=1)

        # sender (RTGS events)
        assert filter.matches({"event_type": "RtgsImmediateSettlement", "sender": "BANK_A"}, tick=1)

        # agent_id (policy events)
        assert filter.matches({"event_type": "PolicySubmit", "agent_id": "BANK_A"}, tick=1)

        # agent_a/agent_b (LSM bilateral)
        assert filter.matches({
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
        }, tick=1)
        assert filter.matches({
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_B",
            "agent_b": "BANK_A",
        }, tick=1)

        # agents/agent_ids (LSM cycle)
        assert filter.matches({
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
        }, tick=1)
        assert filter.matches({
            "event_type": "LsmCycleSettlement",
            "agent_ids": ["BANK_X", "BANK_A", "BANK_Y"],
        }, tick=1)
