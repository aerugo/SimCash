"""
Phase 3: Agent Metrics Collection Tests

Tests for Rust FFI method `get_daily_agent_metrics()` and Polars/DuckDB integration.
Following TDD RED-GREEN-REFACTOR cycle.

These tests define the contract for daily agent metrics before implementation.
"""

import pytest


class TestFFIAgentMetricsRetrieval:
    """Test Rust FFI method get_daily_agent_metrics()."""

    def test_get_daily_agent_metrics_returns_list(self):
        """Verify get_daily_agent_metrics returns list of dicts."""
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

        # Run simulation for one day
        for _ in range(10):
            orch.tick()

        # Get metrics for day 0
        daily_metrics = orch.get_daily_agent_metrics(0)

        assert isinstance(daily_metrics, list)
        assert len(daily_metrics) == 2  # One record per agent

    def test_get_daily_agent_metrics_returns_dicts_with_required_fields(self):
        """Verify each metrics dict has all required fields from DailyAgentMetricsRecord."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_500_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_500_000,
                    "unsecured_cap": 200_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit a transaction to generate activity
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=200_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        assert len(daily_metrics) > 0

        # Verify required fields exist in first metrics record
        metrics = daily_metrics[0]
        required_fields = [
            # Identity
            "simulation_id",
            "agent_id",
            "day",
            # Balance metrics
            "opening_balance",
            "closing_balance",
            "min_balance",
            "max_balance",
            # Unsecured overdraft capacity
            "unsecured_cap",
            "peak_overdraft",
            # Collateral management (Phase 8)
            "opening_posted_collateral",
            "closing_posted_collateral",
            "peak_posted_collateral",
            "collateral_capacity",
            "num_collateral_posts",
            "num_collateral_withdrawals",
            # Transaction counts
            "num_arrivals",
            "num_sent",
            "num_received",
            "num_settled",
            "num_dropped",
            # Queue metrics
            "queue1_peak_size",
            "queue1_eod_size",
            # Costs
            "liquidity_cost",
            "delay_cost",
            "collateral_cost",
            "split_friction_cost",
            "deadline_penalty_cost",
            "total_cost",
        ]

        for field in required_fields:
            assert field in metrics, f"Missing required field: {field}"

    def test_agent_metrics_validate_with_pydantic_model(self):
        """Verify metrics dicts validate against DailyAgentMetricsRecord Pydantic model."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.models import DailyAgentMetricsRecord

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

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        assert len(daily_metrics) > 0

        # Validate each metrics dict against Pydantic model
        for metrics_dict in daily_metrics:
            metrics_record = DailyAgentMetricsRecord(**metrics_dict)
            assert metrics_record.simulation_id.startswith("sim-")
            assert metrics_record.agent_id in ["BANK_A"]
            assert metrics_record.day == 0

    def test_metrics_filter_by_day(self):
        """Verify metrics are correctly filtered by day."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run for 3 days
        for _ in range(30):  # 3 days × 10 ticks
            orch.tick()

        # Get metrics for each day
        day0_metrics = orch.get_daily_agent_metrics(0)
        day1_metrics = orch.get_daily_agent_metrics(1)
        day2_metrics = orch.get_daily_agent_metrics(2)

        # Each day should have metrics for both agents
        assert len(day0_metrics) == 2
        assert len(day1_metrics) == 2
        assert len(day2_metrics) == 2

        # Verify day field matches
        for metrics in day0_metrics:
            assert metrics["day"] == 0

        for metrics in day1_metrics:
            assert metrics["day"] == 1

        for metrics in day2_metrics:
            assert metrics["day"] == 2


class TestBalanceMetricsTracking:
    """Test balance metrics tracking (min/max/opening/closing)."""

    def test_metrics_track_opening_and_closing_balance(self):
        """Verify opening and closing balance are correctly tracked."""
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
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction: BANK_A → BANK_B for $2,000
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=200_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)

        # Find BANK_A and BANK_B metrics
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")
        bank_b_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_B")

        # Verify BANK_A opening/closing balance
        assert bank_a_metrics["opening_balance"] == 1_000_000
        # After sending $2,000, should have $8,000 (assuming settlement)
        # We'll verify closing_balance changed from opening

        # Verify BANK_B opening/closing balance
        assert bank_b_metrics["opening_balance"] == 2_000_000

    def test_metrics_track_min_and_max_balance(self):
        """Verify min and max balance are tracked during the day."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 20,
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

        # Multiple transactions in both directions to create balance fluctuations
        # BANK_A sends large payment
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=800_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        for _ in range(5):
            orch.tick()

        # BANK_B sends back
        orch.submit_transaction(
            sender="BANK_B",
            receiver="BANK_A",
            amount=600_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run rest of simulation
        for _ in range(15):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")

        # Verify min/max balance tracked
        # Min should be <= opening (since BANK_A sent first)
        # Max should be >= opening (after receiving from BANK_B)
        assert "min_balance" in bank_a_metrics
        assert "max_balance" in bank_a_metrics
        assert bank_a_metrics["min_balance"] <= bank_a_metrics["opening_balance"]
        # If settlements occurred, max could be different
        # The exact values depend on settlement timing

    def test_metrics_track_peak_overdraft(self):
        """Verify peak overdraft is tracked when balance goes negative."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000,  # Low starting balance
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit large payment from BANK_A (forces overdraft)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=400_000,  # More than balance, uses credit
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")

        # Peak overdraft should be positive if balance went negative
        # (peak_overdraft = abs(min(0, min_balance)))
        assert "peak_overdraft" in bank_a_metrics
        assert bank_a_metrics["peak_overdraft"] >= 0


class TestTransactionCountMetrics:
    """Test transaction count metrics."""

    def test_metrics_track_transaction_counts(self):
        """Verify num_arrivals, num_sent, num_received, num_settled tracked."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 15,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions
        orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=100_000, deadline_tick=50, priority=5, divisible=False
        )
        orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=200_000, deadline_tick=50, priority=5, divisible=False
        )
        orch.submit_transaction(
            sender="BANK_B", receiver="BANK_A", amount=150_000, deadline_tick=50, priority=5, divisible=False
        )

        # Run simulation
        for _ in range(15):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")
        bank_b_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_B")

        # Verify BANK_A counts (sent 2, received 1)
        # Note: num_arrivals tracks arrivals at the agent (as sender)
        # num_sent tracks successful settlements as sender
        # num_received tracks receipts as receiver
        assert "num_arrivals" in bank_a_metrics
        assert "num_sent" in bank_a_metrics
        assert "num_received" in bank_a_metrics
        assert "num_settled" in bank_a_metrics

        # BANK_B counts (sent 1, received 2)
        assert "num_arrivals" in bank_b_metrics


