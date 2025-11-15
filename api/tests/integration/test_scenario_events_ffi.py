"""
Integration tests for scenario events FFI.

Tests that scenario events can be configured from Python and execute correctly
during simulation. Follows TDD: tests written before Pydantic schemas exist.

These tests verify:
1. Event configuration parsing from Python dicts
2. Event execution at correct ticks
3. Event effects on simulation state
4. Error handling for invalid configurations
"""
import pytest
from payment_simulator._core import Orchestrator


def test_direct_transfer_one_time():
    """
    Test that a one-time DirectTransfer event executes at the specified tick.

    TDD: This test defines expected behavior before implementation.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial balances
    assert orch.get_agent_balance("BANK_A") == 1_000_000
    assert orch.get_agent_balance("BANK_B") == 1_000_000

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # After event execution
    assert orch.get_agent_balance("BANK_A") == 900_000
    assert orch.get_agent_balance("BANK_B") == 1_100_000


def test_direct_transfer_repeating():
    """
    Test that a repeating DirectTransfer event executes at correct intervals.

    TDD: Verifies repeating schedule logic.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 50_000,
                "schedule": "Repeating",
                "start_tick": 10,
                "interval": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run through tick 30 (should trigger at ticks 10, 20, 30)
    for _ in range(31):
        orch.tick()

    # 3 transfers of 50k each = 150k total
    assert orch.get_agent_balance("BANK_A") == 850_000
    assert orch.get_agent_balance("BANK_B") == 1_150_000


def test_collateral_adjustment():
    """
    Test that CollateralAdjustment event modifies credit limits.

    TDD: Verifies collateral adjustment event type.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": 200_000,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial credit limit
    assert orch.get_agent_credit_limit("BANK_A") == 500_000

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # After adjustment
    assert orch.get_agent_credit_limit("BANK_A") == 700_000


def test_global_arrival_rate_change():
    """
    Test that GlobalArrivalRateChange multiplies all agents' arrival rates.

    TDD: Verifies arrival rate modification events.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 50_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 50_000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.5,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial rates
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(1.0)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(2.0)

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # After rate change (halved)
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(0.5)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(1.0)


def test_agent_arrival_rate_change():
    """
    Test that AgentArrivalRateChange modifies specific agent's rate.

    TDD: Verifies per-agent rate modification.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 50_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000,
                        "max": 50_000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
        ],
        "scenario_events": [
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 3.0,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial rates
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(1.0)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(2.0)

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # After rate change (only BANK_A tripled)
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(3.0)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(2.0)


def test_multiple_events_same_tick():
    """
    Test that multiple events can execute in the same tick.

    TDD: Verifies event sequencing.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            },
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # Both events should have executed
    assert orch.get_agent_balance("BANK_A") == 900_000
    assert orch.get_agent_balance("BANK_B") == 1_100_000
    assert orch.get_agent_credit_limit("BANK_A") == 600_000


def test_scenario_events_logged():
    """
    Test that scenario events appear in the event log.

    TDD: Verifies event logging for replay identity.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run through tick 10
    for _ in range(11):
        orch.tick()

    # Check that event was logged
    tick_events = orch.get_tick_events(10)
    scenario_events = [e for e in tick_events if e.get("event_type") == "ScenarioEventExecuted"]

    assert len(scenario_events) > 0, "Scenario event should be logged"


def test_invalid_event_type_rejected():
    """
    Test that invalid event types are rejected with clear error.

    TDD: Verifies error handling.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "InvalidEventType",
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    with pytest.raises(Exception) as exc_info:
        Orchestrator.new(config)

    assert "Invalid event type" in str(exc_info.value)


def test_missing_required_field_rejected():
    """
    Test that events missing required fields are rejected.

    TDD: Verifies validation.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                # Missing: amount
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    with pytest.raises(Exception) as exc_info:
        Orchestrator.new(config)

    assert "amount" in str(exc_info.value).lower()


def test_scenario_events_deterministic():
    """
    Test that scenario events produce deterministic results.

    TDD: Verifies determinism with same seed.
    """
    config1 = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    config2 = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch1 = Orchestrator.new(config1)
    orch2 = Orchestrator.new(config2)

    # Run both for 20 ticks
    for _ in range(20):
        orch1.tick()
        orch2.tick()

    # Results should be identical
    assert orch1.get_agent_balance("BANK_A") == orch2.get_agent_balance("BANK_A")
    assert orch1.get_agent_balance("BANK_B") == orch2.get_agent_balance("BANK_B")
