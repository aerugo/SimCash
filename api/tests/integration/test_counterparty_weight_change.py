"""
Integration tests for CounterpartyWeightChange scenario event.

Tests the CounterpartyWeightChange event type which modifies a specific
agent's counterparty selection weight for one counterparty.

TDD Approach: Tests written first, implementation verified.
"""

import json
import pytest
from payment_simulator._core import Orchestrator


def test_counterparty_weight_change_basic():
    """Test basic counterparty weight change."""
    config = {
        "ticks_per_day": 40,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,  # High rate for good statistics
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_B": 1.0,  # Equal weights initially
                        "BANK_C": 1.0,
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_B",
                "new_weight": 5.0,  # Heavily favor BANK_B
                "schedule": "OneTime",
                "tick": 20,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(40):
        orch.tick()

    events = orch.get_all_events()

    # Count transactions by receiver before and after
    counts_before = {"BANK_B": 0, "BANK_C": 0}
    counts_after = {"BANK_B": 0, "BANK_C": 0}

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_A":
            tick = event.get("tick", 0)
            receiver = event.get("receiver_id", "")

            if tick < 20:
                counts_before[receiver] = counts_before.get(receiver, 0) + 1
            else:
                counts_after[receiver] = counts_after.get(receiver, 0) + 1

    # Before: roughly equal (50/50)
    # After: heavily skewed toward BANK_B (5:1 ratio = 83% BANK_B)
    if counts_after["BANK_B"] + counts_after["BANK_C"] > 10:
        ratio_after = counts_after["BANK_B"] / max(counts_after["BANK_C"], 1)
        # Should be significantly higher than 1:1
        assert ratio_after > 2.0, (
            f"BANK_B should receive significantly more transactions after weight change "
            f"(BANK_B: {counts_after['BANK_B']}, BANK_C: {counts_after['BANK_C']}, ratio: {ratio_after:.1f})"
        )

    # Verify event was logged
    scenario_events = [e for e in events if e.get("event_type") == "ScenarioEventExecuted"]
    weight_events = [e for e in scenario_events if e.get("scenario_event_type") == "counterparty_weight_change"]
    assert len(weight_events) == 1, "Counterparty weight change event should be logged"


def test_counterparty_weight_change_zero_weight():
    """Test setting weight to zero (effectively removing counterparty)."""
    config = {
        "ticks_per_day": 40,
        "num_days": 1,
        "rng_seed": 123,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_B": 1.0,
                        "BANK_C": 1.0,
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_B",
                "new_weight": 0.0,  # Remove BANK_B
                "schedule": "OneTime",
                "tick": 20,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(40):
        orch.tick()

    events = orch.get_all_events()

    # Count transactions to BANK_B after the change
    bank_b_after = 0
    bank_c_after = 0

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_A":
            tick = event.get("tick", 0)
            receiver = event.get("receiver_id", "")

            if tick >= 20:
                if receiver == "BANK_B":
                    bank_b_after += 1
                elif receiver == "BANK_C":
                    bank_c_after += 1

    # After setting BANK_B weight to 0, all transactions should go to BANK_C
    # (or very few to BANK_B due to RNG edge cases)
    if bank_b_after + bank_c_after > 5:
        bank_c_percentage = bank_c_after / (bank_b_after + bank_c_after)
        assert bank_c_percentage > 0.7, (
            f"Most transactions should go to BANK_C after setting BANK_B weight to 0 "
            f"(BANK_B: {bank_b_after}, BANK_C: {bank_c_after})"
        )


def test_counterparty_weight_change_logged_to_events():
    """Verify counterparty weight change event is logged correctly."""
    config = {
        "ticks_per_day": 10,
        "num_days": 1,
        "rng_seed": 555,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.8,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_B": 1.0,
                    },
                    "deadline_range": [5, 10],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_B",
                "new_weight": 2.5,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(10):
        orch.tick()

    events = orch.get_all_events()
    scenario_events = [
        e for e in events if e.get("event_type") == "ScenarioEventExecuted"
    ]

    assert len(scenario_events) >= 1, "Should have at least one scenario event"

    # Find the CounterpartyWeightChange event
    weight_events = [
        e for e in scenario_events
        if e.get("scenario_event_type") == "counterparty_weight_change"
    ]

    assert len(weight_events) == 1, f"Should have exactly 1 counterparty weight change event, got {len(weight_events)}"

    event = weight_events[0]

    # Parse details JSON
    details_json = event.get("details_json", "{}")
    details = json.loads(details_json) if isinstance(details_json, str) else details_json

    # Verify details
    assert details.get("agent") == "BANK_A", f"Agent should be BANK_A, got {details.get('agent')}"
    assert details.get("counterparty") == "BANK_B", f"Counterparty should be BANK_B, got {details.get('counterparty')}"
    assert details.get("new_weight") == 2.5, f"New weight should be 2.5, got {details.get('new_weight')}"


def test_multiple_counterparty_weight_changes():
    """Test multiple weight changes to different counterparties."""
    config = {
        "ticks_per_day": 50,
        "num_days": 1,
        "rng_seed": 777,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_B": 1.0,
                        "BANK_C": 1.0,
                        "BANK_D": 1.0,
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_D",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_B",
                "new_weight": 5.0,  # Favor BANK_B first
                "schedule": "OneTime",
                "tick": 15,
            },
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_C",
                "new_weight": 10.0,  # Then favor BANK_C even more
                "schedule": "OneTime",
                "tick": 30,
            },
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(50):
        orch.tick()

    events = orch.get_all_events()

    # Count by period
    period1_counts = {"BANK_B": 0, "BANK_C": 0, "BANK_D": 0}  # Ticks 0-14: equal weights
    period2_counts = {"BANK_B": 0, "BANK_C": 0, "BANK_D": 0}  # Ticks 15-29: BANK_B favored
    period3_counts = {"BANK_B": 0, "BANK_C": 0, "BANK_D": 0}  # Ticks 30-49: BANK_C favored

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_A":
            tick = event.get("tick", 0)
            receiver = event.get("receiver_id", "")

            if tick < 15:
                period1_counts[receiver] = period1_counts.get(receiver, 0) + 1
            elif tick < 30:
                period2_counts[receiver] = period2_counts.get(receiver, 0) + 1
            else:
                period3_counts[receiver] = period3_counts.get(receiver, 0) + 1

    # Verify we have enough data
    total_p2 = sum(period2_counts.values())
    total_p3 = sum(period3_counts.values())

    if total_p2 > 10 and total_p3 > 10:
        # Period 2: BANK_B should be favored
        assert period2_counts["BANK_B"] > period2_counts["BANK_C"], (
            f"BANK_B should be favored in period 2: {period2_counts}"
        )

        # Period 3: BANK_C should be most favored
        assert period3_counts["BANK_C"] > period3_counts["BANK_B"], (
            f"BANK_C should be most favored in period 3: {period3_counts}"
        )


def test_counterparty_weight_change_new_counterparty():
    """Test adding weight to a counterparty not in original weights."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 999,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_B": 1.0,  # Only BANK_B initially
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_C",  # Add BANK_C
                "new_weight": 2.0,
                "schedule": "OneTime",
                "tick": 15,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(30):
        orch.tick()

    events = orch.get_all_events()

    # Count transactions to BANK_C after the change
    bank_c_after = 0
    total_after = 0

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_A":
            tick = event.get("tick", 0)
            receiver = event.get("receiver_id", "")

            if tick >= 15:
                total_after += 1
                if receiver == "BANK_C":
                    bank_c_after += 1

    # After adding BANK_C with weight 2.0, it should receive some transactions
    # (before the change, all went to BANK_B)
    if total_after > 10:
        bank_c_percentage = bank_c_after / total_after
        assert bank_c_percentage > 0.3, (
            f"BANK_C should receive significant transactions after being added "
            f"(BANK_C: {bank_c_after}/{total_after} = {bank_c_percentage:.1%})"
        )


def test_counterparty_weight_change_isolated():
    """Test that weight change only affects the specified agent."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_C": 1.0,
                        "BANK_D": 1.0,
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {
                        "BANK_C": 1.0,
                        "BANK_D": 1.0,
                    },
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_D",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",  # Only change BANK_A
                "counterparty": "BANK_C",
                "new_weight": 10.0,  # Heavily favor BANK_C
                "schedule": "OneTime",
                "tick": 15,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(30):
        orch.tick()

    events = orch.get_all_events()

    # Count BANK_B's transactions (should remain balanced)
    bank_b_to_c_after = 0
    bank_b_to_d_after = 0

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_B":
            tick = event.get("tick", 0)
            receiver = event.get("receiver_id", "")

            if tick >= 15:
                if receiver == "BANK_C":
                    bank_b_to_c_after += 1
                elif receiver == "BANK_D":
                    bank_b_to_d_after += 1

    # BANK_B's weights should remain roughly equal (not affected by BANK_A's change)
    total_bank_b = bank_b_to_c_after + bank_b_to_d_after
    if total_bank_b > 10:
        ratio = abs(bank_b_to_c_after - bank_b_to_d_after) / total_bank_b
        # Allow for Poisson variance with small sample sizes
        assert ratio < 0.55, (
            f"BANK_B's transactions should remain balanced (not affected by BANK_A's weight change) "
            f"(to C: {bank_b_to_c_after}, to D: {bank_b_to_d_after})"
        )
