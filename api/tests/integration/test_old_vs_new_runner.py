"""
Comparison tests: Old vs New Runner equivalence.

NOTE: These tests are now obsolete as of the complete migration to SimulationRunner.
The old runner implementation has been completely removed (see commit 0ef872e).
These tests are kept for historical reference but are skipped by default.

TDD Approach: Write tests first, then enable new runner by default once all pass.
"""

import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.persistence.connection import DatabaseManager

# Skip all tests in this module - old runner has been completely removed
pytestmark = pytest.mark.skip(
    reason="Old runner implementation has been completely removed. "
    "Migration to SimulationRunner is complete (commit 0ef872e)."
)


@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration with arrivals for meaningful comparison."""
    config = {
        "simulation": {
            "ticks_per_day": 10,
            "num_days": 2,
            "rng_seed": 42,  # Fixed seed for determinism
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "enabled": True,
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 100000,
                        "std_dev": 20000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [5, 15],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "enabled": True,
                    "rate_per_tick": 2.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 100000,
                        "std_dev": 20000,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [5, 15],
                },
            },
        ],
        "lsm_config": {
            "bilateral_offsetting": True,
            "cycle_detection": True,
            "max_iterations": 3,
        },
    }

    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return config_path


class TestDeterminismComparison:
    """Verify deterministic behavior: same seed = same results."""

    def test_verbose_mode_produces_identical_statistics_old_vs_new(self, test_config, tmp_path):
        """Old and new verbose mode should produce identical statistics."""
        # Run with old implementation
        db_path_old = tmp_path / "old.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "false"}):
            with patch("sys.stdout", new_callable=StringIO) as stdout_old:
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=False,
                        output_format="json",
                        stream=False,
                        verbose=True,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_old),
                        simulation_id="test-old",
                    )
                except SystemExit:
                    pass

        # Run with new implementation
        db_path_new = tmp_path / "new.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "true"}):
            with patch("sys.stdout", new_callable=StringIO) as stdout_new:
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=False,
                        output_format="json",
                        stream=False,
                        verbose=True,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_new),
                        simulation_id="test-new",
                    )
                except SystemExit:
                    pass

        # Compare database statistics
        db_old = DatabaseManager(str(db_path_old))
        db_new = DatabaseManager(str(db_path_new))

        # Compare transaction counts
        tx_old = db_old.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE simulation_id = 'test-old'"
        ).fetchone()[0]
        tx_new = db_new.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE simulation_id = 'test-new'"
        ).fetchone()[0]
        assert tx_old == tx_new, f"Transaction count mismatch: old={tx_old}, new={tx_new}"

        # Compare agent metrics counts
        metrics_old = db_old.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = 'test-old'"
        ).fetchone()[0]
        metrics_new = db_new.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = 'test-new'"
        ).fetchone()[0]
        assert metrics_old == metrics_new, f"Metrics count mismatch: old={metrics_old}, new={metrics_new}"

        # Compare simulation_runs metadata (just verify both exist and have same transaction count)
        run_old = db_old.conn.execute(
            "SELECT total_transactions FROM simulation_runs WHERE simulation_id = 'test-old'"
        ).fetchone()
        run_new = db_new.conn.execute(
            "SELECT total_transactions FROM simulation_runs WHERE simulation_id = 'test-new'"
        ).fetchone()

        assert run_old is not None, "Old simulation_runs record not found"
        assert run_new is not None, "New simulation_runs record not found"
        assert run_old[0] == run_new[0], f"Total transactions mismatch: old={run_old[0]}, new={run_new[0]}"

    def test_normal_mode_produces_identical_json_output(self, test_config):
        """Old and new normal mode should produce identical JSON output."""
        # Run with old implementation
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "false"}):
            with patch("sys.stdout", new_callable=StringIO) as stdout_old:
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=False,
                        full_replay=False,
                        db_path=None,
                        simulation_id=None,
                    )
                except SystemExit:
                    pass
                output_old = stdout_old.getvalue()

        # Run with new implementation
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "true"}):
            with patch("sys.stdout", new_callable=StringIO) as stdout_new:
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=False,
                        full_replay=False,
                        db_path=None,
                        simulation_id=None,
                    )
                except SystemExit:
                    pass
                output_new = stdout_new.getvalue()

        # Parse JSON outputs
        assert len(output_old) > 0, f"No output from old implementation"
        assert len(output_new) > 0, f"No output from new implementation"

        json_old = json.loads(output_old.strip())
        json_new = json.loads(output_new.strip())

        # Compare critical statistics (ignoring timing variations)
        assert json_old["metrics"]["total_arrivals"] == json_new["metrics"]["total_arrivals"]
        assert json_old["metrics"]["total_settlements"] == json_new["metrics"]["total_settlements"]
        assert json_old["metrics"]["total_lsm_releases"] == json_new["metrics"]["total_lsm_releases"]
        assert json_old["metrics"]["settlement_rate"] == json_new["metrics"]["settlement_rate"]

        # Compare agent final states
        assert len(json_old["agents"]) == len(json_new["agents"])
        for agent_old, agent_new in zip(json_old["agents"], json_new["agents"]):
            assert agent_old["id"] == agent_new["id"]
            assert agent_old["final_balance"] == agent_new["final_balance"]
            assert agent_old["queue1_size"] == agent_new["queue1_size"]

    @pytest.mark.skip(reason="Stream mode comparison - implement after normal/verbose pass")
    def test_stream_mode_produces_identical_jsonl_output(self, test_config):
        """Old and new stream mode should produce identical JSONL output."""
        pass

    @pytest.mark.skip(reason="Event stream mode comparison - implement after normal/verbose pass")
    def test_event_stream_mode_produces_identical_output(self, test_config):
        """Old and new event_stream mode should produce identical output."""
        pass


class TestPersistenceComparison:
    """Verify database persistence is identical between old and new."""

    def test_policy_snapshots_identical(self, test_config, tmp_path):
        """Policy snapshots should be identical in old and new implementations."""
        # Run with old implementation
        db_path_old = tmp_path / "old_policy.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "false"}):
            with patch("sys.stdout", new_callable=StringIO):
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_old),
                        simulation_id="test-old-policy",
                    )
                except SystemExit:
                    pass

        # Run with new implementation
        db_path_new = tmp_path / "new_policy.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "true"}):
            with patch("sys.stdout", new_callable=StringIO):
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_new),
                        simulation_id="test-new-policy",
                    )
                except SystemExit:
                    pass

        # Compare policy snapshots
        db_old = DatabaseManager(str(db_path_old))
        db_new = DatabaseManager(str(db_path_new))

        snapshots_old = db_old.conn.execute(
            """
            SELECT agent_id, snapshot_day, snapshot_tick, policy_hash, created_by
            FROM policy_snapshots
            WHERE simulation_id = 'test-old-policy'
            ORDER BY agent_id
            """
        ).fetchall()

        snapshots_new = db_new.conn.execute(
            """
            SELECT agent_id, snapshot_day, snapshot_tick, policy_hash, created_by
            FROM policy_snapshots
            WHERE simulation_id = 'test-new-policy'
            ORDER BY agent_id
            """
        ).fetchall()

        assert len(snapshots_old) == len(snapshots_new), "Policy snapshot count mismatch"
        for old, new in zip(snapshots_old, snapshots_new):
            assert old == new, f"Policy snapshot mismatch: old={old}, new={new}"

    def test_eod_data_identical(self, test_config, tmp_path):
        """End-of-day data should be identical in old and new implementations."""
        # Run with old implementation
        db_path_old = tmp_path / "old_eod.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "false"}):
            with patch("sys.stdout", new_callable=StringIO):
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_old),
                        simulation_id="test-old-eod",
                    )
                except SystemExit:
                    pass

        # Run with new implementation
        db_path_new = tmp_path / "new_eod.db"
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "true"}):
            with patch("sys.stdout", new_callable=StringIO):
                try:
                    run_simulation(
                        config=test_config,
                        ticks=None,
                        seed=None,
                        quiet=True,
                        output_format="json",
                        stream=False,
                        verbose=False,
                        event_stream=False,
                        persist=True,
                        full_replay=False,
                        db_path=str(db_path_new),
                        simulation_id="test-new-eod",
                    )
                except SystemExit:
                    pass

        # Compare EOD data
        db_old = DatabaseManager(str(db_path_old))
        db_new = DatabaseManager(str(db_path_new))

        # Compare daily agent metrics (should have 2 days * 2 agents = 4 records)
        metrics_old = db_old.conn.execute(
            """
            SELECT agent_id, day, closing_balance, num_sent, num_received
            FROM daily_agent_metrics
            WHERE simulation_id = 'test-old-eod'
            ORDER BY day, agent_id
            """
        ).fetchall()

        metrics_new = db_new.conn.execute(
            """
            SELECT agent_id, day, closing_balance, num_sent, num_received
            FROM daily_agent_metrics
            WHERE simulation_id = 'test-new-eod'
            ORDER BY day, agent_id
            """
        ).fetchall()

        assert len(metrics_old) == 4, "Should have 4 daily metrics records"
        assert len(metrics_new) == 4, "Should have 4 daily metrics records"
        assert metrics_old == metrics_new, "Daily metrics should be identical"
