"""Payment Simulator CLI - Main entry point."""

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="payment-sim",
    help="Payment Simulator - High-performance RTGS simulation for AI-driven research",
    add_completion=True,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        from payment_simulator.cli.output import console
        console.print("[bold]Payment Simulator[/bold] v0.1.0")
        console.print("Rust-Python hybrid RTGS simulation engine")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """Payment Simulator CLI - Terminal-first interface optimized for AI iteration."""
    pass


# Import commands after app is defined to avoid circular imports
from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.cli.commands.replay import replay_simulation
from payment_simulator.cli.commands.checkpoint import checkpoint_app
from payment_simulator.cli.commands.db import db_app
from payment_simulator.cli.commands.policy_schema import policy_schema
from payment_simulator.cli.commands.validate_policy import validate_policy

app.command(name="run", help="Run a simulation from a configuration file")(run_simulation)
app.command(name="replay", help="Replay a persisted simulation with verbose output for a tick range")(replay_simulation)
app.command(name="policy-schema", help="Generate policy schema documentation")(policy_schema)
app.command(name="validate-policy", help="Validate a policy tree JSON file")(validate_policy)
app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(db_app, name="db")


if __name__ == "__main__":
    app()
