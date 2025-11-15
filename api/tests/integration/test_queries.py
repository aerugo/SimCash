"""
Integration Tests for Query Interface (Phase 5)

Tests analytical query functions for simulation data analysis.

TDD Phase: RED
These tests define requirements before implementation.
Expected to FAIL until Phase 5.2 implementation.
"""

import time
from pathlib import Path

import duckdb
import polars as pl
import pytest
from payment_simulator.persistence.connection import DatabaseManager

# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


@pytest.fixture
def seeded_database(db_path):
    """Create database with test data for queries."""
    manager = DatabaseManager(db_path)
    manager.setup()

    # Seed simulation run
    manager.conn.execute(
        """
        INSERT INTO simulation_runs VALUES (
            'test-sim-001',
            'test_config.yaml',
            'hash123',
            'Test simulation',
            '2025-01-01 00:00:00',
            '2025-01-01 01:00:00',
            100,  -- ticks_per_day
            3,    -- num_days
            12345,  -- rng_seed
            'completed',
            150  -- total_transactions
        )
    """
    )

    # Seed simulations table for queries (Phase 5)
    manager.conn.execute(
        """
        INSERT INTO simulations VALUES (
            'test-sim-001',          -- simulation_id
            'test_config.yaml',      -- config_file
            'hash123',               -- config_hash
            12345,                   -- rng_seed
            100,                     -- ticks_per_day
            3,                       -- num_days
            2,                       -- num_agents
            NULL,                    -- config_json (optional)
            'completed',             -- status
            '2025-01-01 00:00:00',   -- started_at
            '2025-01-01 01:00:00',   -- completed_at
            150,                     -- total_arrivals
            90,                      -- total_settlements (30 settled per day * 3 days)
            50000,                   -- total_cost_cents
            3600.0,                  -- duration_seconds (1 hour)
            8.33                     -- ticks_per_second (300 ticks / 3600 seconds)
        )
    """
    )

    # Seed transactions for 3 days
    transactions = []
    tx_id = 1
    for day in range(3):
        # Each day: 30 settled, 10 pending, 10 dropped
        for i in range(30):
            transactions.append(
                f"('test-sim-001', 'TX{tx_id}', 'BANK_A', 'BANK_B', {100000 + i*1000}, "
                f"5, true, {day*100 + i}, {day}, {day*100 + 99}, {day*100 + i + 10}, "
                f"{day}, 'settled', NULL, {100000 + i*1000}, 10, 5, 15, {i*100})"
            )
            tx_id += 1

        for i in range(10):
            transactions.append(
                f"('test-sim-001', 'TX{tx_id}', 'BANK_A', 'BANK_B', {50000 + i*1000}, "
                f"3, true, {day*100 + i + 30}, {day}, {day*100 + 99}, NULL, "
                f"NULL, 'pending', NULL, 0, 20, 0, 20, 0)"
            )
            tx_id += 1

        for i in range(10):
            transactions.append(
                f"('test-sim-001', 'TX{tx_id}', 'BANK_A', 'BANK_B', {30000 + i*1000}, "
                f"2, false, {day*100 + i + 40}, {day}, {day*100 + 99}, NULL, "
                f"NULL, 'dropped', 'insufficient_liquidity', 0, 15, 0, 15, 0)"
            )
            tx_id += 1

    tx_values = ",\n        ".join(transactions)
    manager.conn.execute(
        f"""
        INSERT INTO transactions (
            simulation_id, tx_id, sender_id, receiver_id, amount, priority, is_divisible,
            arrival_tick, arrival_day, deadline_tick, settlement_tick, settlement_day,
            status, drop_reason, amount_settled, queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
        ) VALUES
        {tx_values}
    """
    )

    # Seed agent metrics for 3 days
    metrics = []
    for day in range(3):
        # BANK_A metrics
        metrics.append(
            f"('test-sim-001', 'BANK_A', {day}, "
            f"{1000000 + day*10000}, {1000000 + (day+1)*10000}, "
            f"{950000 + day*5000}, {1050000 + day*15000}, "
            f"500000, {20000 + day*5000}, "
            f"0, 0, 0, 5000000, 0, 0, "
            f"50, 30, 20, 30, 10, "
            f"5, 3, "
            f"{10000 + day*1000}, {5000 + day*500}, 0, {1000 + day*100}, {500 + day*50}, "
            f"{16500 + day*1650})"
        )

        # BANK_B metrics
        metrics.append(
            f"('test-sim-001', 'BANK_B', {day}, "
            f"{2000000 + day*20000}, {2000000 + (day+1)*20000}, "
            f"{1950000 + day*10000}, {2050000 + day*30000}, "
            f"300000, {10000 + day*2000}, "
            f"0, 0, 0, 3000000, 0, 0, "
            f"20, 30, 10, 20, 5, "
            f"3, 2, "
            f"{5000 + day*500}, {2000 + day*200}, 0, {500 + day*50}, {200 + day*20}, "
            f"{7700 + day*770})"
        )

    metrics_values = ",\n        ".join(metrics)
    manager.conn.execute(
        f"""
        INSERT INTO daily_agent_metrics (
            simulation_id, agent_id, day,
            opening_balance, closing_balance, min_balance, max_balance,
            unsecured_cap, peak_overdraft,
            opening_posted_collateral, closing_posted_collateral, peak_posted_collateral,
            collateral_capacity, num_collateral_posts, num_collateral_withdrawals,
            num_arrivals, num_sent, num_received, num_settled, num_dropped,
            queue1_peak_size, queue1_eod_size,
            liquidity_cost, delay_cost, collateral_cost, split_friction_cost,
            deadline_penalty_cost, total_cost
        ) VALUES
        {metrics_values}
    """
    )

    yield manager

    manager.close()


