"""TDD tests for settlement count accuracy (Discrepancy #2).

Problem:
- Run shows 10 settlements in tick summary
- Replay shows 15 settlements in tick summary
- Suggests double-counting of LSM-settled transactions

Root Cause (hypothesis):
- Settlement counting logic differs between run and replay
- Possible double-counting: Settlement events + LSM tx_ids count
- LSM events may settle transactions WITHOUT emitting Settlement events

Fix Strategy:
- Verify Settlement event emission for LSM-settled transactions
- Ensure consistent counting: count unique settled transactions, not events
- Settlement count = count(Settlement events) + count(LSM-settled tx_ids)
  BUT only if Settlement events aren't also emitted for LSM settlements
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path


def test_replay_settlement_count_matches_run_verbose_output():
    """
    TDD RED: Settlement count in replay tick summary must match run.

    When replaying a tick with settlements:
    - Tick summary should show same settlement count as run
    - Example: If run shows "10 settlements", replay should show "10 settlements"

    Currently FAILS:
    - Run: "10 settlements settled"
    - Replay: "15 settlements settled"
    - Suggests double-counting of LSM settlements
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_minimal_eod.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run with verbose (to capture tick summaries)
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

        # Extract simulation ID from JSON in stdout
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match, "Could not find simulation ID"
        sim_id = match.group(0)

        # Find tick sections with both settlements and LSM - verbose output is in stderr
        # Format: "═══ Tick N ═══" ... "X in, Y settled, Z LSM"
        lines = run_result.stderr.split('\n')

        test_tick = None
        run_settlement_count = None
        run_lsm_count = None

        for i, line in enumerate(lines):
            # Find tick header
            tick_match = re.search(r'═══ Tick (\d+) ═══', line)
            if tick_match:
                tick_num = int(tick_match.group(1))

                # Look ahead for tick summary within next 200 lines
                for j in range(i, min(i + 200, len(lines))):
                    summary_match = re.search(r'(\d+) in.*?(\d+) settled.*?(\d+) LSM', lines[j])
                    if summary_match:
                        arrivals = int(summary_match.group(1))
                        settlements = int(summary_match.group(2))
                        lsm = int(summary_match.group(3))

                        # Prefer tick with both settlements and LSM
                        if settlements > 0 and lsm > 0:
                            test_tick = tick_num
                            run_settlement_count = settlements
                            run_lsm_count = lsm
                            break
                        # Otherwise accept any tick with settlements
                        elif settlements > 0 and test_tick is None:
                            test_tick = tick_num
                            run_settlement_count = settlements
                            run_lsm_count = lsm

                # If we found our ideal tick, stop searching
                if test_tick is not None and run_lsm_count > 0:
                    break

        assert test_tick is not None, (
            f"Could not find tick with settlements in run output.\n"
            f"Searched {len(lines)} lines. Sample output:\n"
            f"{run_result.stdout[:2000]}"
        )

        # Replay that specific tick
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--from-tick", str(test_tick),
                "--to-tick", str(test_tick),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Extract settlement count from replay tick summary - verbose output is in stderr
        replay_lines = replay_result.stderr.split('\n')
        replay_settlement_count = None
        replay_lsm_count = None

        for line in replay_lines:
            summary_match = re.search(r'(\d+) in.*?(\d+) settled.*?(\d+) LSM', line)
            if summary_match:
                replay_settlement_count = int(summary_match.group(2))
                replay_lsm_count = int(summary_match.group(3))
                break

        assert replay_settlement_count is not None, (
            f"No tick summary found in replay output.\n"
            f"Sample output:\n{replay_result.stdout[:2000]}"
        )

        # CRITICAL: Settlement counts must match
        assert replay_settlement_count == run_settlement_count, (
            f"Settlement count mismatch for tick {test_tick}:\n"
            f"  Run:    {run_settlement_count} settlements, {run_lsm_count} LSM\n"
            f"  Replay: {replay_settlement_count} settlements, {replay_lsm_count} LSM\n"
            f"\n"
            f"Discrepancy suggests double-counting of LSM-settled transactions.\n"
            f"Settlement count should represent unique settled transactions, not event count."
        )


def test_settlement_count_includes_lsm_settled_transactions():
    """
    TDD RED: Settlement count must include LSM-settled transactions.

    Settlements can occur through:
    1. RTGS immediate settlement (Settlement event)
    2. RTGS queue release (Settlement event)
    3. LSM bilateral offset (LsmBilateralOffset event with tx_ids)
    4. LSM multilateral cycle (LsmCycleSettlement event with tx_ids)

    Total settlements = count(Settlement events) + count(LSM tx_ids)

    BUT CRITICAL: Check if Settlement events are ALSO emitted for LSM-settled
    transactions. If yes, we'd double-count.

    This test verifies the counting logic is consistent.
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
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert run_result.returncode == 0

        # Extract simulation ID
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        sim_id = match.group(0)

        # Parse JSON output
        json_match = re.search(r'\{.*"simulation".*\}', run_result.stdout, re.DOTALL)
        assert json_match, "Could not find JSON in run output"
        run_json = json.loads(json_match.group(0))

        # Replay full simulation
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0

        # Parse JSON from replay
        replay_json_match = re.search(r'\{.*"simulation".*\}', replay_result.stdout, re.DOTALL)
        assert replay_json_match, "Could not find JSON in replay output"
        replay_json = json.loads(replay_json_match.group(0))

        # Compare settlement counts
        run_settlements = run_json['metrics']['total_settlements']
        replay_settlements = replay_json['metrics']['total_settlements']

        # CRITICAL: Total settlement counts must match
        assert replay_settlements == run_settlements, (
            f"Total settlement count mismatch:\n"
            f"  Run:    {run_settlements} settlements\n"
            f"  Replay: {replay_settlements} settlements\n"
            f"\n"
            f"This indicates settlement counting logic differs between run and replay.\n"
            f"Both should count: Settlement events + LSM-settled tx_ids (without double-counting)."
        )
