"""Phase 1 Tests: Verbose output capture from simulations.

Tests for capturing and filtering tick-by-tick simulation events
for the Castro LLM optimizer context.

These tests verify:
1. Events can be captured from the Orchestrator
2. Events contain all required fields for verbose display
3. Same seed produces identical events (determinism)
4. Events are correctly filtered per agent (isolation)
5. Filtered output can be formatted as verbose text

Critical invariants:
- INV-1: Agent isolation - each agent only sees their own events
- INV-2: Deterministic replay - same seed produces identical output
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter


class TestEventCaptureFromOrchestrator:
    """Test capturing events from the Rust Orchestrator.

    NOTE: These tests use direct Orchestrator calls with dict policy format,
    which doesn't work with the current FFI. The same functionality is covered
    by tests using mock objects.
    """

    @pytest.fixture
    def two_bank_config(self) -> dict:
        """Create a two-bank configuration with bidirectional arrivals."""
        return {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,  # $5,000.00
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.8,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.8,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
            ],
        }

    def test_can_capture_events_from_orchestrator(
        self, two_bank_config: dict
    ) -> None:
        """Orchestrator.get_tick_events() returns all events for a tick."""
        orch = Orchestrator.new(two_bank_config)

        all_events: list[dict] = []
        for tick in range(10):
            orch.tick()
            tick_events = orch.get_tick_events(tick)
            all_events.extend(tick_events)

        # Should have captured some events
        assert len(all_events) > 0, "Should capture events from simulation"

        # Each event should have an event_type
        for event in all_events:
            assert "event_type" in event, "Event should have event_type field"

    def test_events_contain_required_fields(self, two_bank_config: dict) -> None:
        """Events have all fields needed for verbose display."""
        orch = Orchestrator.new(two_bank_config)

        # Run enough ticks to generate various event types
        all_events: list[dict] = []
        for tick in range(15):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        # Categorize events by type
        events_by_type: dict[str, list[dict]] = {}
        for event in all_events:
            event_type = event.get("event_type", "Unknown")
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event)

        # Verify required fields for each event type
        if "Arrival" in events_by_type:
            for event in events_by_type["Arrival"][:3]:  # Check first few
                assert "sender_id" in event, "Arrival needs sender_id"
                assert "receiver_id" in event, "Arrival needs receiver_id"
                assert "amount" in event, "Arrival needs amount"
                assert "tick" in event, "Arrival needs tick"

        if "RtgsImmediateSettlement" in events_by_type:
            for event in events_by_type["RtgsImmediateSettlement"][:3]:
                assert "sender" in event, "Settlement needs sender"
                assert "receiver" in event, "Settlement needs receiver"
                assert "amount" in event, "Settlement needs amount"

    def test_events_are_deterministic(self, two_bank_config: dict) -> None:
        """Same seed produces identical events (INV-2).

        Note: tx_id is a UUID generated at runtime, not from RNG seed.
        We verify determinism of event types, counts, amounts, and ordering.
        """
        # First run
        orch1 = Orchestrator.new(two_bank_config)
        events1: list[dict] = []
        for tick in range(10):
            orch1.tick()
            events1.extend(orch1.get_tick_events(tick))

        # Second run with same config (same seed)
        orch2 = Orchestrator.new(two_bank_config)
        events2: list[dict] = []
        for tick in range(10):
            orch2.tick()
            events2.extend(orch2.get_tick_events(tick))

        # Events should be identical in count and properties
        assert len(events1) == len(events2), "Same seed should produce same event count"

        for i, (e1, e2) in enumerate(zip(events1, events2)):
            assert e1["event_type"] == e2["event_type"], f"Event {i} type mismatch"
            assert e1.get("tick") == e2.get("tick"), f"Event {i} tick mismatch"
            # Note: tx_id is a UUID, not deterministic - skip checking it
            # Compare amount (deterministic from RNG)
            if "amount" in e1:
                assert e1["amount"] == e2["amount"], f"Event {i} amount mismatch"
            # Compare agent fields (deterministic)
            if "sender_id" in e1:
                assert e1["sender_id"] == e2["sender_id"], f"Event {i} sender_id mismatch"
            if "receiver_id" in e1:
                assert e1["receiver_id"] == e2["receiver_id"], f"Event {i} receiver_id mismatch"
            if "agent_id" in e1:
                assert e1["agent_id"] == e2["agent_id"], f"Event {i} agent_id mismatch"


class TestEventFiltering:
    """Test event filtering for agent isolation (INV-1).

    NOTE: These tests use direct Orchestrator calls with dict policy format.
    """

    @pytest.fixture
    def two_bank_config(self) -> dict:
        """Create config with bidirectional transaction flow."""
        return {
            "rng_seed": 12345,
            "ticks_per_day": 30,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 8000,
                            "std_dev": 1500,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 8000,
                            "std_dev": 1500,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
            ],
        }

    def collect_all_events(self, orch: Orchestrator, num_ticks: int) -> list[dict]:
        """Run simulation and collect all events."""
        all_events: list[dict] = []
        for tick in range(num_ticks):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))
        return all_events

    def test_arrivals_filtered_to_sender(self, two_bank_config: dict) -> None:
        """Agent only sees arrivals they initiated (INV-1)."""
        orch = Orchestrator.new(two_bank_config)
        all_events = self.collect_all_events(orch, 20)

        # Filter for BANK_A
        filter_a = EventFilter(agent_id="BANK_A")
        filtered_events = [e for e in all_events if filter_a.matches(e, tick=0)]

        # All arrivals in filtered events should be from BANK_A
        arrivals = [e for e in filtered_events if e.get("event_type") == "Arrival"]
        for arrival in arrivals:
            assert arrival.get("sender_id") == "BANK_A", (
                f"BANK_A filter should only include BANK_A arrivals, "
                f"got sender_id={arrival.get('sender_id')}"
            )

    def test_settlements_visible_to_both_parties(self, two_bank_config: dict) -> None:
        """Both sender and receiver see settlement events (INV-1)."""
        orch = Orchestrator.new(two_bank_config)
        all_events = self.collect_all_events(orch, 20)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find RTGS settlements
        settlements = [
            e for e in all_events if e.get("event_type") == "RtgsImmediateSettlement"
        ]

        if not settlements:
            pytest.skip("No RTGS settlements occurred in this run")

        for settlement in settlements:
            sender = settlement.get("sender")
            receiver = settlement.get("receiver")

            # Sender should see their outgoing settlement
            if sender == "BANK_A":
                assert filter_a.matches(settlement, tick=0), (
                    "Sender BANK_A should see its outgoing settlement"
                )
            elif sender == "BANK_B":
                assert filter_b.matches(settlement, tick=0), (
                    "Sender BANK_B should see its outgoing settlement"
                )

            # Receiver should see incoming settlement (liquidity)
            if receiver == "BANK_A":
                assert filter_a.matches(settlement, tick=0), (
                    "Receiver BANK_A should see incoming settlement"
                )
            elif receiver == "BANK_B":
                assert filter_b.matches(settlement, tick=0), (
                    "Receiver BANK_B should see incoming settlement"
                )

    def test_policy_events_filtered_to_actor(self, two_bank_config: dict) -> None:
        """Policy decisions only visible to acting agent (INV-1)."""
        orch = Orchestrator.new(two_bank_config)
        all_events = self.collect_all_events(orch, 20)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find policy events
        policy_events = [
            e for e in all_events
            if e.get("event_type", "").startswith("Policy")
        ]

        for event in policy_events:
            agent_id = event.get("agent_id")

            if agent_id == "BANK_A":
                assert filter_a.matches(event, tick=0), (
                    "BANK_A policy events should be visible to BANK_A"
                )
                assert not filter_b.matches(event, tick=0), (
                    "BANK_A policy events should NOT be visible to BANK_B"
                )
            elif agent_id == "BANK_B":
                assert filter_b.matches(event, tick=0), (
                    "BANK_B policy events should be visible to BANK_B"
                )
                assert not filter_a.matches(event, tick=0), (
                    "BANK_B policy events should NOT be visible to BANK_A"
                )

    def test_cost_accruals_filtered_to_incurring_agent(
        self, two_bank_config: dict
    ) -> None:
        """Cost events only visible to agent incurring costs (INV-1)."""
        orch = Orchestrator.new(two_bank_config)
        all_events = self.collect_all_events(orch, 25)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find cost accrual events
        cost_events = [
            e for e in all_events if e.get("event_type") == "CostAccrual"
        ]

        for event in cost_events:
            agent_id = event.get("agent_id")

            if agent_id == "BANK_A":
                assert filter_a.matches(event, tick=0), (
                    "BANK_A cost accruals should be visible to BANK_A"
                )
                assert not filter_b.matches(event, tick=0), (
                    "BANK_B should NOT see BANK_A's cost accruals"
                )
            elif agent_id == "BANK_B":
                assert filter_b.matches(event, tick=0), (
                    "BANK_B cost accruals should be visible to BANK_B"
                )
                assert not filter_a.matches(event, tick=0), (
                    "BANK_A should NOT see BANK_B's cost accruals"
                )

    def test_no_cross_agent_leakage(self, two_bank_config: dict) -> None:
        """Agent A never sees Agent B's internal events (INV-1)."""
        orch = Orchestrator.new(two_bank_config)
        all_events = self.collect_all_events(orch, 25)

        filter_a = EventFilter(agent_id="BANK_A")
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # Event types that reveal opponent strategy
        forbidden_for_a = {
            ("Arrival", "BANK_B"),  # BANK_B's outgoing transactions
            ("PolicySubmit", "BANK_B"),
            ("PolicyHold", "BANK_B"),
            ("CostAccrual", "BANK_B"),
        }

        for event in events_a:
            event_type = event.get("event_type")
            agent = event.get("agent_id") or event.get("sender_id")

            if event_type == "Arrival":
                assert event.get("sender_id") != "BANK_B", (
                    "BANK_A should not see BANK_B's arrivals (outgoing transactions)"
                )

            if event_type in ["PolicySubmit", "PolicyHold", "PolicySplit"]:
                assert agent != "BANK_B", (
                    f"BANK_A should not see BANK_B's {event_type} decisions"
                )

            if event_type == "CostAccrual":
                assert agent != "BANK_B", (
                    "BANK_A should not see BANK_B's cost accruals"
                )


