"""Comprehensive Replay Identity Tests - V2 (Post-Fix)

Tests to verify complete replay identity after fixing all the core issues.
These tests ensure run and replay produce byte-for-byte identical output.

Following the golden rule from CLAUDE.md:
- simulation_events table is the ONLY source for replay
- Run and replay MUST produce identical output
- No manual reconstruction, no legacy tables
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest


def normalize_json_output(text: str) -> str:
    """Normalize JSON output for comparison.

    Removes timing fields, replay-specific fields, and normalizes paths to allow comparison.
    """
    try:
        data = json.loads(text)

        # Normalize config file paths (full path -> filename only)
        if "simulation" in data and "config_file" in data["simulation"]:
            config_file = data["simulation"]["config_file"]
            if "/" in config_file or "\\" in config_file:
                data["simulation"]["config_file"] = Path(config_file).name

        # Remove timing fields and replay-specific fields
        if "simulation" in data:
            data["simulation"].pop("duration_seconds", None)
            data["simulation"].pop("ticks_per_second", None)
            data["simulation"].pop("replay_range", None)  # Remove replay-specific field
            data["simulation"].pop("ticks_replayed", None)  # Remove replay-specific field

        if "performance" in data:
            data.pop("performance", None)

        # Normalize numeric types
        if "metrics" in data:
            for key in ["settlement_rate", "cost_efficiency"]:
                if key in data["metrics"]:
                    data["metrics"][key] = float(data["metrics"][key])

        return json.dumps(data, indent=2, sort_keys=True)
    except json.JSONDecodeError:
        return text


def run_and_replay(config_yaml: str) -> tuple[str, str]:
    """Run simulation and replay, return normalized outputs.

    Args:
        config_yaml: YAML configuration string

    Returns:
        Tuple of (run_output, replay_output) both normalized
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        db_path = Path(tmpdir) / "sim.db"

        config_path.write_text(config_yaml)

        # Run simulation
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Get simulation ID
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
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        run_norm = normalize_json_output(run_result.stdout)
        replay_norm = normalize_json_output(replay_result.stdout)

        return run_norm, replay_norm


def test_simple_settlement_replay_identity():
    """Test replay identity for simple settlement scenario."""
    config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 12345

agents:
  - id: BANK_A
    opening_balance: 1000000
    unsecured_cap: 0
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    unsecured_cap: 0
    policy:
      type: Fifo

arrivals:
  - sender: BANK_A
    receiver: BANK_B
    rate_per_tick: 0.1
    amount_distribution:
      type: Normal
      mean: 50000
      std_dev: 10000
    deadline_range: [50, 100]
    priority: 5
    divisible: false
"""

    run_output, replay_output = run_and_replay(config_yaml)

    if run_output != replay_output:
        print("\n=== RUN OUTPUT ===")
        print(run_output)
        print("\n=== REPLAY OUTPUT ===")
        print(replay_output)

    assert run_output == replay_output, "Simple settlement scenario: run and replay must be identical"


def test_lsm_cycles_replay_identity():
    """Test replay identity for LSM cycle settlements."""
    config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 999

lsm_config:
  enabled: true
  activation_tick: 0

agents:
  - id: A
    opening_balance: 10000
    unsecured_cap: 0
    policy:
      type: Fifo

  - id: B
    opening_balance: 10000
    unsecured_cap: 0
    policy:
      type: Fifo

  - id: C
    opening_balance: 10000
    unsecured_cap: 0
    policy:
      type: Fifo

arrivals:
  - sender: A
    receiver: B
    rate_per_tick: 0.05
    amount_distribution:
      type: Normal
      mean: 30000
      std_dev: 5000
    deadline_range: [50, 100]
    priority: 5
    divisible: false

  - sender: B
    receiver: C
    rate_per_tick: 0.05
    amount_distribution:
      type: Normal
      mean: 30000
      std_dev: 5000
    deadline_range: [50, 100]
    priority: 5
    divisible: false

  - sender: C
    receiver: A
    rate_per_tick: 0.05
    amount_distribution:
      type: Normal
      mean: 30000
      std_dev: 5000
    deadline_range: [50, 100]
    priority: 5
    divisible: false
"""

    run_output, replay_output = run_and_replay(config_yaml)

    if run_output != replay_output:
        print("\n=== RUN OUTPUT ===")
        print(run_output)
        print("\n=== REPLAY OUTPUT ===")
        print(replay_output)

    assert run_output == replay_output, "LSM cycles: run and replay must be identical"


def test_overdue_transactions_replay_identity():
    """Test replay identity for overdue transaction scenarios."""
    config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 777

cost_rates:
  deadline_penalty: 50000
  delay_cost_per_tick_per_cent: 0.0001
  overdue_delay_multiplier: 5.0

agents:
  - id: BANK_A
    opening_balance: 5000
    unsecured_cap: 0
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 1000000
    unsecured_cap: 0
    policy:
      type: Fifo

arrivals:
  - sender: BANK_A
    receiver: BANK_B
    rate_per_tick: 0.2
    amount_distribution:
      type: Normal
      mean: 100000
      std_dev: 10000
    deadline_range: [5, 15]
    priority: 5
    divisible: false
