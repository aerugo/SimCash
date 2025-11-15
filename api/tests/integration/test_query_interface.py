"""
Phase 5: Query Interface & Analytics Tests

Tests for pre-built analytical queries.
Following TDD RED-GREEN-REFACTOR cycle.

Key Requirements:
- Query functions return Polars DataFrames
- Fast analytical queries (<1s for 1M+ rows)
- Support for simulation comparison
- Agent performance tracking across days
"""

import pytest
import polars as pl
from datetime import datetime


class TestSimulationListQueries:
    """Test queries for listing and filtering simulation runs."""

    def test_list_all_simulations(self, tmp_path):
        """Verify list_simulations returns all runs in database."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import list_simulations

        # Setup database with multiple simulations
        db_path = tmp_path / "query_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert test simulation records
        db_manager.conn.execute("""
            INSERT INTO simulations (simulation_id, config_file, config_hash, rng_seed,
                                     ticks_per_day, num_days, num_agents, status)
            VALUES
                ('sim-001', 'test1.yaml', 'hash1', 12345, 100, 10, 2, 'completed'),
                ('sim-002', 'test2.yaml', 'hash2', 67890, 100, 10, 2, 'completed'),
                ('sim-003', 'test3.yaml', 'hash3', 11111, 100, 10, 2, 'running')
        """)

        # RED: Function doesn't exist yet
        df = list_simulations(db_manager.conn)

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3
        assert "simulation_id" in df.columns
        assert "status" in df.columns
        assert "rng_seed" in df.columns

    def test_list_simulations_with_status_filter(self, tmp_path):
        """Verify can filter simulations by status."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import list_simulations

        db_path = tmp_path / "filter_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert test data
        db_manager.conn.execute("""
            INSERT INTO simulations (simulation_id, config_file, config_hash, rng_seed,
                                     ticks_per_day, num_days, num_agents, status)
            VALUES
                ('sim-001', 'test.yaml', 'hash1', 12345, 100, 10, 2, 'completed'),
                ('sim-002', 'test.yaml', 'hash2', 67890, 100, 10, 2, 'failed'),
                ('sim-003', 'test.yaml', 'hash3', 11111, 100, 10, 2, 'completed')
        """)

        # RED: Filter parameter doesn't exist yet
        df = list_simulations(db_manager.conn, status='completed')

        assert len(df) == 2
        assert all(df['status'] == 'completed')

    def test_list_simulations_sorted_by_date(self, tmp_path):
        """Verify simulations returned in chronological order."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import list_simulations

        db_path = tmp_path / "sort_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert with different timestamps
        db_manager.conn.execute("""
            INSERT INTO simulations (simulation_id, config_file, config_hash, rng_seed,
                                     ticks_per_day, num_days, num_agents, status, started_at)
            VALUES
                ('sim-001', 'test.yaml', 'hash1', 12345, 100, 10, 2, 'completed', '2025-10-01 10:00:00'),
                ('sim-002', 'test.yaml', 'hash2', 67890, 100, 10, 2, 'completed', '2025-10-01 12:00:00'),
                ('sim-003', 'test.yaml', 'hash3', 11111, 100, 10, 2, 'completed', '2025-10-01 11:00:00')
        """)

        df = list_simulations(db_manager.conn)

        # Should be sorted by started_at descending (most recent first)
        sim_ids = df['simulation_id'].to_list()
        assert sim_ids[0] == 'sim-002'  # Most recent
        assert sim_ids[-1] == 'sim-001'  # Oldest


class TestSimulationDetailQueries:
    """Test queries for simulation run details."""

    def test_get_simulation_summary(self, tmp_path):
        """Verify get_simulation_summary returns all metadata."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_simulation_summary

        db_path = tmp_path / "summary_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert simulation with full metadata
        db_manager.conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, status,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (
                'sim-001', 'test.yaml', 'hash1', 12345,
                100, 5, 2, 'completed',
                1000, 950, 50000,
                10.5, 1200.0
            )
        """)

        # RED: Function doesn't exist
        summary = get_simulation_summary(db_manager.conn, 'sim-001')

        assert isinstance(summary, dict)
        assert summary['simulation_id'] == 'sim-001'
        assert summary['rng_seed'] == 12345
        assert summary['total_arrivals'] == 1000
        assert summary['total_settlements'] == 950
        assert summary['settlement_rate'] == pytest.approx(0.95, rel=0.01)

    def test_get_simulation_summary_not_found(self, tmp_path):
        """Verify get_simulation_summary returns None for missing sim."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_simulation_summary

        db_path = tmp_path / "notfound_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        summary = get_simulation_summary(db_manager.conn, 'nonexistent-sim')

        assert summary is None


