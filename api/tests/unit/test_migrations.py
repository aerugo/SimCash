"""
TDD Cycle 4: Migration System Tests

These tests define the requirements for versioned schema migrations.

Following the RED phase: these tests will fail until we implement the migration manager.
"""

import pytest
import duckdb
from pathlib import Path
from datetime import datetime


class TestMigrationManagerInit:
    """Test MigrationManager initialization."""

    def test_creates_schema_migrations_table(self, tmp_path):
        """MigrationManager should create schema_migrations table on init."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        # Verify table exists
        result = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'schema_migrations'
        """).fetchall()

        assert len(result) == 1, "schema_migrations table should exist"

    def test_schema_migrations_has_correct_columns(self, tmp_path):
        """schema_migrations table should have version, applied_at, description."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        # Query column information
        result = conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'schema_migrations'
            ORDER BY column_name
        """).fetchall()

        column_names = [row[0] for row in result]
        assert "version" in column_names
        assert "applied_at" in column_names
        assert "description" in column_names


class TestAppliedVersions:
    """Test tracking of applied migrations."""

    def test_get_applied_versions_empty_initially(self, tmp_path):
        """Initially, no migrations should be applied."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)
        applied = manager.get_applied_versions()

        assert isinstance(applied, set)
        assert len(applied) == 0

    def test_get_applied_versions_returns_versions(self, tmp_path):
        """Should return set of applied version numbers."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        # Manually insert some migrations
        conn.execute("""
            INSERT INTO schema_migrations (version, applied_at, description)
            VALUES (1, ?, 'initial schema')
        """, [datetime.now()])
        conn.execute("""
            INSERT INTO schema_migrations (version, applied_at, description)
            VALUES (2, ?, 'add settlement type')
        """, [datetime.now()])

        applied = manager.get_applied_versions()

        assert applied == {1, 2}


class TestPendingMigrations:
    """Test detection of pending migrations."""

    def test_get_pending_migrations_empty_directory(self, tmp_path):
        """Empty migrations directory should return no pending migrations."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        assert isinstance(pending, list)
        assert len(pending) == 0

    def test_get_pending_migrations_finds_sql_files(self, tmp_path):
        """Should find .sql files in migrations directory."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create migration files
        (migrations_dir / "001_initial_schema.sql").write_text("CREATE TABLE test (id INT);")
        (migrations_dir / "002_add_column.sql").write_text("ALTER TABLE test ADD COLUMN name VARCHAR;")

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        assert len(pending) == 2
        assert pending[0][0] == 1  # version
        assert pending[1][0] == 2

    def test_get_pending_migrations_parses_description(self, tmp_path):
        """Should extract description from filename."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_add_settlement_type.sql").write_text("-- migration")

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        version, description, sql = pending[0]
        assert version == 1
        assert "settlement type" in description  # Underscores replaced with spaces

    def test_get_pending_migrations_excludes_applied(self, tmp_path):
        """Should exclude already-applied migrations."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create migration files
        (migrations_dir / "001_initial.sql").write_text("CREATE TABLE test (id INT);")
        (migrations_dir / "002_add_column.sql").write_text("ALTER TABLE test ADD COLUMN name VARCHAR;")

        manager = MigrationManager(conn, migrations_dir)

        # Mark version 1 as applied
        conn.execute("""
            INSERT INTO schema_migrations (version, applied_at, description)
            VALUES (1, ?, 'initial')
        """, [datetime.now()])

        pending = manager.get_pending_migrations()

        assert len(pending) == 1
        assert pending[0][0] == 2  # Only version 2 is pending

    def test_get_pending_migrations_returns_sorted(self, tmp_path):
        """Pending migrations should be sorted by version number."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create files in non-sequential order
        (migrations_dir / "003_third.sql").write_text("-- third")
        (migrations_dir / "001_first.sql").write_text("-- first")
        (migrations_dir / "002_second.sql").write_text("-- second")

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        versions = [p[0] for p in pending]
        assert versions == [1, 2, 3]  # Should be sorted


class TestApplyMigration:
    """Test applying individual migrations."""

    def test_apply_migration_executes_sql(self, tmp_path):
        """Should execute migration SQL."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        sql = "CREATE TABLE test_table (id INTEGER, name VARCHAR);"
        manager.apply_migration(1, "create test table", sql)

        # Verify table was created
        result = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'test_table'
        """).fetchall()

        assert len(result) == 1

    def test_apply_migration_records_in_migrations_table(self, tmp_path):
        """Should record migration in schema_migrations table."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        sql = "CREATE TABLE test (id INT);"
        manager.apply_migration(1, "test migration", sql)

        # Verify record exists
        result = conn.execute("""
            SELECT version, description FROM schema_migrations WHERE version = 1
        """).fetchone()

        assert result is not None
        assert result[0] == 1
        assert result[1] == "test migration"

    def test_apply_migration_rollback_on_error(self, tmp_path):
        """Should rollback if migration SQL fails."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        # Invalid SQL
        bad_sql = "THIS IS NOT VALID SQL;"

        with pytest.raises(RuntimeError, match="Migration 1 failed"):
            manager.apply_migration(1, "bad migration", bad_sql)

        # Verify migration was NOT recorded
        result = conn.execute("""
            SELECT COUNT(*) FROM schema_migrations WHERE version = 1
        """).fetchone()

        assert result[0] == 0


class TestApplyPendingMigrations:
    """Test applying all pending migrations."""

    def test_apply_pending_migrations_applies_all(self, tmp_path, capsys):
        """Should apply all pending migrations in order."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create migration files
        (migrations_dir / "001_create_users.sql").write_text("CREATE TABLE users (id INT);")
        (migrations_dir / "002_create_posts.sql").write_text("CREATE TABLE posts (id INT);")

        manager = MigrationManager(conn, migrations_dir)
        manager.apply_pending_migrations()

        # Verify both tables exist
        tables = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name IN ('users', 'posts')
        """).fetchall()

        assert len(tables) == 2

        # Verify both migrations recorded
        applied = manager.get_applied_versions()
        assert applied == {1, 2}

    def test_apply_pending_no_migrations(self, tmp_path, capsys):
        """Should print message when no pending migrations."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)
        manager.apply_pending_migrations()

        captured = capsys.readouterr()
        assert "No pending migrations" in captured.out


