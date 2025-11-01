"""
DuckDB Write Functions

Batch write operations for persistence layer.

Provides functions to write simulation data to DuckDB using Polars DataFrames
for efficient batch operations with zero-copy Arrow format.

Phases 2-4: Transactions, Agent Metrics, and Policy Snapshots
"""

from typing import Any

import duckdb
import polars as pl

from .models import (
    TransactionRecord,
    DailyAgentMetricsRecord,
    PolicySnapshotRecord,
    PolicyDecisionRecord,
    TickAgentStateRecord,
    TickQueueSnapshotRecord,
)


def write_transactions(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    transactions: list[dict[str, Any]],
) -> int:
    """Write transactions to DuckDB.

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        transactions: List of transaction dicts from Rust FFI

    Returns:
        Number of transactions written

    Examples:
        >>> txs = orch.get_transactions_for_day(0)
        >>> count = write_transactions(conn, "sim-001", txs)
        >>> print(f"Wrote {count} transactions")
    """
    if not transactions:
        return 0

    # Create DataFrame
    df = pl.DataFrame(transactions)

    # Add simulation_id
    df = df.with_columns(
        pl.lit(simulation_id).alias("simulation_id")
    )

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO transactions SELECT * FROM df")

    return len(transactions)


def write_daily_agent_metrics(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_metrics: list[dict[str, Any]],
) -> int:
    """Write daily agent metrics to DuckDB.

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_metrics: List of agent metrics dicts from Rust FFI

    Returns:
        Number of agent metric records written

    Examples:
        >>> metrics = orch.get_daily_agent_metrics(0)
        >>> count = write_daily_agent_metrics(conn, "sim-001", metrics)
        >>> print(f"Wrote {count} agent metric records")
    """
    if not agent_metrics:
        return 0

    # Validate first record against schema (optional but helpful for debugging)
    # Note: simulation_id will be added, so we temporarily add it for validation
    test_record = {**agent_metrics[0], "simulation_id": simulation_id}
    DailyAgentMetricsRecord(**test_record)

    # Create DataFrame
    df = pl.DataFrame(agent_metrics)

    # Add simulation_id
    df = df.with_columns(
        pl.lit(simulation_id).alias("simulation_id")
    )

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")

    return len(agent_metrics)


def write_policy_snapshots(
    conn: duckdb.DuckDBPyConnection,
    snapshots: list[dict[str, Any]],
) -> int:
    """Write policy snapshots to DuckDB.

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.

    Args:
        conn: DuckDB connection
        snapshots: List of policy snapshot dicts matching PolicySnapshotRecord schema

    Returns:
        Number of policy snapshots written

    Examples:
        >>> snapshots = [
        ...     {
        ...         "simulation_id": "sim-001",
        ...         "agent_id": "BANK_A",
        ...         "snapshot_day": 0,
        ...         "snapshot_tick": 0,
        ...         "policy_hash": "a" * 64,
        ...         "policy_json": '{"type": "fifo"}',
        ...         "created_by": "init",
        ...     }
        ... ]
        >>> count = write_policy_snapshots(conn, snapshots)
    """
    if not snapshots:
        return 0

    # Validate first record against schema
    PolicySnapshotRecord(**snapshots[0])

    # Convert to Polars DataFrame
    df = pl.DataFrame(snapshots)

    # Ensure column order matches schema
    df = df.select([
        "simulation_id",
        "agent_id",
        "snapshot_day",
        "snapshot_tick",
        "policy_hash",
        "policy_json",
        "created_by",
    ])

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO policy_snapshots SELECT * FROM df")

    return len(snapshots)


# ============================================================================
# Full Replay Writers (Batched EOD Writes)
# ============================================================================