class TestAgentMetricsQueries:
    """Test queries for agent performance metrics."""

    def test_get_agent_daily_metrics(self, tmp_path):
        """Verify get_agent_daily_metrics returns time series."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_agent_daily_metrics

        db_path = tmp_path / "metrics_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert daily metrics for 5 days
        for day in range(5):
            db_manager.conn.execute(f"""
                INSERT INTO daily_agent_metrics (
                    simulation_id, agent_id, day,
                    opening_balance, closing_balance, min_balance, max_balance,
                    unsecured_cap, peak_overdraft,
                    opening_posted_collateral, closing_posted_collateral, peak_posted_collateral, collateral_capacity,
                    num_collateral_posts, num_collateral_withdrawals,
                    num_arrivals, num_sent, num_received, num_settled, num_dropped,
                    queue1_peak_size, queue1_eod_size,
                    liquidity_cost, delay_cost, split_friction_cost, deadline_penalty_cost, collateral_cost,
                    total_cost
                ) VALUES (
                    'sim-001', 'BANK_A', {day},
                    1000000, {950000 - day * 10000}, {900000 - day * 10000}, {1100000 - day * 5000},
                    500000, 0,
                    0, 0, 0, 5000000,
                    0, 0,
                    {50 + day * 5}, 0, 0, {45 + day * 5}, 0,
                    0, 0,
                    0, 0, 0, 0, 0,
                    {5000 + day * 1000}
                )
            """)

        # RED: Function doesn't exist
        df = get_agent_daily_metrics(db_manager.conn, 'sim-001', 'BANK_A')

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 5
        assert "day" in df.columns
        assert "closing_balance" in df.columns
        assert "total_cost" in df.columns

        # Verify data is sorted by day
        assert df['day'].to_list() == [0, 1, 2, 3, 4]

    def test_get_agent_daily_metrics_with_cost_breakdown(self, tmp_path):
        """Verify metrics include all 5 cost types."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_agent_daily_metrics

        db_path = tmp_path / "cost_breakdown_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        db_manager.conn.execute("""
            INSERT INTO daily_agent_metrics (
                simulation_id, agent_id, day,
                opening_balance, closing_balance, min_balance, max_balance,
                unsecured_cap, peak_overdraft,
                opening_posted_collateral, closing_posted_collateral, peak_posted_collateral, collateral_capacity,
                num_collateral_posts, num_collateral_withdrawals,
                num_arrivals, num_sent, num_received, num_settled, num_dropped,
                queue1_peak_size, queue1_eod_size,
                liquidity_cost, delay_cost, split_friction_cost,
                deadline_penalty_cost, collateral_cost, total_cost
            ) VALUES (
                'sim-001', 'BANK_A', 0,
                1000000, 950000, 900000, 1100000,
                500000, 0,
                0, 0, 0, 5000000,
                0, 0,
                0, 0, 0, 0, 0,
                0, 0,
                1000, 2000, 500, 1500, 3000, 8000
            )
        """)

        df = get_agent_daily_metrics(db_manager.conn, 'sim-001', 'BANK_A')

        assert "liquidity_cost" in df.columns
        assert "delay_cost" in df.columns
        assert "split_friction_cost" in df.columns
        assert "deadline_penalty_cost" in df.columns
        assert "collateral_cost" in df.columns
        assert df['total_cost'][0] == 8000


class TestTransactionQueries:
    """Test queries for transaction analysis."""

    def test_get_transactions_for_simulation(self, tmp_path):
        """Verify can query all transactions for a simulation."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_transactions

        db_path = tmp_path / "tx_query_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert test transactions
        for i in range(10):
            db_manager.conn.execute(f"""
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id, amount,
                    priority, is_divisible, deadline_tick,
                    arrival_day, arrival_tick, status, amount_settled,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
                ) VALUES (
                    'sim-001', 'tx-{i:03d}', 'BANK_A', 'BANK_B', {100000 + i * 10000},
                    5, false, 100,
                    0, {i * 10}, 'settled', {100000 + i * 10000},
                    0, 0, 0, 0
                )
            """)

        # RED: Function doesn't exist
        df = get_transactions(db_manager.conn, 'sim-001')

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 10
        assert "tx_id" in df.columns
        assert "amount" in df.columns
        assert all(df['simulation_id'] == 'sim-001')

    def test_get_transactions_with_status_filter(self, tmp_path):
        """Verify can filter transactions by status."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_transactions

        db_path = tmp_path / "tx_filter_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert mixed status transactions
        statuses = ['settled', 'settled', 'pending', 'dropped', 'settled']
        for i, status in enumerate(statuses):
            amount_settled = 100000 if status == 'settled' else 0
            db_manager.conn.execute(f"""
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id, amount,
                    priority, is_divisible, deadline_tick,
                    arrival_day, arrival_tick, status, amount_settled,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
                ) VALUES (
                    'sim-001', 'tx-{i:03d}', 'BANK_A', 'BANK_B', 100000,
                    5, false, 100,
                    0, {i}, '{status}', {amount_settled},
                    0, 0, 0, 0
                )
            """)

        df = get_transactions(db_manager.conn, 'sim-001', status='settled')

        assert len(df) == 3
        assert all(df['status'] == 'settled')

    def test_get_transaction_statistics(self, tmp_path):
        """Verify transaction aggregation statistics."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_transaction_statistics

        db_path = tmp_path / "tx_stats_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert transactions with varying delays
        for i in range(100):
            db_manager.conn.execute(f"""
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id, amount,
                    priority, is_divisible, deadline_tick,
                    arrival_day, arrival_tick, settlement_tick,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost, status, amount_settled
                ) VALUES (
                    'sim-001', 'tx-{i:03d}', 'BANK_A', 'BANK_B', {100000 + i * 1000},
                    5, false, 100,
                    0, {i}, {i + 5}, 0, 0, 5, 0, 'settled', {100000 + i * 1000}
                )
            """)

        # RED: Function doesn't exist
        stats = get_transaction_statistics(db_manager.conn, 'sim-001')

        assert isinstance(stats, dict)
        assert stats['total_count'] == 100
        assert stats['settled_count'] == 100
        assert stats['settlement_rate'] == 1.0
        assert stats['avg_delay_ticks'] == pytest.approx(5.0)


