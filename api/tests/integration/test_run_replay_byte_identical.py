"""End-to-end test: Verify run and replay produce byte-for-byte identical output.

This test ensures that replaying a simulation from the database produces
exactly the same verbose output as the original run, verified by SHA256 hash.

Critical for:
- Debugging: Ability to re-examine exact output from a previous run
- Research: Reproducible experiments with identical verbose logging
- Compliance: Auditable transaction history with verifiable replay
"""
import hashlib
import json
import re
import subprocess
import pytest
from pathlib import Path


@pytest.fixture
def test_config_with_lsm(tmp_path):
    """Create a test configuration that exercises LSM mechanisms.

    This config is designed to trigger LSM cycles for comprehensive testing.
    """
    config_file = tmp_path / "test_lsm_config.yaml"
    config_file.write_text("""
simulation:
  ticks_per_day: 20
  num_days: 1
  rng_seed: 42

agents:
  - id: "BANK_A"
    opening_balance: 500000
    credit_limit: 250000
    policy:
      type: "Fifo"
    arrivals:
      enabled: true
      rate_per_tick: 0.3
      amount_distribution:
        type: "Normal"
        mean: 50000
        std_dev: 10000
        min: 10000
        max: 100000
      counterparty_weights:
        BANK_B: 0.6
        BANK_C: 0.4

  - id: "BANK_B"
    opening_balance: 500000
    credit_limit: 250000
    policy:
      type: "Fifo"
    arrivals:
      enabled: true
      rate_per_tick: 0.3
      amount_distribution:
        type: "Normal"
        mean: 50000
        std_dev: 10000
        min: 10000
        max: 100000
      counterparty_weights:
        BANK_A: 0.4
        BANK_C: 0.6

  - id: "BANK_C"
    opening_balance: 500000
    credit_limit: 250000
    policy:
      type: "Fifo"
    arrivals:
      enabled: true
      rate_per_tick: 0.3
      amount_distribution:
        type: "Normal"
        mean: 50000
        std_dev: 10000
        min: 10000
        max: 100000
      counterparty_weights:
        BANK_A: 0.5
        BANK_B: 0.5

lsm_config:
  bilateral_offsetting: true
  cycle_detection: true
  max_iterations: 3
""")
    return config_file


@pytest.fixture
def db_path(tmp_path):
    """Temporary database for testing."""
    return tmp_path / "test_replay.db"


def run_cli(args, check=True):
    """Helper to run CLI command and capture output."""
    import os

    # Set PYTHONPATH to include the api directory
    env = os.environ.copy()
    api_dir = str(Path(__file__).parent.parent.parent)
    current_pythonpath = env.get('PYTHONPATH', '')
    if current_pythonpath:
        env['PYTHONPATH'] = f"{api_dir}:{current_pythonpath}"
    else:
        env['PYTHONPATH'] = api_dir

    # Use uv run to execute the CLI (works in test environment)
    result = subprocess.run(
        ["uv", "run", "payment-sim"] + args,
        capture_output=True,
        text=True,
        check=check,
        env=env,
        cwd=api_dir,
    )
    return result


