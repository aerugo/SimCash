"""
Simple replay identity test for scenario events using CLI.
"""
import tempfile
import subprocess
import re
from pathlib import Path
import duckdb


def test_scenario_events_replay_identity_simple():
    """
    Simple test: Run simulation with scenario events, then replay and compare.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Create a simple config with scenario events
        config_yaml = """
simulation:
  ticks_per_day: 20
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
      tick: 5

  - type: DirectTransfer
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 25000
    schedule:
      type: OneTime
      tick: 10
"""
        config_path.write_text(config_yaml)

        # Run simulation with persistence
        print("\n=== Running simulation with scenario events ===")
        run_result = subprocess.run(
            ["uv", "run", "payment-sim", "run",
             "--config", str(config_path),
             "--persist",
             "--db-path", str(db_path),
             "--verbose"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/home/user/SimCash/api"
        )

        print(f"Run exit code: {run_result.returncode}")
        if run_result.returncode != 0:
            print(f"Run stderr: {run_result.stderr}")
            print(f"Run stdout: {run_result.stdout}")

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"
        run_output = run_result.stdout

        # Verify events were persisted
        conn = duckdb.connect(str(db_path))
        sim_id = conn.execute("SELECT simulation_id FROM simulations ORDER BY started_at DESC LIMIT 1").fetchone()[0]

        event_count = conn.execute("""
            SELECT COUNT(*) FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'ScenarioEventExecuted'
        """, [sim_id]).fetchone()[0]

        print(f"Found {event_count} scenario events in database")
        assert event_count == 2, f"Expected 2 scenario events, got {event_count}"

        # Get event details
        events = conn.execute("""
            SELECT tick, details FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'ScenarioEventExecuted'
            ORDER BY tick
        """, [sim_id]).fetchall()
        print(f"Events at ticks: {[e[0] for e in events]}")

        conn.close()

        # Replay simulation
        print("\n=== Replaying simulation ===")
        replay_result = subprocess.run(
            ["uv", "run", "payment-sim", "replay",
             "--simulation-id", sim_id,
             "--db-path", str(db_path),
             "--verbose"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/home/user/SimCash/api"
        )

        print(f"Replay exit code: {replay_result.returncode}")
        if replay_result.returncode != 0:
            print(f"Replay stderr: {replay_result.stderr}")

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"
        replay_output = replay_result.stdout

        # Normalize outputs (remove timing info and normalize paths)
        def normalize(text):
            import json
            # Remove ANSI codes
            text = re.sub(r'\x1b\[[0-9;]*m', '', text)

            # Parse JSON output
            try:
                data = json.loads(text)

                # Normalize paths: convert full paths to relative paths
                if "simulation" in data and "config_file" in data["simulation"]:
                    config_file = data["simulation"]["config_file"]
                    if "/" in config_file:
                        data["simulation"]["config_file"] = config_file.split("/")[-1]

                # Remove timing fields
                if "simulation" in data:
                    data["simulation"].pop("duration_seconds", None)
                    data["simulation"].pop("ticks_per_second", None)
                if "performance" in data:
                    data.pop("performance", None)

                return json.dumps(data, indent=2, sort_keys=True)
            except json.JSONDecodeError:
                # Not JSON, return original (should not happen)
                return text

        run_normalized = normalize(run_output)
        replay_normalized = normalize(replay_output)

        # Compare
        print("\n=== Comparison ===")
        if run_normalized == replay_normalized:
            print("✅ Outputs are IDENTICAL!")
        else:
            print("❌ Outputs DIFFER")
            print(f"\nRun output length: {len(run_normalized)}")
            print(f"Replay output length: {len(replay_normalized)}")

            # Show first difference
            run_lines = run_normalized.splitlines()
            replay_lines = replay_normalized.splitlines()

            for i, (r, p) in enumerate(zip(run_lines, replay_lines)):
                if r != p:
                    print(f"\nFirst difference at line {i}:")
                    print(f"Run:    {r}")
                    print(f"Replay: {p}")
                    break

            # Show samples
            print("\n--- Run output (first 30 lines) ---")
            print('\n'.join(run_lines[:30]))
            print("\n--- Replay output (first 30 lines) ---")
            print('\n'.join(replay_lines[:30]))

            # Fail the test if outputs differ
            assert False, "Run and replay outputs should be identical"


if __name__ == "__main__":
    test_scenario_events_replay_identity_simple()
    print("\nTest PASSED!")
