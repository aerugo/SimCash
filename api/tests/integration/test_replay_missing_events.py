"""TDD tests for missing event types in replay output.

These tests verify that replay displays the same event types as run mode.
Following strict TDD: tests are written to FAIL first, then we implement fixes.

Missing events (from docs/plans/breaking_replay_identity.md):
1. TransactionWentOverdue - "❌ Transaction Went Overdue" standalone messages
2. QueuedRtgs - "📋 queued in RTGS" blocks
3. CostAccrual per-tick summary - "💰 Costs Accrued This Tick" summary block
"""

import subprocess
from pathlib import Path
import tempfile
import pytest


def run_simulation_verbose(config_path: str, db_path: str, tick: int = None) -> tuple[str, str]:
    """Run simulation with verbose output.

    Returns:
        tuple: (stdout, stderr) where stdout contains JSON and stderr contains verbose output
    """
    cmd = [
        "uv", "run", "payment-sim", "run",
        "--config", config_path,
        "--persist",
        "--db-path", db_path,
        "--full-replay",
        "--verbose",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Run failed: {result.stderr}")

    return (result.stdout, result.stderr)


def replay_simulation_verbose(simulation_id: str, db_path: str, from_tick: int, to_tick: int) -> tuple[str, str]:
    """Replay simulation with verbose output.

    Returns:
        tuple: (stdout, stderr) where stdout contains JSON and stderr contains verbose output
    """
    cmd = [
        "uv", "run", "payment-sim", "replay",
        "--simulation-id", simulation_id,
        "--db-path", db_path,
        "--from-tick", str(from_tick),
        "--to-tick", str(to_tick),
        "--verbose",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Replay failed: {result.stderr}")

    return (result.stdout, result.stderr)


def extract_simulation_id(run_output: str | tuple[str, str]) -> str:
    """Extract simulation ID from run output.

    Args:
        run_output: Either a string (stdout) or tuple of (stdout, stderr)

    Returns:
        Simulation ID
    """
    import re

    # Handle tuple return from run_simulation_verbose()
    if isinstance(run_output, tuple):
        stdout, stderr = run_output
    else:
        stdout = run_output

    match = re.search(r'"simulation_id":\s*"([^"]+)"', stdout)
    if not match:
        raise ValueError("Could not find simulation_id in output")
    return match.group(1)


@pytest.fixture
def test_config():
    """Use advanced policy crisis config which has overdue transactions."""
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"
    return str(config_path)


@pytest.fixture
def temp_db():
    """Create temporary database path for testing."""
    # Use TemporaryDirectory to get a clean path without creating the file
    # DuckDB will create the file when the simulation runs
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        yield db_path
        # Cleanup happens automatically when tmpdir context exits


# ============================================================================
# TEST 1: TransactionWentOverdue Events Must Be Displayed
# ============================================================================

def test_replay_shows_transaction_went_overdue_events(test_config, temp_db):
    """Replay must display 'Transaction Went Overdue' messages like run does.

    TDD: This test FAILS because replay.py doesn't load or display
    TransactionWentOverdue events, even though they exist in the database.

    Expected in run output:
        ❌ Transaction Went Overdue: TX 098e8f44...
           CORRESPONDENT_HUB → REGIONAL_TRUST | $1,702.23
           Deadline: Tick 298 | Current: Tick 299 | 1 tick late
           💸 Deadline Penalty Charged: $2,500.00

    Expected in replay output:
        SAME (but currently missing)
    """
    # Run simulation - returns (stdout, stderr)
    run_stdout, run_stderr = run_simulation_verbose(test_config, temp_db)
    simulation_id = extract_simulation_id(run_stdout)

    # Find a tick with overdue events
    # From check_events.py we know tick 239 has TransactionWentOverdue
    import duckdb
    conn = duckdb.connect(temp_db)

    # Find first tick with TransactionWentOverdue event
    result = conn.execute(
        "SELECT MIN(tick) FROM simulation_events WHERE event_type = 'TransactionWentOverdue'"
    ).fetchone()

    if not result or result[0] is None:
        pytest.skip("No TransactionWentOverdue events in this simulation")

    overdue_tick = result[0]

    # Get overdue event details
    overdue_event = conn.execute(
        "SELECT tx_id, details FROM simulation_events WHERE event_type = 'TransactionWentOverdue' AND tick = ? LIMIT 1",
        [overdue_tick]
    ).fetchone()

    tx_id_short = overdue_event[0][:8]

    # Close connection before replay to avoid lock conflicts
    conn.close()

    # Replay that specific tick - returns (stdout, stderr)
    replay_stdout, replay_stderr = replay_simulation_verbose(
        simulation_id, temp_db, overdue_tick, overdue_tick
    )

    # ASSERT: Replay must show overdue event - verbose output is in stderr
    assert "Transaction Went Overdue" in replay_stderr, (
        f"Replay output for tick {overdue_tick} does not contain 'Transaction Went Overdue' message. "
        f"Expected to see overdue notification for TX {tx_id_short}"
    )

    # ASSERT: Show the transaction ID
    assert tx_id_short in replay_stderr, (
        f"Replay output does not mention TX {tx_id_short} that went overdue"
    )

    # ASSERT: Show deadline penalty
    assert "Deadline Penalty" in replay_stderr or "💸" in replay_stderr, (
        "Replay output does not show deadline penalty cost"
    )


# ============================================================================
# TEST 2: QueuedRtgs Events Must Be Displayed
# ============================================================================

def test_replay_shows_queued_rtgs_events(test_config, temp_db):
    """Replay must display '📋 queued in RTGS' blocks like run does.

    TDD: This test FAILS because replay.py doesn't load or display
    QueuedRtgs events.

    Expected in run output:
        📋 1 transaction(s) queued in RTGS:
           • TX 485d8a80: CORRESPONDENT_HUB | Insufficient balance

    Expected in replay output:
        SAME (but currently missing)
    """
    # Run simulation - returns (stdout, stderr)
    run_stdout, run_stderr = run_simulation_verbose(test_config, temp_db)
    simulation_id = extract_simulation_id(run_stdout)

    # Find a tick with QueuedRtgs event
    import duckdb
    conn = duckdb.connect(temp_db)

    result = conn.execute(
        "SELECT MIN(tick) FROM simulation_events WHERE event_type = 'QueuedRtgs'"
    ).fetchone()

    if not result or result[0] is None:
        pytest.skip("No QueuedRtgs events in this simulation")

    queued_tick = result[0]

    # Get queued event details
    queued_event = conn.execute(
        "SELECT tx_id FROM simulation_events WHERE event_type = 'QueuedRtgs' AND tick = ? LIMIT 1",
        [queued_tick]
    ).fetchone()

    tx_id_short = queued_event[0][:8]

    # Close connection before replay to avoid lock conflicts
    conn.close()

    # Replay that tick - returns (stdout, stderr)
    replay_stdout, replay_stderr = replay_simulation_verbose(
        simulation_id, temp_db, queued_tick, queued_tick
    )

    # ASSERT: Replay must show queued in RTGS block - verbose output is in stderr
    assert "queued in RTGS" in replay_stderr, (
        f"Replay output for tick {queued_tick} does not contain 'queued in RTGS' block. "
        "Expected to see queued transactions notification."
    )

    # ASSERT: Show the transaction ID
    assert tx_id_short in replay_stderr, (
        f"Replay output does not mention TX {tx_id_short} that was queued in RTGS"
    )


# ============================================================================
# TEST 3: Cost Accrual Summary Must Be Displayed
# ============================================================================

def test_replay_shows_cost_accrual_summary(test_config, temp_db):
    """Replay must display '💰 Costs Accrued This Tick' summary like run does.

    TDD: This test FAILS because replay.py loads CostAccrual events but
    doesn't display the per-tick summary block.

    Expected in run output:
        💰 Costs Accrued This Tick: $5,863.10

           CORRESPONDENT_HUB: $3,133.47
           • Liquidity: $265.00
           • Delay: $2,868.47

           REGIONAL_TRUST: $2,729.63
           • Liquidity: $276.95
           • Delay: $2,452.68

    Expected in replay output:
        SAME (but currently missing)
    """
    # Run simulation - returns (stdout, stderr)
    run_stdout, run_stderr = run_simulation_verbose(test_config, temp_db)
    simulation_id = extract_simulation_id(run_stdout)

    # Find a tick with non-zero cost accruals
    import duckdb
    conn = duckdb.connect(temp_db)

    # Find tick where total cost > 0
    result = conn.execute("""
        SELECT tick
        FROM simulation_events
        WHERE event_type = 'CostAccrual'
        GROUP BY tick
        HAVING COUNT(*) >= 2  -- At least 2 agents
        LIMIT 1
    """).fetchone()

    if not result:
        pytest.skip("No CostAccrual events with multiple agents found")

    cost_tick = result[0]

    # Close connection before replay to avoid lock conflicts
    conn.close()

    # Replay that tick - returns (stdout, stderr)
    replay_stdout, replay_stderr = replay_simulation_verbose(
        simulation_id, temp_db, cost_tick, cost_tick
    )

    # ASSERT: Replay must show cost summary - verbose output is in stderr
    assert "Costs Accrued This Tick" in replay_stderr, (
        f"Replay output for tick {cost_tick} does not contain 'Costs Accrued This Tick' summary. "
        "Expected to see per-tick cost breakdown."
    )

    # ASSERT: Show breakdown by cost type
    # At least one of these cost types should appear
    has_cost_detail = any(
        keyword in replay_stderr
        for keyword in ["Liquidity:", "Delay:", "Penalty:", "Collateral:"]
    )

    assert has_cost_detail, (
        "Replay output does not show cost breakdown (liquidity, delay, etc.)"
    )


# ============================================================================
# INTEGRATION TEST: All Missing Events Together
# ============================================================================

def test_replay_shows_all_event_types_that_run_shows(test_config, temp_db):
    """Replay must show ALL event types that run shows (comprehensive check).

    TDD: This test ensures no event types are silently dropped in replay.
    """
    # Run full simulation - returns (stdout, stderr)
    run_stdout, run_stderr = run_simulation_verbose(test_config, temp_db)
    simulation_id = extract_simulation_id((run_stdout, run_stderr))

    # Replay full simulation - returns (stdout, stderr)
    replay_stdout, replay_stderr = replay_simulation_verbose(
        simulation_id, temp_db, from_tick=0, to_tick=299
    )

    # Check for each missing event type indicator in stderr (where verbose output goes)
    missing_in_replay = []

    # Check 1: TransactionWentOverdue
    if "Transaction Went Overdue" in run_stderr:
        if "Transaction Went Overdue" not in replay_stderr:
            missing_in_replay.append("TransactionWentOverdue events")

    # Check 2: QueuedRtgs
    if "queued in RTGS" in run_stderr:
        if "queued in RTGS" not in replay_stderr:
            missing_in_replay.append("QueuedRtgs events")

    # Check 3: CostAccrual summary
    if "Costs Accrued This Tick" in run_stderr:
        if "Costs Accrued This Tick" not in replay_stderr:
            missing_in_replay.append("CostAccrual summary")

    # ASSERT: All event types must be present
    assert not missing_in_replay, (
        f"Replay is missing the following event types that appear in run: {', '.join(missing_in_replay)}. "
        "Replay must display ALL event types that run displays."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