# ============================================================================
# Agent Performance Queries
# ============================================================================


class TestAgentPerformanceQueries:
    """Test agent performance analytical queries."""

    def test_get_agent_performance_returns_dataframe(self, seeded_database):
        """Should return agent metrics over time as Polars DataFrame."""
        from payment_simulator.persistence.queries import get_agent_performance

        df = get_agent_performance(seeded_database.conn, "test-sim-001", "BANK_A")

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3  # 3 days
        assert "day" in df.columns
        assert "closing_balance" in df.columns
        assert "peak_overdraft" in df.columns
        assert "total_cost" in df.columns

    def test_get_agent_performance_ordered_by_day(self, seeded_database):
        """Results should be ordered by day."""
        from payment_simulator.persistence.queries import get_agent_performance

        df = get_agent_performance(seeded_database.conn, "test-sim-001", "BANK_A")

        days = df["day"].to_list()
        assert days == [0, 1, 2]

    def test_get_agent_performance_filters_by_simulation_and_agent(
        self, seeded_database
    ):
        """Should filter to specific simulation and agent."""
        from payment_simulator.persistence.queries import get_agent_performance

        df = get_agent_performance(seeded_database.conn, "test-sim-001", "BANK_B")

        assert len(df) == 3
        # Verify it's BANK_B data (different opening balance)
        assert df["opening_balance"][0] == 2000000  # BANK_B opening balance

    def test_get_agent_performance_empty_for_nonexistent_agent(self, seeded_database):
        """Should return empty DataFrame for nonexistent agent."""
        from payment_simulator.persistence.queries import get_agent_performance

        df = get_agent_performance(seeded_database.conn, "test-sim-001", "BANK_Z")

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 0


# ============================================================================
# Transaction Analysis Queries
# ============================================================================