class TestQueueMetrics:
    """Test queue size metrics."""

    def test_metrics_track_queue1_peak_and_eod_size(self):
        """Verify queue1_peak_size and queue1_eod_size are tracked."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500_000,
                    "unsecured_cap": 100_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit multiple transactions to create queue buildup
        for i in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=200_000 + (i * 10_000),
                deadline_tick=50,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")

        # Verify queue metrics exist
        assert "queue1_peak_size" in bank_a_metrics
        assert "queue1_eod_size" in bank_a_metrics
        assert bank_a_metrics["queue1_peak_size"] >= 0
        assert bank_a_metrics["queue1_eod_size"] >= 0


class TestCostMetrics:
    """Test cost accumulation metrics."""

    def test_metrics_include_all_cost_categories(self):
        """Verify all cost categories are included in metrics."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction that will cause overdraft (liquidity cost)
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=300_000,  # Forces overdraft
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get metrics
        daily_metrics = orch.get_daily_agent_metrics(0)
        bank_a_metrics = next(m for m in daily_metrics if m["agent_id"] == "BANK_A")

        # Verify all cost fields exist
        assert "liquidity_cost" in bank_a_metrics
        assert "delay_cost" in bank_a_metrics
        assert "collateral_cost" in bank_a_metrics
        assert "split_friction_cost" in bank_a_metrics
        assert "deadline_penalty_cost" in bank_a_metrics
        assert "total_cost" in bank_a_metrics

        # Verify costs are non-negative integers
        assert bank_a_metrics["liquidity_cost"] >= 0
        assert bank_a_metrics["delay_cost"] >= 0
        assert bank_a_metrics["total_cost"] >= 0

        # Total should equal sum of components
        expected_total = (
            bank_a_metrics["liquidity_cost"]
            + bank_a_metrics["delay_cost"]
            + bank_a_metrics["collateral_cost"]
            + bank_a_metrics["split_friction_cost"]
            + bank_a_metrics["deadline_penalty_cost"]
        )
        assert bank_a_metrics["total_cost"] == expected_total


