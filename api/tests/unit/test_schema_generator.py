"""
TDD Cycle 2: DDL Generation Tests

These tests define the requirements for automatic DDL generation from Pydantic models.

Following the RED phase: these tests will fail until we implement the schema generator.
"""

import pytest


class TestTypeMapping:
    """Test Python type to SQL type conversion."""

    def test_python_to_sql_type_basic_types(self):
        """Test basic Python type mappings."""
        from payment_simulator.persistence.schema_generator import python_type_to_sql_type

        assert python_type_to_sql_type(str) == "VARCHAR"
        assert python_type_to_sql_type(int) == "BIGINT"
        assert python_type_to_sql_type(float) == "DOUBLE"
        assert python_type_to_sql_type(bool) == "BOOLEAN"

    def test_python_to_sql_type_datetime(self):
        """Test datetime type mapping."""
        from datetime import datetime
        from payment_simulator.persistence.schema_generator import python_type_to_sql_type

        assert python_type_to_sql_type(datetime) == "TIMESTAMP"

    def test_python_to_sql_type_enum(self):
        """Test enum type mapping."""
        from payment_simulator.persistence.models import TransactionStatus
        from payment_simulator.persistence.schema_generator import python_type_to_sql_type

        assert python_type_to_sql_type(TransactionStatus) == "VARCHAR"

    def test_python_to_sql_type_optional(self):
        """Test Optional type handling."""
        from typing import Optional
        from payment_simulator.persistence.schema_generator import python_type_to_sql_type

        # Optional[str] should map to VARCHAR
        assert python_type_to_sql_type(Optional[str]) == "VARCHAR"
        assert python_type_to_sql_type(Optional[int]) == "BIGINT"


class TestCreateTableDDL:
    """Test CREATE TABLE DDL generation."""

    def test_generate_simple_table_ddl(self):
        """Test generating DDL for a simple model."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import generate_create_table_ddl

        ddl = generate_create_table_ddl(TransactionRecord)

        # Verify table name
        assert "CREATE TABLE IF NOT EXISTS transactions" in ddl

        # Verify some key columns exist
        assert "simulation_id" in ddl
        assert "tx_id" in ddl
        assert "amount" in ddl
        assert "status" in ddl

        # Verify primary key constraint
        assert "PRIMARY KEY (simulation_id, tx_id)" in ddl

    def test_ddl_includes_not_null_constraints(self):
        """Test that required fields have NOT NULL constraints."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import generate_create_table_ddl

        ddl = generate_create_table_ddl(TransactionRecord)

        # Required string field should have NOT NULL
        assert "simulation_id VARCHAR NOT NULL" in ddl or "simulation_id VARCHAR(255) NOT NULL" in ddl

    def test_ddl_allows_nulls_for_optional_fields(self):
        """Test that optional fields don't have NOT NULL constraints."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import generate_create_table_ddl

        ddl = generate_create_table_ddl(TransactionRecord)

        # Optional field should not have NOT NULL
        # settlement_tick is Optional[int]
        lines_with_settlement_tick = [line for line in ddl.split("\n") if "settlement_tick" in line]
        assert len(lines_with_settlement_tick) > 0
        # Should not have NOT NULL in the settlement_tick line
        assert not any("NOT NULL" in line for line in lines_with_settlement_tick)

    def test_ddl_auto_increment_for_id_fields(self):
        """Test that id fields get AUTOINCREMENT."""
        from payment_simulator.persistence.models import CollateralEventRecord
        from payment_simulator.persistence.schema_generator import generate_create_table_ddl

        ddl = generate_create_table_ddl(CollateralEventRecord)

        # The id field should have AUTOINCREMENT (or similar depending on DB)
        # For DuckDB, this might be INTEGER PRIMARY KEY or AUTOINCREMENT
        assert "id" in ddl
        # Will check for AUTOINCREMENT or similar pattern


class TestCreateIndexDDL:
    """Test CREATE INDEX DDL generation."""

    def test_generate_indexes_ddl(self):
        """Test generating index DDL statements."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import generate_create_indexes_ddl

        indexes = generate_create_indexes_ddl(TransactionRecord)

        # Should return a list of DDL statements
        assert isinstance(indexes, list)
        assert len(indexes) > 0

        # Check for specific indexes
        index_str = " ".join(indexes)
        assert "idx_tx_sim_sender" in index_str
        assert "idx_tx_sim_day" in index_str
        assert "idx_tx_status" in index_str

    def test_index_ddl_format(self):
        """Test index DDL statement format."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import generate_create_indexes_ddl

        indexes = generate_create_indexes_ddl(TransactionRecord)

        # Each statement should be a valid CREATE INDEX
        for index in indexes:
            assert "CREATE INDEX IF NOT EXISTS" in index
            assert "ON transactions" in index

    def test_no_indexes_returns_empty_list(self):
        """Test models without indexes return empty list."""
        from pydantic import BaseModel, ConfigDict

        class SimpleModel(BaseModel):
            model_config = ConfigDict(
                table_name="simple",
                primary_key=["id"],
                indexes=[],
            )
            id: int
            name: str

        from payment_simulator.persistence.schema_generator import generate_create_indexes_ddl

        indexes = generate_create_indexes_ddl(SimpleModel)
        assert indexes == []


class TestFullSchemaDDL:
    """Test complete schema generation."""

    def test_generate_full_schema_includes_all_tables(self):
        """Test that full schema generation includes all models."""
        from payment_simulator.persistence.schema_generator import generate_full_schema_ddl

        ddl = generate_full_schema_ddl()

        # Verify all major tables are present
        assert "transactions" in ddl
        assert "simulation_runs" in ddl
        assert "daily_agent_metrics" in ddl
        assert "collateral_events" in ddl

    def test_full_schema_includes_migrations_table(self):
        """Test that schema_migrations table is included."""
        from payment_simulator.persistence.schema_generator import generate_full_schema_ddl

        ddl = generate_full_schema_ddl()

        assert "schema_migrations" in ddl
        assert "version" in ddl
        assert "applied_at" in ddl


class TestDDLValidation:
    """Test DDL validation logic."""

    def test_model_without_table_name_raises_error(self):
        """Test that models without table_name raise error."""
        from pydantic import BaseModel
        from payment_simulator.persistence.schema_generator import generate_create_table_ddl

        class BadModel(BaseModel):
            id: int
            name: str

        with pytest.raises(ValueError, match="missing.*table_name"):
            generate_create_table_ddl(BadModel)