class TestTransactionAnalysisQueries:
    """Test transaction analysis queries."""

    def test_get_settlement_rate_by_day(self, seeded_database):
        """Should calculate settlement rate per day."""
        from payment_simulator.persistence.queries import get_settlement_rate_by_day

        df = get_settlement_rate_by_day(seeded_database.conn, "test-sim-001")

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3  # 3 days
        assert "day" in df.columns
        assert "settlement_rate" in df.columns
        assert "total_transactions" in df.columns
        assert "settled_transactions" in df.columns

        # Verify rates are valid (0-1)
        rates = df["settlement_rate"].to_list()
        assert all(0 <= rate <= 1 for rate in rates)

        # Each day: 30 settled / 50 total = 0.6
        assert all(abs(rate - 0.6) < 0.01 for rate in rates)

    def test_get_daily_transaction_summary(self, seeded_database):
        """Should summarize transactions by day."""
        from payment_simulator.persistence.queries import get_daily_transaction_summary

        df = get_daily_transaction_summary(seeded_database.conn, "test-sim-001")

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3
        assert "day" in df.columns
        assert "total_count" in df.columns
        assert "settled_count" in df.columns
        assert "pending_count" in df.columns
        assert "dropped_count" in df.columns
        assert "total_amount" in df.columns
        assert "settled_amount" in df.columns

        # Verify counts for day 0
        day0 = df.filter(pl.col("day") == 0)
        assert day0["total_count"][0] == 50
        assert day0["settled_count"][0] == 30
        assert day0["pending_count"][0] == 10
        assert day0["dropped_count"][0] == 10

    def test_get_transaction_delays(self, seeded_database):
        """Should calculate transaction delay metrics."""
        from payment_simulator.persistence.queries import get_transaction_delays

        df = get_transaction_delays(seeded_database.conn, "test-sim-001")

        assert isinstance(df, pl.DataFrame)
        assert "day" in df.columns
        assert "avg_delay_ticks" in df.columns
        assert "max_delay_ticks" in df.columns
        assert "p50_delay_ticks" in df.columns
        assert "p95_delay_ticks" in df.columns


# ============================================================================
# System-Wide Metrics
# ============================================================================


class TestSystemMetricsQueries:
    """Test system-wide metrics queries."""

    def test_get_simulation_summary(self, seeded_database):
        """Should return high-level simulation summary."""
        from payment_simulator.persistence.queries import get_simulation_summary

        summary = get_simulation_summary(seeded_database.conn, "test-sim-001")

        assert isinstance(summary, dict)
        assert summary["simulation_id"] == "test-sim-001"
        assert summary["num_days"] == 3
        assert summary["total_transactions"] == 150
        assert summary["settlement_rate"] > 0
        assert "total_volume" in summary
        assert "avg_daily_cost" in summary

    def test_list_simulation_runs(self, seeded_database):
        """Should list all simulation runs."""
        from payment_simulator.persistence.queries import list_simulation_runs

        df = list_simulation_runs(seeded_database.conn)

        assert isinstance(df, pl.DataFrame)
        assert len(df) >= 1
        assert "simulation_id" in df.columns
        assert "config_name" in df.columns
        assert "start_time" in df.columns
        assert "status" in df.columns
        assert "total_transactions" in df.columns


# ============================================================================
# Cost Analysis Queries
# ============================================================================


class TestCostAnalysisQueries:
    """Test cost breakdown and analysis queries."""

    def test_get_cost_breakdown_by_agent(self, seeded_database):
        """Should break down costs by category for each agent."""
        from payment_simulator.persistence.queries import get_cost_breakdown_by_agent

        df = get_cost_breakdown_by_agent(seeded_database.conn, "test-sim-001")

        assert isinstance(df, pl.DataFrame)
        assert "agent_id" in df.columns
        assert "liquidity_cost" in df.columns
        assert "delay_cost" in df.columns
        assert "collateral_cost" in df.columns
        assert "split_friction_cost" in df.columns
        assert "deadline_penalty_cost" in df.columns
        assert "total_cost" in df.columns

        # Should have both BANK_A and BANK_B
        agents = df["agent_id"].to_list()
        assert "BANK_A" in agents
        assert "BANK_B" in agents

    def test_get_daily_cost_trends(self, seeded_database):
        """Should show cost trends over time."""
        from payment_simulator.persistence.queries import get_daily_cost_trends

        df = get_daily_cost_trends(seeded_database.conn, "test-sim-001", "BANK_A")

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3  # 3 days
        assert "day" in df.columns
        assert "total_cost" in df.columns
        assert "liquidity_cost" in df.columns
        assert "delay_cost" in df.columns


