"""
Database Management CLI Commands

Commands for managing the DuckDB persistence layer:
- init: Initialize database schema
- migrate: Apply pending migrations
- validate: Validate schema against Pydantic models
- create-migration: Create new migration template
- list: List all tables
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.migrations import MigrationManager

# Create sub-app for database commands
db_app = typer.Typer(help="Database management commands")
console = Console()


@db_app.command("init")
def db_init(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
):
    """Initialize database schema from Pydantic models."""
    try:
        console.print(f"[yellow]Initializing database at {db_path}...[/yellow]")

        manager = DatabaseManager(db_path)
        manager.initialize_schema()

        console.print(f"[green]✓ Database initialized at {db_path}[/green]")

    except Exception as e:
        console.print(f"[red]✗ Error initializing database: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("migrate")
def db_migrate(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
    migrations_dir: Optional[str] = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="Path to migrations directory",
    ),
):
    """Apply pending schema migrations."""
    try:
        console.print("[yellow]Checking for pending migrations...[/yellow]")

        manager = DatabaseManager(db_path)

        # Override migrations dir if provided
        if migrations_dir:
            manager.migrations_dir = Path(migrations_dir)

        migration_manager = MigrationManager(
            manager.conn, manager.migrations_dir
        )

        pending = migration_manager.get_pending_migrations()

        if not pending:
            console.print("[green]✓ No pending migrations[/green]")
            return

        console.print(
            f"[yellow]Found {len(pending)} pending migration(s)[/yellow]"
        )

        for version, description, _sql in pending:
            console.print(f"  • Migration {version}: {description}")

        migration_manager.apply_pending_migrations()

        console.print(f"[green]✓ Applied {len(pending)} migration(s)[/green]")

    except Exception as e:
        console.print(f"[red]✗ Error applying migrations: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("validate")
def db_validate(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
):
    """Validate database schema against Pydantic models."""
    try:
        console.print("[yellow]Validating database schema...[/yellow]")

        manager = DatabaseManager(db_path)

        # Validate returns True if valid, False otherwise
        is_valid = manager.validate_schema()

        if is_valid:
            console.print("[green]✓ Schema validation passed[/green]")
        else:
            console.print("[red]✗ Schema validation failed[/red]")
            console.print(
                "[yellow]Run 'payment-sim db migrate' to fix schema[/yellow]"
            )
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]✗ Error validating schema: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("create-migration")
def db_create_migration(
    description: str = typer.Argument(
        ..., help="Migration description (e.g., 'add_settlement_type')"
    ),
    migrations_dir: Optional[str] = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="Path to migrations directory",
    ),
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file (for version tracking)",
    ),
):
    """Create a new migration template file."""
    try:
        manager = DatabaseManager(db_path)

        # Override migrations dir if provided
        if migrations_dir:
            manager.migrations_dir = Path(migrations_dir)

        migration_manager = MigrationManager(
            manager.conn, manager.migrations_dir
        )

        filepath = migration_manager.create_migration_template(description)

        console.print(
            f"[green]✓ Created migration template: {filepath}[/green]"
        )
        console.print("[yellow]Next steps:[/yellow]")
        console.print(f"  1. Edit {filepath}")
        console.print("  2. Add your SQL statements")
        console.print("  3. Run 'payment-sim db migrate'")

    except Exception as e:
        console.print(f"[red]✗ Error creating migration: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("list")
def db_list(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
):
    """List all tables in the database."""
    try:
        manager = DatabaseManager(db_path)

        # Query for all tables
        result = manager.conn.execute("""
            SELECT table_name,
                   (SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()

        if not result:
            console.print("[yellow]No tables found in database[/yellow]")
            return

        # Create table display
        table = Table(title="Database Tables")
        table.add_column("Table Name", style="cyan")
        table.add_column("Columns", justify="right", style="magenta")

        for table_name, column_count in result:
            table.add_row(table_name, str(column_count))

        console.print(table)
        console.print(f"\n[green]Total: {len(result)} table(s)[/green]")

    except Exception as e:
        console.print(f"[red]✗ Error listing tables: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("info")
def db_info(
    db_path: str = typer.Option(
        "simulation_data.db",
        "--db-path",
        "-d",
        help="Path to database file",
    ),
):
    """Show database information and statistics."""
    try:
        manager = DatabaseManager(db_path)

        console.print(f"[bold cyan]Database Information[/bold cyan]")
        console.print(f"  Path: {db_path}")

        # Get file size
        if Path(db_path).exists():
            size_bytes = Path(db_path).stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            console.print(f"  Size: {size_mb:.2f} MB")

        # Get table row counts
        console.print("\n[bold]Table Statistics:[/bold]")

        tables = [
            "simulation_runs",
            "transactions",
            "daily_agent_metrics",
            "policy_snapshots",
            "collateral_events",
            "simulation_checkpoints",
        ]

        table = Table()
        table.add_column("Table", style="cyan")
        table.add_column("Row Count", justify="right", style="magenta")

        for table_name in tables:
            try:
                count = manager.conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                table.add_row(table_name, f"{count:,}")
            except Exception:
                # Table might not exist yet
                table.add_row(table_name, "[dim]N/A[/dim]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error getting database info: {e}[/red]")
        raise typer.Exit(code=1)
