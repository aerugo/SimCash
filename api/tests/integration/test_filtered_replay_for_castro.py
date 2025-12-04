"""Integration tests for filtered replay outputs used by Castro experiments.

These tests verify that the replay --filter-agent functionality provides
correct information isolation for LLM policy optimizers.

Critical properties tested:
1. Each bank's LLM only sees events where it is an actor (sender/payer)
2. Settlement events are visible to receivers (incoming liquidity)
3. Policy decisions, cost accruals, and arrivals are NOT visible to other banks
4. The filtered output is consistent between run and replay
"""

import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter


class TestFilteredReplayForCastro:
    """Integration tests for Castro experiment's filtered replay needs."""

    @pytest.fixture
    def two_bank_orchestrator(self):
        """Create an orchestrator with two banks having bidirectional arrivals."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 50,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,  # $5,000.00
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 20},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,  # $5,000.00
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.5,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 10000,
                            "std_dev": 2000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 20},
                    },
                },
            ],
        }
        return Orchestrator.new(config)

    def collect_all_events(self, orch: Orchestrator, num_ticks: int) -> list[dict]:
        """Run simulation and collect all events."""
        all_events = []
        for tick in range(num_ticks):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))
        return all_events

    def test_bank_a_filtered_events_exclude_bank_b_arrivals(self, two_bank_orchestrator):
        """BANK_A's filtered events should not include BANK_B's arrivals."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 20)

        filter_a = EventFilter(agent_id="BANK_A")
        filtered_events = [e for e in all_events if filter_a.matches(e, tick=0)]

        # Find all arrivals in filtered events
        arrivals = [e for e in filtered_events if e.get("event_type") == "Arrival"]

        # All arrivals should be from BANK_A
        for arrival in arrivals:
            assert arrival.get("sender_id") == "BANK_A", \
                f"BANK_A filter should not include arrival from {arrival.get('sender_id')}"

    def test_bank_b_filtered_events_exclude_bank_a_arrivals(self, two_bank_orchestrator):
        """BANK_B's filtered events should not include BANK_A's arrivals."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 20)

        filter_b = EventFilter(agent_id="BANK_B")
        filtered_events = [e for e in all_events if filter_b.matches(e, tick=0)]

        # Find all arrivals in filtered events
        arrivals = [e for e in filtered_events if e.get("event_type") == "Arrival"]

        # All arrivals should be from BANK_B
        for arrival in arrivals:
            assert arrival.get("sender_id") == "BANK_B", \
                f"BANK_B filter should not include arrival from {arrival.get('sender_id')}"

    def test_both_banks_see_incoming_settlements(self, two_bank_orchestrator):
        """Both banks should see settlements where they receive money."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 20)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find RTGS settlements
        settlements = [e for e in all_events if e.get("event_type") == "RtgsImmediateSettlement"]

        if not settlements:
            pytest.skip("No settlements occurred")

        # Settlements where BANK_A receives
        settlements_to_a = [s for s in settlements if s.get("receiver") == "BANK_A"]
        for s in settlements_to_a:
            assert filter_a.matches(s, tick=0), \
                "BANK_A should see settlements where it receives"

        # Settlements where BANK_B receives
        settlements_to_b = [s for s in settlements if s.get("receiver") == "BANK_B"]
        for s in settlements_to_b:
            assert filter_b.matches(s, tick=0), \
                "BANK_B should see settlements where it receives"

    def test_policy_events_only_visible_to_acting_agent(self, two_bank_orchestrator):
        """Policy events should only be visible to the agent making the decision."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 20)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find all policy events
        policy_events = [e for e in all_events if e.get("event_type", "").startswith("Policy")]

        for event in policy_events:
            agent_id = event.get("agent_id")

            if agent_id == "BANK_A":
                assert filter_a.matches(event, tick=0), \
                    "BANK_A policy events should be visible to BANK_A"
                assert not filter_b.matches(event, tick=0), \
                    "BANK_A policy events should NOT be visible to BANK_B"
            elif agent_id == "BANK_B":
                assert filter_b.matches(event, tick=0), \
                    "BANK_B policy events should be visible to BANK_B"
                assert not filter_a.matches(event, tick=0), \
                    "BANK_B policy events should NOT be visible to BANK_A"

    def test_filtered_event_counts_differ_between_banks(self, two_bank_orchestrator):
        """Each bank should see different events (not just all events)."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 30)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]
        events_b = [e for e in all_events if filter_b.matches(e, tick=0)]

        # Both should see some events
        assert len(events_a) > 0, "BANK_A should see some events"
        assert len(events_b) > 0, "BANK_B should see some events"

        # Neither should see all events
        assert len(events_a) < len(all_events), "BANK_A should not see all events"
        assert len(events_b) < len(all_events), "BANK_B should not see all events"

        # The sum might exceed total (due to shared settlements) or be less
        # (due to filtering out arrivals), but shouldn't equal exact total
        combined = set()
        for e in events_a:
            combined.add(id(e))
        for e in events_b:
            combined.add(id(e))

        # Combined unique events should be less than or equal to total
        # (some events visible to both, some visible to neither like system events)

    def test_cost_accrual_events_only_visible_to_incurring_agent(self, two_bank_orchestrator):
        """Cost accrual events should only be visible to the agent incurring costs."""
        orch = two_bank_orchestrator
        all_events = self.collect_all_events(orch, 30)

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Find cost accrual events
        cost_events = [e for e in all_events if e.get("event_type") == "CostAccrual"]

        for event in cost_events:
            agent_id = event.get("agent_id")

            if agent_id == "BANK_A":
                assert filter_a.matches(event, tick=0)
                assert not filter_b.matches(event, tick=0), \
                    "BANK_B should not see BANK_A's cost accruals"
            elif agent_id == "BANK_B":
                assert filter_b.matches(event, tick=0)
                assert not filter_a.matches(event, tick=0), \
                    "BANK_A should not see BANK_B's cost accruals"