# ============================================================================
# Performance Tests
# ============================================================================


class TestQueryPerformance:
    """Test query performance on realistic datasets."""

    def test_agent_performance_query_fast_on_large_dataset(self, db_path):
        """Agent performance query should be fast even with many days."""
        manager = DatabaseManager(db_path)
        manager.setup()

        # Seed 1000 days of metrics for one agent
        import random

        random.seed(12345)
        metrics = []
        for day in range(1000):
            balance = 1000000 + day * 1000
            metrics.append(
                f"('perf-test', 'BANK_A', {day}, "
                f"{balance}, {balance + 10000}, {balance - 5000}, {balance + 15000}, "
                f"500000, 20000, 0, 0, 0, 5000000, 0, 0, "
                f"50, 30, 20, 30, 10, 5, 3, "
                f"10000, 5000, 0, 1000, 500, 16500)"
            )

        # Insert in batches for speed
        batch_size = 100
        for i in range(0, len(metrics), batch_size):
            batch = metrics[i : i + batch_size]
            values = ",\n        ".join(batch)
            manager.conn.execute(
                f"""
                INSERT INTO daily_agent_metrics (
                    simulation_id, agent_id, day,
                    opening_balance, closing_balance, min_balance, max_balance,
                    unsecured_cap, peak_overdraft,
                    opening_posted_collateral, closing_posted_collateral, peak_posted_collateral,
                    collateral_capacity, num_collateral_posts, num_collateral_withdrawals,
                    num_arrivals, num_sent, num_received, num_settled, num_dropped,
                    queue1_peak_size, queue1_eod_size,
                    liquidity_cost, delay_cost, collateral_cost, split_friction_cost,
                    deadline_penalty_cost, total_cost
                ) VALUES {values}
            """
            )

        # Query should complete quickly
        from payment_simulator.persistence.queries import get_agent_performance

        start = time.perf_counter()
        df = get_agent_performance(manager.conn, "perf-test", "BANK_A")
        duration = time.perf_counter() - start

        assert len(df) == 1000
        assert duration < 0.5, f"Query took {duration:.3f}s, expected <0.5s"

        manager.close()

    def test_settlement_rate_query_fast_on_many_transactions(self, db_path):
        """Settlement rate calculation should be fast on large transaction sets."""
        manager = DatabaseManager(db_path)
        manager.setup()

        # Seed 100k transactions across 10 days
        import random

        random.seed(12345)

        batch_size = 1000
        num_batches = 100

        for batch_num in range(num_batches):
            transactions = []
            for i in range(batch_size):
                tx_id = batch_num * batch_size + i
                day = tx_id % 10
                status = "settled" if random.random() < 0.7 else "pending"
                settlement_tick = day * 100 + 50 if status == "settled" else "NULL"
                settlement_day = day if status == "settled" else "NULL"

                transactions.append(
                    f"('perf-test', 'TX{tx_id}', 'BANK_A', 'BANK_B', {100000 + i*1000}, "
                    f"5, true, {day*100 + i%100}, {day}, {day*100 + 99}, {settlement_tick}, "
                    f"{settlement_day}, '{status}', NULL, {100000 if status == 'settled' else 0}, "
                    f"10, 5, 15, {i*10})"
                )

            values = ",\n        ".join(transactions)
            manager.conn.execute(
                f"""
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id, amount, priority, is_divisible,
                    arrival_tick, arrival_day, deadline_tick, settlement_tick, settlement_day,
                    status, drop_reason, amount_settled, queue1_ticks, queue2_ticks,
                    total_delay_ticks, delay_cost
                ) VALUES {values}
            """
            )

        # Query should complete quickly
        from payment_simulator.persistence.queries import get_settlement_rate_by_day

        start = time.perf_counter()
        df = get_settlement_rate_by_day(manager.conn, "perf-test")
        duration = time.perf_counter() - start

        assert len(df) == 10  # 10 days
        assert duration < 1.0, f"Query took {duration:.3f}s, expected <1.0s"

        manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
