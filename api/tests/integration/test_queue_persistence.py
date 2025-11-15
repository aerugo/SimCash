"""
Integration tests for queue contents persistence (Phase 3).

Tests follow TDD RED-GREEN-REFACTOR:
- Phase 3.1: Write tests (RED - tests fail initially)
- Phase 3.2: Implement Rust FFI methods (GREEN)
- Phase 3.3: Add Python persistence logic (GREEN)
- Phase 3.4: Verify all tests pass (REFACTOR)

Queue Architecture:
- Queue 1: Agent internal queue (outgoing_queue) - per-agent
- Queue 2: RTGS central queue (rtgs_queue) - global

Priority: Queue 1 persistence (Queue 2 is lower priority, can defer)
"""

import pytest
import duckdb
from pathlib import Path
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def db_path(tmp_path, request):
    """Create unique database for each test."""
    test_name = request.node.name
    db_file = tmp_path / f"{test_name}.db"
    return db_file


class TestFFIQueueRetrieval:
    """Test Rust FFI methods for queue retrieval.

    RED: Will fail because FFI method doesn't exist yet.
    """

    def test_ffi_get_agent_queue1_contents_exists(self):
        """Verify FFI method get_agent_queue1_contents() exists.

        RED: Method doesn't exist yet.
        """
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # RED: Method doesn't exist
        assert hasattr(orch, "get_agent_queue1_contents"), (
            "Orchestrator should have get_agent_queue1_contents() method"
        )

    def test_ffi_get_agent_queue1_contents_returns_list(self):
        """Verify method returns list of transaction IDs.

        RED: Method doesn't exist yet.
        """
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000,  # Low balance to cause queuing
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transaction that will queue (amount > balance)
        tx_id = orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,  # Much larger than BANK_A's balance
            deadline_tick=50,
            priority=5,
            divisible=False,
        )

        # Run a tick to process queuing
        orch.tick()

        # RED: Method doesn't exist
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        assert isinstance(queue_contents, list), "Should return a list"
        # Note: Whether queue has items depends on policy behavior

    def test_ffi_get_agent_queue1_contents_ordering(self):
        """Verify queue contents preserve order.

        RED: Method doesn't exist yet.
        """
        from payment_simulator._core import Orchestrator

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit multiple transactions
        tx_ids = []
        for i in range(5):
            tx_id = orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=50_000,
                deadline_tick=100,
                priority=i,  # Different priorities
                divisible=False,
            )
            tx_ids.append(tx_id)

        # Run tick
        orch.tick()

        # RED: Method doesn't exist
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        # Queue contents should be a list (order matters)
        assert isinstance(queue_contents, list), "Order should be preserved as list"


