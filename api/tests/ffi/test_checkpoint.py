"""Test checkpoint save/load via FFI (TDD - tests written first).

Sprint 2: FFI Boundary Tests

These tests verify the Python→Rust FFI boundary for checkpoint operations.
All tests must pass before proceeding to Sprint 3 (Database layer).
"""
import pytest
import json
from payment_simulator._core import Orchestrator


@pytest.fixture
def simple_config():
    """Simple simulation configuration for testing."""
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def config_with_transactions():
    """Configuration with arrival config for automatic transactions."""
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 5_000_000,
                "unsecured_cap": 1_000_000,
                "policy": {"type": "LiquidityAware", "target_buffer": 500_000, "urgency_threshold": 5},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {"type": "Normal", "mean": 100_000, "std_dev": 50_000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 3_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Deadline", "urgency_threshold": 10},
                "arrival_config": {
                    "rate_per_tick": 0.3,
                    "amount_distribution": {"type": "Uniform", "min": 50_000, "max": 200_000},
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [5, 30],
                    "priority": 7,
                    "divisible": False,
                },
            },
        ],
    }


# =============================================================================
# Test 1: save_state() returns valid JSON
# =============================================================================


def test_save_state_returns_valid_json(simple_config):
    """FFI: save_state() should return valid JSON string."""
    orch = Orchestrator.new(simple_config)

    # Save state
    state_json = orch.save_state()

    # Should be a string
    assert isinstance(state_json, str), "save_state() should return a string"
    assert len(state_json) > 0, "JSON should not be empty"

    # Should be valid JSON
    state_dict = json.loads(state_json)
    assert isinstance(state_dict, dict), "JSON should deserialize to dict"


def test_save_state_includes_required_fields(simple_config):
    """FFI: Saved state should include all required fields."""
    orch = Orchestrator.new(simple_config)

    # Run a few ticks to create some state
    for _ in range(5):
        orch.tick()

    # Save and parse
    state_json = orch.save_state()
    state = json.loads(state_json)

    # Verify required fields exist
    assert "current_tick" in state
    assert "current_day" in state
    assert "rng_seed" in state
    assert "agents" in state
    assert "transactions" in state
    assert "rtgs_queue" in state
    assert "config_hash" in state

    # Verify types
    assert isinstance(state["current_tick"], int)
    assert isinstance(state["current_day"], int)
    assert isinstance(state["rng_seed"], int)
    assert isinstance(state["agents"], list)
    assert isinstance(state["transactions"], list)
    assert isinstance(state["rtgs_queue"], list)
    assert isinstance(state["config_hash"], str)


def test_save_state_captures_tick_progress(simple_config):
    """FFI: Saved state should capture current tick."""
    orch = Orchestrator.new(simple_config)

    # Initial state
    state0 = json.loads(orch.save_state())
    assert state0["current_tick"] == 0

    # After 3 ticks
    for _ in range(3):
        orch.tick()

    state3 = json.loads(orch.save_state())
    assert state3["current_tick"] == 3

    # After 7 more ticks
    for _ in range(7):
        orch.tick()

    state10 = json.loads(orch.save_state())
    assert state10["current_tick"] == 10


# =============================================================================
# Test 2: load_state() reconstructs orchestrator
# =============================================================================


def test_load_state_restores_orchestrator(simple_config):
    """FFI: load_state() should restore orchestrator from JSON."""
    # Create and run original
    orch1 = Orchestrator.new(simple_config)
    for _ in range(5):
        orch1.tick()

    # Save state
    state_json = orch1.save_state()

    # Load into new orchestrator
    orch2 = Orchestrator.load_state(simple_config, state_json)

    # Should be restored at same tick
    assert orch2.current_tick() == 5
    assert orch2.current_day() == 0


def test_load_state_rejects_config_mismatch(simple_config):
    """FFI: load_state() should reject mismatched config."""
    # Create and save
    orch1 = Orchestrator.new(simple_config)
    orch1.tick()
    state_json = orch1.save_state()

    # Try to load with different config
    different_config = simple_config.copy()
    different_config["rng_seed"] = 99999  # Different seed!

    with pytest.raises(Exception, match="[Cc]onfig.*[Mm]ismatch"):
        Orchestrator.load_state(different_config, state_json)


