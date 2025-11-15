"""TDD test for settlement count accuracy in verbose tick headers (Discrepancy #2).

Problem:
- Run shows: "✅ 10 transaction(s) settled:"
- Replay shows: "✅ 15 transaction(s) settled:"
- This is the header in log_settlement_details(), not the JSON total

Root Cause (hypothesis):
- Display function receives num_settlements parameter
- Run passes correct count (excluding LSM-settled transactions already counted)
- Replay may be double-counting or using wrong source

The Issue:
- Line 661 in output.py: console.print(f"✅ [green]{total} transaction(s) settled:[/green]")
- total = num_settlements (if provided) or calculated from events
- If num_settlements is wrong, header is wrong

This is different from Discrepancy #2 in tick summary (which we already tested).
This is about the settlement DETAIL header.
"""

import re
import subprocess
import tempfile
from pathlib import Path


def test_settlement_detail_header_count_matches():
    """
    TDD RED: Settlement detail header count must match between run and replay.

    The "✅ X transaction(s) settled:" header should show the same count
    in both run and replay for the same tick.

    Currently FAILS:
    - Run: "✅ 10 transaction(s) settled:"
    - Replay: "✅ 15 transaction(s) settled:"

    This suggests double-counting or wrong num_settlements being passed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a config that generates settlements and LSM activity
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

        # Extract simulation ID
        match = re.search(r'sim-[a-z0-9]+', run_result.stdout)
        assert match, "Could not find simulation ID"
        sim_id = match.group(0)

        # Find a tick with settlement detail header in run
        run_lines = run_result.stdout.split('\n')
        test_tick = None
        run_settlement_header_count = None

        for i, line in enumerate(run_lines):
            # Look for settlement detail header
            header_match = re.search(r'✅\s+(\d+)\s+transaction\(s\) settled:', line)
            if header_match:
                # Find the tick number by looking backwards
                for j in range(i, max(0, i-100), -1):
                    tick_match = re.search(r'═══ Tick (\d+) ═══', run_lines[j])
                    if tick_match:
                        test_tick = int(tick_match.group(1))
                        run_settlement_header_count = int(header_match.group(1))
                        break
                if test_tick:
                    break

        if test_tick is None:
            import pytest
            pytest.skip("No settlement detail header found in run output")

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

        # Find settlement detail header in replay
        replay_settlement_header_count = None
        for line in replay_result.stdout.split('\n'):
            header_match = re.search(r'✅\s+(\d+)\s+transaction\(s\) settled:', line)
            if header_match:
                replay_settlement_header_count = int(header_match.group(1))
                break

        if replay_settlement_header_count is None:
            import pytest
            pytest.skip("No settlement detail header found in replay output")

        # CRITICAL: Settlement header counts must match
        assert replay_settlement_header_count == run_settlement_header_count, (
            f"Settlement detail header mismatch for tick {test_tick}:\n"
            f"  Run:    ✅ {run_settlement_header_count} transaction(s) settled:\n"
            f"  Replay: ✅ {replay_settlement_header_count} transaction(s) settled:\n"
            f"\n"
            f"This header count comes from num_settlements passed to log_settlement_details().\n"
            f"Suggests replay is calculating num_settlements incorrectly for this tick."
        )
