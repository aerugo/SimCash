"""Checkpoint CLI commands for save/load simulation.

Provides commands to:
- Save simulation state to database
- Load simulation state from database
- List available checkpoints
- Delete checkpoints
"""
import typer
from typing import Optional
from pathlib import Path
import json
import os

from payment_simulator.cli.output import console
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.checkpoint import CheckpointManager
from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig

# Checkpoint command group
checkpoint_app = typer.Typer(
    name="checkpoint",
    help="Manage simulation checkpoints (save/load/list/delete)",
    no_args_is_help=True,
)


def get_database_manager() -> DatabaseManager:
    """Get database manager with configured path."""
    db_path = os.environ.get("PAYMENT_SIM_DB_PATH", "simulation_data.db")
    db_manager = DatabaseManager(db_path)

    # Initialize if database doesn't exist
    if not Path(db_path).exists():
        console.print(f"[yellow]Initializing database at {db_path}[/yellow]")
        db_manager.setup()
    else:
        # Just connect, don't re-setup
        pass

    return db_manager


# =============================================================================
# Save Command
# =============================================================================


@checkpoint_app.command(name="save")
def save_checkpoint(
    simulation_id: str = typer.Option(..., "--simulation-id", "-s", help="Simulation ID for this checkpoint"),
    state_file: Path = typer.Option(..., "--state-file", "-f", help="Path to state JSON file from orchestrator.save_state()"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Human-readable description"),
    checkpoint_type: str = typer.Option("manual", "--type", "-t", help="Checkpoint type (manual/auto/eod/final)"),
):
    """Save simulation checkpoint to database.

    Example:
        payment-sim checkpoint save --simulation-id sim_001 --state-file state.json --description "After 50 ticks"
    """
    try:
        # Validate inputs
        if not state_file.exists():
            console.print(f"[red]Error: State file not found: {state_file}[/red]")
            raise typer.Exit(1)

        # Read state JSON
        with open(state_file, 'r') as f:
            state_json = f.read()

        # Validate JSON
        try:
            state_dict = json.loads(state_json)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: Invalid JSON in state file: {e}[/red]")
            raise typer.Exit(1)

        # Get database manager
        db_manager = get_database_manager()

        # Create checkpoint manager
        checkpoint_mgr = CheckpointManager(db_manager)

        # Create wrapper to adapt state JSON for CheckpointManager
        class StateWrapper:
            def __init__(self, state_json):
                self._state_json = state_json

            def save_state(self):
                return self._state_json

            def current_tick(self):
                state = json.loads(self._state_json)
                return state["current_tick"]

            def current_day(self):
                state = json.loads(self._state_json)
                return state["current_day"]

        wrapper = StateWrapper(state_json)

        # Save checkpoint
        checkpoint_id = checkpoint_mgr.save_checkpoint(
            orchestrator=wrapper,
            simulation_id=simulation_id,
            checkpoint_type=checkpoint_type,
            description=description,
            created_by="cli"
        )

        # Display success
        console.print(f"[green]✓ Checkpoint saved successfully[/green]")
        console.print(f"  Checkpoint ID: [cyan]{checkpoint_id}[/cyan]")
        console.print(f"  Simulation ID: [cyan]{simulation_id}[/cyan]")
        console.print(f"  Tick: [yellow]{state_dict['current_tick']}[/yellow]")
        console.print(f"  Day: [yellow]{state_dict['current_day']}[/yellow]")

        db_manager.close()

    except Exception as e:
        console.print(f"[red]Error saving checkpoint: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Load Command
# =============================================================================


@checkpoint_app.command(name="load")
def load_checkpoint(
    checkpoint_id: str = typer.Option(None, "--checkpoint-id", "-c", help="Checkpoint ID to load"),
    simulation_id: str = typer.Option(None, "--simulation-id", "-s", help="Simulation ID (for 'latest' checkpoint)"),
    config: Path = typer.Option(..., "--config", help="Configuration file (YAML)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save restored state to file"),
):
    """Load and restore simulation from checkpoint.

    Example:
        payment-sim checkpoint load --checkpoint-id abc123 --config config.yaml
        payment-sim checkpoint load --checkpoint-id latest --simulation-id sim_001 --config config.yaml
    """
    try:
        # Validate that either checkpoint-id or (latest + simulation-id) provided
        if checkpoint_id is None and simulation_id is None:
            console.print("[red]Error: Must provide either --checkpoint-id or --simulation-id with latest[/red]")
            raise typer.Exit(1)

        if checkpoint_id == "latest" and simulation_id is None:
            console.print("[red]Error: --simulation-id required when using 'latest'[/red]")
            raise typer.Exit(1)

        # Validate config exists
        if not config.exists():
            console.print(f"[red]Error: Config file not found: {config}[/red]")
            raise typer.Exit(1)

        # Load config
        import yaml
        with open(config, 'r') as f:
            config_dict = yaml.safe_load(f)

        # Convert to SimulationConfig and get FFI dict
        sim_config = SimulationConfig.from_dict(config_dict)
        ffi_dict = sim_config.to_ffi_dict()

        # Get database manager
        db_manager = get_database_manager()
        checkpoint_mgr = CheckpointManager(db_manager)

        # Get checkpoint
        if checkpoint_id == "latest":
            checkpoint_record = checkpoint_mgr.get_latest_checkpoint(simulation_id)
            if checkpoint_record is None:
                console.print(f"[red]Error: No checkpoints found for simulation {simulation_id}[/red]")
                raise typer.Exit(1)
            actual_checkpoint_id = checkpoint_record["checkpoint_id"]
        else:
            actual_checkpoint_id = checkpoint_id
            checkpoint_record = checkpoint_mgr.get_checkpoint(actual_checkpoint_id)
            if checkpoint_record is None:
                console.print(f"[red]Error: Checkpoint not found: {checkpoint_id}[/red]")
                raise typer.Exit(1)

        # Load orchestrator from checkpoint
        console.print("[yellow]Loading checkpoint...[/yellow]")
        orch = checkpoint_mgr.load_checkpoint(actual_checkpoint_id, ffi_dict)

        # Display restored state
        console.print(f"[green]✓ Simulation restored from checkpoint[/green]")
        console.print(f"  Checkpoint ID: [cyan]{actual_checkpoint_id}[/cyan]")
        console.print(f"  Simulation ID: [cyan]{checkpoint_record['simulation_id']}[/cyan]")
        console.print(f"  Tick: [yellow]{orch.current_tick()}[/yellow]")
        console.print(f"  Day: [yellow]{orch.current_day()}[/yellow]")

        # Save to file if requested
        if output:
            state_json = orch.save_state()
            with open(output, 'w') as f:
                f.write(state_json)
            console.print(f"  Saved state to: [cyan]{output}[/cyan]")

        db_manager.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading checkpoint: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# List Command
# =============================================================================


@checkpoint_app.command(name="list")
def list_checkpoints(
    simulation_id: Optional[str] = typer.Option(None, "--simulation-id", "-s", help="Filter by simulation ID"),
    checkpoint_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by checkpoint type"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Maximum number of results"),
):
    """List available checkpoints.

    Example:
        payment-sim checkpoint list
        payment-sim checkpoint list --simulation-id sim_001
        payment-sim checkpoint list --type manual --limit 10
    """
    try:
        # Get database manager
        db_manager = get_database_manager()
        checkpoint_mgr = CheckpointManager(db_manager)

        # Query checkpoints
        checkpoints = checkpoint_mgr.list_checkpoints(
            simulation_id=simulation_id,
            checkpoint_type=checkpoint_type,
            limit=limit
        )

        if not checkpoints:
            console.print("[yellow]No checkpoints found[/yellow]")
            db_manager.close()
            return

        # Display as table
        from rich.table import Table

        table = Table(title=f"Simulation Checkpoints ({len(checkpoints)} found)")

        table.add_column("Checkpoint ID", style="cyan", no_wrap=True, width=36)
        table.add_column("Sim ID", style="blue", width=20)
        table.add_column("Tick", justify="right", style="yellow")
        table.add_column("Day", justify="right", style="yellow")
        table.add_column("Type", style="magenta")
        table.add_column("Description", style="white", overflow="fold")

        for cp in checkpoints[:50]:  # Limit display to 50 for readability
            table.add_row(
                cp["checkpoint_id"][:8] + "...",  # Truncate ID for display
                cp["simulation_id"][:20],
                str(cp["checkpoint_tick"]),
                str(cp["checkpoint_day"]),
                cp["checkpoint_type"],
                cp.get("description", "")[:40] if cp.get("description") else "-"
            )

        console.print(table)

        if len(checkpoints) > 50:
            console.print(f"[yellow]... and {len(checkpoints) - 50} more (use --limit to see more)[/yellow]")

        db_manager.close()

    except Exception as e:
        console.print(f"[red]Error listing checkpoints: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Delete Command
# =============================================================================


@checkpoint_app.command(name="delete")
def delete_checkpoint(
    checkpoint_id: Optional[str] = typer.Option(None, "--checkpoint-id", "-c", help="Checkpoint ID to delete"),
    simulation_id: Optional[str] = typer.Option(None, "--simulation-id", "-s", help="Delete all checkpoints for simulation"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt"),
):
    """Delete checkpoint(s) from database.

    Example:
        payment-sim checkpoint delete --checkpoint-id abc123
        payment-sim checkpoint delete --simulation-id sim_001 --confirm
    """
    try:
        if checkpoint_id is None and simulation_id is None:
            console.print("[red]Error: Must provide either --checkpoint-id or --simulation-id[/red]")
            raise typer.Exit(1)

        # Get database manager
        db_manager = get_database_manager()
        checkpoint_mgr = CheckpointManager(db_manager)

        if checkpoint_id:
            # Delete single checkpoint
            if not confirm:
                response = typer.confirm(f"Delete checkpoint {checkpoint_id}?")
                if not response:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            result = checkpoint_mgr.delete_checkpoint(checkpoint_id)
            if result:
                console.print(f"[green]✓ Checkpoint {checkpoint_id} deleted[/green]")
            else:
                console.print(f"[yellow]Checkpoint {checkpoint_id} not found (may have been already deleted)[/yellow]")

        elif simulation_id:
            # Delete all checkpoints for simulation
            checkpoints = checkpoint_mgr.list_checkpoints(simulation_id=simulation_id)

            if not checkpoints:
                console.print(f"[yellow]No checkpoints found for simulation {simulation_id}[/yellow]")
                return

            if not confirm:
                response = typer.confirm(f"Delete {len(checkpoints)} checkpoint(s) for simulation {simulation_id}?")
                if not response:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            for cp in checkpoints:
                checkpoint_mgr.delete_checkpoint(cp["checkpoint_id"])

            console.print(f"[green]✓ Deleted {len(checkpoints)} checkpoint(s) for simulation {simulation_id}[/green]")

        db_manager.close()

    except Exception as e:
        console.print(f"[red]Error deleting checkpoint: {e}[/red]")
        raise typer.Exit(1)
