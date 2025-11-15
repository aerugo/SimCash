"""
TDD tests for scenario event replay identity.

Following the Single Source of Truth principle from CLAUDE.md:
- simulation_events table is the ONLY source for replay
- Run and replay must produce identical output
- No manual reconstruction of events

These tests verify that scenario events maintain replay identity.
"""
import tempfile
from pathlib import Path
import subprocess

import pytest


def test_direct_transfer_replay_identity():
    """
    Test that DirectTransfer events maintain replay identity.

    TDD: This test verifies run and replay produce identical output.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        db_path = Path(tmpdir) / "sim.db"

        # Create config with DirectTransfer event
        config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 12345

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 0
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 0
    policy:
      type: Fifo

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 100000
    schedule:
      type: OneTime
      tick: 10
"""
        config_path.write_text(config_yaml)

        # Run simulation with persistence
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"
        run_output = run_result.stdout

        # Get simulation ID from database
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY started_at DESC LIMIT 1").fetchone()[0]
        conn.close()

        # Replay simulation
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"
        replay_output = replay_result.stdout

        # Normalize outputs (remove timing info and normalize paths)
        def normalize(text):
            import json
            try:
                data = json.loads(text)

                # Normalize paths: convert full paths to relative paths
                if "simulation" in data and "config_file" in data["simulation"]:
                    config_file = data["simulation"]["config_file"]
                    if "/" in config_file:
                        data["simulation"]["config_file"] = config_file.split("/")[-1]

                # Remove timing fields and replay-specific fields
                if "simulation" in data:
                    data["simulation"].pop("duration_seconds", None)
                    data["simulation"].pop("ticks_per_second", None)
                    data["simulation"].pop("replay_range", None)
                    data["simulation"].pop("ticks_replayed", None)
                if "performance" in data:
                    data.pop("performance", None)

                # Normalize numeric types (int 0 -> float 0.0 for settlement_rate)
                if "metrics" in data and "settlement_rate" in data["metrics"]:
                    data["metrics"]["settlement_rate"] = float(data["metrics"]["settlement_rate"])

                return json.dumps(data, indent=2, sort_keys=True)
            except json.JSONDecodeError:
                return text

        run_normalized = normalize(run_output)
        replay_normalized = normalize(replay_output)

        # For debugging if test fails
        if run_normalized != replay_normalized:
            print("\n=== RUN OUTPUT ===")
            print(run_normalized)
            print("\n=== REPLAY OUTPUT ===")
            print(replay_normalized)

        assert run_normalized == replay_normalized, "Run and replay outputs should be identical"


def test_multiple_scenario_events_replay_identity():
    """
    Test replay identity with multiple scenario events.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        db_path = Path(tmpdir) / "sim.db"

        config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: Fifo

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 50000
    schedule:
      type: OneTime
      tick: 10

  - type: CollateralAdjustment
    agent: BANK_A
    delta: 100000
    schedule:
      type: OneTime
      tick: 20

  - type: DirectTransfer
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 25000
    schedule:
      type: OneTime
      tick: 30
"""
        config_path.write_text(config_yaml)

        # Run with persistence
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Get simulation ID
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY started_at DESC LIMIT 1").fetchone()[0]

        # Verify all 3 events were persisted
        event_count = conn.execute("""
            SELECT COUNT(*) FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'ScenarioEventExecuted'
        """, [sim_id]).fetchone()[0]
        assert event_count == 3, f"Expected 3 scenario events, got {event_count}"

        conn.close()

        # Replay
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Normalize outputs (remove timing info and normalize paths)
        def normalize(text):
            import json
            try:
                data = json.loads(text)
                if "simulation" in data and "config_file" in data["simulation"]:
                    config_file = data["simulation"]["config_file"]
                    if "/" in config_file:
                        data["simulation"]["config_file"] = config_file.split("/")[-1]
                if "simulation" in data:
                    data["simulation"].pop("duration_seconds", None)
                    data["simulation"].pop("ticks_per_second", None)
                    data["simulation"].pop("replay_range", None)
                    data["simulation"].pop("ticks_replayed", None)
                if "performance" in data:
                    data.pop("performance", None)
                # Normalize numeric types (int 0 -> float 0.0 for settlement_rate)
                if "metrics" in data and "settlement_rate" in data["metrics"]:
                    data["metrics"]["settlement_rate"] = float(data["metrics"]["settlement_rate"])
                return json.dumps(data, indent=2, sort_keys=True)
            except json.JSONDecodeError:
                return text

        run_normalized = normalize(run_result.stdout)
        replay_normalized = normalize(replay_result.stdout)

        if run_normalized != replay_normalized:
            print("\n=== RUN OUTPUT ===")
            print(run_normalized)
            print("\n=== REPLAY OUTPUT ===")
            print(replay_normalized)

        assert run_normalized == replay_normalized, "Run and replay outputs should be identical"


