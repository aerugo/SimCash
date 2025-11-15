"""TDD test for near-deadline section display (Discrepancy #1).

Problem:
- Near-deadline warnings may not appear in replay
- Or they may show wrong tick counts
- "⚠️ Transactions Near Deadline" section missing or inaccurate

Root Cause (hypothesis):
- DatabaseStateProvider.get_near_deadline_transactions() may not be implemented correctly
- Or state_provider may not be querying database properly
- Or display conditions not met

This test verifies near-deadline section parity between run and replay.
"""

import re
import subprocess
import tempfile
from pathlib import Path


def test_near_deadline_section_appears_in_replay():
    """
    TDD RED: Near-deadline section must appear in replay if it appears in run.

    The "⚠️ Transactions Near Deadline" section should show:
    - Same transactions approaching deadlines
    - Same tick counts until deadline
    - Same warning messages

    Currently MAY FAIL (Discrepancy #1):
    - Run shows: "⚠️ 3 transactions approaching deadline"
    - Replay shows: Nothing (section missing)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use config that generates deadline pressure
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_near_deadline.yaml"
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

        # Extract simulation ID
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match, "Could not find simulation ID"
        sim_id = match.group(0)

        # Find a tick with near-deadline section in run
        run_lines = run_result.stdout.split('\n')
        test_tick = None
        run_has_near_deadline = False

        for i, line in enumerate(run_lines):
            # Look for near-deadline section
            if '⚠️' in line and 'Near Deadline' in line:
                # Find the tick number by looking backwards
                for j in range(i, max(0, i-100), -1):
                    tick_match = re.search(r'═══ Tick (\d+) ═══', run_lines[j])
                    if tick_match:
                        test_tick = int(tick_match.group(1))
                        run_has_near_deadline = True
                        break
                if test_tick:
                    break

        if test_tick is None:
            import pytest
            pytest.skip("No near-deadline section found in run output")

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

        # Check if near-deadline section appears in replay
        replay_has_near_deadline = '⚠️' in replay_result.stdout and 'Near Deadline' in replay_result.stdout

        # CRITICAL: Near-deadline section must match
        assert replay_has_near_deadline == run_has_near_deadline, (
            f"Near-deadline section mismatch for tick {test_tick}:\n"
            f"  Run:    {'Present' if run_has_near_deadline else 'Missing'}\n"
            f"  Replay: {'Present' if replay_has_near_deadline else 'Missing'}\n"
            f"\n"
            f"Discrepancy #1: Replay missing or incorrect near-deadline warnings"
        )


def test_near_deadline_transaction_counts_match():
    """
    TDD RED: Near-deadline transaction counts must match between run and replay.

    If near-deadline section appears, the number of transactions shown
    should be identical.

    Currently MAY FAIL:
    - Run: "⚠️ 3 transactions approaching deadline"
    - Replay: "⚠️ 1 transaction approaching deadline"
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "test_near_deadline.yaml"
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
            timeout=60,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert run_result.returncode == 0

        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match
        sim_id = match.group(0)

        # Find tick with near-deadline count
        run_lines = run_result.stdout.split('\n')
        test_tick = None
        run_near_deadline_count = None

        for i, line in enumerate(run_lines):
            # Look for near-deadline count pattern
            count_match = re.search(r'(\d+)\s+transaction.*?[Nn]ear.*?[Dd]eadline', line)
            if count_match:
                # Find the tick
                for j in range(i, max(0, i-100), -1):
                    tick_match = re.search(r'═══ Tick (\d+) ═══', run_lines[j])
                    if tick_match:
                        test_tick = int(tick_match.group(1))
                        run_near_deadline_count = int(count_match.group(1))
                        break
                if test_tick:
                    break

        if test_tick is None:
            import pytest
            pytest.skip("No near-deadline count found in run output")

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
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert replay_result.returncode == 0

        # Extract near-deadline count from replay
        replay_near_deadline_count = None
        for line in replay_result.stdout.split('\n'):
            count_match = re.search(r'(\d+)\s+transaction.*?[Nn]ear.*?[Dd]eadline', line)
            if count_match:
                replay_near_deadline_count = int(count_match.group(1))
                break

        if replay_near_deadline_count is None:
            import pytest
            pytest.skip("No near-deadline count found in replay output")

        # CRITICAL: Counts must match
        assert replay_near_deadline_count == run_near_deadline_count, (
            f"Near-deadline count mismatch for tick {test_tick}:\n"
            f"  Run:    {run_near_deadline_count} transactions\n"
            f"  Replay: {replay_near_deadline_count} transactions\n"
            f"\n"
            f"Suggests DatabaseStateProvider.get_near_deadline_transactions() "
            f"not querying correctly."
        )
