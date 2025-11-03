"""
Unit tests for PersistenceManager.

Tests the centralized persistence layer that eliminates duplication
across execution modes.
"""

from unittest.mock import MagicMock, Mock, call, patch
import pytest
from payment_simulator.cli.execution.persistence import PersistenceManager


class TestPersistenceManagerInitialization:
    """Tests for PersistenceManager initialization."""

    def test_initialization_without_full_replay(self):
        """PersistenceManager should initialize without full replay mode."""
        db_manager = Mock()

        pm = PersistenceManager(
            db_manager=db_manager,
            sim_id="test-sim",
            full_replay=False
        )

        assert pm.db_manager == db_manager
        assert pm.sim_id == "test-sim"
        assert pm.full_replay is False
        assert pm.replay_buffers is None

    def test_initialization_with_full_replay(self):
        """PersistenceManager should initialize buffers for full replay mode."""
        db_manager = Mock()

        pm = PersistenceManager(
            db_manager=db_manager,
            sim_id="test-sim",
            full_replay=True
        )

        assert pm.full_replay is True
        assert pm.replay_buffers is not None
        assert isinstance(pm.replay_buffers, dict)


class TestPersistInitialSnapshots:
    """Tests for persisting initial policy snapshots."""

    @patch('payment_simulator.cli.execution.persistence.write_policy_snapshots')
    def test_persist_initial_snapshots_writes_policies(self, mock_write):
        """persist_initial_snapshots should write policy snapshots to DB."""
        db_manager = Mock()
        orch = Mock()

        # Mock orchestrator returning policies
        orch.get_agent_policies.return_value = [
            {
                "agent_id": "BANK_A",
                "policy_config": {"type": "Fifo", "param": 1}
            },
            {
                "agent_id": "BANK_B",
                "policy_config": {"type": "Lifo", "param": 2}
            }
        ]

        pm = PersistenceManager(db_manager, "test-sim", False)
        pm.persist_initial_snapshots(orch)

        # Verify write was called
        assert mock_write.called
        call_args = mock_write.call_args[0]
        snapshots = call_args[1]  # Second arg is snapshots list

        assert len(snapshots) == 2
        assert snapshots[0]["simulation_id"] == "test-sim"
        assert snapshots[0]["agent_id"] == "BANK_A"
        assert snapshots[0]["snapshot_day"] == 0
        assert snapshots[0]["snapshot_tick"] == 0

    @patch('payment_simulator.cli.execution.persistence.write_policy_snapshots')
    def test_persist_initial_snapshots_includes_policy_hash(self, mock_write):
        """persist_initial_snapshots should compute policy hash."""
        db_manager = Mock()
        orch = Mock()

        orch.get_agent_policies.return_value = [
            {
                "agent_id": "BANK_A",
                "policy_config": {"type": "Fifo"}
            }
        ]

        pm = PersistenceManager(db_manager, "test-sim", False)
        pm.persist_initial_snapshots(orch)

        snapshots = mock_write.call_args[0][1]
        assert "policy_hash" in snapshots[0]
        assert "policy_json" in snapshots[0]
        assert snapshots[0]["created_by"] == "init"


class TestOnTickComplete:
    """Tests for on_tick_complete hook."""

    def test_on_tick_complete_no_op_without_full_replay(self):
        """on_tick_complete should do nothing if full_replay is False."""
        db_manager = Mock()
        orch = Mock()

        pm = PersistenceManager(db_manager, "test-sim", full_replay=False)

        # Should not raise, should not call orchestrator
        pm.on_tick_complete(0, orch)

        assert not orch.called

    def test_on_tick_complete_buffers_data_with_full_replay(self):
        """on_tick_complete should buffer tick data if full_replay is True."""
        db_manager = Mock()
        orch = Mock()

        # Mock orchestrator methods
        orch.get_tick_events.return_value = [
            {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx1"}
        ]
        orch.get_agent_ids.return_value = ["BANK_A"]
        orch.get_agent_balance.return_value = 1000000
        orch.get_agent_accumulated_costs.return_value = {
            "liquidity_cost": 100,
            "delay_cost": 50,
            "collateral_cost": 0,
            "deadline_penalty": 0,
            "split_friction_cost": 0,
        }
        orch.get_agent_collateral_posted.return_value = 0
        orch.get_agent_queue1_contents.return_value = []
        orch.get_rtgs_queue_contents.return_value = []

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)
        pm.on_tick_complete(0, orch)

        # Verify buffers were populated
        assert len(pm.replay_buffers["policy_decisions"]) == 1
        assert len(pm.replay_buffers["agent_states"]) == 1