class TestCreateMigrationTemplate:
    """Test migration template creation."""

    def test_create_migration_template_creates_file(self, tmp_path):
        """Should create migration file with correct naming."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)
        filepath = manager.create_migration_template("add_settlement_type")

        assert filepath.exists()
        assert filepath.name == "001_add_settlement_type.sql"

    def test_create_migration_template_increments_version(self, tmp_path):
        """Should use next version number based on applied migrations."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)

        # Simulate applied migration
        conn.execute("""
            INSERT INTO schema_migrations (version, applied_at, description)
            VALUES (1, ?, 'first migration')
        """, [datetime.now()])

        filepath = manager.create_migration_template("second_migration")

        assert filepath.name == "002_second_migration.sql"

    def test_create_migration_template_has_content(self, tmp_path):
        """Created template should have helpful content."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        manager = MigrationManager(conn, migrations_dir)
        filepath = manager.create_migration_template("add_column")

        content = filepath.read_text()

        assert "Migration" in content
        assert "add column" in content  # Description
        assert "ALTER TABLE" in content  # Example SQL
        assert "Pydantic model" in content  # Reminder


class TestMigrationEdgeCases:
    """Test edge cases and error handling."""

    def test_ignores_non_numeric_filenames(self, tmp_path):
        """Should ignore migration files without numeric prefix."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create files with various names
        (migrations_dir / "001_valid.sql").write_text("-- valid")
        (migrations_dir / "README.md").write_text("# Docs")
        (migrations_dir / "template.sql").write_text("-- template")

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        assert len(pending) == 1
        assert pending[0][0] == 1

    def test_handles_missing_migrations_directory(self, tmp_path):
        """Should handle case when migrations directory doesn't exist yet."""
        from payment_simulator.persistence.migrations import MigrationManager

        conn = duckdb.connect(":memory:")
        migrations_dir = tmp_path / "migrations"  # Not created yet

        manager = MigrationManager(conn, migrations_dir)
        pending = manager.get_pending_migrations()

        # Should not crash, just return empty list
        assert pending == []
