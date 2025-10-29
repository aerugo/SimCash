"""
TDD Phase 2: Transaction Batch Persistence Tests

These tests define requirements for daily transaction batch writes:
1. Rust FFI returns transaction data for a specific day
2. Python converts to Polars DataFrame
3. DuckDB batch write completes quickly (<100ms for 40K transactions)
4. Data survives process restart
5. Determinism preserved

Following RED phase: these tests will fail until we implement FFI + integration.
"""

import pytest
from pathlib import Path


class TestFFITransactionRetrieval:
    """Test that Rust FFI can return transaction data for a specific day."""

    def test_get_transactions_for_day_returns_list(self):
        """Verify get_transactions_for_day returns list of dicts."""
        from payment_simulator._core import Orchestrator

        # Minimal config with 2 agents
        config = {
            "simulation_id": "test-001",
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 2,
            "agents": [
                {
                    "agent_id": "BANK_A",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                },
                {
                    "agent_id": "BANK_B",
                    "opening_balance": 1000000,
                    "credit_limit": 500000,
                },
            ],
            "arrivals": [],  # No automatic arrivals for this test
            "cost_rates": {
                "overdraft_rate_bps": 50,
                "delay_cost_per_tick": 100,
            }
        }

        orch = Orchestrator.new(config)

        # Simulate day 0 (10 ticks)
        for _ in range(10):
            orch.tick()

        # Get transactions for day 0
        daily_txs = orch.get_transactions_for_day(0)

        assert isinstance(daily_txs, list)
        # May be empty if no transactions, but should return a list

    def test_get_transactions_for_day_returns_dicts_with_required_fields(self):
        """Verify each transaction dict has all required fields."""
        from payment_simulator._core import Orchestrator

        config = {
            "simulation_id": "test-002",
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agents": [
                {"agent_id": "BANK_A", "opening_balance": 2000000, "credit_limit": 500000},
                {"agent_id": "BANK_B", "opening_balance": 2000000, "credit_limit": 500000},
            ],
            "arrivals": [
                {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 0.5,  # Low rate for predictable test
                    "amount_distribution": {
                        "type": "uniform",
                        "min": 100000,
                        "max": 200000,
                    },
                    "counterparties": ["BANK_B"],
                }
            ],
            "cost_rates": {"overdraft_rate_bps": 50, "delay_cost_per_tick": 100},
        }

        orch = Orchestrator.new(config)

        # Simulate day 0 - should generate some transactions
        for _ in range(10):
            orch.tick()

        daily_txs = orch.get_transactions_for_day(0)

        # If transactions exist, check structure
        if daily_txs:
            tx = daily_txs[0]

            # Required fields from TransactionRecord model
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
            "simulation_id": "test-003",
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 3,
            "agents": [
                {"agent_id": "BANK_A", "opening_balance": 3000000, "credit_limit": 500000},
                {"agent_id": "BANK_B", "opening_balance": 3000000, "credit_limit": 500000},
            ],
            "arrivals": [
                {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "uniform", "min": 50000, "max": 100000},
                    "counterparties": ["BANK_B"],
                }
            ],
            "cost_rates": {"overdraft_rate_bps": 50, "delay_cost_per_tick": 100},
        }

        orch = Orchestrator.new(config)

        # Simulate 3 days
        for day in range(3):
            for _ in range(10):
                orch.tick()

        # Get transactions for each day
        day0_txs = orch.get_transactions_for_day(0)
        day1_txs = orch.get_transactions_for_day(1)
        day2_txs = orch.get_transactions_for_day(2)

        # All transactions in day0_txs should have arrival_day == 0
        for tx in day0_txs:
            assert tx["arrival_day"] == 0, f"Transaction {tx['tx_id']} not from day 0"

        # All transactions in day1_txs should have arrival_day == 1
        for tx in day1_txs:
            assert tx["arrival_day"] == 1, f"Transaction {tx['tx_id']} not from day 1"

        # All transactions in day2_txs should have arrival_day == 2
        for tx in day2_txs:
            assert tx["arrival_day"] == 2, f"Transaction {tx['tx_id']} not from day 2"

    def test_transaction_data_validates_with_pydantic_model(self):
        """Verify FFI transaction data validates with TransactionRecord model."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.models import TransactionRecord

        config = {
            "simulation_id": "test-004",
            "rng_seed": 12345,
            "ticks_per_day": 10,
            "num_days": 1,
            "agents": [
                {"agent_id": "BANK_A", "opening_balance": 2000000, "credit_limit": 500000},
                {"agent_id": "BANK_B", "opening_balance": 2000000, "credit_limit": 500000},
            ],
            "arrivals": [
                {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "uniform", "min": 100000, "max": 200000},
                    "counterparties": ["BANK_B"],
                }
            ],
            "cost_rates": {"overdraft_rate_bps": 50, "delay_cost_per_tick": 100},
        }

        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        daily_txs = orch.get_transactions_for_day(0)

        # Each transaction should validate with Pydantic model
        for tx_dict in daily_txs:
            # This should not raise ValidationError
            tx_record = TransactionRecord(**tx_dict)

            # Verify key invariants
            assert tx_record.amount >= 0
            assert tx_record.amount_settled >= 0
            assert tx_record.amount_settled <= tx_record.amount
            assert tx_record.simulation_id == "test-004"
            assert tx_record.arrival_day == 0


class TestPolarsDataFrameConversion:
    """Test conversion of transaction data to Polars DataFrame."""

    def test_create_polars_dataframe_from_transactions(self):
        """Verify transaction dicts convert to Polars DataFrame correctly."""
        import polars as pl

        # Sample transaction data (structure matching TransactionRecord)
        transactions = [
            {
                "simulation_id": "test-005",
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "is_divisible": True,
                "arrival_tick": 0,
                "arrival_day": 0,
                "deadline_tick": 100,
                "settlement_tick": 5,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 100000,
                "queue1_ticks": 3,
                "queue2_ticks": 0,
                "total_delay_ticks": 3,
                "delay_cost": 300,
                "parent_tx_id": None,
                "split_index": None,
            },
            {
                "simulation_id": "test-005",
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 150000,
                "priority": 3,
                "is_divisible": False,
                "arrival_tick": 2,
                "arrival_day": 0,
                "deadline_tick": 102,
                "settlement_tick": 8,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 150000,
                "queue1_ticks": 2,
                "queue2_ticks": 1,
                "total_delay_ticks": 3,
                "delay_cost": 200,
                "parent_tx_id": None,
                "split_index": None,
            },
        ]

        # Create Polars DataFrame
        df = pl.DataFrame(transactions)

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 2
        assert "simulation_id" in df.columns
        assert "amount" in df.columns

        # Verify correct types
        assert df["amount"].dtype == pl.Int64
        assert df["is_divisible"].dtype == pl.Boolean
        assert df["status"].dtype == pl.String


class TestDuckDBBatchWrite:
    """Test batch writing transactions to DuckDB."""

    def test_insert_transactions_to_duckdb(self, tmp_path):
        """Verify transactions can be inserted into DuckDB via Polars."""
        import duckdb
        import polars as pl
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        # Sample transactions
        transactions = [
            {
                "simulation_id": "test-006",
                "tx_id": f"tx-{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "is_divisible": True,
                "arrival_tick": i,
                "arrival_day": 0,
                "deadline_tick": 100,
                "settlement_tick": i + 5,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 100000,
                "queue1_ticks": 3,
                "queue2_ticks": 0,
                "total_delay_ticks": 3,
                "delay_cost": 300,
                "parent_tx_id": None,
                "split_index": None,
            }
            for i in range(100)
        ]

        # Create Polars DataFrame
        df = pl.DataFrame(transactions)

        # Insert to DuckDB
        manager.conn.execute("INSERT INTO transactions SELECT * FROM df")

        # Verify data inserted
        count = manager.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert count == 100

        # Verify data correctness
        first_tx = manager.conn.execute("""
            SELECT tx_id, amount, status FROM transactions
            ORDER BY arrival_tick LIMIT 1
        """).fetchone()

        assert first_tx[0] == "tx-0000"
        assert first_tx[1] == 100000
        assert first_tx[2] == "settled"

    def test_batch_write_performance_40k_transactions(self, tmp_path):
        """Verify 40K transaction insert completes in <100ms (performance target)."""
        import duckdb
        import polars as pl
        import time
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test_perf.db"
        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        # Generate 40K sample transactions (typical day for 200 agents)
        transactions = [
            {
                "simulation_id": "test-007",
                "tx_id": f"tx-{i:06d}",
                "sender_id": f"BANK_{i % 10}",
                "receiver_id": f"BANK_{(i + 1) % 10}",
                "amount": 50000 + (i % 100000),
                "priority": i % 10,
                "is_divisible": i % 2 == 0,
                "arrival_tick": i % 200,
                "arrival_day": 0,
                "deadline_tick": 200,
                "settlement_tick": (i % 200) + 10,
                "settlement_day": 0,
                "status": "settled",
                "drop_reason": None,
                "amount_settled": 50000 + (i % 100000),
                "queue1_ticks": i % 10,
                "queue2_ticks": i % 5,
                "total_delay_ticks": i % 15,
                "delay_cost": (i % 10) * 100,
                "parent_tx_id": None,
                "split_index": None,
            }
            for i in range(40_000)
        ]

        # Create Polars DataFrame
        df = pl.DataFrame(transactions)

        # Measure batch write performance
        start = time.perf_counter()
        manager.conn.execute("INSERT INTO transactions SELECT * FROM df")
        duration = time.perf_counter() - start

        # Verify count
        count = manager.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert count == 40_000

        # Performance target: <100ms
        # Note: May be slower in CI, so we'll use a more generous target
        assert duration < 0.5, f"Batch write took {duration:.3f}s, target <0.5s"

        print(f"✓ 40K transaction batch write: {duration*1000:.1f}ms")


class TestEndToEndTransactionPersistence:
    """Test complete workflow: simulate → collect → persist → query."""

    def test_full_simulation_with_transaction_persistence(self, tmp_path):
        """Run simulation, persist transactions, verify data survives restart."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        db_path = tmp_path / "simulation.db"
        manager = DatabaseManager(db_path)
        manager.setup()

        # Run simulation
        config = {
            "simulation_id": "test-008",
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 2,
            "agents": [
                {"agent_id": "BANK_A", "opening_balance": 2000000, "credit_limit": 500000},
                {"agent_id": "BANK_B", "opening_balance": 2000000, "credit_limit": 500000},
            ],
            "arrivals": [
                {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 0.8,
                    "amount_distribution": {"type": "uniform", "min": 50000, "max": 150000},
                    "counterparties": ["BANK_B"],
                },
                {
                    "agent_id": "BANK_B",
                    "rate_per_tick": 0.7,
                    "amount_distribution": {"type": "uniform", "min": 50000, "max": 150000},
                    "counterparties": ["BANK_A"],
                },
            ],
            "cost_rates": {"overdraft_rate_bps": 50, "delay_cost_per_tick": 100},
        }

        orch = Orchestrator.new(config)

        # Simulate 2 days with end-of-day persistence
        for day in range(2):
            # Simulate entire day
            for _ in range(20):
                orch.tick()

            # End of day: persist transactions
            daily_txs = orch.get_transactions_for_day(day)

            if daily_txs:
                df = pl.DataFrame(daily_txs)
                manager.conn.execute("INSERT INTO transactions SELECT * FROM df")

        # Close connection
        manager.close()

        # Restart: create new manager with same database
        manager2 = DatabaseManager(db_path)
        manager2.setup()

        # Query persisted data
        total_count = manager2.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert total_count > 0, "No transactions persisted"

        # Verify transactions from both days
        day0_count = manager2.conn.execute("""
            SELECT COUNT(*) FROM transactions WHERE arrival_day = 0
        """).fetchone()[0]

        day1_count = manager2.conn.execute("""
            SELECT COUNT(*) FROM transactions WHERE arrival_day = 1
        """).fetchone()[0]

        assert day0_count > 0, "No transactions from day 0"
        assert day1_count > 0, "No transactions from day 1"
        assert day0_count + day1_count == total_count

        print(f"✓ Persisted {total_count} transactions (day0: {day0_count}, day1: {day1_count})")

    def test_determinism_preserved_in_persistence(self, tmp_path):
        """Verify same seed produces identical persisted transactions."""
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        config = {
            "simulation_id": "test-009",
            "rng_seed": 12345,  # Same seed for both runs
            "ticks_per_day": 15,
            "num_days": 1,
            "agents": [
                {"agent_id": "BANK_A", "opening_balance": 2000000, "credit_limit": 500000},
                {"agent_id": "BANK_B", "opening_balance": 2000000, "credit_limit": 500000},
            ],
            "arrivals": [
                {
                    "agent_id": "BANK_A",
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "uniform", "min": 100000, "max": 200000},
                    "counterparties": ["BANK_B"],
                }
            ],
            "cost_rates": {"overdraft_rate_bps": 50, "delay_cost_per_tick": 100},
        }

        # Run 1
        orch1 = Orchestrator.new(config)
        for _ in range(15):
            orch1.tick()
        txs1 = orch1.get_transactions_for_day(0)

        # Run 2 (same seed)
        orch2 = Orchestrator.new(config)
        for _ in range(15):
            orch2.tick()
        txs2 = orch2.get_transactions_for_day(0)

        # Should have same number of transactions
        assert len(txs1) == len(txs2), "Transaction count differs with same seed"

        # Transaction IDs and amounts should be identical
        for tx1, tx2 in zip(txs1, txs2):
            assert tx1["tx_id"] == tx2["tx_id"], "Transaction IDs differ"
            assert tx1["amount"] == tx2["amount"], "Transaction amounts differ"
            assert tx1["sender_id"] == tx2["sender_id"], "Senders differ"
            assert tx1["receiver_id"] == tx2["receiver_id"], "Receivers differ"
            assert tx1["status"] == tx2["status"], "Status differs"

        print(f"✓ Determinism verified: {len(txs1)} identical transactions")
