"""
TDD Cycle 1: Database Manager Tests

These tests define the requirements for DatabaseManager that handles:
- DuckDB connection management
- Schema initialization from Pydantic models
- Schema validation
- Migration application
- Context manager support

Following the RED phase: these tests will fail until we implement DatabaseManager.
"""

import pytest
import duckdb
from pathlib import Path


class TestDatabaseManagerInit:
    """Test DatabaseManager initialization."""

    def test_database_manager_creates_connection(self, tmp_path):
        """Verify DatabaseManager creates DuckDB connection."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        assert manager.conn is not None
        assert isinstance(manager.conn, duckdb.DuckDBPyConnection)
        assert manager.db_path == db_path

    def test_database_manager_creates_migrations_dir(self, tmp_path):
        """Verify DatabaseManager creates migrations directory."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        # Should have migrations_dir attribute
        assert hasattr(manager, "migrations_dir")
        assert isinstance(manager.migrations_dir, Path)


class TestSchemaInitialization:
    """Test schema initialization from Pydantic models."""

    def test_initialize_schema_creates_tables(self, tmp_path):
        """Verify initialize_schema creates all tables."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        # Check that expected tables exist
        result = manager.conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
        """).fetchall()

        table_names = {row[0] for row in result}

        # Should have core tables
        assert "transactions" in table_names
        assert "simulation_runs" in table_names
        assert "daily_agent_metrics" in table_names
        assert "collateral_events" in table_names

    def test_initialize_schema_uses_ddl_generator(self, tmp_path):
        """Verify initialize_schema uses generate_full_schema_ddl."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        # Verify transactions table has expected columns
        result = manager.conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'transactions'
        """).fetchall()

        column_names = {row[0] for row in result}

        # Check for key columns from TransactionRecord model
        assert "simulation_id" in column_names
        assert "tx_id" in column_names
        assert "amount" in column_names
        assert "status" in column_names


class TestSchemaValidation:
    """Test schema validation against Pydantic models."""

    def test_validate_schema_returns_true_for_valid_schema(self, tmp_path):
        """Verify validate_schema returns True when schema matches."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        is_valid = manager.validate_schema()
        assert is_valid is True

    def test_validate_schema_returns_false_for_invalid_schema(self, tmp_path):
        """Verify validate_schema detects schema mismatches."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        # Create a table that doesn't match the model
        manager.conn.execute("""
            CREATE TABLE transactions (
                id INTEGER,
                wrong_column VARCHAR
            )
        """)

        is_valid = manager.validate_schema()
        assert is_valid is False


class TestMigrationApplication:
    """Test migration application through DatabaseManager."""

    def test_apply_migrations_uses_migration_manager(self, tmp_path):
        """Verify apply_migrations uses MigrationManager."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        manager = DatabaseManager(db_path, migrations_dir=migrations_dir)

        # Create a test migration
        migration_file = migrations_dir / "001_test_migration.sql"
        migration_file.write_text("CREATE TABLE test_migration_table (id INTEGER);")

        manager.apply_migrations()

        # Check migration was applied
        result = manager.conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'test_migration_table'
        """).fetchall()

        assert len(result) == 1

    def test_apply_migrations_records_in_migrations_table(self, tmp_path):
        """Verify applied migrations are tracked."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        manager = DatabaseManager(db_path, migrations_dir=migrations_dir)

        # Create a test migration
        migration_file = migrations_dir / "001_test.sql"
        migration_file.write_text("CREATE TABLE test_table (id INTEGER);")

        manager.apply_migrations()

        # Check migration was recorded
        result = manager.conn.execute("""
            SELECT version, description FROM schema_migrations
        """).fetchall()

        assert len(result) == 1
        assert result[0][0] == 1
        assert result[0][1] == "test"


class TestSetupMethod:
    """Test complete database setup workflow."""

    def test_setup_initializes_and_validates(self, tmp_path):
        """Verify setup() performs full initialization."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.setup()

        # Should have created tables
        result = manager.conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main'
        """).fetchall()

        table_names = {row[0] for row in result}
        assert "transactions" in table_names
        assert "simulation_runs" in table_names

    def test_setup_raises_on_invalid_schema(self, tmp_path):
        """Verify setup() raises if validation fails."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        manager = DatabaseManager(db_path, migrations_dir=migrations_dir)

        # Create valid schema first
        manager.initialize_schema()
        manager.close()

        # Manually corrupt the database schema to make validation fail
        import duckdb
        conn = duckdb.connect(str(db_path))
        # Add a column with wrong type to cause validation failure
        conn.execute("ALTER TABLE transactions ADD COLUMN extra_wrong_column VARCHAR")
        conn.close()

        # Create fresh manager to test setup - validation should fail
        manager2 = DatabaseManager(db_path, migrations_dir=migrations_dir)

        # setup() should raise because validation will detect the schema mismatch
        with pytest.raises(RuntimeError, match="schema validation failed"):
            manager2.setup()


class TestConnectionManagement:
    """Test connection lifecycle management."""

    def test_close_closes_connection(self, tmp_path):
        """Verify close() closes the DuckDB connection."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        manager.close()

        # Attempting to use closed connection should fail
        with pytest.raises(Exception):
            manager.conn.execute("SELECT 1")

    def test_context_manager_support(self, tmp_path):
        """Verify DatabaseManager works as context manager."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"

        with DatabaseManager(db_path) as manager:
            # Should be usable inside context
            result = manager.conn.execute("SELECT 1").fetchone()
            assert result[0] == 1

        # Connection should be closed after context
        with pytest.raises(Exception):
            manager.conn.execute("SELECT 1")


class TestConvenienceFunctions:
    """Test convenience functions for common operations."""

    def test_get_connection_returns_ready_connection(self, tmp_path):
        """Verify get_connection returns initialized connection."""
        from payment_simulator.persistence.connection import get_connection

        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)

        # Should be a valid connection
        assert isinstance(conn, duckdb.DuckDBPyConnection)

        # Should have tables created
        result = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'transactions'
        """).fetchall()

        assert len(result) == 1

    def test_get_connection_validates_schema(self, tmp_path):
        """Verify get_connection performs schema validation."""
        from payment_simulator.persistence.connection import get_connection

        db_path = tmp_path / "test.db"

        # First call should succeed
        conn = get_connection(db_path)
        assert conn is not None

        # Close connection to test fresh connection
        conn.close()

        # Second call should also succeed (schema already valid)
        conn = get_connection(db_path)
        assert conn is not None


class TestMigrationDirectory:
    """Test migration directory management."""

    def test_migrations_dir_created_automatically(self, tmp_path):
        """Verify migrations directory is created if missing."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        # migrations_dir should exist
        assert manager.migrations_dir.exists()
        assert manager.migrations_dir.is_dir()
