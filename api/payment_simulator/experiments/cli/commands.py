"""Generic experiment CLI commands.

Provides replay and results commands that work with any experiment type
via the StateProvider pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from payment_simulator.experiments.cli.common import build_verbose_config
from payment_simulator.experiments.persistence import ExperimentRepository
from payment_simulator.experiments.runner import (
    display_audit_output,
    display_experiment_output,
)

# Default database path
DEFAULT_DB_PATH = Path("results/experiments.db")

experiment_app = typer.Typer(
    name="experiments",
    help="Generic experiment commands for replay and results",
    no_args_is_help=True,
)
console = Console()


@experiment_app.command()
def replay(
    run_id: Annotated[
        str,
        typer.Argument(help="Run ID to replay (e.g., exp1-20251209-143022-a1b2c3)"),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable all verbose output"),
    ] = False,
    verbose_iterations: Annotated[
        bool,
        typer.Option("--verbose-iterations", help="Show iteration starts"),
    ] = False,
    verbose_bootstrap: Annotated[
        bool,
        typer.Option("--verbose-bootstrap", help="Show bootstrap evaluations"),
    ] = False,
    verbose_llm: Annotated[
        bool,
        typer.Option("--verbose-llm", help="Show LLM call details"),
    ] = False,
    verbose_policy: Annotated[
        bool,
        typer.Option("--verbose-policy", help="Show policy changes"),
    ] = False,
    audit: Annotated[
        bool,
        typer.Option("--audit", help="Show detailed audit trail for each iteration"),
    ] = False,
    start: Annotated[
        int | None,
        typer.Option("--start", help="Start iteration for audit output (inclusive)"),
    ] = None,
    end: Annotated[
        int | None,
        typer.Option("--end", help="End iteration for audit output (inclusive)"),
    ] = None,
) -> None:
    """Replay experiment output from database.

    Displays the same output that was shown during the original run,
    using the unified display function (StateProvider pattern).

    With --audit flag, shows detailed audit trail including:
    - Raw LLM prompts and responses
    - Validation errors and retry attempts
    - Evaluation results for each agent

    Examples:
        # Replay a specific run
        experiments replay exp1-20251209-143022-a1b2c3

        # Replay with verbose output
        experiments replay exp1-20251209-143022-a1b2c3 --verbose

        # Replay from a specific database
        experiments replay exp1-20251209-143022-a1b2c3 --db results/custom.db

        # Show audit trail for iterations 2-3
        experiments replay exp1-20251209-143022-a1b2c3 --audit --start 2 --end 3
    """
    # Validate audit options
    if start is not None and start < 0:
        console.print("[red]Error: --start must be a non-negative integer[/red]")
        raise typer.Exit(1)

    if end is not None and end < 0:
        console.print("[red]Error: --end must be a non-negative integer[/red]")
        raise typer.Exit(1)

    if start is not None and end is not None and start > end:
        console.print(
            f"[red]Error: --start ({start}) cannot be greater than --end ({end})[/red]"
        )
        raise typer.Exit(1)

    # Check database exists
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        raise typer.Exit(1)

    # Open repository
    try:
        repo = ExperimentRepository(db)
    except Exception as e:
        console.print(f"[red]Failed to open database: {e}[/red]")
        raise typer.Exit(1) from e

    # Create provider using StateProvider pattern
    provider = repo.as_state_provider(run_id)

    # Check run exists
    metadata = provider.get_run_metadata()
    if metadata is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        repo.close()
        raise typer.Exit(1)

    # Handle audit mode
    if audit:
        display_audit_output(
            provider=provider,
            console=console,
            start_iteration=start,
            end_iteration=end,
        )
    else:
        # Standard replay mode
        verbose_config = build_verbose_config(
            verbose=verbose,
            verbose_iterations=verbose_iterations if verbose_iterations else None,
            verbose_bootstrap=verbose_bootstrap if verbose_bootstrap else None,
            verbose_llm=verbose_llm if verbose_llm else None,
            verbose_policy=verbose_policy if verbose_policy else None,
        )

        # Display output using unified function
        display_experiment_output(provider, console, verbose_config)

    repo.close()


@experiment_app.command()
def results(
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    experiment: Annotated[
        str | None,
        typer.Option("--experiment", "-e", help="Filter by experiment name"),
    ] = None,
    experiment_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by experiment type"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of results to show"),
    ] = 20,
) -> None:
    """List experiment runs from database.

    Shows run IDs, dates, status, and metrics for all recorded experiments.

    Examples:
        # List all runs
        experiments results

        # Filter by experiment name
        experiments results --experiment exp1

        # Filter by type
        experiments results --type castro

        # Use a specific database
        experiments results --db results/custom.db
    """
    # Check database exists
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        raise typer.Exit(1)

    # Get runs using ExperimentRepository
    try:
        repo = ExperimentRepository(db)
    except Exception as e:
        console.print(f"[red]Failed to open database: {e}[/red]")
        raise typer.Exit(1) from e

    # List experiments (filtered by type and/or name)
    runs = repo.list_experiments(
        experiment_type=experiment_type,
        experiment_name=experiment,
        limit=limit,
    )

    repo.close()

    if not runs:
        if experiment:
            console.print(f"[yellow]No runs found for experiment: {experiment}[/yellow]")
        elif experiment_type:
            console.print(f"[yellow]No runs found for type: {experiment_type}[/yellow]")
        else:
            console.print("[yellow]No experiment runs found in database.[/yellow]")
        return

    # Create results table
    table = Table(title="Experiment Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Experiment", style="green")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Final Cost", justify="right")
    table.add_column("Best Cost", justify="right")
    table.add_column("Iterations", justify="right")
    table.add_column("Converged")
    table.add_column("Started", style="dim")

    for run in runs:
        # Format costs from config dict
        final_cost_val = run.config.get("final_cost")
        best_cost_val = run.config.get("best_cost")
        final_cost = f"${final_cost_val / 100:.2f}" if final_cost_val else "-"
        best_cost = f"${best_cost_val / 100:.2f}" if best_cost_val else "-"
        iterations = str(run.num_iterations) if run.num_iterations else "-"
        converged = "Yes" if run.converged else "No" if run.converged is False else "-"

        # Format status based on completed_at
        if run.completed_at:
            status = "[green]completed[/green]"
        else:
            status = "[yellow]running[/yellow]"

        # Format date
        started = run.created_at[:16].replace("T", " ") if run.created_at else "-"

        table.add_row(
            run.run_id,
            run.experiment_name,
            run.experiment_type,
            status,
            final_cost,
            best_cost,
            iterations,
            converged,
            started,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(runs)} run(s)[/dim]")
