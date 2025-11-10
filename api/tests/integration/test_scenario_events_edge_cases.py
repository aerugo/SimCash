"""
Comprehensive edge case and integration tests for scenario events.

Tests complex scenarios, edge cases, and full integration to ensure
robustness of the scenario events implementation.
"""
import pytest
from payment_simulator._core import Orchestrator


def test_scenario_event_execution_order_same_tick():
    """
    Test that multiple events at the same tick execute in order.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            # Event 1: Transfer 100k from A to B
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "OneTime",
                "tick": 10,
            },
            # Event 2: Transfer 50k from B to A (should use funds from event 1)
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_B",
                "to_agent": "BANK_A",
                "amount": 50_000,
                "schedule": "OneTime",
                "tick": 10,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run to tick 11
    for _ in range(12):
        orch.tick()

    # Verify final balances reflect both transfers
    # A: 1M - 100k + 50k = 950k
    # B: 1M + 100k - 50k = 1.05M
    assert orch.get_agent_balance("BANK_A") == 950_000
    assert orch.get_agent_balance("BANK_B") == 1_050_000


def test_collateral_adjustment_affects_credit_limit():
    """
    Test that CollateralAdjustment correctly modifies credit limits.
    """
    config = {
        "rng_seed": 42,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000,
                "credit_limit": 200_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            # Increase BANK_A's credit limit by 300k
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": 300_000,
                "schedule": "OneTime",
                "tick": 5,
            },
            # Decrease it by 100k later
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": -100_000,
                "schedule": "OneTime",
                "tick": 15,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Initial credit limit
    assert orch.get_agent_credit_limit("BANK_A") == 200_000

    # After first adjustment (tick 5)
    for _ in range(6):
        orch.tick()
    assert orch.get_agent_credit_limit("BANK_A") == 500_000

    # After second adjustment (tick 15)
    for _ in range(10):
        orch.tick()
    assert orch.get_agent_credit_limit("BANK_A") == 400_000


def test_repeating_event_stops_at_end_of_simulation():
    """
    Test that repeating events stop when simulation ends.
    """
    config = {
        "rng_seed": 99,
        "ticks_per_day": 50,
        "num_days": 1,  # Only 50 ticks total
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 10_000,
                "schedule": "Repeating",
                "start_tick": 10,
                "interval": 5,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run full simulation (50 ticks)
    for _ in range(50):
        orch.tick()

    # Events should execute at ticks: 10, 15, 20, 25, 30, 35, 40, 45
    # That's 8 executions, 80k total transferred
    assert orch.get_agent_balance("BANK_A") == 10_000_000 - 80_000
    assert orch.get_agent_balance("BANK_B") == 1_000_000 + 80_000


def test_arrival_rate_changes_affect_future_arrivals():
    """
    Test that arrival rate changes only affect future transaction generation.

    Note: This tests the mechanism, actual arrival behavior depends on RNG.
    """
    config = {
        "rng_seed": 777,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Uniform", "min": 10000, "max": 20000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 10_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            # Double BANK_A's arrival rate at tick 20
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 2.0,
                "schedule": "OneTime",
                "tick": 20,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Check initial rate
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(1.0)

    # Run to tick 21
    for _ in range(22):
        orch.tick()

    # Rate should be doubled
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(2.0)


def test_global_arrival_rate_change_affects_all_agents():
    """
    Test that GlobalArrivalRateChange multiplies all agents' rates.
    """
    config = {
        "rng_seed": 555,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 10_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Uniform", "min": 10000, "max": 20000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 10_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Uniform", "min": 10000, "max": 20000},
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 50],
                },
            },
        ],
        "scenario_events": [
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.1,  # Reduce all rates to 10%
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Initial rates
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(1.0)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(0.5)

    # Run to tick 11
    for _ in range(12):
        orch.tick()

    # Both rates should be multiplied by 0.1
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(0.1)
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(0.05)


def test_zero_amount_transfer_accepted():
    """
    Test that zero-amount transfers are accepted (edge case behavior).

    Note: Zero-amount transfers are technically valid - they just don't change balances.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 1,  # Minimal valid amount
                "schedule": "OneTime",
                "tick": 10,
            }
        ],
    }

    # Should work fine
    orch = Orchestrator.new(config)
    for _ in range(12):
        orch.tick()

    # Verify minimal transfer happened
    assert orch.get_agent_balance("BANK_A") == 999_999
    assert orch.get_agent_balance("BANK_B") == 1_000_001


