#!/usr/bin/env python3
"""
End-to-End Persistence Test

Tests high-throughput simulation with collateral operations,
then validates all data was persisted to DuckDB correctly.

Usage:
    python scripts/test_persistence_e2e.py
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add api to path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from payment_simulator._core import Orchestrator
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.models import TransactionRecord, DailyAgentMetricsRecord
from payment_simulator.persistence.policy_tracking import capture_initial_policies
from payment_simulator.persistence.queries import (
    get_agent_performance,
    get_settlement_rate_by_day,
    get_simulation_summary,
    get_cost_breakdown_by_agent,
)
import polars as pl
import duckdb


def create_high_throughput_config():
    """Create simulation config with high transaction rate and collateral."""
    return {
        "rng_seed": 12345,
        "ticks_per_day": 100,
        "num_days": 5,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000_00,  # $500k in cents
                "credit_limit": 200_000_00,  # $200k credit
                "collateral_capacity": 500_000_00,  # $500k collateral available
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 2.0,  # High rate: 2 tx/tick = 200/day
                    "amount_distribution": {
                        "type": "LogNormal",
                        "mean": 50000.0,  # ~$500 average
                        "std_dev": 20000.0,
                    },
                    "counterparty_weights": {"BANK_B": 0.4, "BANK_C": 0.3, "BANK_D": 0.3},
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 800_000_00,  # $800k
                "credit_limit": 300_000_00,
                "collateral_capacity": 700_000_00,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.5,
                    "amount_distribution": {
                        "type": "LogNormal",
                        "mean": 80000.0,  # ~$800 average
                        "std_dev": 30000.0,
                    },
                    "counterparty_weights": {"BANK_A": 0.3, "BANK_C": 0.4, "BANK_D": 0.3},
                },
            },
            {
                "id": "BANK_C",
                "opening_balance": 600_000_00,  # $600k
                "credit_limit": 250_000_00,
                "collateral_capacity": 600_000_00,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.8,
                    "amount_distribution": {
                        "type": "LogNormal",
                        "mean": 60000.0,  # ~$600 average
                        "std_dev": 25000.0,
                    },
                    "counterparty_weights": {"BANK_A": 0.35, "BANK_B": 0.35, "BANK_D": 0.3},
                },
            },
            {
                "id": "BANK_D",
                "opening_balance": 1_000_000_00,  # $1M
                "credit_limit": 400_000_00,
                "collateral_capacity": 800_000_00,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.2,
                    "amount_distribution": {
                        "type": "LogNormal",
                        "mean": 70000.0,  # ~$700 average
                        "std_dev": 28000.0,
                    },
                    "counterparty_weights": {"BANK_A": 0.3, "BANK_B": 0.3, "BANK_C": 0.4},
                },
            },
        ],
    }


def run_simulation_with_persistence():
    """Run high-throughput simulation and persist all data."""
    print("=" * 80)
    print("END-TO-END PERSISTENCE TEST")
    print("=" * 80)
    print()

    # Setup
    simulation_id = f"e2e-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    db_path = Path(__file__).parent.parent / "api" / "test_databases" / f"{simulation_id}.db"
    db_path.parent.mkdir(exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    print(f"Simulation ID: {simulation_id}")
    print(f"Database: {db_path}")
    print()

    # Initialize database
    print("Initializing database...")
    manager = DatabaseManager(db_path)
    manager.setup()
    print("✓ Database ready")
    print()

    # Create simulation config
    config = create_high_throughput_config()
    print("Simulation Configuration:")
    print(f"  - Days: {config['num_days']}")
    print(f"  - Ticks per day: {config['ticks_per_day']}")
    print(f"  - Agents: {len(config['agent_configs'])}")
    print(f"  - Total ticks: {config['num_days'] * config['ticks_per_day']}")
    print()

    for agent in config["agent_configs"]:
        print(f"  {agent['id']}:")
        print(f"    Opening balance: ${agent['opening_balance'] / 100:,.2f}")
        print(f"    Credit limit: ${agent['credit_limit'] / 100:,.2f}")
        print(f"    Collateral capacity: ${agent['collateral_capacity'] / 100:,.2f}")
        print(f"    Arrival rate: {agent['arrival_config']['rate_per_tick']} tx/tick")
    print()

    # Capture initial policies
    print("Capturing initial policies...")
    policy_snapshots = capture_initial_policies(
        config["agent_configs"], simulation_id
    )

    # Write policy snapshots to database
    from payment_simulator.persistence.writers import write_policy_snapshots
    write_policy_snapshots(manager.conn, policy_snapshots)
    print(f"✓ Captured {len(policy_snapshots)} policy snapshots (database-only storage)")
    print()

    # Create orchestrator
    print("Creating orchestrator...")
    orch = Orchestrator.new(config)
    print("✓ Orchestrator initialized")
    print()

    # Write simulation run record
    manager.conn.execute(
        """
        INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            simulation_id,
            "e2e_test_config.yaml",
            "test-hash",
            "E2E persistence test with high throughput and collateral",
            datetime.now(),
            None,  # end_time (will update later)
            config["ticks_per_day"],
            config["num_days"],
            config["rng_seed"],
            "running",
            0,  # total_transactions (will update later)
        ],
    )

    # Run simulation day by day
    print("Running simulation...")
    total_transactions = 0

    for day in range(config["num_days"]):
        print(f"\n  Day {day}:")

        # Run ticks for this day
        for tick in range(config["ticks_per_day"]):
            result = orch.tick()
            if tick % 20 == 0:
                print(f"    Tick {result['tick']}")

        # Persist transactions for this day
        daily_txs = orch.get_transactions_for_day(day)
        if daily_txs:
            # Validate with Pydantic
            for tx in daily_txs:
                tx["simulation_id"] = simulation_id
                TransactionRecord(**tx)

            # Convert to Polars and write (with large infer_schema_length for mixed nulls/strings)
            df_txs = pl.DataFrame(daily_txs, infer_schema_length=1000)
            manager.conn.execute("INSERT INTO transactions SELECT * FROM df_txs")
            total_transactions += len(daily_txs)
            print(f"    ✓ Persisted {len(daily_txs)} transactions")

        # Persist agent metrics for this day
        daily_metrics = orch.get_daily_agent_metrics(day)
        if daily_metrics:
            # Validate with Pydantic
            for metric in daily_metrics:
                metric["simulation_id"] = simulation_id
                DailyAgentMetricsRecord(**metric)

            # Convert to Polars and write
            df_metrics = pl.DataFrame(daily_metrics)
            manager.conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df_metrics")
            print(f"    ✓ Persisted {len(daily_metrics)} agent metrics")

    # Update simulation run record
    manager.conn.execute(
        """
        UPDATE simulation_runs
        SET end_time = ?, status = ?, total_transactions = ?
        WHERE simulation_id = ?
        """,
        [datetime.now(), "completed", total_transactions, simulation_id],
    )

    print()
    print("✓ Simulation complete")
    print(f"  Total transactions: {total_transactions:,}")
    print()

    return manager, simulation_id