class TestOnDayComplete:
    """Tests for on_day_complete hook."""

    @patch('payment_simulator.cli.execution.persistence._persist_day_data')
    def test_on_day_complete_persists_eod_data(self, mock_persist):
        """on_day_complete should always persist EOD data."""
        db_manager = Mock()
        orch = Mock()

        pm = PersistenceManager(db_manager, "test-sim", full_replay=False)
        pm.on_day_complete(0, orch)

        # Verify _persist_day_data was called
        mock_persist.assert_called_once()
        assert mock_persist.call_args[0][0] == orch
        assert mock_persist.call_args[0][1] == db_manager
        assert mock_persist.call_args[0][2] == "test-sim"
        assert mock_persist.call_args[0][3] == 0  # day

    @patch('payment_simulator.cli.execution.persistence._persist_day_data')
    @patch('payment_simulator.cli.execution.persistence.write_policy_decisions_batch')
    @patch('payment_simulator.cli.execution.persistence.write_tick_agent_states_batch')
    @patch('payment_simulator.cli.execution.persistence.write_tick_queue_snapshots_batch')
    def test_on_day_complete_flushes_replay_buffers(
        self, mock_queue, mock_states, mock_policy, mock_persist
    ):
        """on_day_complete should flush replay buffers if full_replay is True."""
        db_manager = Mock()
        db_manager.conn = Mock()
        orch = Mock()

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)

        # Add some buffered data
        pm.replay_buffers["policy_decisions"].append({"simulation_id": "test-sim"})
        pm.replay_buffers["agent_states"].append({"simulation_id": "test-sim"})
        pm.replay_buffers["queue_snapshots"].append({"simulation_id": "test-sim"})

        pm.on_day_complete(0, orch)

        # Verify batch writes were called
        assert mock_policy.called
        assert mock_states.called
        assert mock_queue.called

        # Verify buffers were cleared
        assert len(pm.replay_buffers["policy_decisions"]) == 0
        assert len(pm.replay_buffers["agent_states"]) == 0
        assert len(pm.replay_buffers["queue_snapshots"]) == 0

    @patch('payment_simulator.cli.execution.persistence._persist_day_data')
    @patch('payment_simulator.cli.execution.persistence.write_policy_decisions_batch')
    def test_on_day_complete_skips_empty_buffers(self, mock_policy, mock_persist):
        """on_day_complete should skip batch write if buffers are empty."""
        db_manager = Mock()
        db_manager.conn = Mock()
        orch = Mock()

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)

        # Buffers are empty
        pm.on_day_complete(0, orch)

        # Should not call batch writes with empty data
        assert not mock_policy.called


class TestPersistFinalMetadata:
    """Tests for persist_final_metadata."""

    @patch('payment_simulator.cli.execution.persistence._persist_simulation_metadata')
    def test_persist_final_metadata_calls_helper(self, mock_persist):
        """persist_final_metadata should call _persist_simulation_metadata."""
        db_manager = Mock()
        orch = Mock()

        pm = PersistenceManager(db_manager, "test-sim", full_replay=False)

        pm.persist_final_metadata(
            config_path="config.yaml",
            config_dict={"simulation": {}},
            ffi_dict={"rng_seed": 42},
            agent_ids=["BANK_A"],
            total_arrivals=100,
            total_settlements=95,
            total_costs=5000,
            duration=1.5,
            orch=orch
        )

        # Verify _persist_simulation_metadata was called with correct args
        mock_persist.assert_called_once()
        call_args = mock_persist.call_args[0]

        assert call_args[0] == db_manager
        assert call_args[1] == "test-sim"
        assert call_args[4]["rng_seed"] == 42
        assert call_args[6] == 100  # total_arrivals
        assert call_args[7] == 95   # total_settlements