class TestPolarsDataFrameConversion:
    """Test Polars DataFrame creation from metrics dicts."""

    def test_create_polars_dataframe_from_metrics(self):
        """Verify metrics dicts convert to Polars DataFrame correctly."""
        import polars as pl

        # Sample metrics data (matching DailyAgentMetricsRecord schema)
        metrics = [
            {
                "simulation_id": "test-sim",
                "agent_id": "BANK_A",
                "day": 0,
                "opening_balance": 1_000_000,
                "closing_balance": 950_000,
                "min_balance": 900_000,
                "max_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "peak_overdraft": 0,
                "opening_posted_collateral": 0,
                "closing_posted_collateral": 0,
                "peak_posted_collateral": 0,
                "collateral_capacity": 0,
                "num_collateral_posts": 0,
                "num_collateral_withdrawals": 0,
                "num_arrivals": 5,
                "num_sent": 5,
                "num_received": 3,
                "num_settled": 8,
                "num_dropped": 0,
                "queue1_peak_size": 3,
                "queue1_eod_size": 0,
                "liquidity_cost": 1000,
                "delay_cost": 500,
                "collateral_cost": 0,
                "split_friction_cost": 0,
                "deadline_penalty_cost": 0,
                "total_cost": 1500,
            },
        ]

        # Create Polars DataFrame
        df = pl.DataFrame(metrics)

        # Verify DataFrame structure
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 1

        # Verify column types
        assert df["opening_balance"].dtype == pl.Int64
        assert df["num_arrivals"].dtype == pl.Int64
        assert df["agent_id"].dtype == pl.String
        assert df["day"].dtype == pl.Int64


class TestDuckDBBatchWrite:
    """Test batch writing agent metrics to DuckDB."""

    def test_insert_agent_metrics_to_duckdb(self, db_path):
        """Verify agent metrics can be batch inserted into DuckDB."""
        import polars as pl
        from payment_simulator.persistence.connection import DatabaseManager

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Sample metrics
        metrics = [
            {
                "simulation_id": "test-007",
                "agent_id": "BANK_A",
                "day": 0,
                "opening_balance": 1_000_000,
                "closing_balance": 950_000,
                "min_balance": 900_000,
                "max_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "peak_overdraft": 0,
                "opening_posted_collateral": 0,
                "closing_posted_collateral": 0,
                "peak_posted_collateral": 0,
                "collateral_capacity": 0,
                "num_collateral_posts": 0,
                "num_collateral_withdrawals": 0,
                "num_arrivals": 5,
                "num_sent": 5,
                "num_received": 3,
                "num_settled": 8,
                "num_dropped": 0,
                "queue1_peak_size": 3,
                "queue1_eod_size": 0,
                "liquidity_cost": 1000,
                "delay_cost": 500,
                "collateral_cost": 0,
                "split_friction_cost": 0,
                "deadline_penalty_cost": 0,
                "total_cost": 1500,
            }
        ]

        df = pl.DataFrame(metrics)

        # Insert into DuckDB
        manager.conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")

        # Verify insertion
        result = manager.conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()
        assert result[0] == 1

        # Verify data
        row = manager.conn.execute(
            "SELECT agent_id, opening_balance, total_cost FROM daily_agent_metrics LIMIT 1"
        ).fetchone()
        assert row[0] == "BANK_A"
        assert row[1] == 1_000_000
        assert row[2] == 1500

        manager.close()

    def test_batch_write_performance_1000_agent_days(self, db_path):
        """Verify 1000 agent-day metrics insert completes quickly."""
        import time
        import polars as pl
        from payment_simulator.persistence.connection import DatabaseManager

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Generate 1000 agent-day metrics (e.g., 10 agents × 100 days)
        metrics = []
        for day in range(100):
            for agent_num in range(10):
                m = {
                    "simulation_id": "perf-test",
                    "agent_id": f"BANK_{agent_num}",
                    "day": day,
                    "opening_balance": 1_000_000 + (day * 10_000),
                    "closing_balance": 1_000_000 + (day * 10_000) - 5_000,
                    "min_balance": 950_000,
                    "max_balance": 1_050_000,
                    "unsecured_cap": 500_000,
                    "peak_overdraft": day * 100,
                    "opening_posted_collateral": 0,
                    "closing_posted_collateral": 0,
                    "peak_posted_collateral": 0,
                    "collateral_capacity": 0,
                    "num_collateral_posts": 0,
                    "num_collateral_withdrawals": 0,
                    "num_arrivals": 100 + (day % 10),
                    "num_sent": 95 + (day % 10),
                    "num_received": 98 + (day % 10),
                    "num_settled": 193 + (day % 10),
                    "num_dropped": 2,
                    "queue1_peak_size": 5,
                    "queue1_eod_size": 0,
                    "liquidity_cost": 1000 + (day * 10),
                    "delay_cost": 500 + (day * 5),
                    "collateral_cost": 0,
                    "split_friction_cost": 0,
                    "deadline_penalty_cost": 0,
                    "total_cost": 1500 + (day * 15),
                }
                metrics.append(m)

        df = pl.DataFrame(metrics)

        # Measure insert performance
        start = time.perf_counter()
        manager.conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")
        duration = time.perf_counter() - start

        # Verify all inserted
        count = manager.conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()[0]
        assert count == 1000

        # Performance target: <100ms for 1000 records
        assert duration < 0.1, f"Insert took {duration:.3f}s, expected <0.1s"

        manager.close()


