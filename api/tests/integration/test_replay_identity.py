"""Test that replay produces identical output to original simulation run.

This is a CRITICAL INVARIANT: Replay must be byte-for-byte identical to the original run.
"""

import pytest
import tempfile
import os
from pathlib import Path
from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.writers import (
    write_tick_agent_states_batch,
)
from payment_simulator.cli.execution.state_provider import (
    DatabaseStateProvider,
    OrchestratorStateProvider,
)
import duckdb


class TestReplayIdentity:
    """Test replay identity - replay must match original run exactly."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(db_path)  # DuckDB will create its own
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
        wal_path = db_path + ".wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)

    def test_agent_state_persistence_and_retrieval(self, temp_db):
        """
        Test that agent state is correctly persisted and retrieved.

        This test reproduces the bug where:
        - Simulation shows: CORRESPONDENT_HUB 189% credit utilization, balance -$41,593.35
        - Replay shows: CORRESPONDENT_HUB 97% credit utilization, balance $0.00

        The bug is that the replay is not loading the correct data from the database.
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,   # $5,000
                    "unsecured_cap": 200000,      # $2,000
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "unsecured_cap": 200000,
                    "policy": {"type": "Fifo"},
                },
            ],
            "lsm_config": {
                "enable_bilateral": True,
                "enable_cycles": True,
                "max_cycle_length": 4,
                "max_cycles_per_tick": 10,
            },
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Post collateral for BANK_A
        orch.post_collateral("BANK_A", 300000)  # $3,000 collateral

        # Create transactions to drain balance
        orch.submit_transaction("BANK_A", "BANK_B", 800000, 50, 5, False)
        orch.submit_transaction("BANK_B", "BANK_A", 700000, 50, 5, False)

        # Run some ticks
        for _ in range(10):
            orch.tick()

        # Capture state from live simulation at current tick
        current_tick = orch.current_tick()
        live_balance_a = orch.get_agent_balance("BANK_A")
        live_credit_limit_a = orch.get_agent_credit_limit("BANK_A")
        live_collateral_a = orch.get_agent_collateral_posted("BANK_A")
        live_allowed_overdraft_a = orch.get_agent_allowed_overdraft_limit("BANK_A")

        # Persist agent states to database
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()

        # Collect agent states with all required fields
        agent_state_records = []
        for agent_id in ["BANK_A", "BANK_B"]:
            balance = orch.get_agent_balance(agent_id)
            credit_limit = orch.get_agent_credit_limit(agent_id)
            collateral = orch.get_agent_collateral_posted(agent_id)
            costs = orch.get_agent_accumulated_costs(agent_id)

            agent_state_records.append({
                "simulation_id": "test_sim",
                "tick": current_tick,
                "day": 0,  # Required field
                "agent_id": agent_id,
                "balance": balance,
                "balance_change": 0,  # Required field (could calculate but not needed for test)
                "unsecured_cap": credit_limit,
                "posted_collateral": collateral,
                "liquidity_cost": costs.get("liquidity_cost", 0),
                "delay_cost": costs.get("delay_cost", 0),
                "collateral_cost": costs.get("collateral_cost", 0),
                "penalty_cost": costs.get("penalty_cost", 0),
                "split_friction_cost": costs.get("split_friction_cost", 0),
                "liquidity_cost_delta": 0,  # Required field
                "delay_cost_delta": 0,  # Required field
                "collateral_cost_delta": 0,  # Required field
                "penalty_cost_delta": 0,  # Required field
                "split_friction_cost_delta": 0,  # Required field
            })

        # Write to database
        write_tick_agent_states_batch(db_manager.conn, agent_state_records)
        db_manager.close()

        # Now load state from database for replay
        replay_conn = duckdb.connect(temp_db)

        # Load agent state from database
        agent_state_query = """
            SELECT *
            FROM tick_agent_states
            WHERE simulation_id = 'test_sim'
            AND tick = ?
            AND agent_id = 'BANK_A'
        """
        result = replay_conn.execute(agent_state_query, [current_tick]).fetchone()

        assert result is not None, "No agent state found in database!"

        columns = [desc[0] for desc in replay_conn.description]
        row_dict = dict(zip(columns, result))

        replay_balance_a = row_dict.get("balance", None)
        replay_credit_limit_a = row_dict.get("credit_limit", None)
        replay_collateral_a = row_dict.get("posted_collateral", None)

        # Calculate replay allowed overdraft (same formula as live)
        if replay_collateral_a is not None and replay_credit_limit_a is not None:
            collateral_haircut = 0.02
            collateral_backing = int(replay_collateral_a * (1.0 - collateral_haircut))
            replay_allowed_overdraft_a = replay_credit_limit_a + collateral_backing
        else:
            replay_allowed_overdraft_a = None

        replay_conn.close()

        # ASSERTIONS: Database must contain correct data
        print(f"\nDEBUG: Live balance: {live_balance_a}, Replay balance: {replay_balance_a}")
        print(f"DEBUG: Live credit limit: {live_credit_limit_a}, Replay credit limit: {replay_credit_limit_a}")
        print(f"DEBUG: Live collateral: {live_collateral_a}, Replay collateral: {replay_collateral_a}")
        print(f"DEBUG: Live allowed overdraft: {live_allowed_overdraft_a}, Replay allowed overdraft: {replay_allowed_overdraft_a}")

        assert replay_balance_a == live_balance_a, \
            f"Balance mismatch: live={live_balance_a}, replay={replay_balance_a}"

        assert replay_credit_limit_a == live_credit_limit_a, \
            f"Credit limit mismatch: live={live_credit_limit_a}, replay={replay_credit_limit_a}"

        assert replay_collateral_a == live_collateral_a, \
            f"Collateral mismatch: live={live_collateral_a}, replay={replay_collateral_a}"

        assert replay_allowed_overdraft_a == live_allowed_overdraft_a, \
            f"Allowed overdraft mismatch: live={live_allowed_overdraft_a}, replay={replay_allowed_overdraft_a}"

    def test_database_state_provider_returns_correct_data(self, temp_db):
        """
        DatabaseStateProvider must return correct agent state from database.

        This tests the DatabaseStateProvider directly to ensure it loads data correctly.
        """
        config = {
            "rng_seed": 42,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,  # $10,000
                    "unsecured_cap": 500000,      # $5,000
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Post collateral
        orch.post_collateral("BANK_A", 200000)  # $2,000

        # Run a few ticks
        for _ in range(5):
            orch.tick()

        current_tick = orch.current_tick()
        live_balance = orch.get_agent_balance("BANK_A")
        live_credit_limit = orch.get_agent_credit_limit("BANK_A")
        live_collateral = orch.get_agent_collateral_posted("BANK_A")

        # Persist agent states to database
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()

        agent_state_records = [{
            "simulation_id": "test_sim",
            "tick": current_tick,
            "day": 0,
            "agent_id": "BANK_A",
            "balance": live_balance,
            "balance_change": 0,
            "unsecured_cap": live_credit_limit,
            "posted_collateral": live_collateral,
            "liquidity_cost": 0,
            "delay_cost": 0,
            "collateral_cost": 0,
            "penalty_cost": 0,
            "split_friction_cost": 0,
            "liquidity_cost_delta": 0,
            "delay_cost_delta": 0,
            "collateral_cost_delta": 0,
            "penalty_cost_delta": 0,
            "split_friction_cost_delta": 0,
        }]

        write_tick_agent_states_batch(db_manager.conn, agent_state_records)
        db_manager.close()

        # Now test DatabaseStateProvider
        replay_conn = duckdb.connect(temp_db)

        # Load agent states for tick
        agent_states_query = """
            SELECT *
            FROM tick_agent_states
            WHERE simulation_id = 'test_sim'
            AND tick = ?
        """
        rows = replay_conn.execute(agent_states_query, [current_tick]).fetchall()
        columns = [desc[0] for desc in replay_conn.description]

        agent_states_dict = {}
        for row in rows:
            row_dict = dict(zip(columns, row))
            agent_id = row_dict["agent_id"]
            agent_states_dict[agent_id] = row_dict

        # Create DatabaseStateProvider
        provider = DatabaseStateProvider(
            conn=replay_conn,
            simulation_id="test_sim",
            tick=current_tick,
            tx_cache={},
            agent_states=agent_states_dict,
            queue_snapshots={},
        )

        # Test that provider returns correct data
        provider_balance = provider.get_agent_balance("BANK_A")
        provider_credit_limit = provider.get_agent_credit_limit("BANK_A")
        provider_collateral = provider.get_agent_collateral_posted("BANK_A")

        replay_conn.close()

        # Assertions
        assert provider_balance == live_balance, \
            f"Provider balance mismatch: live={live_balance}, provider={provider_balance}"

        assert provider_credit_limit == live_credit_limit, \
            f"Provider credit limit mismatch: live={live_credit_limit}, provider={provider_credit_limit}"

        assert provider_collateral == live_collateral, \
            f"Provider collateral mismatch: live={live_collateral}, provider={provider_collateral}"
