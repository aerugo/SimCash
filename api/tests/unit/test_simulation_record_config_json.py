"""Unit tests for SimulationRecord config_json field.

Tests the addition of config_json field to SimulationRecord model
for storing complete simulation configuration.
"""

import json
from datetime import datetime

import pytest
from payment_simulator.persistence.models import SimulationRecord, SimulationStatus


def test_simulation_record_accepts_config_json():
    """Test that SimulationRecord can store config_json."""
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 5,
            "rng_seed": 42,
        },
        "agents": [
            {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 500000},
            {"id": "BANK_B", "opening_balance": 2000000, "unsecured_cap": 0},
        ],
    }

    record = SimulationRecord(
        simulation_id="sim-001",
        config_file="test.yaml",
        config_hash="abc123",
        rng_seed=42,
        ticks_per_day=100,
        num_days=5,
        num_agents=2,
        config_json=json.dumps(config),
        status=SimulationStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    assert record.config_json is not None
    assert isinstance(record.config_json, str)

    # Verify it can be parsed back
    parsed = json.loads(record.config_json)
    assert len(parsed["agents"]) == 2
    assert parsed["agents"][0]["id"] == "BANK_A"


def test_simulation_record_config_json_optional():
    """Test that config_json is optional (backwards compatibility)."""
    record = SimulationRecord(
        simulation_id="sim-002",
        config_file="test.yaml",
        config_hash="abc123",
        rng_seed=42,
        ticks_per_day=100,
        num_days=5,
        num_agents=2,
        # config_json not provided
        status=SimulationStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    assert record.config_json is None


def test_simulation_record_serializes_correctly():
    """Test that SimulationRecord with config_json serializes to dict."""
    config = {
        "simulation": {"ticks_per_day": 100},
        "agents": [{"id": "BANK_A"}],
    }

    record = SimulationRecord(
        simulation_id="sim-003",
        config_file="test.yaml",
        config_hash="abc123",
        rng_seed=42,
        ticks_per_day=100,
        num_days=5,
        num_agents=1,
        config_json=json.dumps(config),
        status=SimulationStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    # Convert to dict (as would happen in database writes)
    record_dict = record.model_dump()

    assert "config_json" in record_dict
    assert record_dict["config_json"] is not None


def test_simulation_record_with_large_config():
    """Test that SimulationRecord handles large config JSON (12-bank scenario)."""
    # Simulate a large config like 12_bank_4_policy_comparison.yaml
    agents = []
    for i in range(12):
        agents.append(
            {
                "id": f"BANK_{i}",
                "opening_balance": 10000000 + (i * 500000),
                "unsecured_cap": 5000000,
                "policy": {"type": "FromJson", "json_path": "policy.json"},
                "arrival_config": {
                    "rate_per_tick": 0.5 + (i * 0.05),
                    "amount_distribution": {
                        "type": "LogNormal",
                        "mean": 11.0,
                        "std_dev": 1.0,
                    },
                    "counterparty_weights": {
                        f"BANK_{j}": 1.0 / 11 for j in range(12) if j != i
                    },
                },
            }
        )

    config = {
        "simulation": {"ticks_per_day": 200, "num_days": 5, "rng_seed": 42},
        "agents": agents,
        "lsm_config": {"enable_bilateral": True, "enable_cycles": True},
        "cost_rates": {
            "overdraft_bps_per_tick": 0.5,
            "delay_cost_per_tick_per_cent": 0.0001,
        },
    }

    config_json = json.dumps(config)

    # Should handle large config
    record = SimulationRecord(
        simulation_id="sim-large",
        config_file="12_bank_scenario.yaml",
        config_hash="large123",
        rng_seed=42,
        ticks_per_day=200,
        num_days=5,
        num_agents=12,
        config_json=config_json,
        status=SimulationStatus.COMPLETED,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    assert record.config_json is not None
    assert len(record.config_json) > 1000  # Should be substantial

    # Verify parseable
    parsed = json.loads(record.config_json)
    assert len(parsed["agents"]) == 12