class TestFullReplayBuffering:
    """Tests for full replay data buffering."""

    def test_buffer_policy_decisions(self):
        """Full replay should buffer policy decision events."""
        db_manager = Mock()
        orch = Mock()

        orch.get_tick_events.return_value = [
            {
                "event_type": "PolicySubmit",
                "agent_id": "BANK_A",
                "tx_id": "tx1",
                "reason": "sufficient_liquidity"
            },
            {
                "event_type": "PolicyHold",
                "agent_id": "BANK_B",
                "tx_id": "tx2",
                "reason": "insufficient_liquidity"
            }
        ]
        orch.get_agent_ids.return_value = []
        orch.get_rtgs_queue_contents.return_value = []  # Mock RTGS queue

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)
        pm.on_tick_complete(5, orch)

        # Verify policy decisions were buffered
        assert len(pm.replay_buffers["policy_decisions"]) == 2
        assert pm.replay_buffers["policy_decisions"][0]["tx_id"] == "tx1"
        assert pm.replay_buffers["policy_decisions"][0]["decision_type"] == "submit"

    def test_buffer_agent_states(self):
        """Full replay should buffer agent state snapshots."""
        db_manager = Mock()
        orch = Mock()

        orch.get_tick_events.return_value = []
        orch.get_agent_ids.return_value = ["BANK_A", "BANK_B"]
        orch.get_agent_balance.side_effect = [1000000, 2000000]
        orch.get_agent_accumulated_costs.return_value = {
            "liquidity_cost": 0,
            "delay_cost": 0,
            "collateral_cost": 0,
            "deadline_penalty": 0,
            "split_friction_cost": 0,
        }
        orch.get_agent_collateral_posted.return_value = 0
        orch.get_agent_queue1_contents.return_value = []
        orch.get_rtgs_queue_contents.return_value = []

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)
        pm.on_tick_complete(0, orch)

        # Verify agent states were buffered
        assert len(pm.replay_buffers["agent_states"]) == 2
        assert pm.replay_buffers["agent_states"][0]["agent_id"] == "BANK_A"
        assert pm.replay_buffers["agent_states"][0]["balance"] == 1000000
        assert pm.replay_buffers["agent_states"][1]["balance"] == 2000000

    def test_buffer_tracks_balance_changes(self):
        """Full replay should track balance changes between ticks."""
        db_manager = Mock()
        orch = Mock()

        orch.get_tick_events.return_value = []
        orch.get_agent_ids.return_value = ["BANK_A"]
        orch.get_agent_accumulated_costs.return_value = {
            "liquidity_cost": 0,
            "delay_cost": 0,
            "collateral_cost": 0,
            "deadline_penalty": 0,
            "split_friction_cost": 0,
        }
        orch.get_agent_collateral_posted.return_value = 0
        orch.get_agent_queue1_contents.return_value = []
        orch.get_rtgs_queue_contents.return_value = []

        pm = PersistenceManager(db_manager, "test-sim", full_replay=True)

        # Tick 0: balance = 1000000
        orch.get_agent_balance.return_value = 1000000
        pm.on_tick_complete(0, orch)

        assert pm.replay_buffers["agent_states"][0]["balance_change"] == 1000000  # Initial

        # Tick 1: balance = 900000 (sent 100000)
        orch.get_agent_balance.return_value = 900000
        pm.on_tick_complete(1, orch)

        assert pm.replay_buffers["agent_states"][1]["balance_change"] == -100000