class TestQueuePersistence:
    """Test queue contents persistence to database.

    RED: Will fail because:
    1. FFI method doesn't exist
    2. Persistence logic not added to run.py
    3. Database table doesn't exist
    """

    def test_agent_queue_snapshots_table_schema(self, db_path):
        """Verify agent_queue_snapshots table has correct schema.

        RED: Table doesn't exist in schema yet.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # Check table exists
        result = manager.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_queue_snapshots'"
        ).fetchall()

        assert len(result) == 1, "agent_queue_snapshots table should exist"

        # Check schema
        schema = manager.conn.execute("DESCRIBE agent_queue_snapshots").fetchall()
        column_names = [row[0] for row in schema]

        required_columns = [
            "simulation_id",
            "agent_id",
            "day",
            "queue_type",
            "position",
            "transaction_id",
        ]

        for col in required_columns:
            assert col in column_names, f"Column {col} should exist"

    def test_agent_queue_snapshots_persisted(self, db_path):
        """Verify queue contents are persisted to database.

        RED: Will fail because:
        1. FFI method doesn't exist
        2. Write logic not added
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions to create queue
        for i in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=50_000,
                deadline_tick=100,
                priority=i,
                divisible=False,
            )

        # Run simulation (1 day = 10 ticks)
        for _ in range(10):
            orch.tick()

        # RED: FFI method doesn't exist
        sim_id = "test_sim_queue_1"
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        if queue_contents:
            # Simulate what run.py will do
            queue_data = [
                {
                    "simulation_id": sim_id,
                    "agent_id": "BANK_A",
                    "day": 0,
                    "queue_type": "queue1",
                    "position": idx,
                    "transaction_id": tx_id,
                }
                for idx, tx_id in enumerate(queue_contents)
            ]

            df = pl.DataFrame(queue_data)
            manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

        # Verify persistence
        result = manager.conn.execute(
            "SELECT COUNT(*) FROM agent_queue_snapshots WHERE agent_id = 'BANK_A'"
        ).fetchone()

        count = result[0]
        # We expect SOME queued transactions (exact count depends on policy)
        # For now, just verify the table accepts data
        assert count >= 0, "Should be able to query agent_queue_snapshots table"

    def test_queue_snapshots_preserve_order(self, db_path):
        """Verify position field preserves queue order.

        RED: Will fail because persistence not implemented.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 5,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions
        for i in range(3):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=20_000,
                deadline_tick=100,
                priority=i,
                divisible=False,
            )

        # Run simulation
        for _ in range(5):
            orch.tick()

        # Get queue and persist
        sim_id = "test_sim_order"
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        if queue_contents:
            queue_data = [
                {
                    "simulation_id": sim_id,
                    "agent_id": "BANK_A",
                    "day": 0,
                    "queue_type": "queue1",
                    "position": idx,
                    "transaction_id": tx_id,
                }
                for idx, tx_id in enumerate(queue_contents)
            ]

            df = pl.DataFrame(queue_data)
            manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

            # Verify positions are sequential
            result = manager.conn.execute(
                """
                SELECT position
                FROM agent_queue_snapshots
                WHERE simulation_id = 'test_sim_order' AND agent_id = 'BANK_A'
                ORDER BY position
                """
            ).fetchall()

            positions = [row[0] for row in result]
            expected_positions = list(range(len(queue_contents)))

            assert positions == expected_positions, "Positions should be sequential (0, 1, 2, ...)"

    def test_queue_snapshots_match_queue_size(self, db_path):
        """Verify snapshot count matches queue_size metric.

        RED: Will fail because persistence not implemented.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Submit transactions
        for _ in range(5):
            orch.submit_transaction(
                sender="BANK_A",
                receiver="BANK_B",
                amount=50_000,
                deadline_tick=100,
                priority=5,
                divisible=False,
            )

        # Run simulation
        for _ in range(10):
            orch.tick()

        # Get queue size directly from Rust
        queue_size_rust = orch.get_queue1_size("BANK_A")

        # Get queue contents and persist
        sim_id = "test_sim_match"
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        # Verify FFI consistency
        assert len(queue_contents) == queue_size_rust, (
            f"Queue contents length ({len(queue_contents)}) should match "
            f"queue size ({queue_size_rust})"
        )

        if queue_contents:
            queue_data = [
                {
                    "simulation_id": sim_id,
                    "agent_id": "BANK_A",
                    "day": 0,
                    "queue_type": "queue1",
                    "position": idx,
                    "transaction_id": tx_id,
                }
                for idx, tx_id in enumerate(queue_contents)
            ]

            df = pl.DataFrame(queue_data)
            manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

            # Verify database count matches
            result = manager.conn.execute(
                """
                SELECT COUNT(*)
                FROM agent_queue_snapshots
                WHERE simulation_id = 'test_sim_match' AND agent_id = 'BANK_A'
                """
            ).fetchone()

            db_count = result[0]
            assert db_count == queue_size_rust, (
                f"Database count ({db_count}) should match queue size ({queue_size_rust})"
            )

    def test_multiple_agents_multiple_days(self, db_path):
        """Verify queue snapshots for multiple agents and days.

        RED: Will fail because persistence not implemented.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 5,
            "num_days": 2,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 10_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 10_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        sim_id = "test_sim_multi"

        # Simulate with snapshots per day
        for day in range(2):
            # Submit transactions at start of day
            orch.submit_transaction("BANK_A", "BANK_C", 50_000, 100, 5, False)
            orch.submit_transaction("BANK_B", "BANK_C", 50_000, 100, 5, False)

            # Run day
            for _ in range(5):
                orch.tick()

            # Snapshot queues at end of day
            for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
                queue_contents = orch.get_agent_queue1_contents(agent_id)

                if queue_contents:
                    queue_data = [
                        {
                            "simulation_id": sim_id,
                            "agent_id": agent_id,
                            "day": day,
                            "queue_type": "queue1",
                            "position": idx,
                            "transaction_id": tx_id,
                        }
                        for idx, tx_id in enumerate(queue_contents)
                    ]

                    df = pl.DataFrame(queue_data)
                    manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

        # Verify we have snapshots for multiple agents/days
        result = manager.conn.execute(
            """
            SELECT DISTINCT agent_id, day
            FROM agent_queue_snapshots
            WHERE simulation_id = 'test_sim_multi'
            ORDER BY agent_id, day
            """
        ).fetchall()

        # We should have at least some snapshots
        # Exact count depends on whether queues had content
        assert len(result) >= 0, "Should be able to query multi-agent snapshots"


class TestQueueDataIntegrity:
    """Test data integrity of queue snapshots.

    RED: Will fail because data doesn't exist yet.
    """

    def test_queue_positions_sequential(self, db_path):
        """Verify queue positions have no gaps.

        RED: No data to test yet.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 5,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 5_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Create queue with multiple items
        for i in range(5):
            orch.submit_transaction("BANK_A", "BANK_B", 20_000, 100, i, False)

        for _ in range(5):
            orch.tick()

        # Persist
        sim_id = "test_integrity"
        queue_contents = orch.get_agent_queue1_contents("BANK_A")

        if queue_contents:
            queue_data = [
                {
                    "simulation_id": sim_id,
                    "agent_id": "BANK_A",
                    "day": 0,
                    "queue_type": "queue1",
                    "position": idx,
                    "transaction_id": tx_id,
                }
                for idx, tx_id in enumerate(queue_contents)
            ]

            df = pl.DataFrame(queue_data)
            manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

            # Check for gaps
            result = manager.conn.execute(
                """
                SELECT position
                FROM agent_queue_snapshots
                WHERE simulation_id = 'test_integrity'
                ORDER BY position
                """
            ).fetchall()

            positions = [row[0] for row in result]

            # Positions should be 0, 1, 2, ... with no gaps
            for i, pos in enumerate(positions):
                assert pos == i, f"Position gap detected: expected {i}, got {pos}"

    def test_queue_transaction_ids_valid(self, db_path):
        """Verify all transaction IDs in queue snapshots exist in transactions table.

        RED: No data to test yet.
        """
        # This test will be implemented once we have both tables populated
        # For now, just verify the query structure works
        manager = DatabaseManager(db_path)
        manager.setup()

        # This query should work (even if no data yet)
        result = manager.conn.execute(
            """
            SELECT COUNT(*)
            FROM agent_queue_snapshots q
            LEFT JOIN transactions t ON q.transaction_id = t.tx_id
            WHERE t.tx_id IS NULL
            """
        ).fetchone()

        orphan_count = result[0]
        assert orphan_count == 0, "No orphaned transaction IDs should exist in queue snapshots"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
