"""
Integration tests for performance diagnostics feature.

Tests verify that timing data is collected, exposed via FFI, and
contains reasonable values.
"""

import pytest
from payment_simulator._core import Orchestrator


def test_tick_result_includes_timing_data():
    """Verify that tick() returns timing data in the result."""
    config = {
        "rng_seed": 12345,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)
    result = orch.tick()

    # Verify timing key exists
    assert "timing" in result, "Result should include timing data"

    timing = result["timing"]

    # Verify all expected fields exist
    assert "arrivals_micros" in timing
    assert "policy_eval_micros" in timing
    assert "rtgs_settlement_micros" in timing
    assert "rtgs_queue_micros" in timing
    assert "lsm_micros" in timing
    assert "cost_accrual_micros" in timing
    assert "total_micros" in timing

    # Verify types
    for field, value in timing.items():
        assert isinstance(value, int), f"{field} should be int, got {type(value)}"

    # Verify total is sum of parts (approximately, accounting for overhead)
    parts_sum = (
        timing["arrivals_micros"]
        + timing["policy_eval_micros"]
        + timing["rtgs_settlement_micros"]
        + timing["rtgs_queue_micros"]
        + timing["lsm_micros"]
        + timing["cost_accrual_micros"]
    )
    assert (
        timing["total_micros"] >= parts_sum
    ), f"Total ({timing['total_micros']}) should be >= sum of parts ({parts_sum})"


def test_timing_values_are_reasonable():
    """Verify that timing values are non-zero and within reasonable bounds."""
    config = {
        "rng_seed": 12345,
        "num_days": 1,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": f"BANK_{i}",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,
                    "amount_distribution": {"type": "Uniform", "min": 1000, "max": 5000},
                    "counterparty_weights": {
                        f"BANK_{j}": 1.0 for j in range(5) if j != i
                    },
                    "deadline_range": [10, 50],
                },
            }
            for i in range(5)
        ],
    }

    orch = Orchestrator.new(config)
    result = orch.tick()

    timing = result["timing"]

    # Total execution should be non-zero and less than 1 second (1M μs)
    assert timing["total_micros"] > 0, "Total time should be positive"
    assert (
        timing["total_micros"] < 1_000_000
    ), f"Tick should complete in < 1 second, got {timing['total_micros']} μs"

    # Each phase should take some time (even if minimal)
    # Note: Some phases might be 0 if there's nothing to do
    assert timing["arrivals_micros"] >= 0
    assert timing["policy_eval_micros"] >= 0
    assert timing["cost_accrual_micros"] >= 0  # Always runs


def test_timing_consistency_across_ticks():
    """Verify timing data is provided consistently for multiple ticks."""
    config = {
        "rng_seed": 99999,
        "num_days": 1,
        "ticks_per_day": 50,
        "agent_configs": [
            {
                "id": "BANK_X",
                "opening_balance": 50000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.5,
                    "amount_distribution": {"type": "Uniform", "min": 1000, "max": 3000},
                    "counterparty_weights": {"BANK_Y": 1.0, "BANK_Z": 1.0},
                    "deadline_range": [10, 40],
                },
            },
            {"id": "BANK_Y", "opening_balance": 50000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
            {"id": "BANK_Z", "opening_balance": 50000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Run multiple ticks
    for tick in range(10):
        result = orch.tick()

        # Every tick should have timing data
        assert "timing" in result, f"Tick {tick} missing timing data"

        timing = result["timing"]

        # Verify structure consistency
        required_fields = [
            "arrivals_micros",
            "policy_eval_micros",
            "rtgs_settlement_micros",
            "rtgs_queue_micros",
            "lsm_micros",
            "cost_accrual_micros",
            "total_micros",
        ]

        for field in required_fields:
            assert field in timing, f"Tick {tick} missing field: {field}"
            assert isinstance(
                timing[field], int
            ), f"Tick {tick} field {field} should be int"
            assert timing[field] >= 0, f"Tick {tick} field {field} should be non-negative"
