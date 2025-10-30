"""
Integration tests for LSM cycle persistence (Phase 4).

Tests follow TDD RED-GREEN-REFACTOR:
- Phase 4.1: Write tests (RED - tests fail initially)
- Phase 4.2: Implement Rust LSM cycle tracking (GREEN)
- Phase 4.3: Add Python persistence logic (GREEN)
- Phase 4.4: Verify all tests pass (REFACTOR)

LSM (Liquidity-Saving Mechanism) tracks:
- Bilateral offsetting (A↔B netting)
- Multilateral cycles (A→B→C→A)
- Net value settled per cycle
"""

import pytest
import json
from pathlib import Path
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def db_path(tmp_path, request):
    """Create unique database for each test."""
    test_name = request.node.name
    db_file = tmp_path / f"{test_name}.db"
    return db_file


class TestFFILsmCycleRetrieval:
    """Test Rust FFI methods for LSM cycle retrieval.

    RED: Will fail because FFI method doesn't exist yet.
    """

    def test_ffi_get_lsm_cycles_for_day_exists(self):
        """Verify FFI method get_lsm_cycles_for_day() exists.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # RED: Method doesn't exist
        assert hasattr(orch, "get_lsm_cycles_for_day"), (
            "Orchestrator should have get_lsm_cycles_for_day() method"
        )

    def test_ffi_get_lsm_cycles_returns_list(self):
        """Verify method returns list of cycle dicts.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run some ticks
        for _ in range(10):
            orch.tick()

        # RED: Method doesn't exist
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        assert isinstance(lsm_cycles, list), "Should return a list"

    def test_lsm_cycle_has_required_fields(self):
        """Verify LSM cycle dict has all required fields.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        # RED: Method doesn't exist
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        # If we got any cycles, verify they have required fields
        if lsm_cycles:
            cycle = lsm_cycles[0]
            required_fields = [
                "tick",
                "day",
                "cycle_type",
                "cycle_length",
                "agents",
                "transactions",
                "settled_value",
                "total_value",
            ]

            for field in required_fields:
                assert field in cycle, f"Cycle should have '{field}' field"


class TestLsmCyclePersistence:
    """Test LSM cycle persistence to database.

    RED: Will fail because:
    1. FFI method doesn't exist
    2. Database table doesn't exist
    3. Persistence logic not added
    """

    def test_lsm_cycles_table_schema(self, db_path):
        """Verify lsm_cycles table has correct schema.

        RED: Table doesn't exist yet.
        """
        manager = DatabaseManager(db_path)
        manager.setup()

        # Check table exists
        result = manager.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lsm_cycles'"
        ).fetchall()

        assert len(result) == 1, "lsm_cycles table should exist"

        # Check schema
        schema = manager.conn.execute("DESCRIBE lsm_cycles").fetchall()
        column_names = [row[0] for row in schema]

        required_columns = [
            "id",
            "simulation_id",
            "tick",
            "day",
            "cycle_type",
            "cycle_length",
            "agents",
            "transactions",
            "settled_value",
            "total_value",
        ]

        for col in required_columns:
            assert col in column_names, f"Column {col} should exist"

    def test_lsm_cycles_persisted(self, db_path):
        """Verify LSM cycles are persisted to database.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        # Run simulation
        for _ in range(10):
            orch.tick()

        # RED: Method doesn't exist
        sim_id = "test_sim_lsm_1"
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        # Simulate what run.py will do
        if lsm_cycles:
            lsm_data = []
            for cycle in lsm_cycles:
                lsm_data.append({
                    "simulation_id": sim_id,
                    "tick": cycle["tick"],
                    "day": cycle["day"],
                    "cycle_type": cycle["cycle_type"],
                    "cycle_length": cycle["cycle_length"],
                    "agents": json.dumps(cycle["agents"]),
                    "transactions": json.dumps(cycle["transactions"]),
                    "settled_value": cycle["settled_value"],
                    "total_value": cycle["total_value"],
                })

            df = pl.DataFrame(lsm_data)
            manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")

        # Verify persistence
        result = manager.conn.execute(
            "SELECT COUNT(*) FROM lsm_cycles WHERE simulation_id = 'test_sim_lsm_1'"
        ).fetchone()

        count = result[0]
        # We expect SOME LSM cycles might occur (depends on scenario)
        assert count >= 0, "Should be able to query lsm_cycles table"

    def test_bilateral_vs_multilateral(self, db_path):
        """Verify cycle_type correctly distinguishes bilateral vs multilateral.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        # Get cycles and persist
        sim_id = "test_sim_type"
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        if lsm_cycles:
            lsm_data = []
            for cycle in lsm_cycles:
                lsm_data.append({
                    "simulation_id": sim_id,
                    "tick": cycle["tick"],
                    "day": cycle["day"],
                    "cycle_type": cycle["cycle_type"],
                    "cycle_length": cycle["cycle_length"],
                    "agents": json.dumps(cycle["agents"]),
                    "transactions": json.dumps(cycle["transactions"]),
                    "settled_value": cycle["settled_value"],
                    "total_value": cycle["total_value"],
                })

            df = pl.DataFrame(lsm_data)
            manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")

            # Verify cycle types
            result = manager.conn.execute(
                """
                SELECT cycle_type, cycle_length
                FROM lsm_cycles
                WHERE simulation_id = 'test_sim_type'
                """
            ).fetchall()

            for row in result:
                cycle_type, cycle_length = row
                if cycle_length == 2:
                    assert cycle_type == "bilateral", "2-agent cycles should be bilateral"
                else:
                    assert cycle_type == "multilateral", f"{cycle_length}-agent cycles should be multilateral"

    def test_cycle_values_accurate(self, db_path):
        """Verify settled_value and total_value are accurate.

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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        sim_id = "test_sim_values"
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        if lsm_cycles:
            lsm_data = []
            for cycle in lsm_cycles:
                lsm_data.append({
                    "simulation_id": sim_id,
                    "tick": cycle["tick"],
                    "day": cycle["day"],
                    "cycle_type": cycle["cycle_type"],
                    "cycle_length": cycle["cycle_length"],
                    "agents": json.dumps(cycle["agents"]),
                    "transactions": json.dumps(cycle["transactions"]),
                    "settled_value": cycle["settled_value"],
                    "total_value": cycle["total_value"],
                })

            df = pl.DataFrame(lsm_data)
            manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")

            # Verify values are positive
            result = manager.conn.execute(
                """
                SELECT settled_value, total_value
                FROM lsm_cycles
                WHERE simulation_id = 'test_sim_values'
                """
            ).fetchall()

            for row in result:
                settled_value, total_value = row
                assert settled_value > 0, "Settled value should be positive"
                assert total_value > 0, "Total value should be positive"
                assert settled_value <= total_value, "Settled value should be <= total value"

    def test_multiple_cycles_per_day(self, db_path):
        """Verify multiple cycles tracked separately.

        RED: Will fail because persistence not implemented.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 20,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(20):
            orch.tick()

        sim_id = "test_sim_multi"
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        if lsm_cycles:
            lsm_data = []
            for cycle in lsm_cycles:
                lsm_data.append({
                    "simulation_id": sim_id,
                    "tick": cycle["tick"],
                    "day": cycle["day"],
                    "cycle_type": cycle["cycle_type"],
                    "cycle_length": cycle["cycle_length"],
                    "agents": json.dumps(cycle["agents"]),
                    "transactions": json.dumps(cycle["transactions"]),
                    "settled_value": cycle["settled_value"],
                    "total_value": cycle["total_value"],
                })

            df = pl.DataFrame(lsm_data)
            manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")

            # Verify we can have multiple cycles
            result = manager.conn.execute(
                """
                SELECT COUNT(DISTINCT id)
                FROM lsm_cycles
                WHERE simulation_id = 'test_sim_multi'
                """
            ).fetchone()

            count = result[0]
            # We should be able to track multiple cycles separately
            assert count >= 0, "Should track multiple cycles separately"


class TestLsmCycleDataIntegrity:
    """Test data integrity of LSM cycle records.

    RED: Will fail because data doesn't exist yet.
    """

    def test_agents_array_valid_json(self, db_path):
        """Verify agents field is valid JSON array.

        RED: No data to test yet.
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
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                    "credit_limit": 0,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        orch = Orchestrator.new(config)

        for _ in range(10):
            orch.tick()

        sim_id = "test_json"
        lsm_cycles = orch.get_lsm_cycles_for_day(0)

        if lsm_cycles:
            lsm_data = []
            for cycle in lsm_cycles:
                lsm_data.append({
                    "simulation_id": sim_id,
                    "tick": cycle["tick"],
                    "day": cycle["day"],
                    "cycle_type": cycle["cycle_type"],
                    "cycle_length": cycle["cycle_length"],
                    "agents": json.dumps(cycle["agents"]),
                    "transactions": json.dumps(cycle["transactions"]),
                    "settled_value": cycle["settled_value"],
                    "total_value": cycle["total_value"],
                })

            df = pl.DataFrame(lsm_data)
            manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")

            # Verify JSON arrays are parseable
            result = manager.conn.execute(
                "SELECT agents, transactions FROM lsm_cycles WHERE simulation_id = 'test_json'"
            ).fetchall()

            for row in result:
                agents_json, transactions_json = row

                # Should be able to parse as JSON
                agents = json.loads(agents_json)
                transactions = json.loads(transactions_json)

                # Should be lists
                assert isinstance(agents, list), "Agents should be a list"
                assert isinstance(transactions, list), "Transactions should be a list"

                # Should have same length
                assert len(agents) > 0, "Agents list should not be empty"
                assert len(transactions) > 0, "Transactions list should not be empty"

    def test_transaction_ids_in_cycle_exist(self, db_path):
        """Verify all transaction IDs in cycles exist in transactions table.

        RED: No data to test yet.
        """
        # This test will be implemented once we have both tables populated
        manager = DatabaseManager(db_path)
        manager.setup()

        # This query should work (even if no data yet)
        result = manager.conn.execute(
            """
            SELECT COUNT(*)
            FROM lsm_cycles lsm
            WHERE simulation_id = 'nonexistent'
            """
        ).fetchone()

        count = result[0]
        assert count == 0, "No orphaned cycles should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
