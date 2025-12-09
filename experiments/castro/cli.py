"""CLI for Castro experiments.

Run Castro experiments using the ai_cash_mgmt module.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from castro.experiments import EXPERIMENTS
from castro.runner import ExperimentRunner

# Load environment variables from .env file (if present)
# This must happen before any LLM client initialization
load_dotenv()

app = typer.Typer(
    name="castro",
    help="Castro experiments using ai_cash_mgmt",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    experiment: Annotated[
        str,
        typer.Argument(help="Experiment key: exp1, exp2, or exp3"),
    ],
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LLM model to use"),
    ] = "claude-sonnet-4-5-20250929",
    max_iter: Annotated[
        int,
        typer.Option("--max-iter", "-i", help="Maximum optimization iterations"),
    ] = 25,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for results"),
    ] = None,
    seed: Annotated[
        int,
        typer.Option("--seed", "-s", help="Master seed for determinism"),
    ] = 42,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable all verbose output"),
    ] = False,
    verbose_policy: Annotated[
        bool,
        typer.Option("--verbose-policy", help="Show policy parameter changes"),
    ] = False,
    verbose_monte_carlo: Annotated[
        bool,
        typer.Option("--verbose-monte-carlo", help="Show per-seed Monte Carlo results"),
    ] = False,
    verbose_llm: Annotated[
        bool,
        typer.Option("--verbose-llm", help="Show LLM call metadata"),
    ] = False,
    verbose_rejections: Annotated[
        bool,
        typer.Option("--verbose-rejections", help="Show rejection analysis"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress verbose output"),
    ] = False,
) -> None:
    """Run a Castro experiment.

    Examples:
        castro run exp1
        castro run exp2 --model gpt-4o --max-iter 50
        castro run exp3 --output ./my_results --seed 123

        # All verbose output
        castro run exp1 --verbose

        # Specific verbose modes
        castro run exp1 --verbose-policy --verbose-monte-carlo

        # Quiet mode (current behavior)
        castro run exp1 --quiet
    """
    from castro.verbose_logging import VerboseConfig

    # Build verbose configuration
    if quiet:
        verbose_config = VerboseConfig()  # All disabled
    else:
        verbose_config = VerboseConfig.from_flags(
            verbose=verbose,
            verbose_policy=verbose_policy if verbose_policy else None,
            verbose_monte_carlo=verbose_monte_carlo if verbose_monte_carlo else None,
            verbose_llm=verbose_llm if verbose_llm else None,
            verbose_rejections=verbose_rejections if verbose_rejections else None,
        )

    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        console.print(f"Available: {', '.join(EXPERIMENTS.keys())}")
        raise typer.Exit(1)

    # Create experiment configuration
    output_dir = output or Path("results")
    exp = EXPERIMENTS[experiment](output_dir=output_dir, model=model)

    # Override settings if specified
    if max_iter != 25:
        exp.max_iterations = max_iter
    if seed != 42:
        exp.master_seed = seed

    # Run the experiment
    console.print(f"[bold]Running {experiment}...[/bold]")
    runner = ExperimentRunner(exp, verbose_config=verbose_config)

    try:
        result = asyncio.run(runner.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    # Print results table
    console.print()
    table = Table(title=f"Results: {exp.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Final Cost", f"${result.final_cost / 100:.2f}")
    table.add_row("Best Cost", f"${result.best_cost / 100:.2f}")
    table.add_row("Iterations", str(result.num_iterations))
    table.add_row("Converged", "Yes" if result.converged else "No")
    table.add_row("Convergence Reason", result.convergence_reason)
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")

    console.print(table)

    # Print per-agent costs
    if result.per_agent_costs:
        console.print("\n[bold]Per-Agent Costs:[/bold]")
        for agent_id, cost in result.per_agent_costs.items():
            console.print(f"  {agent_id}: ${cost / 100:.2f}")


@app.command("list")
def list_experiments() -> None:
    """List available experiments."""
    table = Table(title="Castro Experiments")
    table.add_column("Key", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")

    for key, factory in EXPERIMENTS.items():
        exp = factory()
        table.add_row(key, exp.name, exp.description)

    console.print(table)


@app.command()
def info(
    experiment: Annotated[
        str,
        typer.Argument(help="Experiment key to show details for"),
    ],
) -> None:
    """Show detailed experiment configuration."""
    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        console.print(f"Available: {', '.join(EXPERIMENTS.keys())}")
        raise typer.Exit(1)

    exp = EXPERIMENTS[experiment]()

    console.print(f"[bold cyan]{exp.name}[/bold cyan]")
    console.print(f"Description: {exp.description}")
    console.print()

    # Configuration table
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Scenario Path", str(exp.scenario_path))
    table.add_row("Master Seed", str(exp.master_seed))
    table.add_row("Output Directory", str(exp.output_dir))
    table.add_row("", "")
    table.add_row("[bold]Monte Carlo[/bold]", "")
    table.add_row("  Samples", str(exp.num_samples))
    table.add_row("  Evaluation Ticks", str(exp.evaluation_ticks))
    table.add_row("", "")
    table.add_row("[bold]Convergence[/bold]", "")
    table.add_row("  Max Iterations", str(exp.max_iterations))
    table.add_row("  Stability Threshold", f"{exp.stability_threshold:.1%}")
    table.add_row("  Stability Window", str(exp.stability_window))
    table.add_row("", "")
    table.add_row("[bold]LLM[/bold]", "")
    llm_config = exp.get_llm_config()
    # Provider can be enum or string
    provider_str = (
        llm_config.provider.value
        if hasattr(llm_config.provider, "value")
        else str(llm_config.provider)
    )
    table.add_row("  Provider", provider_str)
    table.add_row("  Model", exp.llm_model)
    table.add_row("  Temperature", str(exp.llm_temperature))
    table.add_row("", "")
    table.add_row("[bold]Agents[/bold]", "")
    table.add_row("  Optimized", ", ".join(exp.optimized_agents))

    console.print(table)


@app.command()
def validate(
    experiment: Annotated[
        str,
        typer.Argument(help="Experiment key to validate"),
    ],
) -> None:
    """Validate experiment configuration.

    Checks that scenario config exists and is valid.
    """
    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        raise typer.Exit(1)

    exp = EXPERIMENTS[experiment]()
    base_dir = Path(__file__).parent
    scenario_path = base_dir / exp.scenario_path

    console.print(f"[bold]Validating {exp.name}...[/bold]")

    # Check scenario file exists
    if not scenario_path.exists():
        console.print(f"[red]Scenario config not found: {scenario_path}[/red]")
        raise typer.Exit(1)

    console.print(f"  [green]Scenario config exists[/green]: {scenario_path}")

    # Try to load it
    try:
        import yaml

        with open(scenario_path) as f:
            config = yaml.safe_load(f)

        # Check required fields
        required_fields = ["simulation", "agents"]
        missing = [f for f in required_fields if f not in config]
        if missing:
            console.print(f"  [red]Missing required fields: {missing}[/red]")
            raise typer.Exit(1)

        console.print("  [green]Config structure valid[/green]")

        # Check agents
        agents = config.get("agents", [])
        agent_ids = [a.get("id", "?") for a in agents]
        console.print(f"  [green]Agents found[/green]: {', '.join(agent_ids)}")

        # Verify optimized agents exist
        missing_agents = [a for a in exp.optimized_agents if a not in agent_ids]
        if missing_agents:
            msg = f"Optimized agents not in config: {missing_agents}"
            console.print(f"  [yellow]Warning: {msg}[/yellow]")
        else:
            console.print("  [green]All optimized agents present[/green]")

    except Exception as e:
        console.print(f"  [red]Failed to parse config: {e}[/red]")
        raise typer.Exit(1) from e

    console.print("\n[green]Validation passed![/green]")


if __name__ == "__main__":
    app()