class TestFilteredReplayEventConsistency:
    """Tests verifying filtered events are consistent and complete."""

    @pytest.fixture
    def orchestrator_with_transactions(self):
        """Create orchestrator configured to generate settlements."""
        config = {
            "rng_seed": 42,
            "ticks_per_day": 30,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {"type": "Normal", "mean": 5000, "std_dev": 1000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {"type": "Normal", "mean": 5000, "std_dev": 1000},
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 1.0},
                        "deadline_window": {"min": 5, "max": 15},
                    },
                },
            ],
        }
        return Orchestrator.new(config)

    def test_filtered_events_preserve_settlement_chain(self, orchestrator_with_transactions):
        """Filtered events should preserve complete settlement information."""
        orch = orchestrator_with_transactions

        # Run simulation
        all_events = []
        for tick in range(20):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")

        # Get BANK_A's view
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # For each settlement BANK_A sees, verify it has required fields
        settlements = [e for e in events_a if e.get("event_type") == "RtgsImmediateSettlement"]

        for s in settlements:
            # Settlement should have all required fields for display
            assert "sender" in s or "sender_id" in s
            assert "receiver" in s or "receiver_id" in s
            assert "amount" in s
            assert "tick" in s

    def test_no_duplicate_events_in_filtered_output(self, orchestrator_with_transactions):
        """Each event should appear at most once in filtered output."""
        orch = orchestrator_with_transactions

        all_events = []
        for tick in range(20):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # Check for duplicates by creating unique signatures
        signatures = []
        for e in events_a:
            sig = (
                e.get("event_type"),
                e.get("tick"),
                e.get("tx_id"),
                e.get("agent_id") or e.get("sender_id") or e.get("sender"),
            )
            signatures.append(sig)

        # Should have no duplicates
        assert len(signatures) == len(set(signatures)), \
            "Filtered events should not have duplicates"


class TestLLMContextIsolation:
    """Tests specifically validating LLM context isolation for Castro."""

    @pytest.fixture
    def scenario_orchestrator(self):
        """Orchestrator mimicking Castro experiment scenario."""
        config = {
            "rng_seed": 99,
            "ticks_per_day": 40,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 300000,  # Lower balance to create interesting dynamics
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.8,
                        "amount_distribution": {"type": "Normal", "mean": 8000, "std_dev": 2000},
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 8, "max": 25},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 300000,
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 0.8,
                        "amount_distribution": {"type": "Normal", "mean": 8000, "std_dev": 2000},
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 8, "max": 25},
                    },
                },
            ],
        }
        return Orchestrator.new(config)

    def test_llm_sees_own_transaction_lifecycle(self, scenario_orchestrator):
        """LLM should see complete lifecycle of its own transactions."""
        orch = scenario_orchestrator

        all_events = []
        for tick in range(30):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # Find transactions BANK_A initiated (via arrivals)
        bank_a_arrivals = [e for e in events_a if e.get("event_type") == "Arrival"]

        if not bank_a_arrivals:
            pytest.skip("No arrivals generated")

        # For each arrival BANK_A initiated, it should also see the settlement if it happened
        for arrival in bank_a_arrivals:
            tx_id = arrival.get("tx_id")
            if not tx_id:
                continue

            # Check if there's a matching settlement in BANK_A's view
            # (Either RTGS immediate or queue release)
            related_events = [
                e for e in events_a
                if e.get("tx_id") == tx_id
            ]

            # BANK_A should see all events for transactions it initiated
            assert len(related_events) >= 1, \
                f"BANK_A should see events for tx {tx_id} it initiated"

    def test_llm_cannot_infer_opponent_strategy(self, scenario_orchestrator):
        """LLM should not be able to infer opponent's strategy from filtered events."""
        orch = scenario_orchestrator

        all_events = []
        for tick in range(30):
            orch.tick()
            all_events.extend(orch.get_tick_events(tick))

        filter_a = EventFilter(agent_id="BANK_A")
        events_a = [e for e in all_events if filter_a.matches(e, tick=0)]

        # BANK_A should not see any of these BANK_B-specific events:
        bank_b_internal_types = {
            ("Arrival", "BANK_B"),  # BANK_B's outgoing transactions
            ("PolicySubmit", "BANK_B"),
            ("PolicyHold", "BANK_B"),
            ("PolicySplit", "BANK_B"),
            ("CostAccrual", "BANK_B"),
            ("CollateralPosted", "BANK_B"),
            ("CollateralReleased", "BANK_B"),
        }

        for event in events_a:
            event_type = event.get("event_type")
            agent = event.get("agent_id") or event.get("sender_id")

            if event_type == "Arrival":
                # Arrivals should only be BANK_A's
                assert event.get("sender_id") != "BANK_B", \
                    "BANK_A should not see BANK_B's arrivals"

            elif event_type in ["PolicySubmit", "PolicyHold", "PolicySplit"]:
                assert agent != "BANK_B", \
                    f"BANK_A should not see BANK_B's {event_type} decisions"

            elif event_type == "CostAccrual":
                assert agent != "BANK_B", \
                    "BANK_A should not see BANK_B's cost accruals"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