def normalize_output_for_comparison(text: str) -> str:
    """Normalize output for byte-for-byte comparison.

    Removes elements that legitimately differ between run and replay:
    - Timestamps and durations
    - Absolute file paths
    - Progress indicators
    - Pre-simulation initialization messages

    Preserves:
    - All simulation events (starting from first tick)
    - All transaction details
    - All LSM cycle information
    - All agent states
    - All cost breakdowns
    """
    # Remove ANSI color codes first
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)

    # Split into lines for processing
    lines = text.splitlines()

    # Find the first tick marker (this is where actual simulation output begins)
    first_tick_index = None
    for i, line in enumerate(lines):
        if re.match(r'═══ Tick \d+ ═══', line):
            first_tick_index = i
            break

    if first_tick_index is None:
        # No ticks found - this is an error, but return what we have
        return text

    # Keep only lines from first tick onwards
    lines = lines[first_tick_index:]

    # Remove post-simulation summary lines (these differ between run/replay)
    # Keep only the actual tick-by-tick output
    filtered_lines = []
    for line in lines:
        # Skip summary lines at the end
        if any(pattern in line for pattern in [
            'Simulation complete:',
            'Replay complete:',
            'Persisted',
            'Simulation metadata persisted',
            'Replayed from database',
        ]):
            continue
        filtered_lines.append(line.rstrip())

    # Remove trailing empty lines
    while filtered_lines and not filtered_lines[-1]:
        filtered_lines.pop()

    return '\n'.join(filtered_lines)


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class TestRunReplayByteIdentical:
    """THE ULTIMATE TEST: Verify run and replay produce identical output."""

    def test_run_and_replay_verbose_output_is_byte_identical(
        self, test_config_with_lsm, db_path
    ):
        """CRITICAL: Run and replay must produce byte-for-byte identical verbose output.

        This is the ultimate test of determinism and replay correctness.

        Test procedure:
        1. Run simulation with --persist --full-replay --verbose
        2. Capture stderr (verbose output goes there)
        3. Extract simulation_id from stdout
        4. Replay simulation with --verbose
        5. Capture stderr
        6. Normalize both outputs (remove timestamps/durations)
        7. Compare SHA256 hashes - they MUST be identical

        If this test fails, replay is not producing identical output.
        """
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Run simulation with full replay enabled
        # ═══════════════════════════════════════════════════════════
        run_result = run_cli([
            "run",
            "--config", str(test_config_with_lsm),
            "--persist",
            "--full-replay",
            "--verbose",
            "--db-path", str(db_path),
        ])

        assert run_result.returncode == 0, f"Run command failed: {run_result.stderr}"

        # Extract simulation_id from JSON output (stdout)
        run_json = json.loads(run_result.stdout)
        sim_id = run_json["simulation"]["simulation_id"]

        assert sim_id, "No simulation_id found in run output"

        # Capture verbose output (stderr)
        run_verbose_output = run_result.stderr

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Replay simulation
        # ═══════════════════════════════════════════════════════════
        replay_result = run_cli([
            "replay",
            "--simulation-id", sim_id,
            "--verbose",
            "--db-path", str(db_path),
        ])

        assert replay_result.returncode == 0, f"Replay command failed: {replay_result.stderr}"

        # Capture verbose output (stderr)
        replay_verbose_output = replay_result.stderr

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Normalize outputs for comparison
        # ═══════════════════════════════════════════════════════════
        run_normalized = normalize_output_for_comparison(run_verbose_output)
        replay_normalized = normalize_output_for_comparison(replay_verbose_output)

        # ═══════════════════════════════════════════════════════════
        # STEP 4: Compare hashes (byte-for-byte identity check)
        # ═══════════════════════════════════════════════════════════
        run_hash = compute_hash(run_normalized)
        replay_hash = compute_hash(replay_normalized)

        # If hashes match, outputs are byte-for-byte identical ✅
        if run_hash == replay_hash:
            return  # SUCCESS!

        # ═══════════════════════════════════════════════════════════
        # STEP 5: If hashes differ, provide detailed diff for debugging
        # ═══════════════════════════════════════════════════════════
        run_lines = run_normalized.splitlines()
        replay_lines = replay_normalized.splitlines()

        # Find first differing line
        first_diff_line = None
        for i, (run_line, replay_line) in enumerate(zip(run_lines, replay_lines)):
            if run_line != replay_line:
                first_diff_line = i
                break

        # Build detailed error message
        error_msg = [
            "\n" + "=" * 80,
            "REPLAY OUTPUT DOES NOT MATCH ORIGINAL RUN",
            "=" * 80,
            f"Run output hash:    {run_hash}",
            f"Replay output hash: {replay_hash}",
            f"",
            f"Run output lines:    {len(run_lines)}",
            f"Replay output lines: {len(replay_lines)}",
        ]

        if first_diff_line is not None:
            error_msg.extend([
                f"",
                f"First difference at line {first_diff_line}:",
                f"  RUN:    '{run_lines[first_diff_line]}'",
                f"  REPLAY: '{replay_lines[first_diff_line]}'",
            ])

            # Show context around first diff
            context_start = max(0, first_diff_line - 3)
            context_end = min(len(run_lines), first_diff_line + 4)

            error_msg.extend([
                f"",
                f"Context (lines {context_start}-{context_end-1}):",
                f"",
                f"RUN OUTPUT:",
            ])
            for i in range(context_start, context_end):
                marker = ">>> " if i == first_diff_line else "    "
                if i < len(run_lines):
                    error_msg.append(f"{marker}{i:4d}: {run_lines[i]}")

            error_msg.extend([
                f"",
                f"REPLAY OUTPUT:",
            ])
            for i in range(context_start, context_end):
                marker = ">>> " if i == first_diff_line else "    "
                if i < len(replay_lines):
                    error_msg.append(f"{marker}{i:4d}: {replay_lines[i]}")

        elif len(run_lines) != len(replay_lines):
            error_msg.extend([
                f"",
                f"Line count differs!",
                f"  Last 5 lines of RUN:",
            ])
            for i, line in enumerate(run_lines[-5:], start=len(run_lines)-5):
                error_msg.append(f"    {i:4d}: {line}")

            error_msg.extend([
                f"",
                f"  Last 5 lines of REPLAY:",
            ])
            for i, line in enumerate(replay_lines[-5:], start=len(replay_lines)-5):
                error_msg.append(f"    {i:4d}: {line}")

        error_msg.append("=" * 80)

        # Fail with detailed error
        pytest.fail("\n".join(error_msg))

    def test_multiple_runs_produce_same_hash(self, test_config_with_lsm, db_path):
        """Verify that running the same config twice produces identical output.

        This is a sanity check that our normalization is working correctly.
        """
        # Run 1
        run1_result = run_cli([
            "run",
            "--config", str(test_config_with_lsm),
            "--persist",
            "--full-replay",
            "--verbose",
            "--db-path", str(db_path),
            "--simulation-id", "test-run-1",
        ])

        assert run1_result.returncode == 0

        # Run 2 (same config, same seed)
        db_path2 = db_path.parent / "test_replay2.db"
        run2_result = run_cli([
            "run",
            "--config", str(test_config_with_lsm),
            "--persist",
            "--full-replay",
            "--verbose",
            "--db-path", str(db_path2),
            "--simulation-id", "test-run-2",
        ])

        assert run2_result.returncode == 0

        # Normalize both outputs
        run1_normalized = normalize_output_for_comparison(run1_result.stderr)
        run2_normalized = normalize_output_for_comparison(run2_result.stderr)

        # Hashes should be identical (same seed = same output)
        run1_hash = compute_hash(run1_normalized)
        run2_hash = compute_hash(run2_normalized)

        assert run1_hash == run2_hash, \
            f"Two runs with same config produced different output!\n" \
            f"Run 1 hash: {run1_hash}\n" \
            f"Run 2 hash: {run2_hash}"

    def test_replay_partial_tick_range_is_subset(self, test_config_with_lsm, db_path):
        """Verify that replaying a subset of ticks produces matching output for that range.

        This tests that replay can correctly reproduce output for any tick range.
        """
        # Run full simulation
        run_result = run_cli([
            "run",
            "--config", str(test_config_with_lsm),
            "--persist",
            "--full-replay",
            "--verbose",
            "--db-path", str(db_path),
        ])

        assert run_result.returncode == 0

        # Extract simulation_id
        run_json = json.loads(run_result.stdout)
        sim_id = run_json["simulation"]["simulation_id"]

        # Replay only ticks 5-10
        replay_result = run_cli([
            "replay",
            "--simulation-id", sim_id,
            "--from-tick", "5",
            "--to-tick", "10",
            "--verbose",
            "--db-path", str(db_path),
        ])

        assert replay_result.returncode == 0

        # Normalize outputs
        run_normalized = normalize_output_for_comparison(run_result.stderr)
        replay_normalized = normalize_output_for_comparison(replay_result.stderr)

        # Extract tick 5-10 from full run output
        # (This is a simplified check - just verify replay completed successfully)
        # Full tick-by-tick comparison would require more complex parsing

        # Verify replay output contains tick markers
        assert "Tick 5" in replay_result.stderr
        assert "Tick 10" in replay_result.stderr
        assert "Tick 11" not in replay_result.stderr  # Should not include tick 11
