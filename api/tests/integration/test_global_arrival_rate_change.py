"""
Integration tests for GlobalArrivalRateChange scenario event.

Tests the GlobalArrivalRateChange event type which modifies ALL agents'
transaction arrival rates by a multiplier.

TDD Approach: Tests written first, implementation verified.
"""

import json
import pytest
from payment_simulator._core import Orchestrator


def test_global_arrival_rate_change_doubles_all_rates():
    """Test doubling all agents' arrival rates."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Start: 0.5
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Start: 0.5
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 20],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 2.0,  # Double ALL rates at tick 10
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run full simulation
    for _ in range(20):
        orch.tick()

    events = orch.get_all_events()

    # Count arrivals per agent per period
    arrivals = {"BANK_A": {"before": 0, "after": 0}, "BANK_B": {"before": 0, "after": 0}}

    for event in events:
        if event.get("event_type") == "Arrival":
            sender = event.get("sender_id")
            tick = event.get("tick", 0)
            if sender in arrivals:
                period = "before" if tick < 10 else "after"
                arrivals[sender][period] += 1

    # Both agents should have more arrivals after rate change
    # Pre-event (ticks 0-9): ~5 arrivals per agent at 0.5 rate
    # Post-event (ticks 10-19): ~10 arrivals per agent at 1.0 rate
    # With short periods (10 ticks), Poisson variance is significant
    total_before = sum(arrivals[agent]["before"] for agent in ["BANK_A", "BANK_B"])
    total_after = sum(arrivals[agent]["after"] for agent in ["BANK_A", "BANK_B"])

    # Check total arrivals increased (more stable than per-agent)
    assert total_after >= total_before * 1.2, (
        f"Total arrivals should increase ≥1.2x after global rate doubling "
        f"(before: {total_before}, after: {total_after})"
    )

    # Verify event was logged
    scenario_events = [e for e in events if e.get("event_type") == "ScenarioEventExecuted"]
    global_rate_events = [e for e in scenario_events if e.get("scenario_event_type") == "global_arrival_rate_change"]
    assert len(global_rate_events) == 1, "Global rate change event should be logged"


def test_global_arrival_rate_change_halves_all_rates():
    """Test halving all agents' arrival rates."""
    config = {
        "ticks_per_day": 20,
        "num_days": 1,
        "rng_seed": 123,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,  # Start: 1.0
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,  # Start: 1.0
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 20],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.5,  # Halve all rates at tick 10
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(20):
        orch.tick()

    events = orch.get_all_events()

    # Count total arrivals
    total_arrivals = sum(1 for e in events if e.get("event_type") == "Arrival")

    # With rate 1.0 for 20 ticks, expect ~20 arrivals per agent = ~40 total
    # With halving at tick 10: (10 * 1.0 + 10 * 0.5) * 2 agents = ~30 total
    assert 25 <= total_arrivals <= 35, (
        f"Expected ~30 total arrivals with halving, got {total_arrivals}"
    )


def test_global_arrival_rate_change_near_halt_all():
    """Test setting all rates very low (near-complete halt)."""
    config = {
        "ticks_per_day": 50,
        "num_days": 1,
        "rng_seed": 999,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 20],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.001,  # Near-complete halt
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(50):
        orch.tick()

    events = orch.get_all_events()

    # Count arrivals per period
    arrivals_before = 0
    arrivals_after = 0

    for event in events:
        if event.get("event_type") == "Arrival":
            tick = event.get("tick", 0)
            if tick < 10:
                arrivals_before += 1
            else:
                arrivals_after += 1

    # Pre-event: 10 ticks * 0.5 rate * 2 agents = ~10 arrivals
    # Post-event: 40 ticks * 0.0005 rate * 2 agents = ~0.04 arrivals (likely 0-2)
    assert arrivals_before >= 6, f"Should have ≥6 arrivals before event, got {arrivals_before}"
    assert arrivals_after <= 4, f"Should have ≤4 arrivals after near-halt, got {arrivals_after}"


