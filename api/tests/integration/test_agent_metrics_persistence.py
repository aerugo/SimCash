"""
Phase 3: Agent Metrics Persistence Tests

Tests for daily agent metrics collection and persistence.
Following TDD RED-GREEN-REFACTOR cycle.
"""

import pytest
import duckdb
from pathlib import Path


class TestFFIAgentMetricsRetrieval:
    """Test Rust FFI method get_daily_agent_metrics()."""

    def test_get_daily_agent_metrics_returns_list(self):
        """Verify get_daily_agent_metrics returns list."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 2,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 300_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run day 0
        for _ in range(10):
            orch.tick()

        # Get metrics for day 0
        daily_metrics = orch.get_daily_agent_metrics(0)

        assert isinstance(daily_metrics, list)
        assert len(daily_metrics) == 2  # Two agents

    def test_get_daily_agent_metrics_returns_dicts_with_required_fields(self):
        """Verify each metrics dict has all required fields."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_500_000,
                    "unsecured_cap": 400_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run day 0
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)

        assert len(daily_metrics) == 1
        metrics = daily_metrics[0]

        # Required fields from DailyAgentMetricsRecord
        required_fields = [
            "agent_id",
            "day",
            "opening_balance",
            "closing_balance",
            "min_balance",
            "max_balance",
            "credit_limit",
            "peak_overdraft",
            # Phase 8: Collateral fields
            "opening_posted_collateral",
            "closing_posted_collateral",
            "peak_posted_collateral",
            "collateral_capacity",
            "num_collateral_posts",
            "num_collateral_withdrawals",
            # Costs
            "liquidity_cost",
            "delay_cost",
            "collateral_cost",
            "split_friction_cost",
            "deadline_penalty_cost",
            "total_cost",
        ]

        for field in required_fields:
            assert field in metrics, f"Missing field: {field}"

    def test_metrics_track_balance_changes(self):
        """Verify metrics accurately track balance changes."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction: BANK_A sends to BANK_B
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=200_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run day 0
        for _ in range(10):
            orch.tick()

        # Get metrics
        metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in metrics if m["agent_id"] == "BANK_A")
        bank_b_metrics = next(m for m in metrics if m["agent_id"] == "BANK_B")

        # BANK_A should have lower closing balance (sent money)
        assert bank_a_metrics["opening_balance"] == 1_000_000
        assert bank_a_metrics["closing_balance"] < 1_000_000

        # BANK_B should have higher closing balance (received money)
        assert bank_b_metrics["opening_balance"] == 1_000_000
        assert bank_b_metrics["closing_balance"] > 1_000_000


class TestPolarsAgentMetricsConversion:
    """Test Polars DataFrame creation from agent metrics."""

    def test_create_polars_dataframe_from_metrics(self):
        """Verify we can create Polars DataFrame from metrics data."""
        from payment_simulator._core import Orchestrator
        import polars as pl

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run day 0
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)

        # Create DataFrame
        df = pl.DataFrame(daily_metrics)

        assert len(df) == 1
        assert "agent_id" in df.columns
        assert "opening_balance" in df.columns
        assert "closing_balance" in df.columns

    def test_dataframe_matches_pydantic_model(self):
        """Verify DataFrame data validates with Pydantic model."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.models import DailyAgentMetricsRecord
        import polars as pl

        config = {
            "rng_seed": 99999,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "TEST_BANK",
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 600_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        df = pl.DataFrame(daily_metrics)

        # Add simulation_id (required by model)
        df = df.with_columns(
            pl.lit("test-sim-001").alias("simulation_id")
        )

        # Validate each row with Pydantic
        for row in df.iter_rows(named=True):
            metrics_record = DailyAgentMetricsRecord(**row)
            assert metrics_record.agent_id == "TEST_BANK"
            assert metrics_record.day == 0


class TestDuckDBAgentMetricsBatchWrite:
    """Test batch writing agent metrics to DuckDB."""

    def test_insert_agent_metrics_to_duckdb(self, tmp_path):
        """Verify we can batch insert agent metrics to DuckDB."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        # Setup database
        db_path = tmp_path / "test_metrics.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Run simulation
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_500_000,
                    "unsecured_cap": 400_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run day 0
        for _ in range(10):
            orch.tick()

        # Get metrics and create DataFrame
        daily_metrics = orch.get_daily_agent_metrics(0)
        df = pl.DataFrame(daily_metrics)

        # Add simulation_id
        df = df.with_columns(
            pl.lit("sim-001").alias("simulation_id")
        )

        # Insert into DuckDB
        db_manager.conn.execute(
            "INSERT INTO daily_agent_metrics SELECT * FROM df"
        )

        # Verify data was inserted
        result = db_manager.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics"
        ).fetchone()

        assert result[0] == 2  # Two agents

        # Verify we can query it
        query_result = db_manager.conn.execute("""
            SELECT agent_id, opening_balance, closing_balance
            FROM daily_agent_metrics
            WHERE simulation_id = 'sim-001'
            ORDER BY agent_id
        """).fetchall()

        assert len(query_result) == 2
        assert query_result[0][0] == "BANK_A"
        assert query_result[1][0] == "BANK_B"

    def test_batch_write_performance_multiple_days(self, tmp_path):
        """Verify batch write performance for multi-day simulation."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl
        import time

        # Setup database
        db_path = tmp_path / "test_perf.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Run 5-day simulation with 10 agents
        config = {
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 5,
            "agent_configs": [
                {
                    "id": f"BANK_{i:02d}",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                }
                for i in range(10)
            ],
        }

        orch = Orchestrator.new(config)

        # Run all days and collect metrics
        all_metrics = []
        for day in range(5):
            # Run ticks for the day
            for _ in range(100):
                orch.tick()

            # Collect metrics for this day
            daily_metrics = orch.get_daily_agent_metrics(day)
            all_metrics.extend(daily_metrics)

        # Create single DataFrame with all metrics
        df = pl.DataFrame(all_metrics)
        df = df.with_columns(
            pl.lit("sim-perf-001").alias("simulation_id")
        )

        # Measure batch write time
        start_time = time.time()
        db_manager.conn.execute(
            "INSERT INTO daily_agent_metrics SELECT * FROM df"
        )
        write_time = time.time() - start_time

        # Verify all data written
        count = db_manager.conn.execute(
            "SELECT COUNT(*) FROM daily_agent_metrics"
        ).fetchone()[0]

        assert count == 50  # 10 agents × 5 days
        assert write_time < 0.1  # Should be fast (<100ms)

        print(f"Wrote {count} agent metric records in {write_time*1000:.2f}ms")


class TestEndToEndAgentMetricsPersistence:
    """Test complete end-to-end agent metrics persistence workflow."""

    def test_full_simulation_with_agent_metrics_persistence(self, tmp_path):
        """Test complete simulation with agent metrics saved to database."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        # Initialize database
        db_path = tmp_path / "full_sim_metrics.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Create simulation
        config = {
            "rng_seed": 99999,
            "ticks_per_day": 50,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 800_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_500_000,
                    "unsecured_cap": 600_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)
        simulation_id = "e2e-test-001"

        # Run simulation and persist metrics after each day
        for day in range(3):
            # Run ticks for the day
            for _ in range(50):
                orch.tick()

            # Persist metrics at end of day
            daily_metrics = orch.get_daily_agent_metrics(day)
            df = pl.DataFrame(daily_metrics)
            df = df.with_columns(
                pl.lit(simulation_id).alias("simulation_id")
            )

            # Write to database
            db_manager.conn.execute(
                "INSERT INTO daily_agent_metrics SELECT * FROM df"
            )

        # Verify all metrics persisted
        total_count = db_manager.conn.execute(
            f"SELECT COUNT(*) FROM daily_agent_metrics WHERE simulation_id = '{simulation_id}'"
        ).fetchone()[0]

        assert total_count == 6  # 2 agents × 3 days

        # Verify we can query metrics by day
        day_0_metrics = db_manager.conn.execute(f"""
            SELECT agent_id, opening_balance, closing_balance
            FROM daily_agent_metrics
            WHERE simulation_id = '{simulation_id}' AND day = 0
            ORDER BY agent_id
        """).fetchall()

        assert len(day_0_metrics) == 2

        # Verify we can track agent across days
        bank_a_history = db_manager.conn.execute(f"""
            SELECT day, opening_balance, closing_balance
            FROM daily_agent_metrics
            WHERE simulation_id = '{simulation_id}' AND agent_id = 'BANK_A'
            ORDER BY day
        """).fetchall()

        assert len(bank_a_history) == 3  # 3 days
        # Verify closing balance of day N becomes opening balance of day N+1
        # (This is expected behavior in multi-day simulations)

    def test_collateral_fields_are_persisted(self, tmp_path):
        """Verify Phase 8 collateral fields are captured in metrics."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        # Initialize database
        db_path = tmp_path / "collateral_metrics.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        # Create simulation (even if agent doesn't use collateral, fields should exist)
        config = {
            "rng_seed": 77777,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get and persist metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        df = pl.DataFrame(daily_metrics)
        df = df.with_columns(
            pl.lit("collateral-test").alias("simulation_id")
        )

        db_manager.conn.execute(
            "INSERT INTO daily_agent_metrics SELECT * FROM df"
        )

        # Verify collateral fields exist
        result = db_manager.conn.execute("""
            SELECT
                opening_posted_collateral,
                closing_posted_collateral,
                peak_posted_collateral,
                collateral_capacity,
                num_collateral_posts,
                num_collateral_withdrawals,
                collateral_cost
            FROM daily_agent_metrics
            WHERE simulation_id = 'collateral-test'
        """).fetchone()

        assert result is not None
        # All collateral fields should be present (even if zero)
        assert len(result) == 7
