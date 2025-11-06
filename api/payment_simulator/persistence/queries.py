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
            ticks_per_second,
            config_json
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
        "config_json": result[12],  # Full configuration JSON for replay
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


# ============================================================================
# Database-Driven Replay Queries
# ============================================================================


def get_transactions_by_tick(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> dict[str, list[dict[str, Any]]]:
    """Get all transactions that arrived or settled on a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        Dict with keys:
        - arrivals: Transactions that arrived on this tick
        - settlements: Transactions that settled on this tick

    Examples:
        >>> txs = get_transactions_by_tick(conn, "sim-001", 10)
        >>> len(txs["arrivals"])
        3
        >>> len(txs["settlements"])
        2
    """
    # Query arrivals for this tick
    arrivals_query = """
        SELECT
            tx_id,
            sender_id,
            receiver_id,
            amount,
            priority,
            is_divisible,
            arrival_tick,
            arrival_day,
            deadline_tick,
            status
        FROM transactions
        WHERE simulation_id = ? AND arrival_tick = ?
        ORDER BY tx_id
    """

    arrivals_result = conn.execute(arrivals_query, [simulation_id, tick]).fetchall()
    arrivals = [
        {
            "tx_id": row[0],
            "sender_id": row[1],
            "receiver_id": row[2],
            "amount": row[3],
            "priority": row[4],
            "is_divisible": row[5],
            "arrival_tick": row[6],
            "arrival_day": row[7],
            "deadline_tick": row[8],
            "status": row[9],
        }
        for row in arrivals_result
    ]

    # Query settlements for this tick
    settlements_query = """
        SELECT
            tx_id,
            sender_id,
            receiver_id,
            amount,
            amount_settled,
            settlement_tick,
            settlement_day,
            status,
            queue1_ticks,
            queue2_ticks,
            total_delay_ticks,
            delay_cost
        FROM transactions
        WHERE simulation_id = ? AND settlement_tick = ?
        ORDER BY tx_id
    """

    settlements_result = conn.execute(settlements_query, [simulation_id, tick]).fetchall()
    settlements = [
        {
            "tx_id": row[0],
            "sender_id": row[1],
            "receiver_id": row[2],
            "amount": row[3],
            "amount_settled": row[4],
            "settlement_tick": row[5],
            "settlement_day": row[6],
            "status": row[7],
            "queue1_ticks": row[8],
            "queue2_ticks": row[9],
            "total_delay_ticks": row[10],
            "delay_cost": row[11],
        }
        for row in settlements_result
    ]

    return {
        "arrivals": arrivals,
        "settlements": settlements,
    }


def get_collateral_events_by_tick(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Get all collateral events for a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        List of collateral event records

    Examples:
        >>> events = get_collateral_events_by_tick(conn, "sim-001", 10)
        >>> events[0]["action"]
        'post'
        >>> events[0]["amount"]
        1000000
    """
    query = """
        SELECT
            agent_id,
            tick,
            day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after
        FROM collateral_events
        WHERE simulation_id = ? AND tick = ?
        ORDER BY id
    """

    result = conn.execute(query, [simulation_id, tick]).fetchall()
    return [
        {
            "agent_id": row[0],
            "tick": row[1],
            "day": row[2],
            "action": row[3],
            "amount": row[4],
            "reason": row[5],
            "layer": row[6],
            "balance_before": row[7],
            "posted_collateral_before": row[8],
            "posted_collateral_after": row[9],
            "available_capacity_after": row[10],
        }
        for row in result
    ]


def get_lsm_cycles_by_tick(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Get all LSM cycles settled on a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        List of LSM cycle records

    Examples:
        >>> cycles = get_lsm_cycles_by_tick(conn, "sim-001", 10)
        >>> cycles[0]["cycle_type"]
        'bilateral'
        >>> cycles[0]["settled_value"]
        100000
    """
    import json

    query = """
        SELECT
            tick,
            day,
            cycle_type,
            cycle_length,
            agents,
            transactions,
            settled_value,
            total_value,
            tx_amounts,
            net_positions,
            max_net_outflow,
            max_net_outflow_agent
        FROM lsm_cycles
        WHERE simulation_id = ? AND tick = ?
        ORDER BY id
    """

    result = conn.execute(query, [simulation_id, tick]).fetchall()
    return [
        {
            "tick": row[0],
            "day": row[1],
            "cycle_type": row[2],
            "cycle_length": row[3],
            "agent_ids": json.loads(row[4]),  # Parse JSON array
            "tx_ids": json.loads(row[5]),     # Parse JSON array
            "settled_value": row[6],
            "total_value": row[7],
            "tx_amounts": json.loads(row[8]) if row[8] else [],
            "net_positions": json.loads(row[9]) if row[9] else {},
            "max_net_outflow": row[10],
            "max_net_outflow_agent": row[11],
        }
        for row in result
    ]


def get_tick_range_summary(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    from_tick: int,
    to_tick: int,
) -> dict[str, Any]:
    """Get aggregate statistics for a tick range.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        from_tick: Starting tick (inclusive)
        to_tick: Ending tick (inclusive)

    Returns:
        Dict with aggregate statistics:
        - total_arrivals: Total transactions that arrived
        - total_settlements: Total transactions that settled
        - total_cost: Total costs accrued
        - avg_delay: Average delay in ticks

    Examples:
        >>> summary = get_tick_range_summary(conn, "sim-001", 0, 10)
        >>> summary["total_arrivals"]
        100
        >>> summary["total_settlements"]
        95
    """
    query = """
        SELECT
            COUNT(*) FILTER (WHERE arrival_tick BETWEEN ? AND ?) as total_arrivals,
            COUNT(*) FILTER (WHERE settlement_tick BETWEEN ? AND ?) as total_settlements,
            SUM(delay_cost) FILTER (WHERE settlement_tick BETWEEN ? AND ?) as total_delay_cost,
            AVG(total_delay_ticks) FILTER (WHERE settlement_tick BETWEEN ? AND ?) as avg_delay_ticks
        FROM transactions
        WHERE simulation_id = ?
    """

    result = conn.execute(
        query,
        [
            from_tick, to_tick,  # arrivals
            from_tick, to_tick,  # settlements
            from_tick, to_tick,  # costs
            from_tick, to_tick,  # avg delay
            simulation_id,
        ]
    ).fetchone()

    if not result:
        return {
            "total_arrivals": 0,
            "total_settlements": 0,
            "total_delay_cost": 0,
            "avg_delay_ticks": 0.0,
        }

    return {
        "total_arrivals": result[0] if result[0] else 0,
        "total_settlements": result[1] if result[1] else 0,
        "total_delay_cost": result[2] if result[2] else 0,
        "avg_delay_ticks": result[3] if result[3] else 0.0,
    }


# ============================================================================
# Full Replay Queries
# ============================================================================


def get_policy_decisions_by_tick(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Get all policy decisions for a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        List of policy decision records

    Examples:
        >>> decisions = get_policy_decisions_by_tick(conn, "sim-001", 10)
        >>> decisions[0]["decision_type"]
        'submit'
    """
    query = """
        SELECT
            agent_id,
            tick,
            day,
            decision_type,
            tx_id,
            reason,
            num_splits,
            child_tx_ids
        FROM policy_decisions
        WHERE simulation_id = ? AND tick = ?
        ORDER BY id
    """

    result = conn.execute(query, [simulation_id, tick]).fetchall()
    return [
        {
            "agent_id": row[0],
            "tick": row[1],
            "day": row[2],
            "decision_type": row[3],
            "tx_id": row[4],
            "reason": row[5],
            "num_splits": row[6],
            "child_tx_ids": row[7],
        }
        for row in result
    ]


def get_tick_agent_states(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Get agent states for a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        List of agent state records

    Examples:
        >>> states = get_tick_agent_states(conn, "sim-001", 10)
        >>> states[0]["balance"]
        1000000
    """
    query = """
        SELECT
            agent_id,
            tick,
            day,
            balance,
            balance_change,
            posted_collateral,
            liquidity_cost,
            delay_cost,
            collateral_cost,
            penalty_cost,
            split_friction_cost,
            liquidity_cost_delta,
            delay_cost_delta,
            collateral_cost_delta,
            penalty_cost_delta,
            split_friction_cost_delta
        FROM tick_agent_states
        WHERE simulation_id = ? AND tick = ?
        ORDER BY agent_id
    """

    result = conn.execute(query, [simulation_id, tick]).fetchall()
    return [
        {
            "agent_id": row[0],
            "tick": row[1],
            "day": row[2],
            "balance": row[3],
            "balance_change": row[4],
            "posted_collateral": row[5],
            "liquidity_cost": row[6],
            "delay_cost": row[7],
            "collateral_cost": row[8],
            "penalty_cost": row[9],
            "split_friction_cost": row[10],
            "liquidity_cost_delta": row[11],
            "delay_cost_delta": row[12],
            "collateral_cost_delta": row[13],
            "penalty_cost_delta": row[14],
            "split_friction_cost_delta": row[15],
        }
        for row in result
    ]


def get_tick_queue_snapshots(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int,
) -> dict[str, dict[str, list[str]]]:
    """Get queue contents for a specific tick.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        tick: Tick number to query

    Returns:
        Dict mapping agent_id -> queue_type -> list of tx_ids in order

    Examples:
        >>> queues = get_tick_queue_snapshots(conn, "sim-001", 10)
        >>> queues["BANK_A"]["queue1"]
        ['tx_001', 'tx_002']
    """
    query = """
        SELECT
            agent_id,
            queue_type,
            position,
            tx_id
        FROM tick_queue_snapshots
        WHERE simulation_id = ? AND tick = ?
        ORDER BY agent_id, queue_type, position
    """

    result = conn.execute(query, [simulation_id, tick]).fetchall()

    # Organize by agent and queue type
    queues: dict[str, dict[str, list[str]]] = {}
    for row in result:
        agent_id = row[0]
        queue_type = row[1]
        tx_id = row[3]

        if agent_id not in queues:
            queues[agent_id] = {}
        if queue_type not in queues[agent_id]:
            queues[agent_id][queue_type] = []

        queues[agent_id][queue_type].append(tx_id)

    return queues
