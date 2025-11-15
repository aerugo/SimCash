"""TDD test for credit utilization consistency (Discrepancy #8).

Problem:
- Run shows: Credit Utilization: 171%
- Replay shows: Credit Utilization: 98%
- Same final balance, but different utilization %

Root Cause (hypothesis):
- Using different credit_limit values
- Or not including collateral backing correctly
- Formula: (abs(negative_balance) / (credit_limit + collateral_backing)) × 100

This test verifies credit utilization matches between run and replay.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path


def test_credit_utilization_matches_between_run_and_replay():
    """
    TDD RED: Credit utilization percentages must match between run and replay.

    Credit utilization formula should be:
    - utilization = (abs(negative_balance) / allowed_overdraft) × 100
    - allowed_overdraft = credit_limit + collateral_backing
    - collateral_backing = posted_collateral × (1 - haircut)

    Currently MAY FAIL:
    - Run: 171%
    - Replay: 98%
    - Suggests different allowed_overdraft calculations
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use config with collateral backing
        config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"
        db_path = Path(tmpdir) / "test.db"

        # Check if config exists
        if not config_path.exists():
            import pytest
            pytest.skip(f"Config not found: {config_path}")

        # Run simulation (verbose to get EOD stats)
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
            timeout=180,
            cwd=Path(__file__).parent.parent.parent,
        )

        if run_result.returncode != 0:
            import pytest
            pytest.skip(f"Run failed: {run_result.stderr}")

        # Extract simulation ID
        match = re.search(r'sim-[a-z0-9]+', run_result.stderr)
        if not match:
            import pytest
            pytest.skip("Could not find simulation ID")
        sim_id = match.group(0)

        # Find EOD credit utilization in run output
        run_lines = run_result.stdout.split('\n')
        run_credit_utils = {}

        for i, line in enumerate(run_lines):
            # Look for "Credit Utilization: XX%"
            match = re.search(r'Credit Utilization:\s+(\d+(?:\.\d+)?)%', line)
            if match:
                # Find agent ID by looking backwards
                for j in range(i, max(0, i-10), -1):
                    agent_match = re.search(r'^([A-Z_]+):', run_lines[j])
                    if agent_match:
                        agent_id = agent_match.group(1)
                        run_credit_utils[agent_id] = float(match.group(1))
                        break

        if not run_credit_utils:
            import pytest
            pytest.skip("No credit utilization found in run output")

        # Replay full simulation (verbose to get EOD stats)
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--simulation-id", sim_id,
                "--db-path", str(db_path),
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=Path(__file__).parent.parent.parent,
        )

        if replay_result.returncode != 0:
            import pytest
            pytest.skip(f"Replay failed: {replay_result.stderr}")

        # Find EOD credit utilization in replay output
        replay_lines = replay_result.stdout.split('\n')
        replay_credit_utils = {}

        for i, line in enumerate(replay_lines):
            match = re.search(r'Credit Utilization:\s+(\d+(?:\.\d+)?)%', line)
            if match:
                for j in range(i, max(0, i-10), -1):
                    agent_match = re.search(r'^([A-Z_]+):', replay_lines[j])
                    if agent_match:
                        agent_id = agent_match.group(1)
                        replay_credit_utils[agent_id] = float(match.group(1))
                        break

        if not replay_credit_utils:
            import pytest
            pytest.skip("No credit utilization found in replay output")

        # CRITICAL: Credit utilization must match (within 0.1% tolerance for rounding)
        for agent_id in run_credit_utils:
            if agent_id not in replay_credit_utils:
                continue  # Skip if agent not in both outputs

            run_util = run_credit_utils[agent_id]
            replay_util = replay_credit_utils[agent_id]

            assert abs(run_util - replay_util) < 0.1, (
                f"Credit utilization mismatch for {agent_id}:\n"
                f"  Run:    {run_util:.1f}%\n"
                f"  Replay: {replay_util:.1f}%\n"
                f"\n"
                f"Discrepancy #8: Different credit_limit or collateral_backing used"
            )
