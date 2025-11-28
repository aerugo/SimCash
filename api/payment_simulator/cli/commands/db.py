"""
Database Management CLI Commands

Commands for managing the DuckDB persistence layer:
- init: Initialize database schema
- migrate: Apply pending migrations
- validate: Validate schema against Pydantic models
- create-migration: Create new migration template
- list: List all tables
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

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
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
) -> None:
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
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
    migrations_dir: Annotated[
        str | None,
        typer.Option("--migrations-dir", "-m", help="Path to migrations directory"),
    ] = None,
) -> None:
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
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
) -> None:
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
    description: Annotated[
        str,
        typer.Argument(help="Migration description (e.g., 'add_settlement_type')"),
    ],
    migrations_dir: Annotated[
        str | None,
        typer.Option("--migrations-dir", "-m", help="Path to migrations directory"),
    ] = None,
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file (for version tracking)"),
    ] = "simulation_data.db",
) -> None:
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
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
) -> None:
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
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
) -> None:
    """Show database information and statistics."""
    try:
        manager = DatabaseManager(db_path)

        console.print("[bold cyan]Database Information[/bold cyan]")
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
                result = manager.conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()
                count = result[0] if result else 0
                table.add_row(table_name, f"{count:,}")
            except Exception:
                # Table might not exist yet
                table.add_row(table_name, "[dim]N/A[/dim]")

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error getting database info: {e}[/red]")
        raise typer.Exit(code=1)


@db_app.command("simulations")
def db_simulations(
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of simulations to show"),
    ] = 20,
) -> None:
    """List simulations in the database."""
    try:
        manager = DatabaseManager(db_path)

        # Query simulation_runs for all simulations
        query = """
            SELECT
                simulation_id,
                config_name,
                rng_seed,
                ticks_per_day,
                num_days,
                status,
                start_time,
                total_transactions
            FROM simulation_runs
            ORDER BY start_time DESC
            LIMIT ?
        """

        results = manager.conn.execute(query, [limit]).fetchall()

        if not results:
            console.print("[yellow]No simulations found in database[/yellow]")
            return

        # Display as table
        table = Table(title=f"Simulations in Database ({len(results)} shown)")

        table.add_column("Simulation ID", style="cyan", no_wrap=True)
        table.add_column("Config", style="blue")
        table.add_column("Seed", justify="right", style="yellow")
        table.add_column("Ticks", justify="right", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Started", style="white")

        for row in results:
            sim_id, config_name, seed, ticks_per_day, num_days, status, start_time, _total_txs = row

            # Format start time
            if start_time:
                from datetime import datetime
                dt = datetime.fromisoformat(start_time) if isinstance(start_time, str) else start_time
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                time_str = "N/A"

            # Calculate total ticks
            total_ticks = ticks_per_day * num_days

            table.add_row(
                sim_id,
                config_name or "N/A",
                str(seed) if seed else "N/A",
                str(total_ticks),
                status or "unknown",
                time_str,
            )

        console.print(table)
        console.print("\n[dim]Use 'payment-sim replay --simulation-id <ID> --config <file>' to replay[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Error listing simulations: {e}[/red]")
        raise typer.Exit(code=1)


def _extract_policy_names(config_json: str) -> dict[str, str]:
    """Extract policy names from simulation config JSON.

    Args:
        config_json: Serialized configuration JSON string

    Returns:
        Dictionary mapping agent_id to policy name (extracted from json_path)

    Examples:
        >>> config = '{"agents": [{"id": "BANK_A", "policy": {"json_path": "backend/policies/efficient.json"}}]}'
        >>> _extract_policy_names(config)
        {'BANK_A': 'efficient'}
    """
    import json as json_module

    policy_names: dict[str, str] = {}

    try:
        config = json_module.loads(config_json)
        agents = config.get("agents", [])

        for agent in agents:
            agent_id = agent.get("id")
            policy = agent.get("policy", {})

            # Extract policy name from json_path if it exists
            if "json_path" in policy:
                json_path = policy["json_path"]
                # Get filename without extension
                # e.g., "backend/policies/efficient_proactive.json" -> "efficient_proactive"
                policy_name = Path(json_path).stem
                policy_names[agent_id] = policy_name
            elif policy.get("type") in ["AlwaysSubmit", "SimpleThreshold", "BasicBalancePreserver"]:
                # Handle built-in policy types
                policy_names[agent_id] = policy.get("type", "Unknown")

    except (json_module.JSONDecodeError, KeyError, TypeError) as e:
        # If parsing fails, return empty dict (charts will just use agent IDs)
        console.print(f"[yellow]Warning: Could not parse policy names from config: {e}[/yellow]")
        return {}

    return policy_names


def _collect_event_based_cost_data(
    conn: Any,
    simulation_id: str,
    agent_ids: list[str],
    ticks_per_day: int,
    num_days: int,
) -> list[dict[str, Any]]:
    """Collect tick-level cost data from simulation events.

    This uses the event-based approach that queries actual cost events from the database,
    rather than linearly interpolating from daily totals.

    Args:
        conn: Database connection
        simulation_id: Simulation ID
        agent_ids: List of agent IDs to collect costs for
        ticks_per_day: Number of ticks per day
        num_days: Number of days in simulation

    Returns:
        List of dicts with tick-level cost data, where each dict has:
        {
            "tick": int,
            "day": int,
            "accumulated_costs": {agent_id: int},  # accumulated costs in cents
            "per_tick_costs": {agent_id: int}       # costs incurred this tick in cents
        }
    """
    from collections import defaultdict

    # Query actual tick-level cost events
    # 1. CostAccrual events for continuous costs (liquidity, delay, collateral)
    cost_accrual_query = """
        SELECT
            tick,
            agent_id,
            CAST(json_extract(details, '$.costs.total') AS INTEGER) as tick_cost
        FROM simulation_events
        WHERE simulation_id = ?
          AND event_type = 'CostAccrual'
        ORDER BY tick
    """

    # 2. TransactionWentOverdue events for deadline penalties
    deadline_penalty_query = """
        SELECT
            tick,
            json_extract(details, '$.sender_id') as agent_id,
            CAST(json_extract(details, '$.deadline_penalty_cost') AS INTEGER) as penalty_cost
        FROM simulation_events
        WHERE simulation_id = ?
          AND event_type = 'TransactionWentOverdue'
        ORDER BY tick
    """

    # Aggregate costs by tick and agent
    tick_agent_costs: defaultdict[int, defaultdict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    # Add continuous costs from CostAccrual events
    for row in conn.execute(cost_accrual_query, [simulation_id]).fetchall():
        tick, agent_id_event, cost = row
        tick_agent_costs[tick][agent_id_event] += cost

    # Add deadline penalties from TransactionWentOverdue events
    for row in conn.execute(deadline_penalty_query, [simulation_id]).fetchall():
        tick, agent_id_event, penalty = row
        tick_agent_costs[tick][agent_id_event] += penalty

    # Add EOD penalties from daily_agent_metrics (these aren't in event stream per-agent)
    # EOD penalties are $5,000 per unsettled transaction assessed at end of each day
    eod_penalty_query = """
        SELECT
            day,
            agent_id,
            deadline_penalty_cost
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        ORDER BY day, agent_id
    """

    for row in conn.execute(eod_penalty_query, [simulation_id]).fetchall():
        day, agent_id_event, deadline_pen = row

        # Calculate costs already captured from events for this agent this day
        event_costs_this_day = 0
        for tick in range(day * ticks_per_day, (day + 1) * ticks_per_day):
            event_costs_this_day += tick_agent_costs[tick].get(agent_id_event, 0)

        # EOD penalty is the difference (what's in daily table but not in events)
        eod_penalty = deadline_pen - event_costs_this_day

        if eod_penalty > 0:
            # Apply EOD penalty at the LAST tick of the day
            eod_tick = (day + 1) * ticks_per_day - 1
            tick_agent_costs[eod_tick][agent_id_event] += eod_penalty

    # Build accumulated costs for all ticks
    max_tick = (ticks_per_day * num_days) - 1
    tick_costs = []
    accumulated = dict.fromkeys(agent_ids, 0)

    for tick in range(max_tick + 1):
        # Store previous accumulated for per-tick calculation
        prev_accumulated = dict(accumulated)

        # Add costs that occurred at this tick
        for agent_id in agent_ids:
            accumulated[agent_id] += tick_agent_costs[tick].get(agent_id, 0)

        # Store both accumulated and per-tick costs
        tick_data = {
            "tick": tick,
            "day": tick // ticks_per_day,
            "accumulated_costs": {agent_id: int(accumulated[agent_id]) for agent_id in agent_ids},
            "per_tick_costs": {agent_id: int(accumulated[agent_id] - prev_accumulated[agent_id]) for agent_id in agent_ids}
        }

        tick_costs.append(tick_data)

    return tick_costs


def _generate_cost_chart_png(
    tick_costs: list[dict[str, Any]],
    agent_ids: list[str],
    simulation_id: str,
    ticks_per_day: int,
    output_path: str,
    show_per_tick: bool = False,
    quiet: bool = False,
    policy_names: dict[str, str] | None = None,
    max_y: int | None = None,
) -> None:
    """Generate a PNG cost chart from tick-level cost data.

    Args:
        tick_costs: List of tick cost data dicts from _collect_event_based_cost_data
        agent_ids: List of agent IDs
        simulation_id: Simulation ID for chart title
        ticks_per_day: Ticks per day for day boundary lines
        output_path: Path to save PNG file
        show_per_tick: If True, show per-tick costs; if False, show accumulated
        quiet: If True, suppress console output
        policy_names: Optional dict mapping agent_id to policy name for legend
        max_y: Optional maximum Y-axis value in dollars (None = adaptive)
    """
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    from pathlib import Path

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    # Prepare data for plotting
    ticks = [data['tick'] for data in tick_costs]

    # Create figure with larger size for readability
    fig, ax = plt.subplots(figsize=(14, 8))

    # Select which costs to plot
    cost_key = 'per_tick_costs' if show_per_tick else 'accumulated_costs'

    # Plot each agent's costs
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    for i, agent_id in enumerate(agent_ids):
        costs_usd = [data[cost_key][agent_id] / 100.0 for data in tick_costs]
        # Create label with policy name if available
        if policy_names and agent_id in policy_names:
            label = f"{agent_id}: {policy_names[agent_id]}"
        else:
            label = agent_id
        ax.plot(ticks, costs_usd, label=label, linewidth=2, color=colors[i % len(colors)])

    # Format y-axis as currency
    def currency_formatter(x: float, p: int) -> str:
        return f'${x:,.0f}'

    ax.yaxis.set_major_formatter(FuncFormatter(currency_formatter))

    # Add labels and title
    mode_str = 'Per-Tick' if show_per_tick else 'Accumulated'
    ax.set_xlabel('Tick', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'{mode_str} Cost (USD)', fontsize=12, fontweight='bold')
    ax.set_title(f'Cost Timeline - {simulation_id}\n{mode_str} Costs by Agent',
                fontsize=14, fontweight='bold', pad=20)

    # Add legend
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

    # Add grid for readability
    ax.grid(True, alpha=0.3, linestyle='--')

    # Set Y-axis limits if specified
    if max_y is not None:
        ax.set_ylim(0, max_y)

    # Add day boundaries as vertical lines
    if ticks_per_day:
        for day in range(1, (max(ticks) // ticks_per_day) + 1):
            day_tick = day * ticks_per_day
            if day_tick <= max(ticks):
                ax.axvline(x=day_tick, color='gray', linestyle=':', alpha=0.5, linewidth=1)
                ax.text(day_tick, ax.get_ylim()[1] * 0.98, f'Day {day}',
                       rotation=90, verticalalignment='top', fontsize=8, alpha=0.7)

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Create directory if it doesn't exist
    chart_path = Path(output_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the chart
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)

    if not quiet:
        console.print(f"[green]✓ Generated chart: {output_path}[/green]")


def generate_cost_charts(
    simulation_id: str,
    db_path: str = "simulation_data.db",
    output_base_path: str | None = None,
    agent: str | None = None,
    quiet: bool = False,
    max_y_per_tick: int | None = None,
    max_y_accumulated: int | None = None,
) -> None:
    """Generate both accumulated and per-tick cost charts for a simulation.

    This is the modern event-based chart generation that should be used by --cost-chart flag.
    It generates TWO charts: {base}_accumulated.png and {base}_per_tick.png

    Args:
        simulation_id: Simulation ID to get costs for
        db_path: Path to database file
        output_base_path: Base path for output files (without extension).
                         Will generate {base}_accumulated.png and {base}_per_tick.png
        agent: Filter costs for specific agent (optional)
        quiet: Suppress informational messages
        max_y_per_tick: Optional maximum Y-axis value for per-tick chart in dollars (None = adaptive)
        max_y_accumulated: Optional maximum Y-axis value for accumulated chart in dollars (None = adaptive)
    """
    from pathlib import Path

    from payment_simulator.api.main import manager
    from payment_simulator.persistence.queries import get_simulation_summary

    if not quiet:
        console.print(f"[yellow]Generating cost charts for simulation {simulation_id}...[/yellow]")

    # Set up database manager
    if not manager.db_manager:
        manager.db_manager = DatabaseManager(db_path)

    conn = manager.db_manager.get_connection()

    # Check if simulation exists
    summary = get_simulation_summary(conn, simulation_id)
    if not summary:
        console.print(f"[red]✗ Simulation not found: {simulation_id}[/red]")
        raise typer.Exit(code=1)

    ticks_per_day = summary["ticks_per_day"]
    num_days = summary.get("num_days", 3)

    # Extract policy names from config for legend
    policy_names = {}
    if summary.get("config_json"):
        policy_names = _extract_policy_names(summary["config_json"])

    # Get all agents from the simulation
    agents_query = """
        SELECT DISTINCT agent_id
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        ORDER BY agent_id
    """
    agent_results = conn.execute(agents_query, [simulation_id]).fetchall()
    all_agents = {row[0] for row in agent_results}

    if not all_agents:
        console.print(f"[yellow]No cost data available for simulation {simulation_id}[/yellow]")
        return

    # Filter agents if requested
    if agent:
        if agent not in all_agents:
            console.print(f"[red]✗ Agent '{agent}' not found in simulation[/red]")
            console.print(f"[yellow]Available agents: {', '.join(sorted(all_agents))}[/yellow]")
            raise typer.Exit(code=1)
        agent_ids = [agent]
    else:
        agent_ids = sorted(all_agents)

    # Collect event-based cost data
    tick_costs = _collect_event_based_cost_data(conn, simulation_id, agent_ids, ticks_per_day, num_days)

    if not tick_costs:
        console.print(f"[yellow]No cost data found for simulation {simulation_id}[/yellow]")
        return

    # Generate both charts
    if output_base_path is None:
        output_base_path = f"cost_chart_{simulation_id}"
    base_path = Path(output_base_path)

    # Accumulated chart
    accumulated_path = str(base_path.parent / f"{base_path.stem}_accumulated.png")
    _generate_cost_chart_png(
        tick_costs=tick_costs,
        agent_ids=agent_ids,
        simulation_id=simulation_id,
        ticks_per_day=ticks_per_day,
        output_path=accumulated_path,
        show_per_tick=False,
        quiet=quiet,
        policy_names=policy_names,
        max_y=max_y_accumulated,
    )

    # Per-tick chart
    per_tick_path = str(base_path.parent / f"{base_path.stem}_per_tick.png")
    _generate_cost_chart_png(
        tick_costs=tick_costs,
        agent_ids=agent_ids,
        simulation_id=simulation_id,
        ticks_per_day=ticks_per_day,
        output_path=per_tick_path,
        show_per_tick=True,
        quiet=quiet,
        policy_names=policy_names,
        max_y=max_y_per_tick,
    )


@db_app.command("costs")
def db_costs(
    simulation_id: Annotated[
        str,
        typer.Argument(help="Simulation ID to get costs for"),
    ],
    db_path: Annotated[
        str,
        typer.Option("--db-path", "-d", help="Path to database file"),
    ] = "simulation_data.db",
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Filter costs for specific agent"),
    ] = None,
    output_csv: Annotated[
        str | None,
        typer.Option("--output-csv", "-o", help="Export to CSV file"),
    ] = None,
    chart_output: Annotated[
        str | None,
        typer.Option("--chart-output", "-c", help="Generate PNG chart (e.g., costs.png)"),
    ] = None,
    show_per_tick: Annotated[
        bool,
        typer.Option("--per-tick", "-p", help="Show per-tick costs instead of accumulated"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of ticks to display (0 = show all)"),
    ] = 50,
) -> None:
    """Get tick-by-tick cost data for a simulation.

    This command uses the same API endpoint as the diagnostic frontend cost chart.
    Shows accumulated costs per agent per tick with optional filtering and export.
    """
    try:
        import csv
        from collections import defaultdict

        from payment_simulator.api.main import manager
        from payment_simulator.persistence.queries import get_simulation_summary

        console.print(f"[yellow]Loading cost timeline for simulation {simulation_id}...[/yellow]")

        # Set up database manager
        if not manager.db_manager:
            manager.db_manager = DatabaseManager(db_path)

        conn = manager.db_manager.get_connection()

        # Check if simulation exists
        summary = get_simulation_summary(conn, simulation_id)
        if not summary:
            console.print(f"[red]✗ Simulation not found: {simulation_id}[/red]")
            raise typer.Exit(code=1)

        ticks_per_day = summary["ticks_per_day"]

        # Extract policy names from config for legend
        policy_names = {}
        if summary.get("config_json"):
            policy_names = _extract_policy_names(summary["config_json"])

        # Get all agents from the simulation
        agents_query = """
            SELECT DISTINCT agent_id
            FROM daily_agent_metrics
            WHERE simulation_id = ?
            ORDER BY agent_id
        """
        agent_results = conn.execute(agents_query, [simulation_id]).fetchall()
        all_agents = {row[0] for row in agent_results}

        if not all_agents:
            console.print(f"[yellow]No cost data available for simulation {simulation_id}[/yellow]")
            raise typer.Exit(code=0)

        # Filter agents if requested
        if agent:
            if agent not in all_agents:
                console.print(f"[red]✗ Agent '{agent}' not found in simulation[/red]")
                console.print(f"[yellow]Available agents: {', '.join(sorted(all_agents))}[/yellow]")
                raise typer.Exit(code=1)
            agent_ids = [agent]
        else:
            agent_ids = sorted(all_agents)

        # Query actual tick-level cost events
        # 1. CostAccrual events for continuous costs (liquidity, delay, collateral)
        # 2. TransactionWentOverdue events for deadline penalties
        cost_accrual_query = """
            SELECT
                tick,
                agent_id,
                CAST(json_extract(details, '$.costs.total') AS INTEGER) as tick_cost
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'CostAccrual'
            ORDER BY tick
        """

        deadline_penalty_query = """
            SELECT
                tick,
                json_extract(details, '$.sender_id') as agent_id,
                CAST(json_extract(details, '$.deadline_penalty_cost') AS INTEGER) as penalty_cost
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'TransactionWentOverdue'
            ORDER BY tick
        """

        # Aggregate costs by tick and agent
        tick_agent_costs: defaultdict[int, defaultdict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Add continuous costs from CostAccrual events
        for row in conn.execute(cost_accrual_query, [simulation_id]).fetchall():
            tick, agent_id_event, cost = row
            tick_agent_costs[tick][agent_id_event] += cost

        # Add deadline penalties from TransactionWentOverdue events
        for row in conn.execute(deadline_penalty_query, [simulation_id]).fetchall():
            tick, agent_id_event, penalty = row
            tick_agent_costs[tick][agent_id_event] += penalty

        # Add EOD penalties from daily_agent_metrics (these aren't in event stream per-agent)
        # EOD penalties are $5,000 per unsettled transaction assessed at end of each day
        eod_penalty_query = """
            SELECT
                day,
                agent_id,
                deadline_penalty_cost
            FROM daily_agent_metrics
            WHERE simulation_id = ?
            ORDER BY day, agent_id
        """

        for row in conn.execute(eod_penalty_query, [simulation_id]).fetchall():
            day, agent_id_event, deadline_pen = row

            # Calculate costs already captured from events for this agent this day
            event_costs_this_day = 0
            for tick in range(day * ticks_per_day, (day + 1) * ticks_per_day):
                event_costs_this_day += tick_agent_costs[tick].get(agent_id_event, 0)

            # EOD penalty is the difference (what's in daily table but not in events)
            eod_penalty = deadline_pen - event_costs_this_day

            if eod_penalty > 0:
                # Apply EOD penalty at the LAST tick of the day
                eod_tick = (day + 1) * ticks_per_day - 1
                tick_agent_costs[eod_tick][agent_id_event] += eod_penalty

        # Get max tick from simulation
        num_days = summary.get("num_days", 3)
        max_tick = (ticks_per_day * num_days) - 1

        # Build accumulated costs for all ticks
        tick_costs = []
        accumulated = dict.fromkeys(agent_ids, 0)

        for tick in range(max_tick + 1):
            # Store previous accumulated for per-tick calculation
            prev_accumulated = dict(accumulated)

            # Add costs that occurred at this tick
            for agent_id in agent_ids:
                accumulated[agent_id] += tick_agent_costs[tick].get(agent_id, 0)

            # Calculate per-tick costs if requested
            if show_per_tick:
                tick_data = {
                    "tick": tick,
                    "day": tick // ticks_per_day,
                    "costs": {agent_id: int(accumulated[agent_id] - prev_accumulated[agent_id]) for agent_id in agent_ids}
                }
            else:
                tick_data = {
                    "tick": tick,
                    "day": tick // ticks_per_day,
                    "costs": {agent_id: int(accumulated[agent_id]) for agent_id in agent_ids}
                }

            tick_costs.append(tick_data)

        # Export to CSV if requested
        if output_csv:
            with open(output_csv, 'w', newline='') as csvfile:
                fieldnames = ['tick', 'day', *agent_ids]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for data in tick_costs:
                    row = {'tick': data['tick'], 'day': data['day']}
                    row.update(data['costs'])
                    writer.writerow(row)

            console.print(f"[green]✓ Exported {len(tick_costs)} tick records to {output_csv}[/green]")
            return

        # Generate chart if requested
        if chart_output:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            from matplotlib.ticker import FuncFormatter

            # Prepare data for plotting
            ticks = [data['tick'] for data in tick_costs]

            # Create figure with larger size for readability
            fig, ax = plt.subplots(figsize=(14, 8))

            # Plot each agent's costs
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            for i, agent_id in enumerate(agent_ids):
                costs_usd = [data['costs'][agent_id] / 100.0 for data in tick_costs]
                # Create label with policy name if available
                if policy_names and agent_id in policy_names:
                    label = f"{agent_id}: {policy_names[agent_id]}"
                else:
                    label = agent_id
                ax.plot(ticks, costs_usd, label=label, linewidth=2, color=colors[i % len(colors)])

            # Format y-axis as currency
            def currency_formatter(x: float, p: int) -> str:
                return f'${x:,.0f}'

            ax.yaxis.set_major_formatter(FuncFormatter(currency_formatter))

            # Add labels and title
            mode_str = 'Per-Tick' if show_per_tick else 'Accumulated'
            ax.set_xlabel('Tick', fontsize=12, fontweight='bold')
            ax.set_ylabel(f'{mode_str} Cost (USD)', fontsize=12, fontweight='bold')
            ax.set_title(f'Cost Timeline - {simulation_id}\n{mode_str} Costs by Agent',
                        fontsize=14, fontweight='bold', pad=20)

            # Add legend
            ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

            # Add grid for readability
            ax.grid(True, alpha=0.3, linestyle='--')

            # Add day boundaries as vertical lines
            if ticks_per_day:
                for day in range(1, (max(ticks) // ticks_per_day) + 1):
                    day_tick = day * ticks_per_day
                    if day_tick <= max(ticks):
                        ax.axvline(x=day_tick, color='gray', linestyle=':', alpha=0.5, linewidth=1)
                        ax.text(day_tick, ax.get_ylim()[1] * 0.98, f'Day {day}',
                               rotation=90, verticalalignment='top', fontsize=8, alpha=0.7)

            # Tight layout to prevent label cutoff
            plt.tight_layout()

            # Save the chart
            plt.savefig(chart_output, dpi=150, bbox_inches='tight')
            plt.close(fig)

            console.print(f"[green]✓ Generated chart: {chart_output}[/green]")
            if not output_csv:  # If only generating chart, return here
                return

        # Display in terminal
        console.print(f"\n[bold cyan]Cost Timeline for {simulation_id}[/bold cyan]")
        console.print(f"  Total ticks: {len(tick_costs)}")
        console.print(f"  Agents: {', '.join(agent_ids)}")
        console.print(f"  Mode: {'Per-tick' if show_per_tick else 'Accumulated'}")

        # Determine which ticks to show
        if limit > 0 and len(tick_costs) > limit:
            # Show first limit/2 and last limit/2
            half = limit // 2
            display_costs = tick_costs[:half] + tick_costs[-half:]
            show_ellipsis = True
        else:
            display_costs = tick_costs
            show_ellipsis = False

        # Create table
        table = Table(title=f"{'Per-Tick' if show_per_tick else 'Accumulated'} Costs")
        table.add_column("Tick", justify="right", style="cyan")
        table.add_column("Day", justify="right", style="blue")

        for agent_id in agent_ids:
            table.add_column(agent_id, justify="right", style="green")

        # Add rows
        prev_tick = -1
        for i, data in enumerate(display_costs):
            if show_ellipsis and i == half and data['tick'] - prev_tick > 1:
                table.add_row("...", "...", *["..." for _ in agent_ids], style="dim")

            # Format costs as dollars
            cost_strs = []
            for agent_id in agent_ids:
                cost_cents = data['costs'][agent_id]
                cost_strs.append(f"${cost_cents / 100:,.2f}")

            table.add_row(
                str(data['tick']),
                str(data['day']),
                *cost_strs
            )
            prev_tick = data['tick']

        console.print()
        console.print(table)

        # Show summary
        console.print()
        table_summary = Table(title="Final Costs Summary")
        table_summary.add_column("Agent", style="cyan")
        table_summary.add_column("Total Cost", justify="right", style="green")

        final_costs = tick_costs[-1]['costs']
        total_system_cost = sum(final_costs.values())

        for agent_id in agent_ids:
            cost = final_costs[agent_id]
            table_summary.add_row(agent_id, f"${cost / 100:,.2f}")

        table_summary.add_row("[bold]TOTAL", f"[bold]${total_system_cost / 100:,.2f}", style="bold yellow")

        console.print(table_summary)

        if limit > 0 and len(tick_costs) > limit:
            console.print(f"\n[dim]Showing {len(display_costs)} of {len(tick_costs)} ticks. Use --limit 0 to show all or --output-csv to export.[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Error getting costs: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(code=1)