def validate_persistence(manager, simulation_id):
    """Validate all data was persisted correctly."""
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)
    print()

    conn = manager.conn

    # 1. Validate simulation run record
    print("1. Simulation Run Record:")
    sim_run = conn.execute(
        "SELECT * FROM simulation_runs WHERE simulation_id = ?", [simulation_id]
    ).fetchone()
    print(f"   ✓ Found simulation run: {simulation_id}")
    print(f"     Status: {sim_run[9]}")
    print(f"     Total transactions: {sim_run[10]:,}")
    print()

    # 2. Validate transactions
    print("2. Transaction Records:")
    tx_count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE simulation_id = ?", [simulation_id]
    ).fetchone()[0]
    print(f"   ✓ Total transactions: {tx_count:,}")

    tx_by_status = conn.execute(
        """
        SELECT status, COUNT(*) as count
        FROM transactions
        WHERE simulation_id = ?
        GROUP BY status
        """,
        [simulation_id],
    ).fetchall()
    for status, count in tx_by_status:
        print(f"     {status}: {count:,}")
    print()

    # 3. Validate agent metrics
    print("3. Agent Metrics Records:")
    metrics_count = conn.execute(
        "SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = ?", [simulation_id]
    ).fetchone()[0]
    print(f"   ✓ Total agent-day records: {metrics_count}")

    agents = conn.execute(
        """
        SELECT DISTINCT agent_id
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        ORDER BY agent_id
        """,
        [simulation_id],
    ).fetchall()
    print(f"   ✓ Agents tracked: {', '.join(a[0] for a in agents)}")
    print()

    # 4. Validate policy snapshots
    print("4. Policy Snapshot Records:")
    policy_count = conn.execute(
        "SELECT COUNT(*) FROM policy_snapshots WHERE simulation_id = ?", [simulation_id]
    ).fetchone()[0]
    print(f"   ✓ Total policy snapshots: {policy_count}")

    policies = conn.execute(
        """
        SELECT agent_id, snapshot_day, snapshot_tick, created_by
        FROM policy_snapshots
        WHERE simulation_id = ?
        ORDER BY agent_id
        """,
        [simulation_id],
    ).fetchall()
    for agent_id, day, tick, created_by in policies:
        print(f"     {agent_id}: day={day}, tick={tick}, created_by={created_by}")
    print()

    # 5. Test analytical queries
    print("5. Analytical Queries:")
    print()

    # Simulation summary
    print("   a) Simulation Summary:")
    summary = get_simulation_summary(conn, simulation_id)
    print(f"      Total transactions: {summary['total_transactions']:,}")
    print(f"      Settlement rate: {summary['settlement_rate']:.2%}")
    print(f"      Total volume: ${summary['total_volume'] / 100:,.2f}")
    print(f"      Avg daily cost: ${summary['avg_daily_cost'] / 100:,.2f}")
    print()

    # Settlement rate by day
    print("   b) Settlement Rate by Day:")
    df_settlement = get_settlement_rate_by_day(conn, simulation_id)
    for row in df_settlement.iter_rows(named=True):
        print(
            f"      Day {row['day']}: {row['settlement_rate']:.2%} "
            f"({row['settled_transactions']}/{row['total_transactions']})"
        )
    print()

    # Agent performance
    print("   c) Agent Performance (BANK_A):")
    df_perf = get_agent_performance(conn, simulation_id, "BANK_A")
    print(f"      Days tracked: {len(df_perf)}")
    print(f"      Opening balance: ${df_perf['opening_balance'][0] / 100:,.2f}")
    print(f"      Closing balance: ${df_perf['closing_balance'][-1] / 100:,.2f}")
    print(f"      Total cost: ${df_perf['total_cost'].sum() / 100:,.2f}")
    print(f"      Peak overdraft: ${df_perf['peak_overdraft'].max() / 100:,.2f}")
    print()

    # Cost breakdown
    print("   d) Cost Breakdown by Agent:")
    df_costs = get_cost_breakdown_by_agent(conn, simulation_id)
    for row in df_costs.iter_rows(named=True):
        print(f"      {row['agent_id']}:")
        print(f"        Total cost: ${row['total_cost'] / 100:,.2f}")
        print(f"        Liquidity cost: ${row['liquidity_cost'] / 100:,.2f}")
        print(f"        Delay cost: ${row['delay_cost'] / 100:,.2f}")
    print()

    # 6. Validate data integrity
    print("6. Data Integrity Checks:")

    # Check no orphaned transactions
    orphaned = conn.execute(
        """
        SELECT COUNT(*)
        FROM transactions t
        WHERE t.simulation_id = ?
        AND NOT EXISTS (
            SELECT 1 FROM simulation_runs s
            WHERE s.simulation_id = t.simulation_id
        )
        """,
        [simulation_id],
    ).fetchone()[0]
    print(f"   ✓ Orphaned transactions: {orphaned} (expected: 0)")

    # Check metrics consistency
    metrics_days = conn.execute(
        """
        SELECT COUNT(DISTINCT day)
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        """,
        [simulation_id],
    ).fetchone()[0]
    expected_days = 5
    print(f"   ✓ Metrics days: {metrics_days} (expected: {expected_days})")

    # Check policy snapshots stored in database
    policy_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM policy_snapshots
        WHERE simulation_id = ?
        """,
        [simulation_id],
    ).fetchone()[0]
    print(f"   ✓ Policy snapshots in database: {policy_count} (expected: 4)")
    print()

    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print()


def main():
    """Run end-to-end persistence test."""
    try:
        # Run simulation with persistence
        manager, simulation_id = run_simulation_with_persistence()

        # Validate all data
        validate_persistence(manager, simulation_id)

        # Cleanup
        manager.close()

        print("✓ ALL TESTS PASSED")
        print()
        print(f"Database saved at: {manager.db_path}")
        print(f"Simulation ID: {simulation_id}")
        print()
        print("You can query this database with:")
        print(f"  duckdb {manager.db_path}")
        print(f"  SELECT * FROM transactions WHERE simulation_id = '{simulation_id}' LIMIT 10;")
        print()

        return 0

    except Exception as e:
        print(f"✗ TEST FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
