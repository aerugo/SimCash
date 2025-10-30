"""
Analytical Query Interface

Pre-defined analytical queries for simulation data analysis.
All functions return Polars DataFrames for efficient data processing.

Phase 5: Query Interface & Analytics
"""

from typing import Any

import duckdb
import polars as pl


# ============================================================================
# Agent Performance Queries
# ============================================================================


def get_agent_performance(
    conn: duckdb.DuckDBPyConnection, simulation_id: str, agent_id: str
) -> pl.DataFrame:
    """Get agent performance metrics over time.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Agent identifier

    Returns:
        Polars DataFrame with columns:
        - day: Day number
        - opening_balance: Balance at start of day
        - closing_balance: Balance at end of day
        - min_balance: Minimum balance during day
        - max_balance: Maximum balance during day
        - peak_overdraft: Maximum overdraft used
        - total_cost: Total costs incurred
        - liquidity_cost: Overdraft costs
        - delay_cost: Queue delay costs
        - num_settled: Transactions settled
        - num_dropped: Transactions dropped

    Examples:
        >>> df = get_agent_performance(conn, "sim-001", "BANK_A")
        >>> df["day"]
        [0, 1, 2, 3, 4]
        >>> df["total_cost"]
        [10000, 12000, 11500, 13000, 12200]
    """
    query = """
        SELECT
            day,
            opening_balance,
            closing_balance,
            min_balance,
            max_balance,
            peak_overdraft,
            total_cost,
            liquidity_cost,
            delay_cost,
            collateral_cost,
            split_friction_cost,
            deadline_penalty_cost,
            num_settled,
            num_dropped,
            num_arrivals,
            num_sent,
            num_received,
            queue1_peak_size,
            queue1_eod_size
        FROM daily_agent_metrics
        WHERE simulation_id = ? AND agent_id = ?
        ORDER BY day
    """

    return conn.execute(query, [simulation_id, agent_id]).pl()


# ============================================================================
# Transaction Analysis Queries
# ============================================================================


def get_settlement_rate_by_day(
    conn: duckdb.DuckDBPyConnection, simulation_id: str
) -> pl.DataFrame:
    """Calculate settlement rate per day.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Polars DataFrame with columns:
        - day: Day number
        - total_transactions: Total transactions arrived
        - settled_transactions: Transactions successfully settled
        - settlement_rate: Fraction settled (0-1)

    Examples:
        >>> df = get_settlement_rate_by_day(conn, "sim-001")
        >>> df["settlement_rate"]
        [0.95, 0.92, 0.94, 0.96]
    """
    query = """
        SELECT
            arrival_day as day,
            COUNT(*) as total_transactions,
            SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) as settled_transactions,
            CAST(SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as settlement_rate
        FROM transactions
        WHERE simulation_id = ?
        GROUP BY arrival_day
        ORDER BY arrival_day
    """

    return conn.execute(query, [simulation_id]).pl()


def get_daily_transaction_summary(
    conn: duckdb.DuckDBPyConnection, simulation_id: str
) -> pl.DataFrame:
    """Summarize transactions by day with counts and amounts.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Polars DataFrame with columns:
        - day: Day number
        - total_count: Total transactions
        - settled_count: Settled transactions
        - pending_count: Pending transactions
        - dropped_count: Dropped transactions
        - total_amount: Total transaction value
        - settled_amount: Value of settled transactions

    Examples:
        >>> df = get_daily_transaction_summary(conn, "sim-001")
        >>> df["total_count"]
        [150, 148, 152, 147]
    """
    query = """
        SELECT
            arrival_day as day,
            COUNT(*) as total_count,
            SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) as settled_count,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN status = 'dropped' THEN 1 ELSE 0 END) as dropped_count,
            SUM(amount) as total_amount,
            SUM(amount_settled) as settled_amount
        FROM transactions
        WHERE simulation_id = ?
        GROUP BY arrival_day
        ORDER BY arrival_day
    """

    return conn.execute(query, [simulation_id]).pl()


def get_transaction_delays(
    conn: duckdb.DuckDBPyConnection, simulation_id: str
) -> pl.DataFrame:
    """Calculate transaction delay statistics by day.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Polars DataFrame with columns:
        - day: Day number
        - avg_delay_ticks: Average delay for settled transactions
        - max_delay_ticks: Maximum delay observed
        - p50_delay_ticks: Median delay (50th percentile)
        - p95_delay_ticks: 95th percentile delay

    Examples:
        >>> df = get_transaction_delays(conn, "sim-001")
        >>> df["avg_delay_ticks"]
        [12.5, 15.2, 13.8, 14.1]
    """
    query = """
        SELECT
            arrival_day as day,
            AVG(total_delay_ticks) as avg_delay_ticks,
            MAX(total_delay_ticks) as max_delay_ticks,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_delay_ticks) as p50_delay_ticks,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_delay_ticks) as p95_delay_ticks
        FROM transactions
        WHERE simulation_id = ? AND status = 'settled'
        GROUP BY arrival_day
        ORDER BY arrival_day
    """

    return conn.execute(query, [simulation_id]).pl()


