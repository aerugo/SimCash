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
) -> dict[str, Any]:
    """Get high-level simulation summary.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        Dictionary with keys:
        - simulation_id: Simulation identifier
        - num_days: Number of days simulated
        - total_transactions: Total transactions processed
        - settlement_rate: Overall settlement rate
        - total_volume: Total transaction value
        - avg_daily_cost: Average cost per day across all agents

    Examples:
        >>> summary = get_simulation_summary(conn, "sim-001")
        >>> summary["settlement_rate"]
        0.94
        >>> summary["total_transactions"]
        5000
    """
    # Get transaction stats
    tx_query = """
        SELECT
            COUNT(*) as total_transactions,
            CAST(SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as settlement_rate,
            SUM(amount) as total_volume
        FROM transactions
        WHERE simulation_id = ?
    """
    tx_result = conn.execute(tx_query, [simulation_id]).fetchone()

    # Get metrics stats
    metrics_query = """
        SELECT
            MAX(day) + 1 as num_days,
            AVG(total_cost) as avg_daily_cost
        FROM daily_agent_metrics
        WHERE simulation_id = ?
    """
    metrics_result = conn.execute(metrics_query, [simulation_id]).fetchone()

    return {
        "simulation_id": simulation_id,
        "total_transactions": tx_result[0] if tx_result[0] is not None else 0,
        "settlement_rate": tx_result[1] if tx_result[1] is not None else 0.0,
        "total_volume": tx_result[2] if tx_result[2] is not None else 0,
        "num_days": metrics_result[0] if metrics_result[0] is not None else 0,
        "avg_daily_cost": metrics_result[1] if metrics_result[1] is not None else 0,
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