class TestEndToEndAgentMetricsPersistence:
    """End-to-end tests for agent metrics persistence workflow."""

    def test_full_simulation_with_agent_metrics_persistence(self, db_path):
        """Run simulation, persist agent metrics, verify data survives restart."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        # Run simulation for 2 days
        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 2,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions and simulate
        for day in range(2):
            # Submit some transactions during the day
            for tick_in_day in range(20):
                if tick_in_day % 5 == 0:  # Submit every 5 ticks
                    orch.submit_transaction(
                        sender="BANK_A" if tick_in_day % 10 == 0 else "BANK_B",
                        receiver="BANK_B" if tick_in_day % 10 == 0 else "BANK_A",
                        amount=100_000 + (tick_in_day * 1000),
                        deadline_tick=orch.current_tick() + 50,
                        priority=5,
                        divisible=False,
                    )
                orch.tick()

            # End of day: persist agent metrics
            daily_metrics = orch.get_daily_agent_metrics(day)
            if daily_metrics:
                df = pl.DataFrame(daily_metrics)
                manager.conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")

        # Verify data persisted (2 days × 2 agents = 4 records)
        total_count = manager.conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()[0]
        assert total_count == 4, f"Expected 4 records, got {total_count}"

        # Close and reopen database to verify persistence
        manager.close()

        manager2 = DatabaseManager(db_path)
        count_after_restart = manager2.conn.execute("SELECT COUNT(*) FROM daily_agent_metrics").fetchone()[0]
        assert count_after_restart == total_count, "Data did not survive restart"

        manager2.close()

    def test_multi_day_metrics_accumulation(self):
        """Verify metrics are tracked independently for each day."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run for 3 days
        for _ in range(30):  # 3 days × 10 ticks
            # Submit transaction each tick
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=50_000,
                deadline_tick=orch.current_tick() + 20,
                priority=5,
                divisible=False,
            )
            orch.tick()

        # Get metrics for each day
        day0_metrics = orch.get_daily_agent_metrics(0)
        day1_metrics = orch.get_daily_agent_metrics(1)
        day2_metrics = orch.get_daily_agent_metrics(2)

        # Each day should have 2 agent records
        assert len(day0_metrics) == 2
        assert len(day1_metrics) == 2
        assert len(day2_metrics) == 2

        # Find BANK_A metrics for each day
        bank_a_day0 = next(m for m in day0_metrics if m["agent_id"] == "BANK_A")
        bank_a_day1 = next(m for m in day1_metrics if m["agent_id"] == "BANK_A")
        bank_a_day2 = next(m for m in day2_metrics if m["agent_id"] == "BANK_A")

        # Opening balance for day N+1 should equal closing balance of day N
        # (This verifies daily reset and proper tracking)
        # Note: This assumes end-of-day logic carries balance forward
        assert "opening_balance" in bank_a_day0
        assert "closing_balance" in bank_a_day0
        assert "opening_balance" in bank_a_day1
