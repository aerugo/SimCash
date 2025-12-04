"""Tests for filtered agent log outputs in Castro experiments.

These tests verify that:
1. LLM optimizers only see events relevant to the bank they're optimizing
2. The filtered replay mechanism works correctly
3. Information isolation is maintained between competing banks

The tests ensure the implementation in reproducible_experiment.py correctly
uses the --filter-agent feature to provide bank-specific views.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the functions we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from reproducible_experiment import (
    get_filtered_replay_output,
    run_single_simulation,
    run_simulations_parallel,
)


# ============================================================================
# Unit Tests for get_filtered_replay_output
# ============================================================================


class TestGetFilteredReplayOutput:
    """Unit tests for get_filtered_replay_output function."""

    def test_constructs_correct_command(self):
        """Verify the function constructs the correct replay command."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Filtered output for BANK_A",
                stderr="",
            )

            result = get_filtered_replay_output(
                simcash_root="/home/user/SimCash",
                db_path="/tmp/test.db",
                simulation_id="test_sim_123",
                agent_id="BANK_A",
            )

            # Verify command was constructed correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert "replay" in cmd
            assert "--simulation-id" in cmd
            assert "test_sim_123" in cmd
            assert "--db-path" in cmd
            assert "/tmp/test.db" in cmd
            assert "--verbose" in cmd
            assert "--filter-agent" in cmd
            assert "BANK_A" in cmd

    def test_returns_stdout_on_success(self):
        """Verify function returns stdout on successful replay."""
        expected_output = "Tick 0\n  BANK_A events...\nTick 1\n  More events..."

        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=expected_output,
                stderr="",
            )

            result = get_filtered_replay_output(
                simcash_root="/home/user/SimCash",
                db_path="/tmp/test.db",
                simulation_id="test_sim",
                agent_id="BANK_A",
            )

            assert result == expected_output

    def test_raises_runtime_error_on_failure(self):
        """Verify function raises RuntimeError when replay fails."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: Simulation not found",
            )

            with pytest.raises(RuntimeError) as exc_info:
                get_filtered_replay_output(
                    simcash_root="/home/user/SimCash",
                    db_path="/tmp/test.db",
                    simulation_id="nonexistent",
                    agent_id="BANK_A",
                )

            assert "BANK_A" in str(exc_info.value)
            assert "Error: Simulation not found" in str(exc_info.value)

    def test_different_agents_use_different_filter_values(self):
        """Verify each agent gets its own filter value."""
        calls = []

        def capture_call(*args, **kwargs):
            calls.append(args[0])
            return MagicMock(returncode=0, stdout="output", stderr="")

        with patch("reproducible_experiment.subprocess.run", side_effect=capture_call):
            # Call for BANK_A
            get_filtered_replay_output(
                simcash_root="/home/user/SimCash",
                db_path="/tmp/test.db",
                simulation_id="test_sim",
                agent_id="BANK_A",
            )

            # Call for BANK_B
            get_filtered_replay_output(
                simcash_root="/home/user/SimCash",
                db_path="/tmp/test.db",
                simulation_id="test_sim",
                agent_id="BANK_B",
            )

        # Verify different filter values
        assert len(calls) == 2
        assert "BANK_A" in calls[0]
        assert "BANK_B" in calls[1]
        assert "BANK_B" not in calls[0]
        assert "BANK_A" not in calls[1]


# ============================================================================
# Unit Tests for run_single_simulation
# ============================================================================


class TestRunSingleSimulation:
    """Unit tests for run_single_simulation function."""

    def test_uses_persist_and_full_replay_flags(self):
        """Verify simulation uses --persist and --full-replay flags."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "costs": {"total_cost": 1000},
                    "agents": [
                        {"id": "BANK_A", "final_balance": 10000},
                        {"id": "BANK_B", "final_balance": 10000},
                    ],
                    "metrics": {"settlement_rate": 1.0},
                }),
                stderr="",
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_single_simulation(
                    ("/tmp/config.yaml", "/home/user/SimCash", 42, tmpdir)
                )

            # Verify command flags
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert "--persist" in cmd
            assert "--full-replay" in cmd
            assert "--quiet" in cmd

    def test_returns_db_path_and_simulation_id(self):
        """Verify result includes db_path and simulation_id for replay."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "costs": {"total_cost": 1000},
                    "agents": [
                        {"id": "BANK_A", "final_balance": 10000},
                        {"id": "BANK_B", "final_balance": 10000},
                    ],
                    "metrics": {"settlement_rate": 1.0},
                }),
                stderr="",
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_single_simulation(
                    ("/tmp/config.yaml", "/home/user/SimCash", 42, tmpdir)
                )

            # Verify db_path and simulation_id are in result
            assert "db_path" in result
            assert "simulation_id" in result
            assert result["seed"] == 42
            assert "sim_42.db" in result["db_path"]
            assert "castro_seed42_" in result["simulation_id"]

    def test_simulation_id_contains_seed_and_uuid(self):
        """Verify simulation ID format includes seed and UUID."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "costs": {"total_cost": 1000},
                    "agents": [],
                    "metrics": {"settlement_rate": 1.0},
                }),
                stderr="",
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_single_simulation(
                    ("/tmp/config.yaml", "/home/user/SimCash", 123, tmpdir)
                )

            sim_id = result["simulation_id"]
            assert sim_id.startswith("castro_seed123_")
            # UUID hex portion should be 8 chars
            uuid_part = sim_id.split("_")[-1]
            assert len(uuid_part) == 8

    def test_error_handling(self):
        """Verify errors are captured in result."""
        with patch("reproducible_experiment.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Config file not found",
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_single_simulation(
                    ("/tmp/nonexistent.yaml", "/home/user/SimCash", 42, tmpdir)
                )

            assert "error" in result
            assert result["seed"] == 42


# ============================================================================
# Unit Tests for run_simulations_parallel
# ============================================================================


class TestRunSimulationsParallel:
    """Unit tests for run_simulations_parallel function."""

    def test_creates_work_dir_if_not_exists(self):
        """Verify work_dir is created if it doesn't exist."""
        with patch("reproducible_experiment.run_single_simulation") as mock_sim:
            mock_sim.return_value = {"seed": 1, "total_cost": 100}

            with tempfile.TemporaryDirectory() as tmpdir:
                work_dir = Path(tmpdir) / "new_subdir"
                assert not work_dir.exists()

                run_simulations_parallel(
                    config_path="/tmp/config.yaml",
                    simcash_root="/home/user/SimCash",
                    seeds=[1],
                    work_dir=work_dir,
                )

                assert work_dir.exists()

    def test_passes_work_dir_to_each_simulation(self):
        """Verify work_dir is passed to each simulation run."""
        captured_args = []

        def capture_args(args):
            captured_args.append(args)
            return {"seed": args[2], "total_cost": 100}

        with patch("reproducible_experiment.run_single_simulation", side_effect=capture_args):
            with tempfile.TemporaryDirectory() as tmpdir:
                run_simulations_parallel(
                    config_path="/tmp/config.yaml",
                    simcash_root="/home/user/SimCash",
                    seeds=[1, 2, 3],
                    work_dir=tmpdir,
                )

        # Verify work_dir was passed to all simulations
        assert len(captured_args) == 3
        for args in captured_args:
            assert args[3] == tmpdir  # work_dir is 4th element


# ============================================================================
# Integration Tests for EventFilter (Bank-Centric Filtering)
# ============================================================================


class TestEventFilterBankCentric:
    """Integration tests verifying bank-centric event filtering.

    These tests verify that the EventFilter correctly filters events
    to show only what each bank should see.
    """

    def test_bank_a_sees_only_bank_a_arrivals(self):
        """BANK_A filter only matches arrivals where BANK_A is sender."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        # BANK_A sends to BANK_B - should match
        arrival_from_a = {
            "event_type": "Arrival",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 10000,
        }
        assert filter_a.matches(arrival_from_a, tick=0)

        # BANK_B sends to BANK_A - should NOT match (even though BANK_A receives)
        arrival_from_b = {
            "event_type": "Arrival",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 10000,
        }
        assert not filter_a.matches(arrival_from_b, tick=0)

    def test_bank_a_sees_incoming_settlements(self):
        """BANK_A filter matches settlements where BANK_A receives money."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        # BANK_B pays BANK_A - BANK_A should see this (incoming liquidity)
        settlement_to_a = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 10000,
        }
        assert filter_a.matches(settlement_to_a, tick=0)

    def test_bank_a_sees_own_outgoing_settlements(self):
        """BANK_A filter matches settlements where BANK_A pays."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        # BANK_A pays BANK_B
        settlement_from_a = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 10000,
        }
        assert filter_a.matches(settlement_from_a, tick=0)

    def test_bank_b_does_not_see_bank_a_arrivals(self):
        """BANK_B filter does NOT match BANK_A's arrivals."""
        from payment_simulator.cli.filters import EventFilter

        filter_b = EventFilter(agent_id="BANK_B")

        arrival_from_a = {
            "event_type": "Arrival",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 10000,
        }
        # BANK_B receives this arrival, but shouldn't see it as an Arrival event
        # (only as a settlement when it settles)
        assert not filter_b.matches(arrival_from_a, tick=0)

    def test_lsm_bilateral_visible_to_both_participants(self):
        """LSM bilateral offset is visible to both agent_a and agent_b."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")
        filter_c = EventFilter(agent_id="BANK_C")

        lsm_event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 10000,
            "amount_b": 8000,
        }

        assert filter_a.matches(lsm_event, tick=0)
        assert filter_b.matches(lsm_event, tick=0)
        assert not filter_c.matches(lsm_event, tick=0)

    def test_lsm_cycle_visible_to_all_participants(self):
        """LSM cycle settlement is visible to all participating agents."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")
        filter_c = EventFilter(agent_id="BANK_C")
        filter_d = EventFilter(agent_id="BANK_D")

        lsm_cycle = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            "net_positions": [1000, -500, -500],
        }

        assert filter_a.matches(lsm_cycle, tick=0)
        assert filter_b.matches(lsm_cycle, tick=0)
        assert filter_c.matches(lsm_cycle, tick=0)
        assert not filter_d.matches(lsm_cycle, tick=0)

    def test_policy_events_only_visible_to_agent(self):
        """Policy events are only visible to the agent making the decision."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        policy_event = {
            "event_type": "PolicySubmit",
            "agent_id": "BANK_A",
            "tx_id": "tx-001",
        }

        assert filter_a.matches(policy_event, tick=0)
        assert not filter_b.matches(policy_event, tick=0)

    def test_cost_accrual_only_visible_to_agent(self):
        """Cost accrual events are only visible to the agent incurring costs."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        cost_event = {
            "event_type": "CostAccrual",
            "agent_id": "BANK_A",
            "costs": {"delay": 100, "overdraft": 50},
        }

        assert filter_a.matches(cost_event, tick=0)
        assert not filter_b.matches(cost_event, tick=0)