def test_load_state_rejects_corrupted_json(simple_config):
    """FFI: load_state() should reject invalid JSON."""
    with pytest.raises(Exception):
        Orchestrator.load_state(simple_config, "{not valid json}")

    with pytest.raises(Exception):
        Orchestrator.load_state(simple_config, '{"missing": "required_fields"}')


# =============================================================================
# Test 3: Determinism after restore
# =============================================================================


def test_determinism_after_restore(config_with_transactions):
    """FFI: CRITICAL - Restored orchestrator must be deterministic."""
    # Original: run 10 ticks, save, continue 10 more
    orch1 = Orchestrator.new(config_with_transactions)

    results_1a = [orch1.tick() for _ in range(10)]
    state_json = orch1.save_state()
    results_1b = [orch1.tick() for _ in range(10)]

    # Restored: load at tick 10, run 10 more
    orch2 = Orchestrator.load_state(config_with_transactions, state_json)
    results_2b = [orch2.tick() for _ in range(10)]

    # Results after restore MUST match results from original
    assert len(results_1b) == len(results_2b)

    for i, (r1, r2) in enumerate(zip(results_1b, results_2b)):
        assert r1["tick"] == r2["tick"], f"Tick {i}: tick numbers differ"
        assert r1["num_arrivals"] == r2["num_arrivals"], f"Tick {i}: arrivals differ"
        assert r1["num_settlements"] == r2["num_settlements"], f"Tick {i}: settlements differ"
        assert r1["num_lsm_releases"] == r2["num_lsm_releases"], f"Tick {i}: LSM releases differ"


def test_save_load_roundtrip_preserves_exact_state(simple_config):
    """FFI: Multiple save/load cycles should preserve state."""
    # Original
    orch1 = Orchestrator.new(simple_config)
    for _ in range(7):
        orch1.tick()

    state1 = orch1.save_state()

    # First roundtrip
    orch2 = Orchestrator.load_state(simple_config, state1)
    state2 = orch2.save_state()

    # Second roundtrip
    orch3 = Orchestrator.load_state(simple_config, state2)
    state3 = orch3.save_state()

    # States should be identical (JSON may differ in whitespace, so parse and compare)
    dict1 = json.loads(state1)
    dict2 = json.loads(state2)
    dict3 = json.loads(state3)

    assert dict1 == dict2, "First roundtrip changed state"
    assert dict2 == dict3, "Second roundtrip changed state"


# =============================================================================
# Test 4: Balance conservation
# =============================================================================


def test_balance_conservation_preserved(config_with_transactions):
    """FFI: Total system balance must be conserved across save/load."""
    orch1 = Orchestrator.new(config_with_transactions)

    # Calculate initial total balance
    initial_total = sum(
        orch1.get_agent_balance(agent_id)
        for agent_id in orch1.get_agent_ids()
    )

    # Run 20 ticks
    for _ in range(20):
        orch1.tick()

    # Save and load
    state_json = orch1.save_state()
    orch2 = Orchestrator.load_state(config_with_transactions, state_json)

    # Total balance should still equal initial
    restored_total = sum(
        orch2.get_agent_balance(agent_id)
        for agent_id in orch2.get_agent_ids()
    )

    assert restored_total == initial_total, \
        f"Balance conservation violated: {initial_total} → {restored_total}"


# =============================================================================
# Test 5: get_checkpoint_info() (helper for diagnostics)
# =============================================================================


def test_get_checkpoint_info_returns_metadata(simple_config):
    """FFI: get_checkpoint_info() should return checkpoint metadata."""
    orch = Orchestrator.new(simple_config)
    for _ in range(15):
        orch.tick()

    state_json = orch.save_state()

    # Get info without deserializing entire state
    info = Orchestrator.get_checkpoint_info(state_json)

    assert isinstance(info, dict)
    assert info["current_tick"] == 15
    assert info["current_day"] == 0
    assert "rng_seed" in info
    assert "config_hash" in info
    assert "num_agents" in info
    assert "num_transactions" in info


def test_get_checkpoint_info_handles_invalid_json():
    """FFI: get_checkpoint_info() should handle invalid JSON gracefully."""
    with pytest.raises(Exception):
        Orchestrator.get_checkpoint_info("{invalid json")

    with pytest.raises(Exception):
        Orchestrator.get_checkpoint_info('{"missing": "fields"}')
