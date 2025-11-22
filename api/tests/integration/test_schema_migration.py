"""
Test schema migration and validation issues.

Tests for ensuring that schema validation failures properly handle
table recreation when columns are missing or mismatched.
"""

import tempfile
from pathlib import Path

import duckdb
import pytest

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.writers import write_transactions


class TestSchemaMigration:
    """Test schema migration and validation."""

    def test_schema_column_mismatch_on_write(self):
        """
        Test that writing transactions with new schema to old database fails.

        This reproduces the bug where:
        1. Database has old schema (21 columns, missing overdue_since_tick)
        2. Rust FFI returns transactions with new schema (22 columns)
        3. Write fails with "table has 21 columns but 22 values were supplied"

        This test should FAIL before the fix and PASS after the fix.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Step 1: Create database with OLD schema (without overdue_since_tick)
            conn = duckdb.connect(str(db_path))

            # Manually create transactions table with old schema (21 columns, no overdue_since_tick)
            old_schema_ddl = """
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL,
                sender_id VARCHAR NOT NULL,
                receiver_id VARCHAR NOT NULL,
                amount BIGINT NOT NULL,
                priority BIGINT NOT NULL,
                is_divisible BOOLEAN NOT NULL,
                arrival_tick BIGINT NOT NULL,
                arrival_day BIGINT NOT NULL,
                deadline_tick BIGINT NOT NULL,
                settlement_tick BIGINT,
                settlement_day BIGINT,
                status VARCHAR NOT NULL,
                drop_reason VARCHAR,
                amount_settled BIGINT NOT NULL,
                queue1_ticks BIGINT NOT NULL,
                queue2_ticks BIGINT NOT NULL,
                total_delay_ticks BIGINT NOT NULL,
                delay_cost BIGINT NOT NULL,
                parent_tx_id VARCHAR,
                split_index BIGINT,
                PRIMARY KEY (simulation_id, tx_id)
            );
            """
            conn.execute(old_schema_ddl)
            conn.close()

            # Step 2: Try to write transaction data with NEW schema (22 columns)
            # This simulates what happens when Rust FFI returns data with overdue_since_tick
            manager = DatabaseManager(db_path)

            # Create sample transaction data with all fields (including overdue_since_tick)
            transactions = [
                {
                    "simulation_id": "sim-12345",
                    "tx_id": "tx-001",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "priority": 5,
                    "is_divisible": False,
                    "arrival_tick": 0,
                    "arrival_day": 0,
                    "deadline_tick": 10,
                    "settlement_tick": 5,
                    "settlement_day": 0,
                    "status": "settled",
                    "overdue_since_tick": None,  # New field causing the mismatch
                    "drop_reason": None,
                    "amount_settled": 100000,
                    "queue1_ticks": 0,
                    "queue2_ticks": 0,
                    "total_delay_ticks": 0,
                    "delay_cost": 0,
                    "parent_tx_id": None,
                    "split_index": None,
                    "rtgs_priority": None,
                    "rtgs_submission_tick": None,
                    "declared_rtgs_priority": None,
                }
            ]

            # Step 3: This should fail with column mismatch error
            # After fix, the schema validation should detect the missing column,
            # drop the table, and recreate it with the correct schema
            with pytest.raises(Exception) as exc_info:
                write_transactions(manager.conn, "sim-12345", transactions)

            # Verify it's the column mismatch error we expect
            assert "21 columns but 25 values" in str(exc_info.value)

            manager.close()

    def test_schema_validation_detects_missing_column(self):
        """
        Test that schema validation correctly detects missing overdue_since_tick column.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create database with old schema (missing overdue_since_tick)
            conn = duckdb.connect(str(db_path))
            old_schema_ddl = """
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL,
                sender_id VARCHAR NOT NULL,
                receiver_id VARCHAR NOT NULL,
                amount BIGINT NOT NULL,
                priority BIGINT NOT NULL,
                is_divisible BOOLEAN NOT NULL,
                arrival_tick BIGINT NOT NULL,
                arrival_day BIGINT NOT NULL,
                deadline_tick BIGINT NOT NULL,
                settlement_tick BIGINT,
                settlement_day BIGINT,
                status VARCHAR NOT NULL,
                drop_reason VARCHAR,
                amount_settled BIGINT NOT NULL,
                queue1_ticks BIGINT NOT NULL,
                queue2_ticks BIGINT NOT NULL,
                total_delay_ticks BIGINT NOT NULL,
                delay_cost BIGINT NOT NULL,
                parent_tx_id VARCHAR,
                split_index BIGINT,
                PRIMARY KEY (simulation_id, tx_id)
            );
            """
            conn.execute(old_schema_ddl)
            conn.close()

            # Validate schema - should detect missing column
            manager = DatabaseManager(db_path)
            is_valid = manager.validate_schema(quiet=True)

            # Should be invalid (missing overdue_since_tick)
            assert not is_valid, "Schema validation should detect missing overdue_since_tick column"

            manager.close()

    def test_schema_reinitialization_after_validation_failure(self):
        """
        Test that schema re-initialization after validation failure properly recreates tables.

        This is the core fix: when validation fails, we should DROP and recreate tables,
        not just run CREATE TABLE IF NOT EXISTS (which does nothing for existing tables).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Step 1: Create database with old schema
            conn = duckdb.connect(str(db_path))
            old_schema_ddl = """
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL,
                sender_id VARCHAR NOT NULL,
                receiver_id VARCHAR NOT NULL,
                amount BIGINT NOT NULL,
                priority BIGINT NOT NULL,
                is_divisible BOOLEAN NOT NULL,
                arrival_tick BIGINT NOT NULL,
                arrival_day BIGINT NOT NULL,
                deadline_tick BIGINT NOT NULL,
                settlement_tick BIGINT,
                settlement_day BIGINT,
                status VARCHAR NOT NULL,
                drop_reason VARCHAR,
                amount_settled BIGINT NOT NULL,
                queue1_ticks BIGINT NOT NULL,
                queue2_ticks BIGINT NOT NULL,
                total_delay_ticks BIGINT NOT NULL,
                delay_cost BIGINT NOT NULL,
                parent_tx_id VARCHAR,
                split_index BIGINT,
                PRIMARY KEY (simulation_id, tx_id)
            );
            """
            conn.execute(old_schema_ddl)
            conn.close()

            # Step 2: Validate and reinitialize (simulating what CLI does)
            manager = DatabaseManager(db_path)

            # Validation should fail
            is_valid = manager.validate_schema(quiet=True)
            assert not is_valid, "Schema should be invalid (missing overdue_since_tick)"

            # Re-initialize schema with force_recreate=True (this is the fix)
            manager.initialize_schema(force_recreate=True)

            # Step 3: Validate again - should now be valid
            is_valid_after = manager.validate_schema(quiet=True)
            assert is_valid_after, "Schema should be valid after re-initialization"

            # Step 4: Try to write transactions - should succeed now
            transactions = [
                {
                    "simulation_id": "sim-12345",
                    "tx_id": "tx-001",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "priority": 5,
                    "is_divisible": False,
                    "arrival_tick": 0,
                    "arrival_day": 0,
                    "deadline_tick": 10,
                    "settlement_tick": 5,
                    "settlement_day": 0,
                    "status": "settled",
                    "overdue_since_tick": None,
                    "drop_reason": None,
                    "amount_settled": 100000,
                    "queue1_ticks": 0,
                    "queue2_ticks": 0,
                    "total_delay_ticks": 0,
                    "delay_cost": 0,
                    "parent_tx_id": None,
                    "split_index": None,
                    "rtgs_priority": None,
                    "rtgs_submission_tick": None,
                    "declared_rtgs_priority": None,
                }
            ]

            # This should succeed without column mismatch error
            count = write_transactions(manager.conn, "sim-12345", transactions)
            assert count == 1, "Should successfully write 1 transaction"

            manager.close()