# ============================================================================
# Integration Tests for Information Isolation
# ============================================================================


class TestInformationIsolation:
    """Tests verifying information isolation between banks.

    These tests ensure that the filtered logs do NOT reveal:
    - Other bank's internal policy decisions
    - Other bank's arrivals (what they're sending)
    - Other bank's cost accruals
    """

    def test_bank_a_cannot_see_bank_b_policy_decisions(self):
        """BANK_A should never see BANK_B's policy decisions."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        bank_b_decisions = [
            {"event_type": "PolicySubmit", "agent_id": "BANK_B", "tx_id": "tx-001"},
            {"event_type": "PolicyHold", "agent_id": "BANK_B", "tx_id": "tx-002"},
            {"event_type": "PolicySplit", "agent_id": "BANK_B", "tx_id": "tx-003"},
        ]

        for event in bank_b_decisions:
            assert not filter_a.matches(event, tick=0), \
                f"BANK_A should not see BANK_B's {event['event_type']}"

    def test_bank_a_cannot_see_bank_b_cost_accruals(self):
        """BANK_A should never see BANK_B's cost accruals."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        bank_b_cost = {
            "event_type": "CostAccrual",
            "agent_id": "BANK_B",
            "costs": {"delay": 1000, "overdraft": 500},
        }

        assert not filter_a.matches(bank_b_cost, tick=0), \
            "BANK_A should not see BANK_B's cost accruals"

    def test_bank_a_cannot_see_bank_b_arrivals(self):
        """BANK_A should never see what transactions BANK_B is sending."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")

        # BANK_B sending to BANK_A - BANK_A should not see the arrival
        bank_b_arrival = {
            "event_type": "Arrival",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 50000,
        }

        assert not filter_a.matches(bank_b_arrival, tick=0), \
            "BANK_A should not see BANK_B's arrivals (even when BANK_A is receiver)"

    def test_symmetric_isolation(self):
        """Verify isolation is symmetric - neither bank sees the other's internals."""
        from payment_simulator.cli.filters import EventFilter

        filter_a = EventFilter(agent_id="BANK_A")
        filter_b = EventFilter(agent_id="BANK_B")

        # Events that BANK_A generates
        bank_a_events = [
            {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx-001"},
            {"event_type": "CostAccrual", "agent_id": "BANK_A", "costs": {}},
        ]

        # Events that BANK_B generates
        bank_b_events = [
            {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            {"event_type": "PolicyHold", "agent_id": "BANK_B", "tx_id": "tx-002"},
            {"event_type": "CostAccrual", "agent_id": "BANK_B", "costs": {}},
        ]

        # BANK_A sees its own events
        for event in bank_a_events:
            assert filter_a.matches(event, tick=0)

        # BANK_B sees its own events
        for event in bank_b_events:
            assert filter_b.matches(event, tick=0)

        # BANK_A does NOT see BANK_B's events
        for event in bank_b_events:
            assert not filter_a.matches(event, tick=0)

        # BANK_B does NOT see BANK_A's events
        for event in bank_a_events:
            assert not filter_b.matches(event, tick=0)


# ============================================================================
# Mock-based Integration Tests for ReproducibleExperiment
# ============================================================================


class TestReproducibleExperimentFilteredOutputs:
    """Tests for filtered output tracking in ReproducibleExperiment."""

    def test_extract_best_worst_context_calls_filtered_replay(self):
        """Verify _extract_best_worst_context calls get_filtered_replay_output for each agent."""
        # This test verifies the integration without running actual simulations
        from reproducible_experiment import ReproducibleExperiment

        # Mock the dependencies
        with patch("reproducible_experiment.ExperimentDatabase"), \
             patch("reproducible_experiment.LLMOptimizer"), \
             patch("reproducible_experiment.load_yaml_config") as mock_load, \
             patch("reproducible_experiment.load_json_policy") as mock_policy, \
             patch("reproducible_experiment.get_filtered_replay_output") as mock_replay:

            mock_load.return_value = {"agents": [], "cost_rates": {}}
            mock_policy.return_value = {"type": "Fifo"}
            mock_replay.return_value = "Filtered output"

            # Create mock experiment (skip full init)
            with patch.object(ReproducibleExperiment, "__init__", lambda self, *args, **kwargs: None):
                exp = ReproducibleExperiment.__new__(ReproducibleExperiment)
                exp.simcash_root = Path("/home/user/SimCash")
                exp.last_best_seed_output_bank_a = None
                exp.last_best_seed_output_bank_b = None
                exp.last_worst_seed_output_bank_a = None
                exp.last_worst_seed_output_bank_b = None
                exp.last_best_seed = 0
                exp.last_worst_seed = 0
                exp.last_best_cost = 0
                exp.last_worst_cost = 0
                exp.last_cost_breakdown = {}
                exp.last_best_result = None
                exp.last_worst_result = None

                # Simulate results
                results = [
                    {
                        "seed": 1,
                        "total_cost": 1000,
                        "db_path": "/tmp/sim_1.db",
                        "simulation_id": "sim_1",
                        "cost_breakdown": {},
                    },
                    {
                        "seed": 2,
                        "total_cost": 2000,
                        "db_path": "/tmp/sim_2.db",
                        "simulation_id": "sim_2",
                        "cost_breakdown": {},
                    },
                ]

                exp._extract_best_worst_context(results, {})

                # Verify get_filtered_replay_output was called 4 times
                # (2 seeds × 2 agents)
                assert mock_replay.call_count == 4

                # Verify calls were made for both agents
                call_agents = [call[1]["agent_id"] for call in mock_replay.call_args_list]
                assert call_agents.count("BANK_A") == 2
                assert call_agents.count("BANK_B") == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
