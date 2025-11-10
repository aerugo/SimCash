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
                "payment-sim", "run",
                "--config", str(config_path),
                "--persist", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"
        run_output = run_result.stdout

        # Get simulation ID from database
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY created_at DESC LIMIT 1").fetchone()[0]
        conn.close()

        # Replay simulation
        replay_result = subprocess.run(
            [
                "payment-sim", "replay",
                str(db_path),
                "--simulation-id", sim_id,
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"
        replay_output = replay_result.stdout

        # Compare outputs (ignoring timing lines)
        run_lines = [line for line in run_output.splitlines() if "Duration:" not in line and "ms" not in line]
        replay_lines = [line for line in replay_output.splitlines() if "Duration:" not in line and "ms" not in line]

        # For debugging if test fails
        if run_lines != replay_lines:
            print("\\n=== RUN OUTPUT ===")
            print("\\n".join(run_lines[:50]))
            print("\\n=== REPLAY OUTPUT ===")
            print("\\n".join(replay_lines[:50]))

        assert run_lines == replay_lines, "Run and replay outputs should be identical"

        # Verify scenario event appears in both outputs
        scenario_event_lines = [line for line in run_lines if "DirectTransfer" in line or "BANK_A" in line]
        assert len(scenario_event_lines) > 0, "Scenario event should appear in output"


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
                "payment-sim", "run",
                "--config", str(config_path),
                "--persist", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Get simulation ID
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY created_at DESC LIMIT 1").fetchone()[0]

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
                "payment-sim", "replay",
                str(db_path),
                "--simulation-id", sim_id,
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Compare outputs
        run_lines = [line for line in run_result.stdout.splitlines() if "Duration:" not in line and "ms" not in line]
        replay_lines = [line for line in replay_result.stdout.splitlines() if "Duration:" not in line and "ms" not in line]

        assert run_lines == replay_lines, "Run and replay outputs should be identical"


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
                "payment-sim", "run",
                "--config", str(config_path),
                "--persist", str(db_path),
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert run_result.returncode == 0

        # Get simulation ID
        import duckdb
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY created_at DESC LIMIT 1").fetchone()[0]

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
                "payment-sim", "replay",
                str(db_path),
                "--simulation-id", sim_id,
                "--verbose"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert replay_result.returncode == 0

        # Compare outputs
        run_lines = [line for line in run_result.stdout.splitlines() if "Duration:" not in line and "ms" not in line]
        replay_lines = [line for line in replay_result.stdout.splitlines() if "Duration:" not in line and "ms" not in line]

        assert run_lines == replay_lines, "Run and replay outputs should be identical"


@pytest.mark.skip(reason="Requires payment-sim CLI to be available")
def test_scenario_events_appear_in_verbose_output():
    """
    Test that scenario events appear in verbose output during both run and replay.

    This is a placeholder to remind us to verify display output once
    StateProvider methods are implemented.
    """
    pass