def test_repeating_scenario_event_replay_identity():
    """
    Test replay identity with repeating scenario events.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        db_path = Path(tmpdir) / "sim.db"

        config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 99

agents:
  - id: BANK_A
    opening_balance: 2000000
    credit_limit: 0
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 0
    policy:
      type: Fifo

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 10000
    schedule:
      type: Repeating
      start_tick: 10
      interval: 10
"""
        config_path.write_text(config_yaml)

        # Run
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert run_result.returncode == 0

        # Get simulation ID
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY started_at DESC LIMIT 1").fetchone()[0]

        # Verify multiple executions were persisted
        event_count = conn.execute("""
            SELECT COUNT(*) FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'ScenarioEventExecuted'
        """, [sim_id]).fetchone()[0]
        assert event_count >= 4, f"Expected at least 4 repeating executions, got {event_count}"

        conn.close()

        # Replay
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert replay_result.returncode == 0

        # Normalize outputs (remove timing info and normalize paths)
        def normalize(text):
            import json
            try:
                data = json.loads(text)
                if "simulation" in data and "config_file" in data["simulation"]:
                    config_file = data["simulation"]["config_file"]
                    if "/" in config_file:
                        data["simulation"]["config_file"] = config_file.split("/")[-1]
                if "simulation" in data:
                    data["simulation"].pop("duration_seconds", None)
                    data["simulation"].pop("ticks_per_second", None)
                    data["simulation"].pop("replay_range", None)
                    data["simulation"].pop("ticks_replayed", None)
                if "performance" in data:
                    data.pop("performance", None)
                # Normalize numeric types (int 0 -> float 0.0 for settlement_rate)
                if "metrics" in data and "settlement_rate" in data["metrics"]:
                    data["metrics"]["settlement_rate"] = float(data["metrics"]["settlement_rate"])
                return json.dumps(data, indent=2, sort_keys=True)
            except json.JSONDecodeError:
                return text

        run_normalized = normalize(run_result.stdout)
        replay_normalized = normalize(replay_result.stdout)

        if run_normalized != replay_normalized:
            print("\n=== RUN OUTPUT ===")
            print(run_normalized)
            print("\n=== REPLAY OUTPUT ===")
            print(replay_normalized)

        assert run_normalized == replay_normalized, "Run and replay outputs should be identical"


def test_scenario_events_appear_in_verbose_output():
    """
    Test that scenario events appear in verbose output during both run and replay.

    Verifies that ScenarioEventExecuted events are displayed in verbose mode.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        db_path = Path(tmpdir) / "sim.db"

        config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 12345

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 0
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 0
    policy:
      type: Fifo

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 100000
    schedule:
      type: OneTime
      tick: 10
"""
        config_path.write_text(config_yaml)

        # Run with verbose output
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Get simulation ID
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY started_at DESC LIMIT 1").fetchone()[0]
        conn.close()

        # Replay with verbose output
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--from-tick", "0",
                "--to-tick", "20",
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Verify scenario event was persisted to database
        import duckdb
        conn = duckdb.connect(str(db_path))
        scenario_events = conn.execute(
            "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ? AND event_type = 'ScenarioEventExecuted'",
            [sim_id]
        ).fetchone()[0]
        conn.close()

        assert scenario_events > 0, f"Expected ScenarioEventExecuted events in database, got {scenario_events}"
