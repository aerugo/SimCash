"""StateProvider Contract Tests.

These tests ensure that both OrchestratorStateProvider (live FFI) and
DatabaseStateProvider (replay) return identical results for the same
simulation state.

This is critical for maintaining replay identity - if the two providers
return different values, the display output will diverge even though
the display logic is shared.
"""

import pytest
import tempfile
import os
from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.state_provider import (
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator.cli.execution.persistence import PersistenceManager
from payment_simulator.persistence.connection import DatabaseManager


class TestStateProviderContract:
    """Test that StateProvider implementations return identical results."""

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

    def test_get_agent_balance_contract(self, temp_db):
        """TEST: Both providers must return identical agent balances.

        This is a unit test that verifies the StateProvider contract.
        We manually construct the state and verify both providers return
        the same value.
        """
        # Create minimal simulation
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 5,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 200000,
                    "credit_limit": 75000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run simulation
        orch = Orchestrator.new(config)

        # Submit a transaction to change balances
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=10000,
            deadline_tick=10,
            priority=5,
            divisible=False,
        )

        # Tick once to process
        orch.tick()

        # Get current state via OrchestratorStateProvider
        live_provider = OrchestratorStateProvider(orch)
        live_balance_a = live_provider.get_agent_balance("BANK_A")
        live_balance_b = live_provider.get_agent_balance("BANK_B")

        # Manually construct DatabaseStateProvider with same state
        # (simulating what would be loaded from database)
        agent_states = {
            "BANK_A": {
                "balance": live_balance_a,  # Use the actual value from live
                "credit_limit": 50000,
                "collateral_posted": 0,
                "liquidity_cost": 0,
                "delay_cost": 0,
                "collateral_cost": 0,
                "penalty_cost": 0,
                "split_friction_cost": 0,
            },
            "BANK_B": {
                "balance": live_balance_b,  # Use the actual value from live
                "credit_limit": 75000,
                "collateral_posted": 0,
                "liquidity_cost": 0,
                "delay_cost": 0,
                "collateral_cost": 0,
                "penalty_cost": 0,
                "split_friction_cost": 0,
            },
        }

        db_manager = DatabaseManager(temp_db)
        db_provider = DatabaseStateProvider(
            conn=db_manager.conn,
            simulation_id="test-sim-001",
            tick=0,
            tx_cache={},
            agent_states=agent_states,
            queue_snapshots={},
        )

        db_balance_a = db_provider.get_agent_balance("BANK_A")
        db_balance_b = db_provider.get_agent_balance("BANK_B")

        # CRITICAL ASSERTION: Balances must match exactly
        # Since we constructed agent_states from live values, this verifies
        # that DatabaseStateProvider correctly returns what was stored
        assert live_balance_a == db_balance_a, \
            f"BANK_A balance mismatch: live={live_balance_a}, db={db_balance_a}"
        assert live_balance_b == db_balance_b, \
            f"BANK_B balance mismatch: live={live_balance_b}, db={db_balance_b}"

        # Also verify the balances actually changed
        assert live_balance_a == 90000, \
            f"BANK_A should have 90000 after sending 10000, got {live_balance_a}"
        assert live_balance_b == 210000, \
            f"BANK_B should have 210000 after receiving 10000, got {live_balance_b}"

    def test_get_agent_credit_limit_contract(self, temp_db):
        """TEST: Both providers must return identical credit limits."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 5,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100000,
                    "credit_limit": 50000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Get from live provider
        live_provider = OrchestratorStateProvider(orch)
        live_credit_limit = live_provider.get_agent_credit_limit("BANK_A")

        # Manually construct DatabaseStateProvider with same state
        agent_states = {
            "BANK_A": {
                "balance": 100000,
                "credit_limit": 50000,  # From config
                "collateral_posted": 0,
                "liquidity_cost": 0,
                "delay_cost": 0,
                "collateral_cost": 0,
                "penalty_cost": 0,
                "split_friction_cost": 0,
            }
        }

        db_manager = DatabaseManager(temp_db)
        db_provider = DatabaseStateProvider(
            conn=db_manager.conn,
            simulation_id="test-sim-002",
            tick=0,
            tx_cache={},
            agent_states=agent_states,
            queue_snapshots={},
        )

        db_credit_limit = db_provider.get_agent_credit_limit("BANK_A")

        # CRITICAL ASSERTION: Credit limits must match
        assert live_credit_limit == db_credit_limit, \
            f"Credit limit mismatch: live={live_credit_limit}, db={db_credit_limit}"

        # Also verify it's the expected value from config
        assert live_credit_limit == 50000, \
            f"Expected credit limit 50000, got {live_credit_limit}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