"""

    run_output, replay_output = run_and_replay(config_yaml)

    if run_output != replay_output:
        print("\n=== RUN OUTPUT ===")
        print(run_output)
        print("\n=== REPLAY OUTPUT ===")
        print(replay_output)

    assert run_output == replay_output, "Overdue transactions: run and replay must be identical"


def test_multi_agent_complex_scenario_replay_identity():
    """Test replay identity for complex multi-agent scenario."""
    config_yaml = """
simulation:
  ticks_per_day: 100
  num_days: 2
  rng_seed: 424242

lsm_config:
  enabled: true
  activation_tick: 10

cost_rates:
  liquidity_cost_per_tick_per_cent: 0.0001
  deadline_penalty: 25000
  delay_cost_per_tick_per_cent: 0.0001

agents:
  - id: HUB
    opening_balance: 500000
    unsecured_cap: 100000
    policy:
      type: Fifo

  - id: BANK_A
    opening_balance: 200000
    unsecured_cap: 50000
    policy:
      type: Fifo

  - id: BANK_B
    opening_balance: 150000
    unsecured_cap: 50000
    policy:
      type: Fifo

  - id: BANK_C
    opening_balance: 100000
    unsecured_cap: 25000
    policy:
      type: Fifo

arrivals:
  - sender: BANK_A
    receiver: HUB
    rate_per_tick: 0.1
    amount_distribution:
      type: Normal
      mean: 50000
      std_dev: 10000
    deadline_range: [30, 80]
    priority: 5
    divisible: false
    counterparty_weights:
      HUB: 1.0

  - sender: BANK_B
    receiver: HUB
    rate_per_tick: 0.1
    amount_distribution:
      type: Normal
      mean: 40000
      std_dev: 8000
    deadline_range: [30, 80]
    priority: 5
    divisible: false
    counterparty_weights:
      HUB: 1.0

  - sender: BANK_C
    receiver: HUB
    rate_per_tick: 0.05
    amount_distribution:
      type: Normal
      mean: 30000
      std_dev: 5000
    deadline_range: [30, 80]
    priority: 5
    divisible: false
    counterparty_weights:
      HUB: 1.0

  - sender: HUB
    receiver: BANK_A
    rate_per_tick: 0.08
    amount_distribution:
      type: Normal
      mean: 45000
      std_dev: 9000
    deadline_range: [30, 80]
    priority: 5
    divisible: false
    counterparty_weights:
      BANK_A: 0.4
      BANK_B: 0.4
      BANK_C: 0.2
"""

    run_output, replay_output = run_and_replay(config_yaml)

    if run_output != replay_output:
        print("\n=== RUN OUTPUT ===")
        print(run_output)
        print("\n=== REPLAY OUTPUT ===")
        print(replay_output)

    assert run_output == replay_output, "Multi-agent complex scenario: run and replay must be identical"


def test_high_volume_stress_replay_identity():
    """Test replay identity under high transaction volume."""
    config_yaml = """
simulation:
  ticks_per_day: 50
  num_days: 1
  rng_seed: 55555

lsm_config:
  enabled: true
  activation_tick: 0

agents:
  - id: A
    opening_balance: 1000000
    unsecured_cap: 200000
    policy:
      type: Fifo

  - id: B
    opening_balance: 1000000
    unsecured_cap: 200000
    policy:
      type: Fifo

  - id: C
    opening_balance: 1000000
    unsecured_cap: 200000
    policy:
      type: Fifo

  - id: D
    opening_balance: 1000000
    unsecured_cap: 200000
    policy:
      type: Fifo

arrivals:
  - sender: A
    receiver: B
    rate_per_tick: 0.5
    amount_distribution:
      type: Normal
      mean: 100000
      std_dev: 20000
    deadline_range: [20, 40]
    priority: 5
    divisible: false
    counterparty_weights:
      B: 0.4
      C: 0.3
      D: 0.3

  - sender: B
    receiver: A
    rate_per_tick: 0.5
    amount_distribution:
      type: Normal
      mean: 90000
      std_dev: 18000
    deadline_range: [20, 40]
    priority: 5
    divisible: false
    counterparty_weights:
      A: 0.3
      C: 0.4
      D: 0.3

  - sender: C
    receiver: B
    rate_per_tick: 0.5
    amount_distribution:
      type: Normal
      mean: 95000
      std_dev: 19000
    deadline_range: [20, 40]
    priority: 5
    divisible: false
    counterparty_weights:
      A: 0.3
      B: 0.3
      D: 0.4

  - sender: D
    receiver: C
    rate_per_tick: 0.5
    amount_distribution:
      type: Normal
      mean: 85000
      std_dev: 17000
    deadline_range: [20, 40]
    priority: 5
    divisible: false
    counterparty_weights:
      A: 0.4
      B: 0.3
      C: 0.3
"""

    run_output, replay_output = run_and_replay(config_yaml)

    if run_output != replay_output:
        print("\n=== RUN OUTPUT ===")
        print(run_output)
        print("\n=== REPLAY OUTPUT ===")
        print(replay_output)

    assert run_output == replay_output, "High volume stress test: run and replay must be identical"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
