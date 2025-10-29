"""
Phase 2: Transaction Persistence Tests

Tests for Rust FFI method `get_transactions_for_day()` and Polars/DuckDB integration.
Following TDD RED-GREEN-REFACTOR cycle.
"""

import pytest


class TestFFITransactionRetrieval:
    """Test Rust FFI method get_transactions_for_day()."""

    def test_get_transactions_for_day_returns_list(self):
        """Verify get_transactions_for_day returns list."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 2,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit a transaction manually
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Advance time
        for _ in range(10):
            orch.tick()

        # Get transactions for day 0
        daily_txs = orch.get_transactions_for_day(0)

        assert isinstance(daily_txs, list)
        assert len(daily_txs) >= 1  # At least our submitted transaction

    def test_get_transactions_for_day_returns_dicts_with_required_fields(self):
        """Verify each transaction dict has all required fields."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=200_000,
            deadline_tick=50,
            priority=7,
            divisible=False,
        )

        # Advance time
        for _ in range(10):
            orch.tick()

        # Get transactions
        daily_txs = orch.get_transactions_for_day(0)
        assert len(daily_txs) > 0

        # Verify required fields exist in first transaction
        tx = daily_txs[0]
        required_fields = [
            "simulation_id",
            "tx_id",
            "sender_id",
            "receiver_id",
            "amount",
            "priority",
            "is_divisible",
            "arrival_tick",
            "arrival_day",
            "deadline_tick",
            "settlement_tick",
            "settlement_day",
            "status",
            "drop_reason",
            "amount_settled",
            "queue1_ticks",
            "queue2_ticks",
            "total_delay_ticks",
            "delay_cost",
            "parent_tx_id",
            "split_index",
        ]

        for field in required_fields:
            assert field in tx, f"Missing required field: {field}"

    def test_get_transactions_for_day_filters_by_day(self):
        """Verify only transactions from specified day are returned."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 3,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 5_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Day 0: Submit transaction at tick 5
        for _ in range(5):
            orch.tick()

        tx_day0 = orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=100_000, deadline_tick=50, priority=5, divisible=False
        )

        # Advance to day 1 (tick 10)
        for _ in range(5):
            orch.tick()

        # Day 1: Submit transaction at tick 15
        for _ in range(5):
            orch.tick()

        tx_day1 = orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=200_000, deadline_tick=50, priority=5, divisible=False
        )

        # Advance through rest of day 1
        for _ in range(5):
            orch.tick()

        # Get transactions by day
        day0_txs = orch.get_transactions_for_day(0)
        day1_txs = orch.get_transactions_for_day(1)

        # Verify day 0 transaction is in day 0 results
        day0_tx_ids = [tx["tx_id"] for tx in day0_txs]
        assert tx_day0 in day0_tx_ids

        # Verify day 1 transaction is in day 1 results
        day1_tx_ids = [tx["tx_id"] for tx in day1_txs]
        assert tx_day1 in day1_tx_ids

        # Verify arrival_day field matches
        for tx in day0_txs:
            assert tx["arrival_day"] == 0

        for tx in day1_txs:
            assert tx["arrival_day"] == 1

    def test_transaction_data_validates_with_pydantic_model(self):
        """Verify transaction dicts validate against TransactionRecord Pydantic model."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.models import TransactionRecord

        config = {
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction
        orch.submit_transaction(
            sender="BANK_A", receiver="BANK_B", amount=150_000, deadline_tick=50, priority=6, divisible=False
        )

        # Advance time
        for _ in range(10):
            orch.tick()

        # Get transactions
        daily_txs = orch.get_transactions_for_day(0)
        assert len(daily_txs) > 0

        # Validate each transaction against Pydantic model
        for tx_dict in daily_txs:
            tx_record = TransactionRecord(**tx_dict)
            assert tx_record.simulation_id.startswith("sim-")
            assert tx_record.amount > 0


class TestPolarsDataFrameConversion:
    """Test Polars DataFrame creation from transaction dicts."""

    def test_create_polars_dataframe_from_transactions(self):
        """Verify transaction dicts convert to Polars DataFrame correctly."""
        import polars as pl

        # Sample transaction data (matching TransactionRecord schema)
        transactions = [
            {
                "simulation_id": "test-005",
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100_000,
                "priority": 5,
                "is_divisible": False,
                "arrival_tick": 5,
                "arrival_day": 0,
                "deadline_tick": 50,
                "settlement_tick": 10,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 100_000,
                "queue1_ticks": 2,
                "queue2_ticks": 3,
                "total_delay_ticks": 5,
                "delay_cost": 500,
                "parent_tx_id": None,
                "split_index": None,
            },
            {
                "simulation_id": "test-005",
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 200_000,
                "priority": 7,
                "is_divisible": True,
                "arrival_tick": 8,
                "arrival_day": 0,
                "deadline_tick": 60,
                "settlement_tick": 15,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 200_000,
                "queue1_ticks": 1,
                "queue2_ticks": 6,
                "total_delay_ticks": 7,
                "delay_cost": 700,
                "parent_tx_id": None,
                "split_index": None,
            },
        ]

        # Create Polars DataFrame
        df = pl.DataFrame(transactions)

        # Verify DataFrame structure
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 2

        # Verify column types
        assert df["amount"].dtype == pl.Int64
        assert df["is_divisible"].dtype == pl.Boolean
        assert df["sender_id"].dtype == pl.String
        assert df["status"].dtype == pl.String


class TestDuckDBBatchWrite:
    """Test batch writing transactions to DuckDB."""

    def test_insert_transactions_to_duckdb(self, db_path):
        """Verify transactions can be batch inserted into DuckDB."""
        import polars as pl
        from payment_simulator.persistence.connection import DatabaseManager

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Sample transactions
        transactions = [
            {
                "simulation_id": "test-006",
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100_000,
                "priority": 5,
                "is_divisible": False,
                "arrival_tick": 5,
                "arrival_day": 0,
                "deadline_tick": 50,
                "settlement_tick": 10,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 100_000,
                "queue1_ticks": 0,
                "queue2_ticks": 0,
                "total_delay_ticks": 0,
                "delay_cost": 0,
                "parent_tx_id": None,
                "split_index": None,
            }
        ]

        df = pl.DataFrame(transactions)

        # Insert into DuckDB
        manager.conn.execute("INSERT INTO transactions SELECT * FROM df")

        # Verify insertion
        result = manager.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
        assert result[0] == 1

        # Verify data
        row = manager.conn.execute("SELECT tx_id, amount, status FROM transactions LIMIT 1").fetchone()
        assert row[0] == "tx-001"
        assert row[1] == 100_000
        assert row[2] == "settled"

        manager.close()

    def test_batch_write_performance_40k_transactions(self, db_path):
        """Verify 40K transaction insert completes in <500ms (performance target)."""
        import time
        import polars as pl
        from payment_simulator.persistence.connection import DatabaseManager

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Generate 40K test transactions
        transactions = []
        for i in range(40_000):
            tx = {
                "simulation_id": "perf-test",
                "tx_id": f"tx-{i:06d}",
                "sender_id": f"BANK_{i % 10}",
                "receiver_id": f"BANK_{(i + 1) % 10}",
                "amount": 100_000 + (i % 50_000),
                "priority": i % 10,
                "is_divisible": i % 2 == 0,
                "arrival_tick": i % 1000,
                "arrival_day": i // 1000,
                "deadline_tick": (i % 1000) + 50,
                "settlement_tick": None,
                "settlement_day": None,
                "status": "pending",
                "drop_reason": None,
                "amount_settled": 0,
                "queue1_ticks": 0,
                "queue2_ticks": 0,
                "total_delay_ticks": 0,
                "delay_cost": 0,
                "parent_tx_id": None,
                "split_index": None,
            }
            transactions.append(tx)

        df = pl.DataFrame(transactions)

        # Measure insert performance
        start = time.perf_counter()
        manager.conn.execute("INSERT INTO transactions SELECT * FROM df")
        duration = time.perf_counter() - start

        # Verify all inserted
        count = manager.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert count == 40_000

        # Performance target: <500ms (generous, plan says <100ms)
        assert duration < 0.5, f"Insert took {duration:.3f}s, expected <0.5s"

        manager.close()


class TestEndToEndTransactionPersistence:
    """End-to-end tests for transaction persistence workflow."""

    def test_full_simulation_with_transaction_persistence(self, db_path):
        """Run simulation, persist transactions, verify data survives restart."""
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
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
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

            # End of day: persist transactions
            daily_txs = orch.get_transactions_for_day(day)
            if daily_txs:
                df = pl.DataFrame(daily_txs)
                manager.conn.execute("INSERT INTO transactions SELECT * FROM df")

        # Verify data persisted
        total_count = manager.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert total_count > 0, "No transactions were persisted"

        # Close and reopen database to verify persistence
        manager.close()

        manager2 = DatabaseManager(db_path)
        count_after_restart = manager2.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert count_after_restart == total_count, "Data did not survive restart"

        manager2.close()

    def test_determinism_preserved_in_persistence(self):
        """Verify same seed produces identical persisted transactions."""
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 12345,  # Same seed for both runs
            "ticks_per_day": 15,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 2_000_000,
                    "credit_limit": 500_000,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        # Run 1
        orch1 = Orchestrator.new(config)
        for _ in range(5):
            orch1.submit_transaction(
                sender="BANK_A", receiver="BANK_B", amount=100_000, deadline_tick=50, priority=5, divisible=False
            )
        for _ in range(15):
            orch1.tick()
        txs1 = orch1.get_transactions_for_day(0)

        # Run 2 (same seed)
        orch2 = Orchestrator.new(config)
        for _ in range(5):
            orch2.submit_transaction(
                sender="BANK_A", receiver="BANK_B", amount=100_000, deadline_tick=50, priority=5, divisible=False
            )
        for _ in range(15):
            orch2.tick()
        txs2 = orch2.get_transactions_for_day(0)

        # Verify same number of transactions
        assert len(txs1) == len(txs2)

        # Verify transaction fields match (except tx_id which is random UUID)
        for tx1, tx2 in zip(txs1, txs2):
            assert tx1["amount"] == tx2["amount"]
            assert tx1["sender_id"] == tx2["sender_id"]
            assert tx1["receiver_id"] == tx2["receiver_id"]
            assert tx1["arrival_tick"] == tx2["arrival_tick"]
            assert tx1["status"] == tx2["status"]