class TestPolicyComparisonQueries:
    """Test queries for comparing simulation runs."""

    def test_compare_simulations(self, tmp_path):
        """Verify can compare KPIs across two simulations."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import compare_simulations

        db_path = tmp_path / "compare_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert two simulations
        db_manager.conn.execute("""
            INSERT INTO simulations (simulation_id, config_file, config_hash, rng_seed,
                                     ticks_per_day, num_days, num_agents, status,
                                     total_arrivals, total_settlements, total_cost_cents)
            VALUES
                ('sim-001', 'test.yaml', 'hash1', 12345, 100, 5, 2, 'completed', 1000, 950, 50000),
                ('sim-002', 'test.yaml', 'hash2', 12345, 100, 5, 2, 'completed', 1000, 980, 45000)
        """)

        # RED: Function doesn't exist
        comparison = compare_simulations(db_manager.conn, 'sim-001', 'sim-002')

        assert isinstance(comparison, dict)
        assert 'sim1' in comparison
        assert 'sim2' in comparison
        assert 'delta' in comparison

        # Verify delta calculations
        assert comparison['delta']['settlement_rate'] == pytest.approx(0.03, rel=0.01)  # 98% - 95%
        assert comparison['delta']['total_cost'] < 0  # sim-002 has lower cost

    def test_compare_agent_performance(self, tmp_path):
        """Verify can compare agent performance across simulations."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import compare_agent_performance

        db_path = tmp_path / "agent_compare_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert agent metrics for two simulations
        for sim_id, total_cost in [('sim-001', 50000), ('sim-002', 45000)]:
            for day in range(3):
                db_manager.conn.execute(f"""
                    INSERT INTO daily_agent_metrics (
                        simulation_id, agent_id, day,
                        opening_balance, closing_balance, min_balance, max_balance,
                        unsecured_cap, peak_overdraft,
                        opening_posted_collateral, closing_posted_collateral, peak_posted_collateral, collateral_capacity,
                        num_collateral_posts, num_collateral_withdrawals,
                        num_arrivals, num_sent, num_received, num_settled, num_dropped,
                        queue1_peak_size, queue1_eod_size,
                        liquidity_cost, delay_cost, split_friction_cost, deadline_penalty_cost, collateral_cost,
                        total_cost
                    ) VALUES (
                        '{sim_id}', 'BANK_A', {day},
                        1000000, 950000, 900000, 1100000,
                        500000, 0,
                        0, 0, 0, 5000000,
                        0, 0,
                        0, 0, 0, 0, 0,
                        0, 0,
                        0, 0, 0, 0, 0,
                        {total_cost // 3}
                    )
                """)

        # RED: Function doesn't exist
        df = compare_agent_performance(db_manager.conn, 'sim-001', 'sim-002', 'BANK_A')

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3  # 3 days
        assert "day" in df.columns
        assert "sim1_total_cost" in df.columns
        assert "sim2_total_cost" in df.columns
        assert "cost_delta" in df.columns