# ============================================================================
# System-Wide Metrics
# ============================================================================


def get_simulation_summary(
    conn: duckdb.DuckDBPyConnection, simulation_id: str
) -> dict[str, Any] | None:
    """Get high-level simulation summary from simulations table.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Dictionary with simulation metadata, or None if not found

    Examples:
        >>> summary = get_simulation_summary(conn, "sim-001")
        >>> summary["settlement_rate"]
        0.94
        >>> summary["total_arrivals"]
        1000
    """
    # Query simulations table
    query = """
        SELECT
            simulation_id,
            config_file,
            rng_seed,
            ticks_per_day,
            num_days,
            num_agents,
            status,
            total_arrivals,
            total_settlements,
            total_cost_cents,
            duration_seconds,
            ticks_per_second
        FROM simulations
        WHERE simulation_id = ?
    """

    result = conn.execute(query, [simulation_id]).fetchone()

    if not result:
        return None

    # Calculate settlement rate
    settlement_rate = 0.0
    if result[7] and result[7] > 0:  # total_arrivals
        settlement_rate = result[8] / result[7]  # total_settlements / total_arrivals

    total_arrivals = result[7] if result[7] else 0
    total_settlements = result[8] if result[8] else 0
    total_cost_cents = result[9] if result[9] else 0
    num_days = result[4]

    return {
        "simulation_id": result[0],
        "config_file": result[1],
        "rng_seed": result[2],
        "ticks_per_day": result[3],
        "num_days": num_days,
        "num_agents": result[5],
        "status": result[6],
        "total_arrivals": total_arrivals,
        "total_settlements": total_settlements,
        "total_transactions": total_arrivals,  # Alias for compatibility
        "settlement_rate": settlement_rate,
        "total_cost_cents": total_cost_cents,
        "total_volume": total_arrivals,  # Total transaction volume (same as arrivals)
        "avg_daily_cost": total_cost_cents / num_days if num_days > 0 else 0.0,
        "duration_seconds": result[10] if result[10] else 0.0,
        "ticks_per_second": result[11] if result[11] else 0.0,
    }


def list_simulation_runs(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """List all simulation runs in database.

    Args:
        conn: DuckDB connection

    Returns:
        Polars DataFrame with columns:
        - simulation_id: Simulation identifier
        - config_name: Configuration file name
        - description: Simulation description
        - start_time: When simulation started
        - end_time: When simulation ended
        - status: Simulation status
        - total_transactions: Number of transactions processed
        - num_days: Number of days simulated

    Examples:
        >>> df = list_simulation_runs(conn)
        >>> df["simulation_id"]
        ["sim-001", "sim-002", "sim-003"]
    """
    query = """
        SELECT
            simulation_id,
            config_name,
            description,
            start_time,
            end_time,
            status,
            total_transactions,
            num_days
        FROM simulation_runs
        ORDER BY start_time DESC
    """

    return conn.execute(query).pl()


# ============================================================================
# Cost Analysis Queries
# ============================================================================


def get_cost_breakdown_by_agent(
    conn: duckdb.DuckDBPyConnection, simulation_id: str
) -> pl.DataFrame:
    """Break down costs by category for each agent.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Polars DataFrame with columns:
        - agent_id: Agent identifier
        - liquidity_cost: Total overdraft costs
        - delay_cost: Total queue delay costs
        - collateral_cost: Total collateral opportunity costs
        - split_friction_cost: Total split friction costs
        - deadline_penalty_cost: Total deadline penalties
        - total_cost: Sum of all costs

    Examples:
        >>> df = get_cost_breakdown_by_agent(conn, "sim-001")
        >>> df.filter(pl.col("agent_id") == "BANK_A")["total_cost"]
        [150000]
    """
    query = """
        SELECT
            agent_id,
            SUM(liquidity_cost) as liquidity_cost,
            SUM(delay_cost) as delay_cost,
            SUM(collateral_cost) as collateral_cost,
            SUM(split_friction_cost) as split_friction_cost,
            SUM(deadline_penalty_cost) as deadline_penalty_cost,
            SUM(total_cost) as total_cost
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        GROUP BY agent_id
        ORDER BY total_cost DESC
    """

    return conn.execute(query, [simulation_id]).pl()


def get_daily_cost_trends(
    conn: duckdb.DuckDBPyConnection, simulation_id: str, agent_id: str
) -> pl.DataFrame:
    """Show cost trends over time for a specific agent.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Agent identifier

    Returns:
        Polars DataFrame with columns:
        - day: Day number
        - total_cost: Total cost for the day
        - liquidity_cost: Overdraft cost
        - delay_cost: Queue delay cost
        - collateral_cost: Collateral opportunity cost
        - split_friction_cost: Split friction cost
        - deadline_penalty_cost: Deadline penalty

    Examples:
        >>> df = get_daily_cost_trends(conn, "sim-001", "BANK_A")
        >>> df["total_cost"]
        [10000, 12000, 11500, 13000]
    """
    query = """
        SELECT
            day,
            total_cost,
            liquidity_cost,
            delay_cost,
            collateral_cost,
            split_friction_cost,
            deadline_penalty_cost
        FROM daily_agent_metrics
        WHERE simulation_id = ? AND agent_id = ?
        ORDER BY day
    """

    return conn.execute(query, [simulation_id, agent_id]).pl()


# ============================================================================
# Phase 5: Query Interface & Analytics
# ============================================================================


def list_simulations(
    conn: duckdb.DuckDBPyConnection,
    status: str | None = None,
) -> pl.DataFrame:
    """List all simulation runs with optional status filter.

    Args:
        conn: DuckDB connection
        status: Optional status filter ('running', 'completed', 'failed')

    Returns:
        Polars DataFrame with simulation metadata sorted by started_at DESC

    Examples:
        >>> df = list_simulations(conn)
        >>> df = list_simulations(conn, status='completed')
    """
    query = "SELECT * FROM simulations"

    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)

    query += " ORDER BY started_at DESC"

    return conn.execute(query, params).pl()


