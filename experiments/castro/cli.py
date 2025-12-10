"""CLI for Castro experiments.

Run Castro experiments using the ai_cash_mgmt module.

Uses PydanticAI for unified LLM support with provider:model string format.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from castro.experiments import DEFAULT_MODEL, EXPERIMENTS
from castro.runner import ExperimentRunner

# Load environment variables from .env file (if present)
# This must happen before any LLM client initialization
load_dotenv()

app = typer.Typer(
    name="castro",
    help="Castro experiments using ai_cash_mgmt with PydanticAI",
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
        typer.Option(
            "--model",
            "-m",
            help="LLM model in provider:model format (e.g., anthropic:claude-sonnet-4-5)",
        ),
    ] = DEFAULT_MODEL,
    thinking_budget: Annotated[
        int | None,
        typer.Option(
            "--thinking-budget",
            "-t",
            help="Token budget for Anthropic extended thinking (Claude only)",
        ),
    ] = None,
    reasoning_effort: Annotated[
        str | None,
        typer.Option(
            "--reasoning-effort",
            "-r",
            help="OpenAI reasoning effort: low, medium, or high (GPT models only)",
        ),
    ] = None,
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
    verbose_bootstrap: Annotated[
        bool,
        typer.Option("--verbose-bootstrap", help="Show per-sample bootstrap results"),
    ] = False,
    verbose_llm: Annotated[
        bool,
        typer.Option("--verbose-llm", help="Show LLM call metadata"),
    ] = False,
    verbose_rejections: Annotated[
        bool,
        typer.Option("--verbose-rejections", help="Show rejection analysis"),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Show debug output (validation errors, LLM retries)"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress verbose output"),
    ] = False,
) -> None:
    """Run a Castro experiment.

    Model format: provider:model-name

    Supported providers:
        - anthropic: Claude models (claude-sonnet-4-5, etc.)
        - openai: GPT models (gpt-5.1, gpt-4.1, o1, o3, etc.)
        - google: Gemini models (gemini-2.5-flash, etc.)

    Examples:
        # Default (Anthropic Claude)
        castro run exp1

        # OpenAI with high reasoning effort
        castro run exp1 --model openai:gpt-5.1 --reasoning-effort high

        # Anthropic with extended thinking
        castro run exp1 --model anthropic:claude-sonnet-4-5 --thinking-budget 8000

        # Google Gemini
        castro run exp1 --model google:gemini-2.5-flash

        # All verbose output
        castro run exp1 --verbose

        # Specific verbose modes
        castro run exp1 --verbose-policy --verbose-bootstrap
    """
    from castro.verbose_logging import VerboseConfig

    # Validate reasoning_effort if provided
    if reasoning_effort and reasoning_effort not in ("low", "medium", "high"):
        console.print(
            f"[red]Invalid reasoning effort: {reasoning_effort}. "
            "Must be low, medium, or high.[/red]"
        )
        raise typer.Exit(1)

    # Build verbose configuration
    if quiet:
        verbose_config = VerboseConfig()  # All disabled
    else:
        verbose_config = VerboseConfig.from_flags(
            verbose=verbose,
            verbose_policy=verbose_policy if verbose_policy else None,
            verbose_bootstrap=verbose_bootstrap if verbose_bootstrap else None,
            verbose_llm=verbose_llm if verbose_llm else None,
            verbose_rejections=verbose_rejections if verbose_rejections else None,
            debug=debug,
        )

    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        console.print(f"Available: {', '.join(EXPERIMENTS.keys())}")
        raise typer.Exit(1)

    # Create experiment configuration with new model format
    output_dir = output or Path("results")
    exp = EXPERIMENTS[experiment](
        output_dir=output_dir,
        model=model,
        thinking_budget=thinking_budget,
        reasoning_effort=reasoning_effort,
    )

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

    table.add_row("Run ID", result.run_id)
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
    table.add_row("[bold]Bootstrap Evaluation[/bold]", "")
    table.add_row("  Deterministic", "Yes" if exp.deterministic else "No")
    table.add_row("  Samples", str(exp.num_samples))
    table.add_row("  Evaluation Ticks", str(exp.evaluation_ticks))
    table.add_row("", "")
    table.add_row("[bold]Convergence[/bold]", "")
    table.add_row("  Max Iterations", str(exp.max_iterations))
    table.add_row("  Stability Threshold", f"{exp.stability_threshold:.1%}")
    table.add_row("  Stability Window", str(exp.stability_window))
    table.add_row("", "")
    table.add_row("[bold]LLM[/bold]", "")
    model_config = exp.get_model_config()
    table.add_row("  Model", model_config.model)
    table.add_row("  Provider", model_config.provider)
    table.add_row("  Temperature", str(model_config.temperature))
    if model_config.thinking_budget:
        table.add_row("  Thinking Budget", str(model_config.thinking_budget))
    if model_config.reasoning_effort:
        table.add_row("  Reasoning Effort", model_config.reasoning_effort)
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


# Default database path for results storage
DEFAULT_DB_PATH = Path("results/castro.db")


@app.command()
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
        castro replay exp1-20251209-143022-a1b2c3

        # Replay with verbose output
        castro replay exp1-20251209-143022-a1b2c3 --verbose

        # Replay from a specific database
        castro replay exp1-20251209-143022-a1b2c3 --db results/custom.db

        # Show audit trail for iterations 2-3
        castro replay exp1-20251209-143022-a1b2c3 --audit --start 2 --end 3
    """
    import duckdb

    from castro.display import VerboseConfig, display_experiment_output
    from castro.state_provider import DatabaseExperimentProvider

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

    # Connect to database
    try:
        conn = duckdb.connect(str(db), read_only=True)
    except Exception as e:
        console.print(f"[red]Failed to open database: {e}[/red]")
        raise typer.Exit(1) from e

    # Create provider
    provider = DatabaseExperimentProvider(conn=conn, run_id=run_id)

    # Check run exists
    metadata = provider.get_run_metadata()
    if metadata is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        conn.close()
        raise typer.Exit(1)

    # Handle audit mode
    if audit:
        from castro.audit_display import display_audit_output

        display_audit_output(
            provider=provider,
            console=console,
            start_iteration=start,
            end_iteration=end,
        )
    else:
        # Standard replay mode
        # Build verbose config
        verbose_config = VerboseConfig.from_flags(
            verbose=verbose,
            verbose_iterations=verbose_iterations,
            verbose_bootstrap=verbose_bootstrap,
            verbose_llm=verbose_llm,
            verbose_policy=verbose_policy,
        )

        # Display output using unified function
        display_experiment_output(provider, console, verbose_config)

    conn.close()