class TestPolicyProvenanceQueries:
    """Test queries for policy version tracking."""

    def test_get_agent_policy_history(self, tmp_path):
        """Verify can query policy changes over time."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_agent_policy_history

        db_path = tmp_path / "policy_history_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert policy snapshots
        import hashlib
        import json

        policies = [
            (0, 0, {"type": "Fifo"}, "init"),
            (2, 0, {"type": "Deadline", "urgency_threshold": 10}, "manual"),
            (5, 0, {"type": "LiquidityAware", "target_buffer": 500000, "urgency_threshold": 5}, "llm"),
        ]

        for day, tick, policy_config, created_by in policies:
            policy_json = json.dumps(policy_config, sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            db_manager.conn.execute(f"""
                INSERT INTO policy_snapshots (
                    simulation_id, agent_id, snapshot_day, snapshot_tick,
                    policy_hash, policy_json, created_by
                ) VALUES (
                    'sim-001', 'BANK_A', {day}, {tick},
                    '{policy_hash}', '{policy_json}', '{created_by}'
                )
            """)

        # RED: Function doesn't exist
        df = get_agent_policy_history(db_manager.conn, 'sim-001', 'BANK_A')

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3
        assert "snapshot_day" in df.columns
        assert "created_by" in df.columns
        assert "policy_json" in df.columns

        # Verify chronological order
        assert df['snapshot_day'].to_list() == [0, 2, 5]
        assert df['created_by'].to_list() == ['init', 'manual', 'llm']

    def test_get_policy_at_day(self, tmp_path):
        """Verify can answer: 'What policy was agent using on day X?'"""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_policy_at_day

        db_path = tmp_path / "policy_at_day_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert policy snapshots
        import hashlib
        import json

        policies = [
            (0, {"type": "Fifo"}),
            (3, {"type": "Deadline", "urgency_threshold": 10}),
            (7, {"type": "LiquidityAware", "target_buffer": 500000, "urgency_threshold": 5}),
        ]

        for day, policy_config in policies:
            policy_json = json.dumps(policy_config, sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            db_manager.conn.execute(f"""
                INSERT INTO policy_snapshots (
                    simulation_id, agent_id, snapshot_day, snapshot_tick,
                    policy_hash, policy_json, created_by
                ) VALUES (
                    'sim-001', 'BANK_A', {day}, 0,
                    '{policy_hash}', '{policy_json}', 'init'
                )
            """)

        # RED: Function doesn't exist
        # Query: What policy on day 5? (Should return Deadline policy from day 3)
        policy = get_policy_at_day(db_manager.conn, 'sim-001', 'BANK_A', day=5)

        assert policy is not None
        assert policy['policy_config']['type'] == 'Deadline'
        assert policy['snapshot_day'] == 3

        # Query: What policy on day 8? (Should return LiquidityAware from day 7)
        policy_day8 = get_policy_at_day(db_manager.conn, 'sim-001', 'BANK_A', day=8)
        assert policy_day8['policy_config']['type'] == 'LiquidityAware'


class TestPerformanceQueries:
    """Test query performance with large datasets."""

    def test_large_transaction_query_performance(self, tmp_path):
        """Verify can query 1M+ transactions in <1 second."""
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import get_transaction_statistics
        import time

        db_path = tmp_path / "perf_test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Insert 100K transactions (scaled down for testing)
        # Real test would use 1M+
        batch_size = 1000
        num_batches = 100

        for batch in range(num_batches):
            values = []
            for i in range(batch_size):
                tx_id = batch * batch_size + i
                values.append(f"('sim-001', 'tx-{tx_id:06d}', 'BANK_A', 'BANK_B', {100000 + i}, 5, false, 100, 0, {i}, 'settled', {100000 + i}, 0, 0, 0, 0)")

            values_str = ", ".join(values)
            db_manager.conn.execute(f"""
                INSERT INTO transactions (simulation_id, tx_id, sender_id, receiver_id, amount, priority, is_divisible, deadline_tick, arrival_day, arrival_tick, status, amount_settled, queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost)
                VALUES {values_str}
            """)

        # Measure query performance
        start = time.perf_counter()
        stats = get_transaction_statistics(db_manager.conn, 'sim-001')
        duration = time.perf_counter() - start

        assert stats['total_count'] == 100_000
        assert duration < 1.0, f"Query took {duration:.3f}s, expected <1.0s"