def get_agent_daily_metrics(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_id: str,
) -> pl.DataFrame:
    """Get daily time series metrics for a specific agent.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Agent identifier

    Returns:
        Polars DataFrame with daily metrics sorted by day

    Examples:
        >>> df = get_agent_daily_metrics(conn, "sim-001", "BANK_A")
        >>> print(df['closing_balance'])
    """
    query = """
        SELECT *
        FROM daily_agent_metrics
        WHERE simulation_id = ? AND agent_id = ?
        ORDER BY day
    """

    return conn.execute(query, [simulation_id, agent_id]).pl()


def get_transactions(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    status: str | None = None,
) -> pl.DataFrame:
    """Query transactions with optional status filter.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        status: Optional filter by status ('pending', 'settled', 'dropped')

    Returns:
        Polars DataFrame with transaction records

    Examples:
        >>> all_txs = get_transactions(conn, "sim-001")
        >>> settled = get_transactions(conn, "sim-001", status="settled")
    """
    query = "SELECT * FROM transactions WHERE simulation_id = ?"
    params = [simulation_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY arrival_tick"

    return conn.execute(query, params).pl()


def get_transaction_statistics(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
) -> dict[str, Any]:
    """Get aggregate transaction statistics for a simulation.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Dict with aggregate statistics:
        - total_count: Total transactions
        - settled_count: Number settled
        - settlement_rate: Fraction settled (0-1)
        - avg_delay_ticks: Average delay in ticks

    Examples:
        >>> stats = get_transaction_statistics(conn, "sim-001")
        >>> print(stats['settlement_rate'])
    """
    query = """
        SELECT
            COUNT(*) as total_count,
            SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) as settled_count,
            CAST(SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as settlement_rate,
            AVG(total_delay_ticks) as avg_delay_ticks
        FROM transactions
        WHERE simulation_id = ?
    """

    result = conn.execute(query, [simulation_id]).fetchone()

    if not result or result[0] == 0:
        return {
            "total_count": 0,
            "settled_count": 0,
            "settlement_rate": 0.0,
            "avg_delay_ticks": 0.0,
        }

    return {
        "total_count": result[0],
        "settled_count": result[1],
        "settlement_rate": result[2] if result[2] else 0.0,
        "avg_delay_ticks": result[3] if result[3] else 0.0,
    }


def compare_simulations(
    conn: duckdb.DuckDBPyConnection,
    sim_id1: str,
    sim_id2: str,
) -> dict[str, Any]:
    """Compare key metrics between two simulations.

    Args:
        conn: DuckDB connection
        sim_id1: First simulation ID
        sim_id2: Second simulation ID

    Returns:
        Dict with three keys:
        - sim1: Metrics for first simulation
        - sim2: Metrics for second simulation
        - delta: Differences (sim2 - sim1)

    Examples:
        >>> comparison = compare_simulations(conn, "sim-fifo", "sim-deadline")
        >>> print(comparison['delta']['settlement_rate'])
    """
    # Get metadata for both simulations
    query = """
        SELECT
            total_arrivals,
            total_settlements,
            total_cost_cents,
            CAST(total_settlements AS DOUBLE) / total_arrivals as settlement_rate
        FROM simulations
        WHERE simulation_id = ?
    """

    result1 = conn.execute(query, [sim_id1]).fetchone()
    result2 = conn.execute(query, [sim_id2]).fetchone()

    if not result1 or not result2:
        raise ValueError("One or both simulations not found")

    sim1_data = {
        "simulation_id": sim_id1,
        "total_arrivals": result1[0],
        "total_settlements": result1[1],
        "total_cost": result1[2],
        "settlement_rate": result1[3],
    }

    sim2_data = {
        "simulation_id": sim_id2,
        "total_arrivals": result2[0],
        "total_settlements": result2[1],
        "total_cost": result2[2],
        "settlement_rate": result2[3],
    }

    delta = {
        "settlement_rate": sim2_data["settlement_rate"] - sim1_data["settlement_rate"],
        "total_cost": sim2_data["total_cost"] - sim1_data["total_cost"],
    }

    return {
        "sim1": sim1_data,
        "sim2": sim2_data,
        "delta": delta,
    }


def compare_agent_performance(
    conn: duckdb.DuckDBPyConnection,
    sim_id1: str,
    sim_id2: str,
    agent_id: str,
) -> pl.DataFrame:
    """Compare a specific agent's performance across two simulations.

    Args:
        conn: DuckDB connection
        sim_id1: First simulation ID
        sim_id2: Second simulation ID
        agent_id: Agent identifier

    Returns:
        Polars DataFrame with side-by-side daily metrics

    Examples:
        >>> df = compare_agent_performance(conn, "sim-001", "sim-002", "BANK_A")
        >>> # DataFrame has columns: day, sim1_total_cost, sim2_total_cost, cost_delta
    """
    # Get metrics for both simulations
    metrics1 = get_agent_daily_metrics(conn, sim_id1, agent_id)
    metrics2 = get_agent_daily_metrics(conn, sim_id2, agent_id)

    # Select relevant columns and rename
    df1 = metrics1.select([
        pl.col("day"),
        pl.col("total_cost").alias("sim1_total_cost"),
    ])

    df2 = metrics2.select([
        pl.col("day"),
        pl.col("total_cost").alias("sim2_total_cost"),
    ])

    # Join on day and calculate delta
    comparison = df1.join(df2, on="day", how="inner")
    comparison = comparison.with_columns(
        (pl.col("sim2_total_cost") - pl.col("sim1_total_cost")).alias("cost_delta")
    )

    return comparison


def get_agent_policy_history(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_id: str,
) -> pl.DataFrame:
    """Get policy change history for an agent.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Agent identifier

    Returns:
        Polars DataFrame with policy snapshots ordered by time

    Examples:
        >>> df = get_agent_policy_history(conn, "sim-001", "BANK_A")
        >>> # Shows all policy changes over time
    """
    query = """
        SELECT
            snapshot_day,
            snapshot_tick,
            policy_hash,
            policy_json,
            created_by
        FROM policy_snapshots
        WHERE simulation_id = ? AND agent_id = ?
        ORDER BY snapshot_day, snapshot_tick
    """

    return conn.execute(query, [simulation_id, agent_id]).pl()


def get_policy_at_day(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    agent_id: str,
    day: int,
) -> dict[str, Any] | None:
    """Get the policy that was active for an agent on a specific day.

    This answers the provenance question: "What policy was agent X using on day Y?"

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        agent_id: Agent identifier
        day: Day number to query

    Returns:
        Dict with policy snapshot data including parsed policy_config, or None if not found

    Examples:
        >>> policy = get_policy_at_day(conn, "sim-001", "BANK_A", 5)
        >>> print(policy['policy_config'])
    """
    import json

    query = """
        SELECT
            snapshot_day,
            snapshot_tick,
            policy_hash,
            policy_json,
            created_by
        FROM policy_snapshots
        WHERE simulation_id = ?
          AND agent_id = ?
          AND snapshot_day <= ?
        ORDER BY snapshot_day DESC, snapshot_tick DESC
        LIMIT 1
    """

    result = conn.execute(query, [simulation_id, agent_id, day]).fetchone()

    if not result:
        return None

    # Parse the JSON string to get policy config
    policy_config = json.loads(result[3])

    return {
        "snapshot_day": result[0],
        "snapshot_tick": result[1],
        "policy_hash": result[2],
        "policy_config": policy_config,
        "created_by": result[4],
    }
