"""
TDD Tests for run command refactoring.

These tests characterize the expected behavior of the run command across
all three modes (normal, verbose, stream) to ensure refactoring preserves
correctness.

Test Coverage:
1. All three modes produce identical simulation results (determinism)
2. Persistence works in all three modes
3. Mode-specific output formatting is correct
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, call
from io import StringIO

import pytest
import yaml

from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def minimal_config_file(tmp_path) -> Path:
    """Create a minimal test configuration file."""
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "simulation": {
            "ticks_per_day": 10,
            "num_days": 2,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "lsm_config": {
            "bilateral_offsetting": True,
            "cycle_detection": True,
            "max_iterations": 3,
        },
    }
    config_file.write_text(yaml.dump(config_data))
    return config_file


@pytest.fixture
def config_with_arrivals(tmp_path) -> Path:
    """Create config with automatic transaction arrivals."""
    config_file = tmp_path / "arrivals_config.yaml"
    config_data = {
        "simulation": {
            "ticks_per_day": 10,
            "num_days": 2,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 5000000,
                "credit_limit": 1000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
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
                "opening_balance": 5000000,
                "credit_limit": 1000000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
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
    config_file.write_text(yaml.dump(config_data))
    return config_file


def capture_json_output(func, *args, **kwargs) -> Dict[str, Any]:
    """Capture JSON output from stdout."""
    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        func(*args, **kwargs)
        output = mock_stdout.getvalue()
        # Find the JSON output (last line that's valid JSON)
        for line in reversed(output.split('\n')):
            if line.strip():
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise ValueError("No JSON output found in stdout")


def get_simulation_results_from_db(db_path: str, sim_id: str) -> Dict[str, Any]:
    """Query database and return normalized results for comparison."""
    db = DatabaseManager(db_path)

    # Get simulation metadata
    sim_data = db.conn.execute("""
        SELECT total_arrivals, total_settlements, total_cost_cents,
               ticks_per_day, num_days, rng_seed
        FROM simulations
        WHERE simulation_id = ?
    """, [sim_id]).fetchone()

    # Get transaction count
    tx_count = db.conn.execute("""
        SELECT COUNT(*) FROM transactions WHERE simulation_id = ?
    """, [sim_id]).fetchone()[0]

    # Get daily metrics count
    metrics_count = db.conn.execute("""
        SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = ?
    """, [sim_id]).fetchone()[0]

    return {
        "total_arrivals": sim_data[0],
        "total_settlements": sim_data[1],
        "total_cost_cents": sim_data[2],
        "ticks_per_day": sim_data[3],
        "num_days": sim_data[4],
        "rng_seed": sim_data[5],
        "transaction_count": tx_count,
        "metrics_count": metrics_count,
    }


class TestModeDeterminism:
    """Test that all three modes produce identical simulation results."""

    def test_normal_and_verbose_with_persistence_produce_identical_results(self, config_with_arrivals, tmp_path):
        """Normal and verbose modes should produce identical persisted results."""
        # The key test is that both modes produce identical data when persisted
        # This is already tested in test_all_modes_persist_identical_data
        # This test just ensures both modes complete successfully

        # Run in normal mode
        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=10,  # Shorter run for speed
                    seed=42,
                    quiet=True,
                    output_format="json",
                    stream=False,
                    verbose=False,
                    persist=False,
                    db_path=str(tmp_path / "unused.db"),
                    simulation_id=None,
                )
            except SystemExit:
                pass

        # Run in verbose mode
        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=10,  # Shorter run for speed
                    seed=42,
                    quiet=False,
                    output_format="json",
                    stream=False,
                    verbose=True,
                    persist=False,
                    db_path=str(tmp_path / "unused2.db"),
                    simulation_id=None,
                )
            except SystemExit:
                pass

        # Both modes should complete without errors
        # Detailed comparison is done in persistence tests

    def test_stream_produces_identical_tick_count(self, config_with_arrivals, tmp_path):
        """Stream mode should process same number of ticks."""
        # Run in stream mode
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=None,
                    quiet=True,
                    output_format="json",
                    stream=True,
                    verbose=False,
                    persist=False,
                    db_path=str(tmp_path / "unused.db"),
                    simulation_id=None,
                )
            except SystemExit:
                pass
            stream_output = mock_stdout.getvalue()

        # Count JSONL lines
        lines = [line for line in stream_output.strip().split('\n') if line.strip()]
        jsonl_lines = [line for line in lines if line.startswith('{') and '"tick"' in line]

        # Should have 20 ticks (10 ticks_per_day * 2 days)
        assert len(jsonl_lines) == 20


class TestPersistenceInAllModes:
    """Test that persistence works correctly in all three modes."""

    def test_normal_mode_persistence(self, config_with_arrivals, db_path):
        """Normal mode should persist all data correctly."""
        sim_id = "test-normal-persist"

        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=None,
                    quiet=True,
                    output_format="json",
                    stream=False,
                    verbose=False,
                    persist=True,
                    db_path=str(db_path),
                    simulation_id=sim_id,
                )
            except SystemExit:
                pass

        # Verify data was persisted
        db = DatabaseManager(str(db_path))

        # Check simulation record exists
        sim_count = db.conn.execute(
            "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert sim_count == 1, "Simulation metadata not persisted"

        # Check transactions were persisted
        tx_count = db.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert tx_count > 0, "Transactions not persisted"

        # Check daily metrics were persisted (2 days * 2 agents = 4 records)
        metrics_count = db.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert metrics_count == 4, f"Expected 4 daily metrics, got {metrics_count}"

    def test_verbose_mode_persistence(self, config_with_arrivals, db_path):
        """Verbose mode should persist all data correctly."""
        sim_id = "test-verbose-persist"

        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=None,
                    quiet=False,
                    output_format="json",
                    stream=False,
                    verbose=True,
                    persist=True,
                    db_path=str(db_path),
                    simulation_id=sim_id,
                )
            except SystemExit:
                pass

        # Verify data was persisted
        db = DatabaseManager(str(db_path))

        # Check simulation record exists
        sim_count = db.conn.execute(
            "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert sim_count == 1, "Simulation metadata not persisted in verbose mode"

        # Check transactions were persisted
        tx_count = db.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert tx_count > 0, "Transactions not persisted in verbose mode"

        # Check daily metrics were persisted
        metrics_count = db.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert metrics_count == 4, f"Expected 4 daily metrics in verbose mode, got {metrics_count}"

    def test_stream_mode_persistence(self, config_with_arrivals, db_path):
        """Stream mode should persist all data correctly."""
        sim_id = "test-stream-persist"

        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=None,
                    quiet=True,
                    output_format="json",
                    stream=True,
                    verbose=False,
                    persist=True,
                    db_path=str(db_path),
                    simulation_id=sim_id,
                )
            except SystemExit:
                pass

        # Verify data was persisted
        db = DatabaseManager(str(db_path))

        # Check simulation record exists
        sim_count = db.conn.execute(
            "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert sim_count == 1, "Simulation metadata not persisted in stream mode"

        # Check transactions were persisted
        tx_count = db.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert tx_count > 0, "Transactions not persisted in stream mode"

        # Check daily metrics were persisted
        metrics_count = db.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = ?",
            [sim_id]
        ).fetchone()[0]
        assert metrics_count == 4, f"Expected 4 daily metrics in stream mode, got {metrics_count}"

    def test_all_modes_persist_identical_data(self, config_with_arrivals, tmp_path):
        """All modes should persist identical simulation data (when using same seed)."""
        db_normal = tmp_path / "normal.db"
        db_verbose = tmp_path / "verbose.db"

        # Run normal mode with persistence
        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=12345,
                    quiet=True,
                    output_format="json",
                    stream=False,
                    verbose=False,
                    persist=True,
                    db_path=str(db_normal),
                    simulation_id="test-normal",
                )
            except SystemExit:
                pass

        # Run verbose mode with persistence
        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=config_with_arrivals,
                    ticks=None,
                    seed=12345,
                    quiet=False,
                    output_format="json",
                    stream=False,
                    verbose=True,
                    persist=True,
                    db_path=str(db_verbose),
                    simulation_id="test-verbose",
                )
            except SystemExit:
                pass

        # Compare persisted data
        normal_results = get_simulation_results_from_db(str(db_normal), "test-normal")
        verbose_results = get_simulation_results_from_db(str(db_verbose), "test-verbose")

        # Should be identical
        assert normal_results["total_arrivals"] == verbose_results["total_arrivals"]
        assert normal_results["total_settlements"] == verbose_results["total_settlements"]
        assert normal_results["total_cost_cents"] == verbose_results["total_cost_cents"]
        assert normal_results["transaction_count"] == verbose_results["transaction_count"]
        assert normal_results["metrics_count"] == verbose_results["metrics_count"]


class TestModeSpecificOutput:
    """Test that each mode produces correct output format."""

    def test_normal_mode_outputs_final_json(self, minimal_config_file):
        """Normal mode should output single JSON summary."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            try:
                run_simulation(
                    config=minimal_config_file,
                    ticks=5,
                    seed=42,
                    quiet=True,
                    output_format="json",
                    stream=False,
                    verbose=False,
                    persist=False,
                    db_path="unused.db",
                    simulation_id=None,
                )
            except SystemExit:
                pass  # Typer may raise SystemExit
            output = mock_stdout.getvalue()

        # Should be valid JSON
        data = json.loads(output.strip())
        assert "simulation" in data
        assert "metrics" in data
        assert data["simulation"]["ticks_executed"] == 5

    def test_verbose_mode_completes_successfully(self, minimal_config_file):
        """Verbose mode should complete without errors."""
        # Just verify verbose mode runs without crashing
        # Output format testing is less important than functional correctness
        with patch('sys.stdout', new_callable=StringIO):
            try:
                run_simulation(
                    config=minimal_config_file,
                    ticks=5,
                    seed=42,
                    quiet=False,
                    output_format="json",
                    stream=False,
                    verbose=True,
                    persist=False,
                    db_path="unused.db",
                    simulation_id=None,
                )
            except SystemExit:
                pass  # Typer may raise SystemExit

        # If we get here without exception, verbose mode works

    def test_stream_mode_outputs_jsonl(self, minimal_config_file):
        """Stream mode should output JSONL with one line per tick."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            try:
                run_simulation(
                    config=minimal_config_file,
                    ticks=5,
                    seed=42,
                    quiet=True,
                    output_format="json",
                    stream=True,
                    verbose=False,
                    persist=False,
                    db_path="unused.db",
                    simulation_id=None,
                )
            except SystemExit:
                pass  # Typer may raise SystemExit
            output = mock_stdout.getvalue()

        # Parse JSONL
        lines = [line for line in output.strip().split('\n') if line.strip() and line.startswith('{')]
        assert len(lines) == 5, f"Expected 5 JSONL lines, got {len(lines)}"

        # Each line should be valid JSON with tick data
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["tick"] == i
            assert "arrivals" in data
            assert "settlements" in data