class TestVerboseOutputFormatting:
    """Test formatting events into verbose output text."""

    @pytest.fixture
    def sample_arrival_event(self) -> dict:
        """Create a sample Arrival event."""
        return {
            "event_type": "Arrival",
            "tick": 5,
            "tx_id": "tx_001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "priority": 5,
            "deadline": 15,
        }

    @pytest.fixture
    def sample_settlement_event(self) -> dict:
        """Create a sample RtgsImmediateSettlement event."""
        return {
            "event_type": "RtgsImmediateSettlement",
            "tick": 5,
            "tx_id": "tx_001",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 100000,
            "sender_balance_before": 500000,
            "sender_balance_after": 400000,
        }

    @pytest.fixture
    def sample_policy_event(self) -> dict:
        """Create a sample PolicySubmit event."""
        return {
            "event_type": "PolicySubmit",
            "tick": 5,
            "agent_id": "BANK_A",
            "tx_id": "tx_001",
            "decision": "Release",
        }

    @pytest.fixture
    def sample_cost_event(self) -> dict:
        """Create a sample CostAccrual event."""
        return {
            "event_type": "CostAccrual",
            "tick": 10,
            "agent_id": "BANK_A",
            "cost_type": "delay",
            "amount": 500,
            "tx_id": "tx_001",
        }

    def test_format_arrival_event(self, sample_arrival_event: dict) -> None:
        """Arrival events contain all fields for formatting."""
        event = sample_arrival_event

        # Verify all fields needed for verbose display are present
        assert event["event_type"] == "Arrival"
        assert "tick" in event
        assert "tx_id" in event
        assert "sender_id" in event
        assert "receiver_id" in event
        assert "amount" in event
        assert "priority" in event
        assert "deadline" in event

        # Verify we can create a formatted string
        formatted = (
            f"[Tick {event['tick']}] Arrival: {event['sender_id']} → {event['receiver_id']} "
            f"${event['amount'] / 100:.2f} (priority={event['priority']}, deadline={event['deadline']})"
        )
        assert "BANK_A" in formatted
        assert "BANK_B" in formatted
        assert "$1,000.00" in formatted or "$1000.00" in formatted

    def test_format_settlement_event(self, sample_settlement_event: dict) -> None:
        """Settlement events contain all fields for formatting."""
        event = sample_settlement_event

        assert event["event_type"] == "RtgsImmediateSettlement"
        assert "tick" in event
        assert "sender" in event
        assert "receiver" in event
        assert "amount" in event

        # Verify we can create a formatted string
        formatted = (
            f"[Tick {event['tick']}] Settlement: {event['sender']} → {event['receiver']} "
            f"${event['amount'] / 100:.2f}"
        )
        assert "Settlement" in formatted
        assert "BANK_A" in formatted

    def test_format_policy_event(self, sample_policy_event: dict) -> None:
        """Policy decision events contain all fields for formatting."""
        event = sample_policy_event

        assert event["event_type"] == "PolicySubmit"
        assert "tick" in event
        assert "agent_id" in event
        assert "decision" in event

        formatted = (
            f"[Tick {event['tick']}] {event['agent_id']} Policy: {event['decision']}"
        )
        assert "BANK_A" in formatted
        assert "Release" in formatted

    def test_format_cost_accrual_event(self, sample_cost_event: dict) -> None:
        """Cost accrual events contain all fields for formatting."""
        event = sample_cost_event

        assert event["event_type"] == "CostAccrual"
        assert "tick" in event
        assert "agent_id" in event
        assert "cost_type" in event
        assert "amount" in event

        formatted = (
            f"[Tick {event['tick']}] {event['agent_id']} Cost: "
            f"{event['cost_type']} ${event['amount'] / 100:.2f}"
        )
        assert "BANK_A" in formatted
        assert "delay" in formatted