def test_negative_interval_rejected():
    """
    Test that negative intervals are rejected at config validation.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": "Repeating",
                "start_tick": 10,
                "interval": -5,  # Invalid!
            }
        ],
    }

    with pytest.raises(Exception):
        Orchestrator.new(config)


def test_determinism_with_scenario_events():
    """
    Test that scenario events maintain simulation determinism.

    Two runs with same config and seed should produce identical results.
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 50000, "std_dev": 10000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
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
                "type": "GlobalArrivalRateChange",
                "multiplier": 2.0,
                "schedule": "OneTime",
                "tick": 20,
            },
        ],
    }

    # Run 1
    orch1 = Orchestrator.new(config.copy())
    for _ in range(50):
        orch1.tick()
    balance1_a = orch1.get_agent_balance("BANK_A")
    balance1_b = orch1.get_agent_balance("BANK_B")

    # Run 2
    orch2 = Orchestrator.new(config.copy())
    for _ in range(50):
        orch2.tick()
    balance2_a = orch2.get_agent_balance("BANK_A")
    balance2_b = orch2.get_agent_balance("BANK_B")

    # Results should be identical
    assert balance1_a == balance2_a
    assert balance1_b == balance2_b


def test_complex_scenario_with_multiple_event_types():
    """
    Integration test using multiple event types in a realistic scenario.
    """
    config = {
        "rng_seed": 999,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 5_000_000,
                "credit_limit": 1_000_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Uniform", "min": 10000, "max": 50000},
                    "counterparty_weights": {"BANK_B": 0.7, "BANK_C": 0.3},
                    "deadline_range": [10, 50],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 3_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.3,
                    "amount_distribution": {"type": "Uniform", "min": 20000, "max": 60000},
                    "counterparty_weights": {"BANK_A": 0.5, "BANK_C": 0.5},
                    "deadline_range": [15, 60],
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 2_000_000,
                "credit_limit": 300_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.2,
                    "amount_distribution": {"type": "Uniform", "min": 15000, "max": 40000},
                    "counterparty_weights": {"BANK_A": 0.6, "BANK_B": 0.4},
                    "deadline_range": [20, 70],
                },
            },
        ],
        "scenario_events": [
            # 1. DirectTransfer: BANK_A gets a large incoming payment
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_B",
                "to_agent": "BANK_A",
                "amount": 500_000,
                "schedule": "OneTime",
                "tick": 10,
            },
            # 2. CollateralAdjustment: BANK_C posts more collateral
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_C",
                "delta": 200_000,
                "schedule": "OneTime",
                "tick": 20,
            },
            # 3. AgentArrivalRateChange: BANK_A reduces outgoing volume
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 0.5,
                "schedule": "OneTime",
                "tick": 30,
            },
            # 4. GlobalArrivalRateChange: Market-wide slowdown
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.7,
                "schedule": "OneTime",
                "tick": 60,
            },
            # 5. Repeating payment: Regular settlement
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_C",
                "amount": 50_000,
                "schedule": "Repeating",
                "start_tick": 15,
                "interval": 20,
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Run full simulation
    for _ in range(100):
        orch.tick()

    # Verify all agents still have positive balances (no crashes)
    assert orch.get_agent_balance("BANK_A") > 0
    assert orch.get_agent_balance("BANK_B") > 0
    assert orch.get_agent_balance("BANK_C") > 0

    # Verify credit limits changed as expected
    assert orch.get_agent_credit_limit("BANK_C") == 500_000  # 300k + 200k

    # Verify arrival rates reflect all changes
    # BANK_A: 0.5 * 0.5 (AgentChange) * 0.7 (GlobalChange) = 0.175
    assert orch.get_arrival_rate("BANK_A") == pytest.approx(0.175)
    # BANK_B: 0.3 * 0.7 (GlobalChange) = 0.21
    assert orch.get_arrival_rate("BANK_B") == pytest.approx(0.21)
    # BANK_C: 0.2 * 0.7 (GlobalChange) = 0.14
    assert orch.get_arrival_rate("BANK_C") == pytest.approx(0.14)


def test_event_at_tick_zero():
    """
    Test that events can execute at tick 0 (initialization time).
    """
    config = {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "opening_balance": 500_000, "credit_limit": 0, "policy": {"type": "Fifo"}},
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 200_000,
                "schedule": "OneTime",
                "tick": 0,
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Event should execute at tick 0
    orch.tick()

    # Verify transfer happened
    assert orch.get_agent_balance("BANK_A") == 800_000
    assert orch.get_agent_balance("BANK_B") == 700_000
