"""Test that persistence layer captures unsecured_cap for replay."""
import pytest
from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.persistence import PersistenceManager


class TestPersistenceManagerCapturesCreditLimit:
    """Test that PersistenceManager captures unsecured_cap during full replay."""

    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator with agents having credit limits."""
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1000000,
                    "unsecured_cap": 500000,  # Important: credit limit set
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2000000,
                    "unsecured_cap": 1000000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }
        return Orchestrator.new(config)

    def test_persistence_manager_buffers_unsecured_cap(self, orchestrator):
        """PersistenceManager should buffer unsecured_cap in agent_states."""
        # Mock db_manager
        class MockDBManager:
            pass

        persistence = PersistenceManager(
            db_manager=MockDBManager(),
            sim_id="test_sim",
            full_replay=True,
        )

        # Execute one tick
        orchestrator.tick()
        persistence.on_tick_complete(tick=0, orch=orchestrator)

        # Check buffered agent states
        agent_states = persistence.replay_buffers["agent_states"]
        assert len(agent_states) > 0, "Should have buffered agent states"

        # Find BANK_A state
        bank_a_state = [s for s in agent_states if s["agent_id"] == "BANK_A"][0]

        # CRITICAL: unsecured_cap must be in the buffered data
        assert "unsecured_cap" in bank_a_state, \
            "PersistenceManager must buffer unsecured_cap for replay"
        assert bank_a_state["unsecured_cap"] == 500000

    def test_all_agents_unsecured_caps_buffered(self, orchestrator):
        """All agents' credit limits should be buffered correctly."""
        class MockDBManager:
            pass

        persistence = PersistenceManager(
            db_manager=MockDBManager(),
            sim_id="test_sim_all",
            full_replay=True,
        )

        orchestrator.tick()
        persistence.on_tick_complete(tick=0, orch=orchestrator)

        agent_states = persistence.replay_buffers["agent_states"]

        # Check both agents
        bank_a = [s for s in agent_states if s["agent_id"] == "BANK_A"][0]
        bank_b = [s for s in agent_states if s["agent_id"] == "BANK_B"][0]

        assert "unsecured_cap" in bank_a
        assert bank_a["unsecured_cap"] == 500000
        assert "unsecured_cap" in bank_b
        assert bank_b["unsecured_cap"] == 1000000


class TestDatabaseStateProviderWithPersistedCreditLimit:
    """Test that DatabaseStateProvider can read persisted unsecured_cap."""

    def test_database_state_provider_reads_unsecured_cap(self):
        """DatabaseStateProvider should correctly read unsecured_cap from persisted data."""
        from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

        # Mock database data with unsecured_cap
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": 1000000,
                    "unsecured_cap": 500000,  # This comes from database
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }

        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        # Should be able to get credit limit
        unsecured_cap = provider.get_agent_unsecured_cap("BANK_A")
        assert unsecured_cap == 500000