def write_policy_decisions_batch(
    conn: duckdb.DuckDBPyConnection,
    decisions: list[dict[str, Any]],
) -> int:
    """Write policy decisions in batch (called at EOD).

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.
    Collects all policy decisions for a day and writes them atomically.

    Args:
        conn: DuckDB connection
        decisions: List of policy decision dicts for the day

    Returns:
        Number of policy decisions written

    Examples:
        >>> decisions = [
        ...     {
        ...         "simulation_id": "sim-001",
        ...         "agent_id": "BANK_A",
        ...         "tick": 10,
        ...         "day": 0,
        ...         "decision_type": "submit",
        ...         "tx_id": "tx_00001",
        ...         "reason": None,
        ...         "num_splits": None,
        ...         "child_tx_ids": None,
        ...     }
        ... ]
        >>> count = write_policy_decisions_batch(conn, decisions)
    """
    if not decisions:
        return 0

    # Validate first record
    test_record = {**decisions[0]}
    test_record.pop("id", None)  # Remove auto-increment field if present
    PolicyDecisionRecord(**test_record)

    # Convert to Polars DataFrame
    df = pl.DataFrame(decisions)

    # Insert into DuckDB (zero-copy via Arrow)
    # Note: id column is auto-increment, so we exclude it from INSERT
    columns = [
        "simulation_id",
        "agent_id",
        "tick",
        "day",
        "decision_type",
        "tx_id",
        "reason",
        "num_splits",
        "child_tx_ids",
    ]
    df = df.select([col for col in columns if col in df.columns])

    # Specify columns explicitly to exclude auto-increment id column
    col_list = ", ".join(columns)
    conn.execute(f"INSERT INTO policy_decisions ({col_list}) SELECT * FROM df")

    return len(decisions)


def write_tick_agent_states_batch(
    conn: duckdb.DuckDBPyConnection,
    states: list[dict[str, Any]],
) -> int:
    """Write agent states in batch (called at EOD).

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.
    Collects all agent state snapshots for a day and writes them atomically.

    Args:
        conn: DuckDB connection
        states: List of agent state dicts for the day

    Returns:
        Number of agent state records written

    Examples:
        >>> states = [
        ...     {
        ...         "simulation_id": "sim-001",
        ...         "agent_id": "BANK_A",
        ...         "tick": 10,
        ...         "day": 0,
        ...         "balance": 1000000,
        ...         "balance_change": -5000,
        ...         "posted_collateral": 0,
        ...         "liquidity_cost": 100,
        ...         "delay_cost": 50,
        ...         "collateral_cost": 0,
        ...         "penalty_cost": 0,
        ...         "split_friction_cost": 0,
        ...         "liquidity_cost_delta": 10,
        ...         "delay_cost_delta": 5,
        ...         "collateral_cost_delta": 0,
        ...         "penalty_cost_delta": 0,
        ...         "split_friction_cost_delta": 0,
        ...     }
        ... ]
        >>> count = write_tick_agent_states_batch(conn, states)
    """
    if not states:
        return 0

    # Validate first record
    TickAgentStateRecord(**states[0])

    # Convert to Polars DataFrame
    df = pl.DataFrame(states)

    # Ensure column order matches schema
    df = df.select([
        "simulation_id",
        "agent_id",
        "tick",
        "day",
        "balance",
        "balance_change",
        "posted_collateral",
        "liquidity_cost",
        "delay_cost",
        "collateral_cost",
        "penalty_cost",
        "split_friction_cost",
        "liquidity_cost_delta",
        "delay_cost_delta",
        "collateral_cost_delta",
        "penalty_cost_delta",
        "split_friction_cost_delta",
    ])

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO tick_agent_states SELECT * FROM df")

    return len(states)


def write_tick_queue_snapshots_batch(
    conn: duckdb.DuckDBPyConnection,
    snapshots: list[dict[str, Any]],
) -> int:
    """Write queue snapshots in batch (called at EOD).

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.
    Collects all queue snapshots for a day and writes them atomically.

    Args:
        conn: DuckDB connection
        snapshots: List of queue snapshot dicts for the day

    Returns:
        Number of queue snapshot records written

    Examples:
        >>> snapshots = [
        ...     {
        ...         "simulation_id": "sim-001",
        ...         "agent_id": "BANK_A",
        ...         "tick": 10,
        ...         "queue_type": "queue1",
        ...         "position": 0,
        ...         "tx_id": "tx_00001",
        ...     }
        ... ]
        >>> count = write_tick_queue_snapshots_batch(conn, snapshots)
    """
    if not snapshots:
        return 0

    # Validate first record
    TickQueueSnapshotRecord(**snapshots[0])

    # Convert to Polars DataFrame
    df = pl.DataFrame(snapshots)

    # Ensure column order matches schema
    df = df.select([
        "simulation_id",
        "agent_id",
        "tick",
        "queue_type",
        "position",
        "tx_id",
    ])

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO tick_queue_snapshots SELECT * FROM df")

    return len(snapshots)