@app.command()
def results(
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    experiment: Annotated[
        str | None,
        typer.Option("--experiment", "-e", help="Filter by experiment name"),
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
        castro results

        # Filter by experiment
        castro results --experiment exp1

        # Use a specific database
        castro results --db results/custom.db
    """
    import duckdb

    from castro.persistence import ExperimentEventRepository

    # Check database exists
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        raise typer.Exit(1)

    # Connect to database
    try:
        conn = duckdb.connect(str(db), read_only=True)
    except Exception as e:
        console.print(f"[red]Failed to open database: {e}[/red]")
        raise typer.Exit(1) from e

    # Get runs
    repo = ExperimentEventRepository(conn)
    runs = repo.list_runs(experiment_filter=experiment, limit=limit)

    conn.close()

    if not runs:
        if experiment:
            console.print(f"[yellow]No runs found for experiment: {experiment}[/yellow]")
        else:
            console.print("[yellow]No experiment runs found in database.[/yellow]")
        return

    # Create results table
    table = Table(title="Experiment Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Experiment", style="green")
    table.add_column("Status")
    table.add_column("Final Cost", justify="right")
    table.add_column("Best Cost", justify="right")
    table.add_column("Iterations", justify="right")
    table.add_column("Converged")
    table.add_column("Model")
    table.add_column("Started", style="dim")

    for run in runs:
        # Format costs
        final_cost = f"${run.final_cost / 100:.2f}" if run.final_cost else "-"
        best_cost = f"${run.best_cost / 100:.2f}" if run.best_cost else "-"
        iterations = str(run.num_iterations) if run.num_iterations else "-"
        converged = "Yes" if run.converged else "No" if run.converged is False else "-"

        # Format status with color
        status = run.status
        if status == "completed":
            status = "[green]completed[/green]"
        elif status == "running":
            status = "[yellow]running[/yellow]"
        elif status == "failed":
            status = "[red]failed[/red]"

        # Format date
        started = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "-"

        # Format model (truncate if long)
        model = run.model or "-"
        if len(model) > 25:
            model = model[:22] + "..."

        table.add_row(
            run.run_id,
            run.experiment_name,
            status,
            final_cost,
            best_cost,
            iterations,
            converged,
            model,
            started,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(runs)} run(s)[/dim]")


if __name__ == "__main__":
    app()
