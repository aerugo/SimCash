"""
TDD Cycle 3: Schema Validation Tests

These tests define the requirements for runtime schema validation that ensures
the database schema matches the Pydantic models.

Following the RED phase: these tests will fail until we implement validation.
"""

import pytest
import duckdb


class TestSchemaValidationDetectsMissing:
    """Test validation detects missing columns."""

    def test_validate_detects_missing_column(self):
        """Validation should detect when database is missing a column."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import validate_table_schema

        # Create in-memory database with incomplete schema
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL,
                amount BIGINT NOT NULL
                -- Missing many other columns!
            )
        """)

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid, "Should detect missing columns"
        assert len(errors) > 0, "Should return error messages"

        # Check that specific missing columns are reported
        error_text = " ".join(errors).lower()
        assert "sender_id" in error_text or "missing" in error_text

    def test_validate_detects_multiple_missing_columns(self):
        """Validation should report all missing columns."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import validate_table_schema

        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL
                -- Missing most columns
            )
        """)

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid
        # Should detect multiple missing columns
        assert len(errors) >= 5, "Should detect many missing columns"


class TestSchemaValidationDetectsExtra:
    """Test validation detects extra/unexpected columns."""

    def test_validate_detects_extra_column(self):
        """Validation should detect columns in DB not in model."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import (
            generate_create_table_ddl,
            validate_table_schema,
        )

        conn = duckdb.connect(":memory:")

        # Create table with correct schema
        ddl = generate_create_table_ddl(TransactionRecord)
        conn.execute(ddl)

        # Add an extra column not in model
        conn.execute("ALTER TABLE transactions ADD COLUMN extra_field VARCHAR")

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid, "Should detect extra column"
        assert len(errors) > 0

        error_text = " ".join(errors).lower()
        assert "extra" in error_text or "unexpected" in error_text


class TestSchemaValidationPasses:
    """Test validation passes when schema matches."""

    def test_validate_passes_for_matching_schema(self):
        """Validation should pass when DB matches model exactly."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import (
            generate_create_table_ddl,
            validate_table_schema,
        )

        conn = duckdb.connect(":memory:")

        # Create table using auto-generated DDL
        ddl = generate_create_table_ddl(TransactionRecord)
        conn.execute(ddl)

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert is_valid, f"Validation should pass, but got errors: {errors}"
        assert len(errors) == 0, "Should have no errors"

    def test_validate_all_core_models(self):
        """All core models should validate successfully."""
        from payment_simulator.persistence.models import (
            CollateralEventRecord,
            DailyAgentMetricsRecord,
            SimulationRunRecord,
            TransactionRecord,
        )
        from payment_simulator.persistence.schema_generator import (
            generate_create_table_ddl,
            validate_table_schema,
        )

        models = [
            TransactionRecord,
            SimulationRunRecord,
            DailyAgentMetricsRecord,
            CollateralEventRecord,
        ]

        conn = duckdb.connect(":memory:")

        for model in models:
            # Create table
            ddl = generate_create_table_ddl(model)
            conn.execute(ddl)

            # Validate
            is_valid, errors = validate_table_schema(conn, model)

            table_name = model.model_config["table_name"]
            assert is_valid, f"{table_name} validation failed: {errors}"
            assert len(errors) == 0


class TestSchemaValidationMissingTable:
    """Test validation handles missing tables."""

    def test_validate_detects_missing_table(self):
        """Validation should detect when table doesn't exist."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import validate_table_schema

        conn = duckdb.connect(":memory:")
        # Don't create the table

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid, "Should detect missing table"
        assert len(errors) > 0

        error_text = " ".join(errors).lower()
        assert "not exist" in error_text or "transactions" in error_text


class TestSchemaValidationDescriptiveErrors:
    """Test validation provides clear error messages."""

    def test_error_messages_specify_table_name(self):
        """Error messages should include table name."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import validate_table_schema

        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL
            )
        """)

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid
        # At least one error should mention the table
        assert any("transactions" in err.lower() for err in errors)

    def test_error_messages_specify_column_names(self):
        """Error messages should name specific missing columns."""
        from payment_simulator.persistence.models import TransactionRecord
        from payment_simulator.persistence.schema_generator import validate_table_schema

        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL
                -- Missing sender_id, receiver_id, etc.
            )
        """)

        is_valid, errors = validate_table_schema(conn, TransactionRecord)

        assert not is_valid
        # Errors should mention specific missing columns
        error_text = " ".join(errors).lower()
        assert "sender_id" in error_text or "column" in error_text


class TestSchemaValidationEdgeCases:
    """Test validation handles edge cases."""

    def test_validate_handles_empty_model(self):
        """Validation should handle models with minimal fields."""
        from pydantic import BaseModel, ConfigDict
        from payment_simulator.persistence.schema_generator import (
            generate_create_table_ddl,
            validate_table_schema,
        )

        class MinimalModel(BaseModel):
            model_config = ConfigDict(
                table_name="minimal",
                primary_key=["id"],
            )
            id: int

        conn = duckdb.connect(":memory:")
        ddl = generate_create_table_ddl(MinimalModel)
        conn.execute(ddl)

        is_valid, errors = validate_table_schema(conn, MinimalModel)

        assert is_valid
        assert len(errors) == 0

    def test_validate_case_sensitivity(self):
        """Validation should handle column name case correctly."""
        from pydantic import BaseModel, ConfigDict
        from payment_simulator.persistence.schema_generator import validate_table_schema

        class TestModel(BaseModel):
            model_config = ConfigDict(
                table_name="test_case",
                primary_key=["id"],
            )
            id: int
            user_name: str

        conn = duckdb.connect(":memory:")
        # DuckDB is case-insensitive by default, but let's test
        conn.execute("""
            CREATE TABLE test_case (
                id BIGINT NOT NULL,
                user_name VARCHAR NOT NULL,
                PRIMARY KEY (id)
            )
        """)

        is_valid, errors = validate_table_schema(conn, TestModel)

        assert is_valid, f"Case handling failed: {errors}"
