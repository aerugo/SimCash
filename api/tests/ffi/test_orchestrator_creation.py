"""Test orchestrator creation via FFI."""
import pytest
from payment_simulator._core import Orchestrator


def test_create_minimal_orchestrator():
    """Should create orchestrator with minimal config."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)
    assert orch is not None


def test_invalid_config_raises_error():
    """Should raise ValueError for invalid config."""
    with pytest.raises(ValueError, match="ticks_per_day must be positive"):
        Orchestrator.new({"ticks_per_day": 0, "num_days": 1, "rng_seed": 123, "agent_configs": []})


def test_type_conversion():
    """Should handle Python types correctly."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,  # Python int → Rust i64
                "credit_limit": 500_000,
                "policy": {"type": "LiquidityAware", "target_buffer": 200_000, "urgency_threshold": 5},
            },
        ],
    }

    orch = Orchestrator.new(config)
    assert orch is not None
