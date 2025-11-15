"""Test tick execution via FFI."""
import pytest
from payment_simulator._core import Orchestrator


def test_tick_returns_result():
    """Should execute tick and return TickResult."""
    orch = Orchestrator.new(_minimal_config())
    result = orch.tick()

    assert "tick" in result
    assert "num_arrivals" in result
    assert "num_settlements" in result
    assert result["tick"] == 0  # First tick is 0


def test_multiple_ticks():
    """Should execute multiple ticks sequentially."""
    orch = Orchestrator.new(_minimal_config())

    results = [orch.tick() for _ in range(10)]

    # Verify tick counter increases
    assert [r["tick"] for r in results] == list(range(10))


def _minimal_config():
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 0, "policy": {"type": "Fifo"}},
        ],
    }
