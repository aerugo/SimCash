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
