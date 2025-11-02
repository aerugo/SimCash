"""Integration tests for config_json persistence.

Tests that complete configuration is stored and retrieved correctly
from the database, enabling the diagnostic frontend to display full
agent details and configuration.
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from payment_simulator.persistence.connection import DatabaseManager


def test_persist_simulation_stores_config_json():
    """Test that simulation metadata includes config_json."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        conn = db_manager.get_connection()

        # Create a config with agents
        config_dict = {
            "simulation": {
                "ticks_per_day": 200,
                "num_days": 5,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10000000,
                    "credit_limit": 5000000,
                    "policy": {"type": "FromJson", "json_path": "policy.json"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 20000000,
                    "credit_limit": 0,
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
            },
        }

        config_json = json.dumps(config_dict)

        # Insert simulation with config_json
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                "sim-001",
                "test.yaml",
                "abc123",
                42,
                200,
                5,
                2,
                config_json,
                "completed",
                datetime.now(),
            ],
        )

        # Query it back
        row = conn.execute(
            "SELECT config_json FROM simulations WHERE simulation_id = ?",
            ["sim-001"],
        ).fetchone()

        assert row is not None
        assert row[0] is not None

        # Verify it parses correctly
        stored_config = json.loads(row[0])
        assert "agents" in stored_config
        assert len(stored_config["agents"]) == 2
        assert stored_config["agents"][0]["id"] == "BANK_A"
        assert stored_config["agents"][0]["opening_balance"] == 10000000
        assert stored_config["agents"][1]["id"] == "BANK_B"


def test_config_json_handles_large_configs():
    """Test that config_json can store large configurations like 12-bank scenario."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        conn = db_manager.get_connection()

        # Create a large config similar to 12_bank_4_policy_comparison.yaml
        agents = []
        for i in range(12):
            agents.append(
                {
                    "id": f"BANK_{i}",
                    "opening_balance": 10000000 + (i * 500000),
                    "credit_limit": 5000000,
                    "policy": {"type": "FromJson", "json_path": f"policy_{i}.json"},
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

        config_dict = {
            "simulation": {"ticks_per_day": 200, "num_days": 5, "rng_seed": 42},
            "agents": agents,
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
                "max_cycle_length": 5,
            },
            "cost_rates": {
                "overdraft_bps_per_tick": 0.5,
                "delay_cost_per_tick_per_cent": 0.0001,
                "collateral_cost_per_tick_bps": 0.0003,
            },
        }

        config_json = json.dumps(config_dict)

        # Should be substantial
        assert len(config_json) > 5000

        # Insert
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                "sim-large",
                "12_bank_scenario.yaml",
                "large123",
                42,
                200,
                5,
                12,
                config_json,
                "completed",
                datetime.now(),
            ],
        )

        # Query and verify
        row = conn.execute(
            "SELECT config_json FROM simulations WHERE simulation_id = ?",
            ["sim-large"],
        ).fetchone()

        stored_config = json.loads(row[0])
        assert len(stored_config["agents"]) == 12
        assert stored_config["agents"][0]["id"] == "BANK_0"
        assert stored_config["agents"][11]["id"] == "BANK_11"
        assert "lsm_config" in stored_config


def test_backwards_compatibility_without_config_json():
    """Test that simulations without config_json still work (backwards compatibility)."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        conn = db_manager.get_connection()

        # Insert simulation WITHOUT config_json (old format)
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                "sim-old",
                "old.yaml",
                "old123",
                99,
                100,
                3,
                2,
                "completed",
                datetime.now(),
            ],
        )

        # Should still be queryable
        row = conn.execute(
            "SELECT simulation_id, config_json FROM simulations WHERE simulation_id = ?",
            ["sim-old"],
        ).fetchone()

        assert row is not None
        assert row[0] == "sim-old"
        assert row[1] is None  # config_json is NULL for old simulations
