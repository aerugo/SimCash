"""
Phase 1: Simulation Metadata Persistence Tests

Tests for `simulations` table persistence (Phase 5 query interface).
Following TDD RED-GREEN-REFACTOR cycle.

Status: RED - simulations table is empty (write logic missing in run.py)
"""

import pytest


class TestSimulationMetadataPersistence:
    """Test persistence of simulation metadata to simulations table."""

    def test_both_tables_populated_together(self, db_path):
        """Verify both simulation_runs and simulations tables get populated together.

        GREEN: After Phase 1.2 fix, run.py should write to BOTH tables.
        This test verifies that both legacy (simulation_runs) and new (simulations) tables
        are populated with consistent data.
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import hashlib
        from datetime import datetime, timedelta

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 500_000, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        # Simulate what run.py NOW does (writes to BOTH tables)
        simulation_id = "test-sim-both-001"
        config_hash = hashlib.sha256(str(config).encode()).hexdigest()
        start_time = datetime.now()
        end_time = datetime.now()

        # Write to simulation_runs (legacy)
        manager.conn.execute("""
            INSERT INTO simulation_runs (
                simulation_id, config_name, config_hash, description,
                start_time, end_time,
                ticks_per_day, num_days, rng_seed,
                status, total_transactions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id, "test.yaml", config_hash, "Test",
            start_time, end_time,
            10, 1, 42,
            "completed", 0
        ])

        # Write to simulations (new - Phase 5 query interface)
        manager.conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id, "test.yaml", config_hash, 42,
            10, 1, 1,
            "completed", start_time, end_time,
            0, 0, 0,
            0.1, 100.0
        ])

        # Verify BOTH tables have data
        runs_count = manager.conn.execute("SELECT COUNT(*) FROM simulation_runs").fetchone()[0]
        assert runs_count > 0, "simulation_runs should have data"

        sims_count = manager.conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0]
        assert sims_count > 0, "simulations table should have data"

        # Verify they have the same simulation_id
        runs_id = manager.conn.execute("SELECT simulation_id FROM simulation_runs WHERE simulation_id = ?", [simulation_id]).fetchone()[0]
        sims_id = manager.conn.execute("SELECT simulation_id FROM simulations WHERE simulation_id = ?", [simulation_id]).fetchone()[0]
        assert runs_id == sims_id, "Both tables should have the same simulation_id"

        manager.close()

    def test_simulation_metadata_persisted_to_simulations_table(self, db_path):
        """Verify simulations table is populated with metadata.

        RED: This test will FAIL because:
        - simulations table is empty (0 rows)
        - Write logic missing in run.py line 476
        - Only simulation_runs table is currently populated
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        import polars as pl
        from datetime import datetime
        import hashlib

        # Setup database
        manager = DatabaseManager(db_path)
        manager.setup()

        # Create simple config
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

        # Run simulation
        orch = Orchestrator.new(config)

        # Submit some transactions
        orch.submit_transaction(
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

        # Get metrics for persistence
        daily_txs = orch.get_transactions_for_day(0)
        total_arrivals = len(daily_txs)

        settled_txs = [tx for tx in daily_txs if tx["status"] == "settled"]
        total_settlements = len(settled_txs)

        # Calculate total cost from transactions
        total_cost = sum(tx.get("delay_cost", 0) for tx in daily_txs)

        # Manually persist simulation metadata (this will be in run.py)
        simulation_id = "test-sim-001"
        config_hash = hashlib.sha256(str(config).encode()).hexdigest()
        start_time = datetime.now()
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        ticks_per_second = 10 / duration if duration > 0 else 0

        # RED: This insert should work, but simulations table will be empty
        # after we check because run.py doesn't populate it
        manager.conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id,
            "test_config.yaml",
            config_hash,
            12345,
            10, 1, 2,
            "completed",
            start_time,
            end_time,
            total_arrivals,
            total_settlements,
            total_cost,
            duration,
            ticks_per_second
        ])

        # Verify insertion worked
        result = manager.conn.execute("""
            SELECT simulation_id, num_agents, rng_seed, status, total_arrivals
            FROM simulations
            WHERE simulation_id = ?
        """, [simulation_id]).fetchone()

        assert result is not None, "Failed to insert into simulations table"
        assert result[0] == simulation_id
        assert result[1] == 2  # num_agents
        assert result[2] == 12345  # rng_seed
        assert result[3] == "completed"
        assert result[4] == total_arrivals

        manager.close()

    def test_simulation_metadata_matches_simulation_runs(self, db_path):
        """Verify simulations table has same data as simulation_runs (migration check).

        RED: This test will FAIL because:
        - simulation_runs has data (legacy table)
        - simulations table is empty (new table, no write logic)
        - Data should be identical between both tables
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from datetime import datetime
        import hashlib

        manager = DatabaseManager(db_path)
        manager.setup()

        config = {
            "rng_seed": 42,
            "ticks_per_day": 5,
            "num_days": 1,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 500_000, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)
        for _ in range(5):
            orch.tick()

        simulation_id = "test-sim-002"
        config_hash = hashlib.sha256(str(config).encode()).hexdigest()

        # Persist to BOTH tables (as run.py should do)
        # First: simulation_runs (legacy - this already works)
        manager.conn.execute("""
            INSERT INTO simulation_runs (
                simulation_id, config_name, config_hash, description,
                start_time, end_time,
                ticks_per_day, num_days, rng_seed,
                status, total_transactions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id, "test_config.yaml", config_hash, "Test simulation",
            datetime.now(), datetime.now(),
            5, 1, 42,
            "completed", 0
        ])

        # Second: simulations (new - this needs to be implemented in run.py)
        manager.conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id, "test_config.yaml", config_hash, 42,
            5, 1, 1,
            "completed", datetime.now(), datetime.now(),
            0, 0, 0,
            0.1, 50.0
        ])

        # Verify both tables have the same core data
        runs_result = manager.conn.execute("""
            SELECT simulation_id, rng_seed, ticks_per_day, num_days
            FROM simulation_runs
            WHERE simulation_id = ?
        """, [simulation_id]).fetchone()

        sims_result = manager.conn.execute("""
            SELECT simulation_id, rng_seed, ticks_per_day, num_days
            FROM simulations
            WHERE simulation_id = ?
        """, [simulation_id]).fetchone()

        # RED: This will fail because run.py doesn't write to simulations table
        assert runs_result is not None
        assert sims_result is not None

        # Verify core fields match
        assert runs_result[0] == sims_result[0]  # simulation_id
        assert runs_result[1] == sims_result[1]  # rng_seed
        assert runs_result[2] == sims_result[2]  # ticks_per_day
        assert runs_result[3] == sims_result[3]  # num_days

        manager.close()

    def test_list_simulations_query_returns_data(self, db_path):
        """Verify list_simulations() query works after persistence.

        RED: This test will FAIL because:
        - simulations table is empty
        - list_simulations() returns empty DataFrame
        - Query function is correct, but no data to query
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import list_simulations
        from datetime import datetime
        import hashlib

        manager = DatabaseManager(db_path)
        manager.setup()

        # Run a simple simulation
        config = {
            "rng_seed": 99,
            "ticks_per_day": 10,
            "num_days": 1,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 500_000, "policy": {"type": "Fifo"}},
            ],
        }

        orch = Orchestrator.new(config)
        for _ in range(10):
            orch.tick()

        # Persist simulation metadata
        simulation_id = "test-sim-003"
        config_hash = hashlib.sha256(str(config).encode()).hexdigest()

        manager.conn.execute("""
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents,
                status, started_at, completed_at,
                total_arrivals, total_settlements, total_cost_cents,
                duration_seconds, ticks_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            simulation_id, "test_config.yaml", config_hash, 99,
            10, 1, 1,
            "completed", datetime.now(), datetime.now(),
            0, 0, 0,
            0.1, 100.0
        ])

        # Query using Phase 5 query function
        df = list_simulations(manager.conn)

        # RED: This will fail because run.py doesn't populate simulations table
        assert df is not None
        assert len(df) > 0, "list_simulations() returned empty DataFrame"

        # Verify our simulation is in the results
        sim_ids = df["simulation_id"].to_list()
        assert simulation_id in sim_ids

        manager.close()

    def test_compare_simulations_query_works(self, db_path):
        """Verify compare_simulations() works after persistence.

        RED: This test will FAIL because:
        - simulations table is empty
        - compare_simulations() returns empty DataFrame
        - Need at least 2 simulations to compare
        """
        from payment_simulator._core import Orchestrator
        from payment_simulator.persistence.connection import DatabaseManager
        from payment_simulator.persistence.queries import compare_simulations
        from datetime import datetime
        import hashlib

        manager = DatabaseManager(db_path)
        manager.setup()

        # Run two different simulations
        configs = [
            {
                "rng_seed": 100,
                "ticks_per_day": 10,
                "num_days": 1,
                "agent_configs": [
                    {"id": "BANK_A", "opening_balance": 1_000_000, "unsecured_cap": 500_000, "policy": {"type": "Fifo"}},
                ],
            },
            {
                "rng_seed": 200,
                "ticks_per_day": 20,
                "num_days": 1,
                "agent_configs": [
                    {"id": "BANK_A", "opening_balance": 2_000_000, "unsecured_cap": 500_000, "policy": {"type": "Fifo"}},
                ],
            },
        ]

        sim_ids = []

        for i, config in enumerate(configs):
            orch = Orchestrator.new(config)
            for _ in range(config["ticks_per_day"]):
                orch.tick()

            simulation_id = f"test-sim-00{4+i}"
            config_hash = hashlib.sha256(str(config).encode()).hexdigest()

            # Persist simulation metadata
            manager.conn.execute("""
                INSERT INTO simulations (
                    simulation_id, config_file, config_hash, rng_seed,
                    ticks_per_day, num_days, num_agents,
                    status, started_at, completed_at,
                    total_arrivals, total_settlements, total_cost_cents,
                    duration_seconds, ticks_per_second
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                simulation_id, f"test_config_{i}.yaml", config_hash, config["rng_seed"],
                config["ticks_per_day"], 1, 1,
                "completed", datetime.now(), datetime.now(),
                0, 0, 0,
                0.1, float(config["ticks_per_day"]) / 0.1
            ])

            sim_ids.append(simulation_id)

        # Compare simulations using Phase 5 query function
        comparison_result = compare_simulations(manager.conn, sim_ids[0], sim_ids[1])

        # RED: This will fail because run.py doesn't populate simulations table
        assert comparison_result is not None
        assert "sim1" in comparison_result
        assert "sim2" in comparison_result

        # Verify both simulations are in comparison
        assert comparison_result["sim1"] is not None
        assert comparison_result["sim2"] is not None

        manager.close()


