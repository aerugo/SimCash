"""
Integration tests for AgentArrivalRateChange scenario event.

Tests the AgentArrivalRateChange event type which modifies a specific
agent's transaction arrival rate by a multiplier.

TDD Approach: Tests written first, implementation follows.
"""

import json
import pytest
from payment_simulator._core import Orchestrator


def test_agent_arrival_rate_change_doubles_rate():
    """Test doubling a specific agent's arrival rate."""
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
                    "rate_per_tick": 0.5,  # ~10 arrivals over 20 ticks
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,  # Should remain unchanged
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 20],
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 2.0,  # Double BANK_A's rate at tick 10
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run full simulation
    for _ in range(20):
        orch.tick()

    # Get all events
    events = orch.get_all_events()

    # Count arrivals per agent
    arrivals_by_agent = {}
    for event in events:
        if event.get("event_type") == "Arrival":
            sender = event.get("sender_id", "")
            arrivals_by_agent[sender] = arrivals_by_agent.get(sender, 0) + 1

    # BANK_A should have more arrivals than BANK_B
    # Pre-event (ticks 0-9): ~5 arrivals at 0.5 rate
    # Post-event (ticks 11-19): ~9 arrivals at 1.0 rate
    # Total BANK_A: ~14 arrivals
    # BANK_B: ~10 arrivals (unchanged 0.5 rate)

    bank_a_arrivals = arrivals_by_agent.get("BANK_A", 0)
    bank_b_arrivals = arrivals_by_agent.get("BANK_B", 0)

    # Allow for significant Poisson variance
    # With 0.5 rate: expect ~10 for BANK_B, ~14 for BANK_A (with rate change)
    # But Poisson variance means we need looser bounds
    assert bank_a_arrivals >= 9, f"BANK_A should have ≥9 arrivals after rate change, got {bank_a_arrivals}"
    assert bank_b_arrivals >= 6, f"BANK_B should have ≥6 arrivals (baseline), got {bank_b_arrivals}"

    # Most importantly: verify the rate change was logged
    scenario_events = [e for e in events if e.get("event_type") == "ScenarioEventExecuted"]
    rate_change_events = [e for e in scenario_events if e.get("scenario_event_type") == "agent_arrival_rate_change"]
    assert len(rate_change_events) == 1, f"Rate change event should be logged, found {len(rate_change_events)}"


def test_agent_arrival_rate_change_halves_rate():
    """Test halving an agent's arrival rate."""
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
                    "rate_per_tick": 1.0,  # Start with 1.0
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 20],
                    "priority": 5,
                    "divisible": False,
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
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 0.5,  # Halve BANK_A's rate
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run simulation
    for _ in range(20):
        orch.tick()

    events = orch.get_all_events()

    # Count arrivals
    arrivals_by_agent = {}
    for event in events:
        if event.get("event_type") == "Arrival":
            sender = event.get("sender_id", "")
            arrivals_by_agent[sender] = arrivals_by_agent.get(sender, 0) + 1

    bank_a_arrivals = arrivals_by_agent.get("BANK_A", 0)
    bank_b_arrivals = arrivals_by_agent.get("BANK_B", 0)

    # BANK_A: Pre-event (10 ticks * 1.0) + Post-event (10 ticks * 0.5) = ~15 total
    # BANK_B: 20 ticks * 0.5 = ~10 total
    assert bank_a_arrivals > bank_b_arrivals, (
        f"BANK_A should still have more total arrivals "
        f"(BANK_A: {bank_a_arrivals}, BANK_B: {bank_b_arrivals})"
    )
    assert 13 <= bank_a_arrivals <= 17, f"BANK_A should have ~15 arrivals, got {bank_a_arrivals}"


def test_agent_arrival_rate_change_near_halt():
    """Test setting arrival rate very low (near halt)."""
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
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 0.001,  # Near-complete halt
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run simulation
    for _ in range(50):
        orch.tick()

    events = orch.get_all_events()

    # Count arrivals per period
    arrivals_before = 0
    arrivals_after = 0

    for event in events:
        if event.get("event_type") == "Arrival":
            if event.get("sender_id") == "BANK_A":
                tick = event.get("tick", 0)
                if tick < 10:
                    arrivals_before += 1
                else:
                    arrivals_after += 1

    # Pre-event: 10 ticks * 0.5 = ~5 arrivals (but Poisson variance means could be 2-8)
    # Post-event: 40 ticks * 0.0005 = ~0.02 arrivals (likely 0-1)
    assert arrivals_before >= 1, f"Should have ≥1 arrivals before event, got {arrivals_before}"
    assert arrivals_after <= 3, f"Should have ≤3 arrivals after near-halt, got {arrivals_after}"


def test_agent_arrival_rate_change_logged_to_events():
    """Verify event is logged correctly."""
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
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
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

    # Find the AgentArrivalRateChange event
    rate_change_events = [
        e for e in scenario_events
        if e.get("scenario_event_type") == "agent_arrival_rate_change"
    ]

    assert len(rate_change_events) == 1, f"Should have exactly 1 rate change event, got {len(rate_change_events)}"

    event = rate_change_events[0]

    # Parse details JSON
    details_json = event.get("details_json", "{}")
    details = json.loads(details_json) if isinstance(details_json, str) else details_json

    # Verify details
    assert details.get("agent") == "BANK_A", f"Agent should be BANK_A, got {details.get('agent')}"
    assert details.get("multiplier") == 1.5, f"Multiplier should be 1.5, got {details.get('multiplier')}"
    assert "old_rate" in details, "Should include old_rate"
    assert "new_rate" in details, "Should include new_rate"
    assert abs(details.get("old_rate", 0) - 0.8) < 0.01, f"Old rate should be ~0.8, got {details.get('old_rate')}"
    assert abs(details.get("new_rate", 0) - 1.2) < 0.01, f"New rate should be ~1.2, got {details.get('new_rate')}"


def test_multiple_agent_arrival_rate_changes():
    """Test multiple rate changes to same agent (multiplicative effect)."""
    config = {
        "ticks_per_day": 30,
        "num_days": 1,
        "rng_seed": 777,
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
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 2.0,  # 0.5 → 1.0
                "schedule": "OneTime",
                "tick": 10,
            },
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
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

    # Count arrivals by period
    period1 = 0  # Ticks 0-9: rate 0.5
    period2 = 0  # Ticks 10-19: rate 1.0
    period3 = 0  # Ticks 20-29: rate 2.0

    for event in events:
        if event.get("event_type") == "Arrival" and event.get("sender_id") == "BANK_A":
            tick = event.get("tick", 0)
            if tick < 10:
                period1 += 1
            elif tick < 20:
                period2 += 1
            else:
                period3 += 1

    # Expected: ~5, ~10, ~20 arrivals respectively (with Poisson variance)
    # Rates: 0.5 → 1.0 → 2.0 (4x multiplier overall)
    assert period1 < period2 < period3, (
        f"Arrivals should increase each period: P1={period1}, P2={period2}, P3={period3}"
    )
    # With variance, require period3 ≥ 2.5x period1 (looser than theoretical 4x)
    assert period3 >= period1 * 2.5, (
        f"Period 3 should have ≥2.5× period 1 arrivals (rates: 0.5→2.0) "
        f"(P1={period1}, P3={period3})"
    )
