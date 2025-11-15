"""Test configuration loading and validation (TDD - tests written first)."""
import pytest
from pathlib import Path
import tempfile
import yaml


def test_load_simple_config():
    """Test loading a minimal valid configuration."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        # Verify structure
        assert config.simulation.ticks_per_day == 100
        assert config.simulation.num_days == 1
        assert config.simulation.rng_seed == 12345

        assert len(config.agents) == 1
        assert config.agents[0].id == "BANK_A"
        assert config.agents[0].opening_balance == 1_000_000
        assert config.agents[0].credit_limit == 0
    finally:
        Path(config_path).unlink()


def test_config_validation_missing_required_fields():
    """Test that validation catches missing required fields."""
    from payment_simulator.config import load_config, ValidationError

    # Missing agents
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        with pytest.raises((ValidationError, ValueError, KeyError)):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_config_validation_invalid_values():
    """Test that validation catches invalid values."""
    from payment_simulator.config import load_config, ValidationError

    # Invalid ticks_per_day (must be > 0)
    config_dict = {
        "simulation": {
            "ticks_per_day": 0,  # Invalid!
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        with pytest.raises((ValidationError, ValueError)):
            load_config(config_path)
    finally:
        Path(config_path).unlink()


def test_config_with_arrival_generation():
    """Test loading config with arrival generation."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 100_000,
                        "std_dev": 20_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": False,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        # Verify arrival config loaded
        assert config.agents[0].arrival_config is not None
        assert config.agents[0].arrival_config.rate_per_tick == 0.5
        assert config.agents[0].arrival_config.amount_distribution.type == "Normal"
        assert config.agents[0].arrival_config.amount_distribution.mean == 100_000
    finally:
        Path(config_path).unlink()


def test_config_with_different_policies():
    """Test loading config with various policy types."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "Deadline",
                    "urgency_threshold": 10,
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {
                    "type": "LiquidityAware",
                    "target_buffer": 500_000,
                    "urgency_threshold": 5,
                },
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        assert len(config.agents) == 3
        assert config.agents[0].policy.type == "Fifo"
        assert config.agents[1].policy.type == "Deadline"
        assert config.agents[2].policy.type == "LiquidityAware"
    finally:
        Path(config_path).unlink()


def test_config_to_ffi_dict():
    """Test converting Pydantic config to FFI-compatible dict."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        # Convert to FFI dict
        ffi_dict = config.to_ffi_dict()

        # Verify structure matches what FFI expects
        assert "ticks_per_day" in ffi_dict
        assert "num_days" in ffi_dict
        assert "rng_seed" in ffi_dict
        assert "agent_configs" in ffi_dict

        assert ffi_dict["ticks_per_day"] == 100
        assert len(ffi_dict["agent_configs"]) == 1
        assert ffi_dict["agent_configs"][0]["id"] == "BANK_A"
    finally:
        Path(config_path).unlink()


def test_config_with_cost_rates():
    """Test loading config with cost rate overrides."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "cost_rates": {
            "overdraft_bps_per_tick": 0.002,
            "delay_cost_per_tick_per_cent": 0.0002,
            "eod_penalty_per_transaction": 20_000,
            "deadline_penalty": 75_000,
            "split_friction_cost": 2000,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        # Verify cost rates loaded
        assert config.cost_rates is not None
        assert config.cost_rates.overdraft_bps_per_tick == 0.002
        assert config.cost_rates.eod_penalty_per_transaction == 20_000
    finally:
        Path(config_path).unlink()


def test_config_with_lsm_settings():
    """Test loading config with LSM configuration (updated field names)."""
    from payment_simulator.config import load_config

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": True,
            "max_cycle_length": 5,
            "max_cycles_per_tick": 15,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        config_path = f.name

    try:
        config = load_config(config_path)

        # Verify LSM config loaded with correct field names
        assert config.lsm_config is not None
        assert config.lsm_config.enable_bilateral is True
        assert config.lsm_config.enable_cycles is True
        assert config.lsm_config.max_cycle_length == 5
        assert config.lsm_config.max_cycles_per_tick == 15
    finally:
        Path(config_path).unlink()


def test_lsm_config_ffi_dict_conversion():
    """Test that LSM config correctly converts to FFI dict with proper field names.

    This test verifies the fix for the configuration field name mismatch bug.
    Previously, Python used different field names than Rust expected, causing
    LSM configuration to be silently ignored.
    """
    from payment_simulator.config import SimulationConfig

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "lsm_config": {
            "enable_bilateral": False,  # Non-default value
            "enable_cycles": False,      # Non-default value
            "max_cycle_length": 6,       # Non-default value (default is 4)
            "max_cycles_per_tick": 20,   # Non-default value (default is 10)
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    ffi_dict = config.to_ffi_dict()

    # Verify LSM config exists in FFI dict
    assert "lsm_config" in ffi_dict
    lsm_ffi = ffi_dict["lsm_config"]

    # Verify field names match what Rust FFI expects (not Python names)
    assert "enable_bilateral" in lsm_ffi
    assert "enable_cycles" in lsm_ffi
    assert "max_cycle_length" in lsm_ffi
    assert "max_cycles_per_tick" in lsm_ffi

    # Verify values are correctly passed through
    assert lsm_ffi["enable_bilateral"] is False
    assert lsm_ffi["enable_cycles"] is False
    assert lsm_ffi["max_cycle_length"] == 6
    assert lsm_ffi["max_cycles_per_tick"] == 20

    # Verify old incorrect field names are NOT present
    assert "bilateral_enabled" not in lsm_ffi
    assert "cycle_detection_enabled" not in lsm_ffi
    assert "max_iterations" not in lsm_ffi
    assert "enabled" not in lsm_ffi


def test_lsm_config_defaults():
    """Test that LSM config uses correct defaults when not specified."""
    from payment_simulator.config import SimulationConfig

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        # No lsm_config specified - should use defaults
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    ffi_dict = config.to_ffi_dict()

    # Verify LSM config uses defaults
    lsm_ffi = ffi_dict["lsm_config"]
    assert lsm_ffi["enable_bilateral"] is True    # Default
    assert lsm_ffi["enable_cycles"] is True       # Default
    assert lsm_ffi["max_cycle_length"] == 4       # Default
    assert lsm_ffi["max_cycles_per_tick"] == 10   # Default


def test_config_from_dict_directly():
    """Test creating config from dict without file."""
    from payment_simulator.config import SimulationConfig

    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    # Should be able to create from dict
    config = SimulationConfig.from_dict(config_dict)

    assert config.simulation.ticks_per_day == 100
    assert len(config.agents) == 1