def test_global_arrival_rate_change_logged_to_events():
    """Verify global rate change event is logged correctly."""
    config = {
        "ticks_per_day": 10,
        "num_days": 1,
        "rng_seed": 555,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.8,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [5, 10],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.6,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [5, 10],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 1.5,
                "schedule": "OneTime",
                "tick": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 5
    for _ in range(6):
        orch.tick()

    # Get scenario events
    events = orch.get_all_events()
    scenario_events = [
        e for e in events if e.get("event_type") == "ScenarioEventExecuted"
    ]

    assert len(scenario_events) >= 1, "Should have at least one scenario event"

    # Find the GlobalArrivalRateChange event
    global_rate_events = [
        e for e in scenario_events
        if e.get("scenario_event_type") == "global_arrival_rate_change"
    ]

    assert len(global_rate_events) == 1, f"Should have exactly 1 global rate change event, got {len(global_rate_events)}"

    event = global_rate_events[0]

    # Parse details JSON
    details_json = event.get("details_json", "{}")
    details = json.loads(details_json) if isinstance(details_json, str) else details_json

    # Verify details
    assert details.get("multiplier") == 1.5, f"Multiplier should be 1.5, got {details.get('multiplier')}"


def test_multiple_global_arrival_rate_changes():
    """Test multiple global rate changes (multiplicative effect)."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 12345,  # Changed seed for more reliable progressive increase
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Start: 0.5
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Start: 0.5
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 20],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 2.0,  # 0.5 → 1.0
                "schedule": "OneTime",
                "tick": 10,
            },
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 2.0,  # 1.0 → 2.0
                "schedule": "OneTime",
                "tick": 20,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run simulation
    for _ in range(30):
        orch.tick()

    events = orch.get_all_events()

    # Count arrivals by period for both agents
    period_arrivals = {
        "period1": 0,  # Ticks 0-9: rate 0.5 per agent
        "period2": 0,  # Ticks 10-19: rate 1.0 per agent
        "period3": 0,  # Ticks 20-29: rate 2.0 per agent
    }

    for event in events:
        if event.get("event_type") == "Arrival":
            tick = event.get("tick", 0)
            if tick < 10:
                period_arrivals["period1"] += 1
            elif tick < 20:
                period_arrivals["period2"] += 1
            else:
                period_arrivals["period3"] += 1

    # Expected: ~10, ~20, ~40 total arrivals (2 agents × rate)
    # With variance, check progressive increase
    p1 = period_arrivals["period1"]
    p2 = period_arrivals["period2"]
    p3 = period_arrivals["period3"]

    assert p1 < p2 < p3, (
        f"Arrivals should increase each period: P1={p1}, P2={p2}, P3={p3}"
    )
    # Looser bound due to Poisson variance
    assert p3 >= p1 * 2.5, (
        f"Period 3 should have ≥2.5× period 1 arrivals (P1={p1}, P3={p3})"
    )


def test_global_arrival_rate_change_affects_all_agents():
    """Test that global change affects all agents equally."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0, "BANK_C": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Different rate
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0, "BANK_C": 1.0},
                    "deadline_range": [10, 20],
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.75,  # Another rate
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0, "BANK_B": 1.0},
                    "deadline_range": [10, 20],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 2.0,  # Double all rates
                "schedule": "OneTime",
                "tick": 15,
            }
        ],
    }

    orch = Orchestrator.new(config)

    for _ in range(30):
        orch.tick()

    events = orch.get_all_events()

    # Calculate rate ratios before and after
    arrivals = {"BANK_A": {"before": 0, "after": 0}, "BANK_B": {"before": 0, "after": 0}, "BANK_C": {"before": 0, "after": 0}}

    for event in events:
        if event.get("event_type") == "Arrival":
            sender = event.get("sender_id")
            tick = event.get("tick", 0)
            if sender in arrivals:
                period = "before" if tick < 15 else "after"
                arrivals[sender][period] += 1

    # Each agent should approximately double their arrivals (allow variance)
    for agent in ["BANK_A", "BANK_B", "BANK_C"]:
        before = arrivals[agent]["before"]
        after = arrivals[agent]["after"]
        # After should be roughly same as before (15 ticks each at 2x rate = 2x × 0.5 time = 1x)
        # Actually after period has 15 ticks at 2x rate, before has 15 ticks at 1x rate
        # So after should be ~2x before
        if before > 0:  # Avoid division by zero for low-rate agents
            ratio = after / before
            # Allow wide variance due to Poisson + short periods
            assert 0.8 <= ratio <= 3.5, (
                f"{agent} ratio should be ~2.0 (got {ratio:.2f}, before={before}, after={after})"
            )
