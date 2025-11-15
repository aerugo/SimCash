"""Integration tests for diagnostic API with config_json.

Tests that the GET /simulations/{sim_id} endpoint correctly parses
and returns full configuration including agents from config_json.
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from payment_simulator.api.main import app, manager
from payment_simulator.persistence.connection import DatabaseManager


def test_get_simulation_metadata_with_config_json():
    """Test that API endpoint returns full config with agents when config_json is present."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Set database manager in app
        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        # Create config with agents
        config = {
            "simulation": {"ticks_per_day": 200, "num_days": 5, "rng_seed": 42},
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10000000,
                    "unsecured_cap": 5000000,
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 20000000,
                    "unsecured_cap": 0,
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 15000000,
                    "unsecured_cap": 2500000,
                },
            ],
        }

        sim_id = "sim-test-001"
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "test.yaml",
                "abc123",
                42,
                200,
                5,
                3,
                json.dumps(config),
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Query API
        client = TestClient(app)
        response = client.get(f"/simulations/{sim_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify full config returned
        assert "config" in data
        assert "agents" in data["config"]

        # Critical: agents array should NOT be empty!
        assert len(data["config"]["agents"]) == 3

        # Verify agent details
        agents = data["config"]["agents"]
        assert agents[0]["id"] == "BANK_A"
        assert agents[0]["opening_balance"] == 10000000
        assert agents[0]["credit_limit"] == 5000000

        assert agents[1]["id"] == "BANK_B"
        assert agents[1]["opening_balance"] == 20000000

        assert agents[2]["id"] == "BANK_C"


def test_get_simulation_metadata_without_config_json_fallback():
    """Test that API gracefully handles missing config_json (backwards compatibility)."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        # Insert simulation WITHOUT config_json
        sim_id = "sim-old-001"
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "old.yaml",
                "old123",
                99,
                100,
                3,
                2,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Query API
        client = TestClient(app)
        response = client.get(f"/simulations/{sim_id}")

        assert response.status_code == 200
        data = response.json()

        # Should still return config, but agents will be empty
        assert "config" in data
        assert "agents" in data["config"]
        assert len(data["config"]["agents"]) == 0  # Empty for old simulations

        # Basic fields should still be present
        assert data["config"]["rng_seed"] == 99
        assert data["config"]["ticks_per_day"] == 100


def test_get_simulation_metadata_with_12_bank_config():
    """Test with large config similar to 12_bank_4_policy_comparison.yaml."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        # Create 12-bank config
        agents = [
            {
                "id": f"BANK_{i}",
                "opening_balance": 10000000 + (i * 1000000),
                "unsecured_cap": 5000000,
            }
            for i in range(12)
        ]

        config = {
            "simulation": {"ticks_per_day": 200, "num_days": 5, "rng_seed": 42},
            "agents": agents,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": True},
        }

        sim_id = "sim-12-bank"
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "12_bank.yaml",
                "bank123",
                42,
                200,
                5,
                12,
                json.dumps(config),
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Query API
        client = TestClient(app)
        response = client.get(f"/simulations/{sim_id}")

        assert response.status_code == 200
        data = response.json()

        # Should have all 12 agents
        assert len(data["config"]["agents"]) == 12

        # Verify first and last
        assert data["config"]["agents"][0]["id"] == "BANK_0"
        assert data["config"]["agents"][11]["id"] == "BANK_11"

        # Verify LSM config preserved
        assert "lsm_config" in data["config"]
        assert data["config"]["lsm_config"]["enable_bilateral"] is True


def test_get_agent_list_from_database():
    """Test that GET /simulations/{sim_id}/agents returns agents from database."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        sim_id = "sim-agents-test"

        # Insert simulation
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "test.yaml",
                "abc",
                42,
                100,
                1,
                2,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Insert daily agent metrics for 2 agents (including collateral fields)
        conn.execute(
            """
            INSERT INTO daily_agent_metrics (
                simulation_id, agent_id, day,
                opening_balance, closing_balance, min_balance, max_balance,
                credit_limit, peak_overdraft,
                opening_posted_collateral, closing_posted_collateral, peak_posted_collateral,
                collateral_capacity, num_collateral_posts, num_collateral_withdrawals,
                num_arrivals, num_sent, num_received, num_settled, num_dropped,
                queue1_peak_size, queue1_eod_size,
                liquidity_cost, delay_cost, collateral_cost,
                split_friction_cost, deadline_penalty_cost, total_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "BANK_A",
                0,
                10000000,
                9500000,
                9000000,
                10500000,
                5000000,
                -1000000,
                0,  # opening_posted_collateral
                0,  # closing_posted_collateral
                0,  # peak_posted_collateral
                50000000,  # collateral_capacity (10x credit_limit)
                0,  # num_collateral_posts
                0,  # num_collateral_withdrawals
                50,
                25,
                25,
                48,
                2,
                5,
                0,
                10000,
                5000,
                2000,
                500,
                1000,
                18500,
            ],
        )

        conn.execute(
            """
            INSERT INTO daily_agent_metrics (
                simulation_id, agent_id, day,
                opening_balance, closing_balance, min_balance, max_balance,
                credit_limit, peak_overdraft,
                opening_posted_collateral, closing_posted_collateral, peak_posted_collateral,
                collateral_capacity, num_collateral_posts, num_collateral_withdrawals,
                num_arrivals, num_sent, num_received, num_settled, num_dropped,
                queue1_peak_size, queue1_eod_size,
                liquidity_cost, delay_cost, collateral_cost,
                split_friction_cost, deadline_penalty_cost, total_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "BANK_B",
                0,
                20000000,
                19800000,
                19500000,
                20200000,
                0,
                0,
                0,  # opening_posted_collateral
                0,  # closing_posted_collateral
                0,  # peak_posted_collateral
                0,  # collateral_capacity (0 because credit_limit is 0)
                0,  # num_collateral_posts
                0,  # num_collateral_withdrawals
                45,
                20,
                25,
                44,
                1,
                3,
                0,
                0,
                3000,
                0,
                200,
                500,
                3700,
            ],
        )

        # Query API
        client = TestClient(app)
        response = client.get(f"/simulations/{sim_id}/agents")

        assert response.status_code == 200
        data = response.json()

        # Should return 2 agents
        assert "agents" in data
        assert len(data["agents"]) == 2

        # Verify agent data aggregated from metrics
        agents = {agent["agent_id"]: agent for agent in data["agents"]}

        assert "BANK_A" in agents
        assert agents["BANK_A"]["total_sent"] == 25
        assert agents["BANK_A"]["total_received"] == 25
        assert agents["BANK_A"]["total_settled"] == 48
        assert agents["BANK_A"]["total_cost_cents"] == 18500

        assert "BANK_B" in agents
        assert agents["BANK_B"]["total_sent"] == 20
        assert agents["BANK_B"]["total_cost_cents"] == 3700