class TestFilteredEventsForContext:
    """Test collecting filtered events for LLM context building.

    NOTE: These tests use direct Orchestrator calls with dict policy format.
    """

    @pytest.fixture
    def simulation_config(self) -> dict:
        """Create a config that generates interesting events."""
        return {
            "rng_seed": 98765,
            "ticks_per_day": 25,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 300000,  # Lower balance for more cost events
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.2,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 12000,
                            "std_dev": 3000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 0.6, 8: 0.4},
                        "deadline_window": {"min": 4, "max": 12},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 300000,
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.2,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 12000,
                            "std_dev": 3000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 0.6, 8: 0.4},
                        "deadline_window": {"min": 4, "max": 12},
                    },
                },
            ],
        }

    def test_filtered_events_per_agent_differ(
        self, simulation_config: dict
    ) -> None:
        """Each agent receives different filtered events."""
        orch = Orchestrator.new(simulation_config)

        all_events: list[dict] = []
        for tick in range(25):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]
        events_b = [e for e in all_events if filter_b.matches(e, tick=0)]

        # Both should have events
        assert len(events_a) > 0, "BANK_A should see some events"
        assert len(events_b) > 0, "BANK_B should see some events"

        # But not all events
        assert len(events_a) < len(all_events), (
            "BANK_A should not see all events"
        )
        assert len(events_b) < len(all_events), (
            "BANK_B should not see all events"
        )

        # Events should be different (different arrivals, policy events)
        # Compare arrivals specifically - they should be completely different
        arrivals_a = [
            e["tx_id"] for e in events_a if e.get("event_type") == "Arrival"
        ]
        arrivals_b = [
            e["tx_id"] for e in events_b if e.get("event_type") == "Arrival"
        ]

        # Arrivals should not overlap (each bank only sees its own)
        assert set(arrivals_a).isdisjoint(set(arrivals_b)), (
            "Banks should see different arrivals (their own outgoing transactions)"
        )

    def test_filtered_events_substantial_for_context(
        self, simulation_config: dict
    ) -> None:
        """Filtered events should be substantial enough for LLM context."""
        orch = Orchestrator.new(simulation_config)

        all_events: list[dict] = []
        for tick in range(25):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # Should have multiple event types
        event_types = {e.get("event_type") for e in events_a}
        assert len(event_types) >= 2, (
            f"Should have multiple event types for rich context, got: {event_types}"
        )

        # Should have arrivals (outgoing transactions)
        arrivals = [e for e in events_a if e.get("event_type") == "Arrival"]
        assert len(arrivals) > 0, "Should have some arrivals for context"

    def test_events_grouped_by_tick_for_display(
        self, simulation_config: dict
    ) -> None:
        """Events should be groupable by tick for tick-by-tick display."""
        orch = Orchestrator.new(simulation_config)

        events_by_tick: dict[int, list[dict]] = {}
        for tick in range(15):
            orch.tick()
            tick_events = orch.get_tick_events(tick)
            if tick_events:
                events_by_tick[tick] = tick_events

        # Should have events at multiple ticks
        assert len(events_by_tick) > 1, "Should have events at multiple ticks"

        # Each tick's events should have consistent tick field
        for tick, events in events_by_tick.items():
            for event in events:
                event_tick = event.get("tick")
                if event_tick is not None:
                    assert event_tick == tick, (
                        f"Event tick {event_tick} doesn't match collection tick {tick}"
                    )


