"""TDD Test: EOD Metrics Must Use Full Day Scope, Not Display Range

DISCREPANCY #5: EOD metrics showing only tick 299 stats instead of full day.

Expected:
- Replay with --from-tick 299 --to-tick 299 should show full Day 2 metrics
- Total transactions should be ~278 (all day), not 6 (just tick 299)
- Settlement rate should be realistic (~70%), not impossible (250%)

TDD RED: This test will FAIL because replay uses tick display range for EOD metrics.
"""

import tempfile
import subprocess
import json
from pathlib import Path
import pytest


def test_replay_eod_metrics_use_full_day_scope_not_display_range():
    """
    TDD RED: Replay EOD metrics must show full day statistics, not just displayed tick range.

    When replaying tick 199 of day 1 (last tick of day 1):
    - EOD banner should show full day 1 unsettled count
    - Total transactions should be ~100 (full day 1)
    - Settlement rate should be realistic (not >100%)

    Currently FAILS because replay queries only tick 199.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_minimal_eod.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run full simulation
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
            cwd=Path(__file__).parent.parent.parent,
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Extract simulation ID
        import re
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match, "Could not find simulation ID"
        sim_id = match.group(0)

        # Replay single tick from end of day 1 (tick 99 is last tick of day 1)
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--from-tick", "99",
                "--to-tick", "99",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Parse JSON from replay output
        replay_json = None
        for line in replay_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('{'):
                try:
                    replay_json = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        assert replay_json is not None, "Could not find JSON in replay output"

        # CRITICAL ASSERTIONS: EOD metrics must use full day scope, not display range

        # 1. Total transactions should be for full simulation, not just one tick
        total_tx = replay_json['metrics']['total_arrivals']
        assert total_tx > 50, (
            f"EOD total transactions shows {total_tx}, but this appears to be "
            f"only tick 99 arrivals (1-2). Should show full simulation arrivals (>50)."
        )

        # 2. Settlement rate must be realistic (not >100%)
        settlement_rate = replay_json['metrics']['settlement_rate']
        assert settlement_rate <= 1.0, (
            f"Settlement rate is {settlement_rate*100:.1f}% which is impossible. "
            f"This indicates replay is dividing settlements by arrivals from different scopes."
        )

        # 3. Check verbose output EOD banner (if verbose was enabled)
        # Note: This test doesn't use --verbose, so we won't have EOD banner
        # That's tested in the next test function


def test_replay_eod_banner_matches_run_when_replaying_eod_tick():
    """
    TDD RED: When replaying the last tick of a day, EOD banner must match run output.

    Currently FAILS because:
    - Run shows: "X unsettled, $Y in penalties"
    - Replay shows: "0 unsettled, $0 in penalties"
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_minimal_eod.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run with verbose
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert run_result.returncode == 0, f"Run failed: {run_result.stderr}"

        # Extract EOD banner from run (day 0, tick 99) - verbose output is in stderr
        # Note: tick 99 is last tick of day 0 (ticks 0-99 = day 0 with ticks_per_day=100)
        run_eod = [line for line in run_result.stderr.split('\n') if 'End of Day 0' in line and 'unsettled' in line]
        assert len(run_eod) > 0, "No EOD banner in run output"

        # Extract simulation ID from JSON in stdout
        import re
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match, "Could not find simulation ID"
        sim_id = match.group(0)

        # Replay tick 99 with verbose (last tick of day 0)
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--from-tick", "99",
                "--to-tick", "99",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Extract EOD banner from replay - verbose output is in stderr
        replay_eod = [line for line in replay_result.stderr.split('\n') if 'End of Day 0' in line and 'unsettled' in line]
        assert len(replay_eod) > 0, "No EOD banner in replay output"

        # Parse unsettled counts
        run_match = re.search(r'(\d+)\s+unsettled', run_eod[0])
        replay_match = re.search(r'(\d+)\s+unsettled', replay_eod[0])

        assert run_match, f"Could not parse run EOD: {run_eod[0]}"
        assert replay_match, f"Could not parse replay EOD: {replay_eod[0]}"

        run_unsettled = int(run_match.group(1))
        replay_unsettled = int(replay_match.group(1))

        # CRITICAL: Unsettled counts must match
        assert replay_unsettled == run_unsettled, (
            f"EOD unsettled count mismatch:\n"
            f"  Run:    {run_unsettled} unsettled\n"
            f"  Replay: {replay_unsettled} unsettled\n"
            f"Replay must show full day statistics, not just tick 99."
        )


def test_replay_day_summary_metrics_match_run():
    """
    TDD RED: Day summary metrics in replay must match run.

    Currently FAILS:
    - Run: Total Transactions: 278, Settled: 194 (69.8%)
    - Replay: Total Transactions: 6, Settled: 15 (250.0%)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_minimal_eod.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run simulation
        run_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "run",
                "--config", str(config_path),
                "--persist",
                "--db-path", str(db_path),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert run_result.returncode == 0

        # Extract simulation ID from JSON in stdout
        import re
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        sim_id = match.group(0)

        # Extract day 1 summary from run - verbose output is in stderr
        run_lines = run_result.stderr.split('\n')
        run_summary_start = None
        for i, line in enumerate(run_lines):
            if 'END OF DAY 1 SUMMARY' in line:
                run_summary_start = i
                break

        assert run_summary_start is not None, "No day 1 summary in run output"

        # Extract total transactions from run
        run_total_match = None
        for line in run_lines[run_summary_start:run_summary_start+20]:
            if 'Total Transactions:' in line:
                run_total_match = re.search(r'Total Transactions:\s+(\d+)', line)
                break

        assert run_total_match, "Could not find total transactions in run summary"
        run_total_tx = int(run_total_match.group(1))

        # Replay tick 99 (last tick of day 1)
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--from-tick", "99",
                "--to-tick", "99",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0

        # Extract day 1 summary from replay - verbose output is in stderr
        replay_lines = replay_result.stderr.split('\n')
        replay_summary_start = None
        for i, line in enumerate(replay_lines):
            if 'END OF DAY 1 SUMMARY' in line:
                replay_summary_start = i
                break

        assert replay_summary_start is not None, "No day 1 summary in replay output"

        # Extract total transactions from replay
        replay_total_match = None
        for line in replay_lines[replay_summary_start:replay_summary_start+20]:
            if 'Total Transactions:' in line:
                replay_total_match = re.search(r'Total Transactions:\s+(\d+)', line)
                break

        assert replay_total_match, "Could not find total transactions in replay summary"
        replay_total_tx = int(replay_total_match.group(1))

        # CRITICAL: Total transactions must match
        assert replay_total_tx == run_total_tx, (
            f"Day 1 total transactions mismatch:\n"
            f"  Run:    {run_total_tx} transactions\n"
            f"  Replay: {replay_total_tx} transactions\n"
            f"Replay is showing only tick 99 arrivals instead of full day 1."
        )
