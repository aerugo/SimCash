"""
DuckDB Connection Manager

Manages database connections, schema initialization, validation, and migrations.
Provides a high-level interface for database setup and lifecycle management.
"""

from pathlib import Path
from typing import Any

import duckdb

from .migrations import MigrationManager
from .models import (
    CollateralEventRecord,
    DailyAgentMetricsRecord,
    PolicySnapshotRecord,
    SimulationRunRecord,
    TransactionRecord,
)
from .schema_generator import generate_full_schema_ddl, validate_table_schema


class DatabaseManager:
    """Manages DuckDB connection and schema.

    Responsibilities:
    - Create and manage DuckDB connection
    - Initialize database schema from Pydantic models
    - Validate schema matches models
    - Apply pending migrations
    - Provide context manager for clean resource management

    Usage:
        # Simple usage
        manager = DatabaseManager("simulation_data.db")
        manager.setup()  # Initialize, migrate, validate

        # Context manager usage
        with DatabaseManager("simulation_data.db") as manager:
            manager.setup()
            # Use manager.conn for queries

    Example:
        >>> manager = DatabaseManager("test.db")
        >>> manager.setup()
        Initializing database schema...
          ✓ Schema initialized
        No pending migrations
        Validating database schema...
          ✓ transactions
          ✓ simulation_runs
          ✓ daily_agent_metrics
          ✓ collateral_events
        Database setup complete
    """

    def __init__(
        self, db_path: str | Path = "simulation_data.db", migrations_dir: Path | None = None
    ):
        """Initialize database manager.

        Args:
            db_path: Path to DuckDB database file
            migrations_dir: Path to migrations directory (optional, defaults to api/migrations/)

        Examples:
            >>> manager = DatabaseManager("my_simulation.db")
            >>> manager = DatabaseManager(Path("/data/simulation.db"))
            >>> # For testing with custom migrations dir
            >>> manager = DatabaseManager("test.db", migrations_dir=Path("/tmp/migrations"))
        """
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))

        # Determine migrations directory
        if migrations_dir is not None:
            self.migrations_dir = Path(migrations_dir)
        else:
            # Default: api/payment_simulator/persistence/connection.py -> api/migrations/
            self.migrations_dir = Path(__file__).parent.parent.parent / "migrations"

        self.migrations_dir.mkdir(exist_ok=True, parents=True)

    def initialize_schema(self):
        """Initialize database schema from Pydantic models.

        Generates DDL from all Pydantic models and executes it to create tables.
        Uses CREATE TABLE IF NOT EXISTS, so safe to run multiple times.

        Examples:
            >>> manager.initialize_schema()
            Initializing database schema...
              ✓ Schema initialized
        """
        print("Initializing database schema...")

        # Generate DDL from models
        ddl = generate_full_schema_ddl()

        # DuckDB doesn't have executescript, so split and execute individually
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in ddl.split(";") if s.strip()]
        for statement in statements:
            self.conn.execute(statement)

        print("  ✓ Schema initialized")

    def validate_schema(self) -> bool:
        """Validate that database schema matches Pydantic models.

        Checks each model's table against the actual database schema.
        Prints validation results for each table.

        Returns:
            True if all tables valid, False if any mismatches found

        Examples:
            >>> manager.validate_schema()
            Validating database schema...
              ✓ transactions
              ✓ simulation_runs
              ✓ daily_agent_metrics
              ✓ collateral_events
            True

            >>> # With schema mismatch
            >>> manager.validate_schema()
            Validating database schema...
              ✗ transactions:
                  Missing column: settlement_type
              ✓ simulation_runs
            False
        """
        print("Validating database schema...")

        models = [
            TransactionRecord,
            SimulationRunRecord,
            DailyAgentMetricsRecord,
            CollateralEventRecord,
            PolicySnapshotRecord,
        ]

        all_valid = True
        for model in models:
            is_valid, errors = validate_table_schema(self.conn, model)
            if not is_valid:
                all_valid = False
                table_name = model.model_config.get("table_name", "unknown")
                print(f"  ✗ {table_name}:")
                for error in errors:
                    print(f"      {error}")
            else:
                table_name = model.model_config.get("table_name", "unknown")
                print(f"  ✓ {table_name}")

        return all_valid

    def apply_migrations(self):
        """Apply pending schema migrations.

        Uses MigrationManager to scan migrations directory and apply
        any unapplied .sql migration files.

        Examples:
            >>> manager.apply_migrations()
            Found 2 pending migration(s)
            Applying migration 1: initial schema
              ✓ Migration 1 applied successfully
            Applying migration 2: add settlement type
              ✓ Migration 2 applied successfully
            All migrations applied successfully

            >>> # No pending migrations
            >>> manager.apply_migrations()
            No pending migrations
        """
        migration_manager = MigrationManager(self.conn, self.migrations_dir)
        migration_manager.apply_pending_migrations()

    def setup(self):
        """Complete database setup: initialize + migrate + validate + load templates.

        Performs full database setup in correct order:
        1. Initialize schema from Pydantic models
        2. Apply any pending migrations
        3. Validate schema matches models
        4. Load policy templates (once per database)

        Raises:
            RuntimeError: If schema validation fails

        Examples:
            >>> manager = DatabaseManager("test.db")
            >>> manager.setup()
            Initializing database schema...
              ✓ Schema initialized
            No pending migrations
            Validating database schema...
              ✓ transactions
              ✓ simulation_runs
              ✓ daily_agent_metrics
              ✓ collateral_events
              ✓ policy_snapshots
              ✓ Policy templates loaded (5 templates)
            Database setup complete
        """
        # 1. Initialize schema (creates tables if not exist)
        self.initialize_schema()

        # 2. Apply pending migrations
        self.apply_migrations()

        # 3. Validate schema matches models
        if not self.validate_schema():
            raise RuntimeError(
                "Database schema validation failed. "
                "This likely means the database schema is out of sync with Pydantic models. "
                "Create a migration file to fix the schema, or delete the database and reinitialize."
            )

        # 4. Load policy templates if not already loaded
        self._load_policy_templates_if_needed()

        print("Database setup complete")

    def _load_policy_templates_if_needed(self):
        """Load policy templates from disk if not already in database."""
        # Check if templates already loaded
        existing_count = self.conn.execute(
            "SELECT COUNT(*) FROM policy_snapshots WHERE simulation_id = 'templates'"
        ).fetchone()[0]

        if existing_count > 0:
            print(f"  ✓ Policy templates already loaded ({existing_count} templates)")
            return

        # Load templates from disk
        from .policy_tracking import load_policy_templates
        from .writers import write_policy_snapshots

        print("  Loading policy templates from disk...")
        templates = load_policy_templates()

        if templates:
            write_policy_snapshots(self.conn, templates)
            print(f"  ✓ Loaded {len(templates)} policy templates")
        else:
            print("  ⚠ No policy templates found")

    def close(self):
        """Close database connection.

        Examples:
            >>> manager = DatabaseManager("test.db")
            >>> manager.close()
        """
        self.conn.close()

    def __enter__(self):
        """Enter context manager.

        Returns:
            DatabaseManager instance

        Examples:
            >>> with DatabaseManager("test.db") as manager:
            ...     result = manager.conn.execute("SELECT 1").fetchone()
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close connection.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.close()


# ============================================================================
# Convenience Functions
# ============================================================================


def get_connection(db_path: str | Path = "simulation_data.db") -> duckdb.DuckDBPyConnection:
    """Get database connection with automatic setup.

    Creates DatabaseManager, runs full setup (initialize + migrate + validate),
    and returns the ready-to-use connection.

    This is a convenience function for quick database access when you don't
    need the full DatabaseManager API.

    Args:
        db_path: Path to DuckDB database file

    Returns:
        Ready-to-use DuckDB connection

    Raises:
        RuntimeError: If schema validation fails

    Examples:
        >>> conn = get_connection("my_simulation.db")
        Initializing database schema...
          ✓ Schema initialized
        No pending migrations
        Validating database schema...
          ✓ transactions
        Database setup complete

        >>> result = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
        >>> print(result[0])
        0
    """
    manager = DatabaseManager(db_path)
    manager.setup()
    return manager.conn
