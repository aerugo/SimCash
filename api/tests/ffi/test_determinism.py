"""Test determinism preservation across FFI."""
import pytest
from payment_simulator._core import Orchestrator


def test_same_seed_same_results():
    """Identical seed must produce identical outcomes."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 100_000, "std_dev": 20_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }

    # Run simulation twice with same seed
    orch1 = Orchestrator.new(config)
    results1 = [orch1.tick() for _ in range(50)]

    orch2 = Orchestrator.new(config)
    results2 = [orch2.tick() for _ in range(50)]

    # Must be identical (excluding timing which varies with CPU scheduling)
    # Compare only simulation-relevant fields
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        assert r1["tick"] == r2["tick"], f"Tick {i}: tick mismatch"
        assert r1["num_arrivals"] == r2["num_arrivals"], f"Tick {i}: num_arrivals mismatch"
        assert r1["num_settlements"] == r2["num_settlements"], f"Tick {i}: num_settlements mismatch"
        assert r1["num_lsm_releases"] == r2["num_lsm_releases"], f"Tick {i}: num_lsm_releases mismatch"
        assert r1["total_cost"] == r2["total_cost"], f"Tick {i}: total_cost mismatch"
        # timing field intentionally excluded - it varies with CPU scheduling


def test_different_seed_different_results():
    """Different seeds should produce different outcomes."""
    config_template = {
        "ticks_per_day": 100,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 100_000, "std_dev": 20_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {"id": "BANK_B", "opening_balance": 2_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }

    config1 = {**config_template, "rng_seed": 12345}
    config2 = {**config_template, "rng_seed": 54321}

    orch1 = Orchestrator.new(config1)
    results1 = [orch1.tick() for _ in range(50)]

    orch2 = Orchestrator.new(config2)
    results2 = [orch2.tick() for _ in range(50)]

    # Should be different (with high probability)
    assert results1 != results2
