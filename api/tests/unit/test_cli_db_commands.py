"""
Phase 1.6: CLI Database Commands Tests

Following TDD approach: Write tests first, then implement.
"""

import pytest
from pathlib import Path
from typer.testing import CliRunner


class TestDBInitCommand:
    """Test payment-sim db init command."""

    def test_db_init_creates_database_file(self, tmp_path):
        """db init should create database file."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # RED: Command doesn't exist yet
        result = runner.invoke(
            app, ["db", "init", "--db-path", str(db_path)]
        )

        assert result.exit_code == 0
        assert db_path.exists()
        assert "Database initialized" in result.stdout

    def test_db_init_creates_all_tables(self, tmp_path):
        """db init should create all schema tables."""
        from payment_simulator.cli.main import app
        import duckdb

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        result = runner.invoke(
            app, ["db", "init", "--db-path", str(db_path)]
        )

        assert result.exit_code == 0

        # Verify tables exist
        conn = duckdb.connect(str(db_path))
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "transactions" in table_names
        assert "simulation_runs" in table_names
        assert "daily_agent_metrics" in table_names
        assert "policy_snapshots" in table_names
        assert "collateral_events" in table_names
        assert "simulation_checkpoints" in table_names
        assert "schema_migrations" in table_names

        conn.close()

    def test_db_init_is_idempotent(self, tmp_path):
        """Running db init twice should not fail."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # First init
        result1 = runner.invoke(
            app, ["db", "init", "--db-path", str(db_path)]
        )
        assert result1.exit_code == 0

        # Second init (should succeed, not error)
        result2 = runner.invoke(
            app, ["db", "init", "--db-path", str(db_path)]
        )
        assert result2.exit_code == 0
        assert "already initialized" in result2.stdout.lower() or "initialized" in result2.stdout.lower()


class TestDBMigrateCommand:
    """Test payment-sim db migrate command."""

    def test_db_migrate_with_no_migrations(self, tmp_path):
        """db migrate with no pending migrations should succeed."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # Initialize first
        runner.invoke(app, ["db", "init", "--db-path", str(db_path)])

        # Run migrate
        result = runner.invoke(
            app, ["db", "migrate", "--db-path", str(db_path)]
        )

        assert result.exit_code == 0
        assert "No pending migrations" in result.stdout or "migrations applied" in result.stdout.lower()

    def test_db_migrate_applies_pending_migrations(self, tmp_path):
        """db migrate should apply pending migration files."""
        from payment_simulator.cli.main import app
        import duckdb

        runner = CliRunner()
        db_path = tmp_path / "test.db"
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Initialize database
        runner.invoke(app, ["db", "init", "--db-path", str(db_path)])

        # Create a test migration
        migration_file = migrations_dir / "001_add_test_table.sql"
        migration_file.write_text("""
-- Migration 001: add test table
CREATE TABLE IF NOT EXISTS test_table (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL
);
""")

        # Run migrate
        result = runner.invoke(
            app,
            [
                "db",
                "migrate",
                "--db-path",
                str(db_path),
                "--migrations-dir",
                str(migrations_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Migration 1" in result.stdout or "applied" in result.stdout.lower()

        # Verify table was created
        conn = duckdb.connect(str(db_path))
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name='test_table'"
        ).fetchall()
        assert len(tables) == 1
        conn.close()


class TestDBValidateCommand:
    """Test payment-sim db validate command."""

    def test_db_validate_on_valid_schema(self, tmp_path):
        """db validate should pass on valid schema."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # Initialize database
        runner.invoke(app, ["db", "init", "--db-path", str(db_path)])

        # Validate
        result = runner.invoke(
            app, ["db", "validate", "--db-path", str(db_path)]
        )

        assert result.exit_code == 0
        assert "valid" in result.stdout.lower() or "✓" in result.stdout

    def test_db_validate_detects_missing_table(self, tmp_path):
        """db validate should detect schema mismatches."""
        from payment_simulator.cli.main import app
        import duckdb

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # Create database with incomplete schema
        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE transactions (
                simulation_id VARCHAR NOT NULL,
                tx_id VARCHAR NOT NULL
            )
        """
        )
        conn.close()

        # Validate (should fail)
        result = runner.invoke(
            app, ["db", "validate", "--db-path", str(db_path)]
        )

        assert result.exit_code != 0
        assert "invalid" in result.stdout.lower() or "missing" in result.stdout.lower()


class TestDBCreateMigrationCommand:
    """Test payment-sim db create-migration command."""

    def test_db_create_migration_creates_file(self, tmp_path):
        """db create-migration should create migration file."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        db_path = tmp_path / "test.db"

        result = runner.invoke(
            app,
            [
                "db",
                "create-migration",
                "add_new_field",
                "--migrations-dir",
                str(migrations_dir),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0

        # Check file was created
        migration_files = list(migrations_dir.glob("*.sql"))
        assert len(migration_files) == 1

        migration_file = migration_files[0]
        assert "add_new_field" in migration_file.name
        assert migration_file.name.startswith("001_")

        # Check file has template content
        content = migration_file.read_text()
        assert "Migration" in content
        assert "add_new_field" in content.lower()

    def test_db_create_migration_increments_version(self, tmp_path):
        """db create-migration should auto-increment version number."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        db_path = tmp_path / "test.db"

        # Create first migration
        runner.invoke(
            app,
            [
                "db",
                "create-migration",
                "first_migration",
                "--migrations-dir",
                str(migrations_dir),
                "--db-path",
                str(db_path),
            ],
        )

        # Create second migration
        result = runner.invoke(
            app,
            [
                "db",
                "create-migration",
                "second_migration",
                "--migrations-dir",
                str(migrations_dir),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0

        # Check both files exist with correct versions
        migration_files = sorted(migrations_dir.glob("*.sql"))
        assert len(migration_files) == 2
        assert migration_files[0].name.startswith("001_")
        assert migration_files[1].name.startswith("002_")


class TestDBListCommand:
    """Test payment-sim db list command."""

    def test_db_list_shows_tables(self, tmp_path):
        """db list should show all tables."""
        from payment_simulator.cli.main import app

        runner = CliRunner()
        db_path = tmp_path / "test.db"

        # Initialize database
        runner.invoke(app, ["db", "init", "--db-path", str(db_path)])

        # List tables
        result = runner.invoke(
            app, ["db", "list", "--db-path", str(db_path)]
        )

        assert result.exit_code == 0
        assert "transactions" in result.stdout
        assert "simulation_runs" in result.stdout
        assert "daily_agent_metrics" in result.stdout