class TestVerboseOutputCapture:
    """Test the VerboseOutputCapture class implementation.

    NOTE: These tests use direct Orchestrator calls with dict policy format.
    """

    @pytest.fixture
    def capture_config(self) -> dict:
        """Create config for capture testing."""
        return {
            "rng_seed": 77777,
            "ticks_per_day": 15,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 400000,
                    "unsecured_cap": 150000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.9,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2500,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 4, "max": 12},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 400000,
                    "unsecured_cap": 150000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.9,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2500,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 4, "max": 12},
                    },
                },
            ],
        }

    def test_capture_run_and_capture(self, capture_config: dict) -> None:
        """VerboseOutputCapture.run_and_capture() captures events."""
        from castro.verbose_capture import VerboseOutputCapture

        orch = Orchestrator.new(capture_config)
        capture = VerboseOutputCapture()

        output = capture.run_and_capture(orch, ticks=10)

        # Should have captured events
        assert output.total_ticks == 10
        assert len(output.events_by_tick) > 0
        assert len(output.agent_ids) == 2
        assert "BANK_A" in output.agent_ids
        assert "BANK_B" in output.agent_ids

    def test_capture_get_all_events(self, capture_config: dict) -> None:
        """VerboseOutput.get_all_events() returns events in tick order."""
        from castro.verbose_capture import VerboseOutputCapture

        orch = Orchestrator.new(capture_config)
        capture = VerboseOutputCapture()

        output = capture.run_and_capture(orch, ticks=10)
        all_events = output.get_all_events()

        # Should have events
        assert len(all_events) > 0

        # Events should be in tick order
        prev_tick = -1
        for event in all_events:
            tick = event.get("tick", 0)
            assert tick >= prev_tick, "Events should be in tick order"
            prev_tick = tick

    def test_capture_filter_for_agent(self, capture_config: dict) -> None:
        """VerboseOutput.filter_for_agent() returns filtered string."""
        from castro.verbose_capture import VerboseOutputCapture

        orch = Orchestrator.new(capture_config)
        capture = VerboseOutputCapture()

        output = capture.run_and_capture(orch, ticks=15)
        filtered_a = output.filter_for_agent("BANK_A")
        filtered_b = output.filter_for_agent("BANK_B")

        # Both should have content
        assert len(filtered_a) > 0, "BANK_A should have filtered output"
        assert len(filtered_b) > 0, "BANK_B should have filtered output"

        # Should be different (different arrivals, policies)
        # (Could be same length but different content)
        assert filtered_a != filtered_b or len(filtered_a) == 0

    def test_capture_filter_contains_tick_headers(self, capture_config: dict) -> None:
        """Filtered output should contain tick headers."""
        from castro.verbose_capture import VerboseOutputCapture

        orch = Orchestrator.new(capture_config)
        capture = VerboseOutputCapture()

        output = capture.run_and_capture(orch, ticks=10)
        filtered = output.filter_for_agent("BANK_A")

        # Should contain tick headers
        assert "=== TICK" in filtered

    def test_capture_filter_formats_events(self, capture_config: dict) -> None:
        """Filtered output should format events readably."""
        from castro.verbose_capture import VerboseOutputCapture

        orch = Orchestrator.new(capture_config)
        capture = VerboseOutputCapture()

        output = capture.run_and_capture(orch, ticks=15)
        filtered = output.filter_for_agent("BANK_A")

        # Should contain formatted event indicators
        # At minimum should have arrivals or settlements
        has_events = (
            "[Arrival]" in filtered
            or "[Settlement]" in filtered
            or "[Policy" in filtered
            or "[Cost]" in filtered
        )
        assert has_events, f"Should have formatted events, got: {filtered[:500]}"

    def test_capture_from_existing(self, capture_config: dict) -> None:
        """capture_from_existing() works on already-run orchestrator."""
        from castro.verbose_capture import VerboseOutputCapture

        # Run orchestrator manually first
        orch = Orchestrator.new(capture_config)
        for _ in range(10):
            orch.tick()

        # Now capture from existing
        capture = VerboseOutputCapture()
        output = capture.capture_from_existing(orch, ticks=10)

        # Should have captured events
        assert output.total_ticks == 10
        assert len(output.events_by_tick) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
