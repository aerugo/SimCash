"""
DuckDB Write Functions

Batch write operations for persistence layer.

Provides functions to write simulation data to DuckDB using Polars DataFrames
for efficient batch operations with zero-copy Arrow format.

Phase 4: Policy Snapshot Tracking
"""

from typing import Any

import duckdb
import polars as pl

from .models import PolicySnapshotRecord


def write_policy_snapshots(
    conn: duckdb.DuckDBPyConnection,
    snapshots: list[dict[str, Any]],
) -> None:
    """Write policy snapshots to DuckDB.

    Uses Polars DataFrame for efficient batch writes via Apache Arrow.

    Args:
        conn: DuckDB connection
        snapshots: List of policy snapshot dicts matching PolicySnapshotRecord schema

    Examples:
        >>> snapshots = [
        ...     {
        ...         "simulation_id": "sim-001",
        ...         "agent_id": "BANK_A",
        ...         "snapshot_day": 0,
        ...         "snapshot_tick": 0,
        ...         "policy_hash": "a" * 64,
        ...         "policy_file_path": "backend/policies/BANK_A_policy_v1.json",
        ...         "policy_json": '{"type": "fifo"}',
        ...         "created_by": "init",
        ...     }
        ... ]
        >>> write_policy_snapshots(conn, snapshots)
    """
    if not snapshots:
        return

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
        "policy_file_path",
        "policy_json",
        "created_by",
    ])

    # Insert into DuckDB (zero-copy via Arrow)
    conn.execute("INSERT INTO policy_snapshots SELECT * FROM df")