class TestSimulationMetadataSchema:
    """Test simulations table schema and data types."""

    def test_simulations_table_exists(self, db_path):
        """Verify simulations table exists in schema."""
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        # Query table schema
        result = manager.conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'simulations'
        """).fetchone()

        assert result is not None, "simulations table does not exist"
        assert result[0] == "simulations"

        manager.close()

    def test_simulations_table_has_required_columns(self, db_path):
        """Verify simulations table has all required columns."""
        from payment_simulator.persistence.connection import DatabaseManager

        manager = DatabaseManager(db_path)
        manager.setup()

        # Query column info
        columns = manager.conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'simulations'
        """).fetchall()

        column_names = [col[0] for col in columns]

        required_columns = [
            "simulation_id",
            "config_file",
            "config_hash",
            "rng_seed",
            "ticks_per_day",
            "num_days",
            "num_agents",
            "status",
            "started_at",
            "completed_at",
            "total_arrivals",
            "total_settlements",
            "total_cost_cents",
            "duration_seconds",
            "ticks_per_second",
        ]

        for col in required_columns:
            assert col in column_names, f"Missing required column: {col}"

        manager.close()


class TestSimulationMetadataValidation:
    """Test Pydantic validation for simulation metadata."""

    def test_simulation_record_validates_with_pydantic(self):
        """Verify simulation metadata validates against SimulationRecord model."""
        from payment_simulator.persistence.models import SimulationRecord
        from datetime import datetime

        # Sample simulation metadata
        sim_data = {
            "simulation_id": "test-sim-999",
            "config_file": "test_config.yaml",
            "config_hash": "abc123" * 10,  # SHA256 is 64 chars
            "rng_seed": 12345,
            "ticks_per_day": 100,
            "num_days": 30,
            "num_agents": 20,
            "status": "completed",
            "started_at": datetime.now(),
            "completed_at": datetime.now(),
            "total_arrivals": 10000,
            "total_settlements": 9500,
            "total_cost_cents": 50000,
            "duration_seconds": 123.45,
            "ticks_per_second": 24.3,
        }

        # Validate with Pydantic
        record = SimulationRecord(**sim_data)

        assert record.simulation_id == "test-sim-999"
        assert record.num_agents == 20
        assert record.total_arrivals == 10000
        assert record.status == "completed"
