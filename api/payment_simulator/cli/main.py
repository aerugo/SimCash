"""Payment Simulator CLI - Main entry point."""

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="payment-sim",
    help="Payment Simulator - High-performance RTGS simulation for AI-driven research",
    add_completion=True,
    no_args_is_help=True,
)


def version_callback(value: bool):
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
):
    """Payment Simulator CLI - Terminal-first interface optimized for AI iteration."""
    pass


# Import commands after app is defined to avoid circular imports
from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.cli.commands.checkpoint import checkpoint_app
from payment_simulator.cli.commands.db import db_app

app.command(name="run", help="Run a simulation from a configuration file")(run_simulation)
app.add_typer(checkpoint_app, name="checkpoint")
app.add_typer(db_app, name="db")


if __name__ == "__main__":
    app()
