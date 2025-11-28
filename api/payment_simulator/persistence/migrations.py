"""
Schema Migration System

Manages versioned database schema migrations using numbered SQL files.
Ensures database schema can evolve safely over time.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb


class MigrationManager:
    """Manages database schema migrations.

    Responsibilities:
    - Track applied migrations in schema_migrations table
    - Scan migrations directory for pending .sql files
    - Apply migrations in order with transaction safety
    - Create migration templates for developers

    Usage:
        manager = MigrationManager(conn, migrations_dir)
        manager.apply_pending_migrations()
    """

    def __init__(self, conn: Any, migrations_dir: Path):
        """Initialize migration manager.

        Args:
            conn: DuckDB connection
            migrations_dir: Directory containing migration .sql files
        """
        self.conn = conn
        self.migrations_dir = Path(migrations_dir)

        # Ensure schema_migrations table exists
        self._create_migrations_table()

    def _create_migrations_table(self) -> None:
        """Create schema_migrations table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL,
                description VARCHAR NOT NULL
            )
        """)

    def get_applied_versions(self) -> set[int]:
        """Get set of applied migration versions.

        Returns:
            Set of version numbers (e.g., {1, 2, 5})

        Examples:
            >>> manager = MigrationManager(conn, migrations_dir)
            >>> applied = manager.get_applied_versions()
            >>> 1 in applied
            True
        """
        result = self.conn.execute("""
            SELECT version FROM schema_migrations ORDER BY version
        """).fetchall()

        return {row[0] for row in result}

    def get_pending_migrations(self) -> list[tuple[int, str, str]]:
        """Get list of pending migrations.

        Scans migrations_dir for .sql files with numeric prefix (e.g., "001_*.sql")
        and returns those not yet applied.

        Returns:
            List of (version, description, sql_content) tuples, sorted by version

        Examples:
            >>> pending = manager.get_pending_migrations()
            >>> for version, desc, sql in pending:
            ...     print(f"Version {version}: {desc}")
        """
        # Check if directory exists
        if not self.migrations_dir.exists():
            return []

        applied = self.get_applied_versions()
        pending = []

        # Scan for .sql files
        for migration_file in self.migrations_dir.glob("*.sql"):
            filename = migration_file.name

            # Skip files without numeric prefix
            if not filename[0].isdigit():
                continue

            # Parse version number from filename (e.g., "001" from "001_add_column.sql")
            version_str = filename.split('_')[0]
            version = int(version_str)

            # Skip if already applied
            if version in applied:
                continue

            # Extract description from filename
            # "001_add_settlement_type.sql" → "add settlement type"
            description = filename[4:-4].replace('_', ' ')  # Remove "001_" prefix and ".sql" suffix

            # Read SQL content
            sql_content = migration_file.read_text()

            pending.append((version, description, sql_content))

        # Sort by version number
        return sorted(pending, key=lambda x: x[0])

    def apply_migration(self, version: int, description: str, sql_content: str) -> None:
        """Apply a single migration.

        Executes the migration SQL and records it in schema_migrations table.
        Uses transaction to ensure atomicity - either both succeed or both fail.

        Args:
            version: Migration version number
            description: Human-readable description
            sql_content: SQL to execute

        Raises:
            RuntimeError: If migration fails (rolled back)

        Examples:
            >>> sql = "CREATE TABLE users (id INT, name VARCHAR);"
            >>> manager.apply_migration(1, "create users table", sql)
        """
        print(f"Applying migration {version}: {description}")

        self.conn.begin()
        try:
            # Execute migration SQL
            self.conn.execute(sql_content)

            # Record migration
            self.conn.execute("""
                INSERT INTO schema_migrations (version, applied_at, description)
                VALUES (?, ?, ?)
            """, [version, datetime.now(), description])

            self.conn.commit()
            print(f"  ✓ Migration {version} applied successfully")

        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Migration {version} failed: {e}") from e

    def apply_pending_migrations(self) -> None:
        """Apply all pending migrations in order.

        Scans for pending migrations and applies them sequentially.
        Stops at first failure.

        Examples:
            >>> manager.apply_pending_migrations()
            Found 2 pending migration(s)
            Applying migration 1: initial schema
              ✓ Migration 1 applied successfully
            Applying migration 2: add settlement type
              ✓ Migration 2 applied successfully
            All migrations applied successfully
        """
        pending = self.get_pending_migrations()

        if not pending:
            print("No pending migrations")
            return

        print(f"Found {len(pending)} pending migration(s)")

        for version, description, sql_content in pending:
            self.apply_migration(version, description, sql_content)

        print("All migrations applied successfully")

    def create_migration_template(self, description: str) -> Path:
        """Create a new migration file template.

        Generates a numbered .sql file with helpful template content.
        Version number is automatically incremented from latest applied migration.

        Args:
            description: Migration description (e.g., "add_settlement_type")

        Returns:
            Path to created migration file

        Examples:
            >>> filepath = manager.create_migration_template("add_settlement_type")
            Created migration template: migrations/002_add_settlement_type.sql
            >>> print(filepath.name)
            002_add_settlement_type.sql
        """
        # Ensure migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Get next version number by checking both applied and existing file versions
        applied = self.get_applied_versions()

        # Also check for existing migration files (not yet applied)
        existing_files = list(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
        file_versions = set()
        for f in existing_files:
            try:
                version = int(f.name.split('_')[0])
                file_versions.add(version)
            except (ValueError, IndexError):
                continue

        # Next version is max of both applied and file versions + 1
        all_versions = applied | file_versions
        next_version = max(all_versions) + 1 if all_versions else 1

        # Create filename with zero-padded version
        filename = f"{next_version:03d}_{description}.sql"
        filepath = self.migrations_dir / filename

        # Write helpful template (keep underscores in description for searchability)
        template = f"""-- Migration {next_version}: {description}
-- Created: {datetime.now().isoformat()}

-- Add your migration SQL here
-- Example:
-- ALTER TABLE transactions ADD COLUMN settlement_type VARCHAR;

-- Don't forget to update the corresponding Pydantic model!
"""
        filepath.write_text(template)

        print(f"Created migration template: {filepath}")
        return filepath
