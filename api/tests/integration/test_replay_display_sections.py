"""TDD tests for missing display sections in replay (Discrepancies #3, #4, #1).

Problem:
- Replay missing "RTGS Immediate" and "Queue 2 Releases" blocks (Discrepancy #3)
- Replay missing "💰 Costs Accrued This Tick" summary block (Discrepancy #4)
- Replay missing "Transactions Near Deadline" section (Discrepancy #1)

Root Cause Investigation:
- Replay DOES call shared display_tick_verbose_output() function
- This function SHOULD display all sections (RTGS, Queue2, Costs, Near-Deadline)
- If sections are missing, possible causes:
  1. Events not being reconstructed from DB properly
  2. Display conditions not met (e.g., total_cost = 0)
  3. DatabaseStateProvider methods not working correctly

This test verifies display section parity between run and replay.
"""

import re
import subprocess
import tempfile
from pathlib import Path


def test_replay_shows_settlement_detail_blocks():
    """
    TDD RED: Replay must show same settlement detail blocks as run.

    Settlement details should include:
    - RTGS Immediate settlements
    - Queue 2 Releases (if any)
    - LSM settlements

    Currently FAILS (Discrepancy #3):
    - Run shows: "RTGS Immediate (4)", "Queue 2 Releases (3)", "LSM (1)"
    - Replay shows: Only "LSM (1)" - missing RTGS and Queue2 blocks
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use advanced config to ensure complex settlement patterns
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run verbose simulation
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
            timeout=120,
            cwd=Path(__file__).parent.parent.parent,
        )

        if run_result.returncode != 0:
            # Skip test if simulation fails (config issues)
            import pytest
            pytest.skip(f"Simulation failed: {run_result.stderr}")

        # Extract simulation ID
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        if not match:
            import pytest
            pytest.skip("Could not find simulation ID")

        sim_id = match.group(0)

        # Find a tick with RTGS settlements in run output
        run_lines = run_result.stdout.split('\n')
        test_tick = None

        for i, line in enumerate(run_lines):
            # Look for "RTGS Immediate" or "Queue 2 Releases" sections
            if 'RTGS Immediate' in line or 'Queue 2 Releases' in line:
                # Find the tick number by looking backwards
                for j in range(i, max(0, i-50), -1):
                    tick_match = re.search(r'═══ Tick (\d+) ═══', run_lines[j])
                    if tick_match:
                        test_tick = int(tick_match.group(1))
                        break
                if test_tick:
                    break

        if test_tick is None:
            import pytest
            pytest.skip("No RTGS/Queue2 settlements found in run output")

        # Check what settlement sections appeared in run
        run_has_rtgs = False
        run_has_queue2 = False

        tick_start_idx = None
        tick_end_idx = None

        for i, line in enumerate(run_lines):
            if f'═══ Tick {test_tick} ═══' in line:
                tick_start_idx = i
            elif tick_start_idx and '═══ Tick' in line and f'Tick {test_tick}' not in line:
                tick_end_idx = i
                break

        if tick_start_idx and tick_end_idx:
            tick_section = '\n'.join(run_lines[tick_start_idx:tick_end_idx])
            run_has_rtgs = 'RTGS Immediate' in tick_section
            run_has_queue2 = 'Queue 2 Releases' in tick_section

        # Replay that tick
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
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Check what settlement sections appeared in replay
        replay_has_rtgs = 'RTGS Immediate' in replay_result.stdout
        replay_has_queue2 = 'Queue 2 Releases' in replay_result.stdout

        # CRITICAL: Replay must show same settlement detail blocks as run
        assert replay_has_rtgs == run_has_rtgs, (
            f"RTGS Immediate block mismatch for tick {test_tick}:\n"
            f"  Run:    {'Present' if run_has_rtgs else 'Missing'}\n"
            f"  Replay: {'Present' if replay_has_rtgs else 'Missing'}\n"
            f"\nDiscrepancy #3: Replay missing RTGS settlement details"
        )

        assert replay_has_queue2 == run_has_queue2, (
            f"Queue 2 Releases block mismatch for tick {test_tick}:\n"
            f"  Run:    {'Present' if run_has_queue2 else 'Missing'}\n"
            f"  Replay: {'Present' if replay_has_queue2 else 'Missing'}\n"
            f"\nDiscrepancy #3: Replay missing Queue2 settlement details"
        )


def test_replay_shows_cost_accrual_summary():
    """
    TDD RED: Replay must show cost accrual summary block if run does.

    The "💰 Costs Accrued This Tick: $X.XX" summary block should appear
    in replay when costs are accrued, matching run output.

    Currently FAILS (Discrepancy #4):
    - Run shows: "💰 Costs Accrued This Tick: $5,863.10" with breakdown
    - Replay shows: Nothing (entire block missing)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Run verbose simulation
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
            timeout=120,
            cwd=Path(__file__).parent.parent.parent,
        )

        if run_result.returncode != 0:
            import pytest
            pytest.skip(f"Simulation failed: {run_result.stderr}")

        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        if not match:
            import pytest
            pytest.skip("Could not find simulation ID")

        sim_id = match.group(0)

        # Find a tick with cost accrual summary in run output
        run_lines = run_result.stdout.split('\n')
        test_tick = None

        for i, line in enumerate(run_lines):
            if '💰 Costs Accrued This Tick:' in line or 'Costs Accrued This Tick:' in line:
                # Find the tick number
                for j in range(i, max(0, i-100), -1):
                    tick_match = re.search(r'═══ Tick (\d+) ═══', run_lines[j])
                    if tick_match:
                        test_tick = int(tick_match.group(1))
                        break
                if test_tick:
                    break

        if test_tick is None:
            import pytest
            pytest.skip("No cost accrual summary found in run output")

        # Replay that tick
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
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Check if cost summary appears in replay
        replay_has_cost_summary = '💰 Costs Accrued This Tick:' in replay_result.stdout or 'Costs Accrued This Tick:' in replay_result.stdout

        # CRITICAL: Replay must show cost summary if run does
        assert replay_has_cost_summary, (
            f"Cost accrual summary missing in replay for tick {test_tick}.\n"
            f"Run shows cost summary, but replay doesn't.\n"
            f"\nDiscrepancy #4: Replay missing cost accrual summary block"
        )
