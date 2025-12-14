"""Generic experiment CLI commands.

Provides replay, results, run, list, info, and validate commands that work
with any experiment type via the StateProvider pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from payment_simulator.experiments.cli.common import build_verbose_config
from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.persistence import ExperimentRepository
from payment_simulator.experiments.runner import (
    display_audit_output,
    display_experiment_output,
)

# Default database path
DEFAULT_DB_PATH = Path("results/experiments.db")

experiment_app = typer.Typer(
    name="experiments",
    help="Generic experiment commands for run, list, info, validate, replay, and results",
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


@experiment_app.command()
def validate(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML config file"),
    ],
) -> None:
    """Validate experiment YAML configuration.

    Checks that the configuration file is valid YAML and contains all
    required fields for running an experiment.

    Examples:
        # Validate a config file
        experiments validate exp1.yaml

        # Validate from experiments directory
        experiments validate experiments/castro/experiments/exp1.yaml
    """
    if not config_path.exists():
        console.print(f"[red]Error: File not found: {config_path}[/red]")
        raise typer.Exit(1)

    try:
        config = ExperimentConfig.from_yaml(config_path)
        console.print(f"[green]Configuration valid: {config.name}[/green]")

        # Show summary
        console.print(f"  Evaluation mode: {config.evaluation.mode}")
        console.print(f"  Max iterations: {config.convergence.max_iterations}")
        console.print(f"  Optimized agents: {', '.join(config.optimized_agents)}")

    except yaml.YAMLError as e:
        console.print(f"[red]YAML syntax error: {e}[/red]")
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        console.print(f"[red]File error: {e}[/red]")
        raise typer.Exit(1) from e
    except ValueError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@experiment_app.command()
def info(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML config file"),
    ],
) -> None:
    """Show detailed experiment information.

    Displays all configuration details for an experiment including
    evaluation settings, convergence criteria, LLM configuration,
    and optimized agents.

    Examples:
        # Show info for an experiment
        experiments info exp1.yaml

        # Show info from experiments directory
        experiments info experiments/castro/experiments/exp1.yaml
    """
    if not config_path.exists():
        console.print(f"[red]Error: File not found: {config_path}[/red]")
        raise typer.Exit(1)

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1) from e

    # Name and description
    console.print(f"[bold cyan]Experiment: {config.name}[/bold cyan]")
    if config.description:
        console.print(f"Description: {config.description}")
    console.print()

    # Scenario
    console.print("[bold]Scenario:[/bold]")
    console.print(f"  Path: {config.scenario_path}")
    console.print()

    # Evaluation settings
    console.print("[bold]Evaluation:[/bold]")
    console.print(f"  Mode: {config.evaluation.mode}")
    console.print(f"  Ticks: {config.evaluation.ticks}")
    if config.evaluation.mode == "bootstrap" and config.evaluation.num_samples:
        console.print(f"  Samples: {config.evaluation.num_samples}")
    console.print()

    # Convergence settings
    console.print("[bold]Convergence:[/bold]")
    console.print(f"  Max iterations: {config.convergence.max_iterations}")
    console.print(f"  Stability threshold: {config.convergence.stability_threshold}")
    console.print(f"  Stability window: {config.convergence.stability_window}")
    console.print(f"  Improvement threshold: {config.convergence.improvement_threshold}")
    console.print()

    # LLM settings
    console.print("[bold]LLM:[/bold]")
    console.print(f"  Model: {config.llm.model}")
    console.print(f"  Temperature: {config.llm.temperature}")
    if config.llm.system_prompt:
        prompt_preview = config.llm.system_prompt[:100]
        if len(config.llm.system_prompt) > 100:
            prompt_preview += "..."
        console.print(f"  System prompt: {len(config.llm.system_prompt)} chars")
        console.print(f"    Preview: {prompt_preview!r}")
    console.print()

    # Agents
    console.print("[bold]Optimized Agents:[/bold]")
    for agent in config.optimized_agents:
        console.print(f"  - {agent}")
    console.print()

    # Output settings
    console.print("[bold]Output:[/bold]")
    if config.output:
        console.print(f"  Directory: {config.output.directory}")
        console.print(f"  Database: {config.output.database}")
    else:
        console.print("  Directory: (not configured)")
        console.print("  Database: (not configured)")
    console.print(f"  Master seed: {config.master_seed}")


@experiment_app.command("list")
def list_experiments(
    directory: Annotated[
        Path,
        typer.Argument(help="Directory containing experiment YAML files"),
    ] = Path("."),
) -> None:
    """List available experiments in directory.

    Scans the specified directory for YAML files and displays
    experiment names, descriptions, and key configuration details.

    Examples:
        # List experiments in current directory
        experiments list

        # List experiments in specific directory
        experiments list experiments/castro/experiments/
    """
    if not directory.exists():
        console.print(f"[red]Error: Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    if not directory.is_dir():
        console.print(f"[red]Error: Not a directory: {directory}[/red]")
        raise typer.Exit(1)

    # Scan for YAML files
    yaml_files = sorted(
        list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    )

    if not yaml_files:
        console.print(f"[yellow]No experiment YAML files found in {directory}[/yellow]")
        return

    # Create table
    table = Table(title=f"Experiments in {directory}")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Mode")
    table.add_column("Agents")
    table.add_column("File", style="dim")

    valid_count = 0
    for yaml_file in yaml_files:
        try:
            config = ExperimentConfig.from_yaml(yaml_file)
            # Truncate description if too long
            desc = config.description
            if len(desc) > 40:
                desc = desc[:37] + "..."

            agents = ", ".join(config.optimized_agents)
            if len(agents) > 30:
                agents = agents[:27] + "..."

            table.add_row(
                config.name,
                desc,
                config.evaluation.mode,
                agents,
                yaml_file.name,
            )
            valid_count += 1
        except Exception as e:
            console.print(f"[yellow]Warning: Skipping {yaml_file.name}: {e}[/yellow]")

    if valid_count > 0:
        console.print(table)
        console.print(f"\n[dim]Found {valid_count} valid experiment(s)[/dim]")
    else:
        console.print("[yellow]No valid experiment configurations found[/yellow]")


@experiment_app.command()
def template(
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (stdout if not specified)",
        ),
    ] = None,
) -> None:
    """Generate an experiment configuration template.

    Creates a YAML template with sensible defaults and all required fields.
    You can modify this template to create your own experiments.

    Examples:
        # Print template to stdout
        payment-sim experiment template

        # Save template to file
        payment-sim experiment template -o my_experiment.yaml
    """
    template_config = {
        "name": "my_experiment",
        "description": "Description of your experiment",
        "scenario": "configs/scenario.yaml",
        "evaluation": {
            "mode": "bootstrap",
            "num_samples": 10,
            "ticks": 12,
        },
        "convergence": {
            "max_iterations": 50,
            "stability_threshold": 0.05,
            "stability_window": 5,
            "improvement_threshold": 0.01,
        },
        "llm": {
            "model": "anthropic:claude-sonnet-4-5",
            "temperature": 0.0,
            "max_retries": 3,
            "timeout_seconds": 120,
        },
        "optimized_agents": ["BANK_A"],
        "constraints": "your_module.constraints.YOUR_CONSTRAINTS",
        "output": {
            "directory": "results",
            "database": "experiments.db",
            "verbose": True,
        },
        "master_seed": 42,
    }

    yaml_content = yaml.dump(template_config, default_flow_style=False, sort_keys=False)

    if output:
        output.write_text(yaml_content)
        console.print(f"[green]Template written to {output}[/green]")
    else:
        console.print(yaml_content)


@experiment_app.command()
def run(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML config file"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate config without executing"),
    ] = False,
    seed: Annotated[
        int | None,
        typer.Option("--seed", "-s", help="Override master seed from config"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Override LLM model (e.g., 'openai:gpt-4o', 'anthropic:claude-sonnet-4-5')"),
    ] = None,
    reasoning_effort: Annotated[
        str | None,
        typer.Option("--reasoning-effort", help="OpenAI reasoning effort level (low/medium/high)"),
    ] = None,
    thinking_budget: Annotated[
        int | None,
        typer.Option("--thinking-budget", help="Anthropic extended thinking budget tokens"),
    ] = None,
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file for persistence"),
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
    persist_bootstrap: Annotated[
        bool,
        typer.Option("--persist-bootstrap", help="Persist bootstrap sample simulations to database for replay"),
    ] = False,
) -> None:
    """Run experiment from YAML configuration.

    Loads the experiment configuration, creates a runner, and executes
    the optimization loop. Results are persisted to the database.

    Use --dry-run to validate the configuration without executing.

    Examples:
        # Run an experiment
        experiments run exp1.yaml

        # Dry run (validate only)
        experiments run exp1.yaml --dry-run

        # Run with seed override
        experiments run exp1.yaml --seed 12345

        # Run with a different model (overrides YAML config)
        experiments run exp1.yaml --model openai:gpt-4o

        # Run with OpenAI reasoning model with high effort
        experiments run exp1.yaml --model openai:o1 --reasoning-effort high

        # Run with Anthropic extended thinking
        experiments run exp1.yaml --model anthropic:claude-sonnet-4-5 --thinking-budget 16000

        # Run with verbose output
        experiments run exp1.yaml --verbose

        # Run with custom database
        experiments run exp1.yaml --db results/custom.db
    """
    if not config_path.exists():
        console.print(f"[red]Error: File not found: {config_path}[/red]")
        raise typer.Exit(1)

    # Load and validate config
    try:
        config = ExperimentConfig.from_yaml(config_path)
    except yaml.YAMLError as e:
        console.print(f"[red]YAML syntax error: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1) from e

    # Show what we loaded
    console.print(f"[cyan]Loaded experiment: {config.name}[/cyan]")

    # Handle seed override
    if seed is not None:
        config = config.with_seed(seed)
        console.print(f"[cyan]Using seed override: {seed}[/cyan]")

    # Handle LLM overrides
    if model is not None or reasoning_effort is not None or thinking_budget is not None:
        config = config.with_llm_overrides(
            model=model,
            reasoning_effort=reasoning_effort,
            thinking_budget=thinking_budget,
        )
        if model is not None:
            console.print(f"[cyan]Using model override: {model}[/cyan]")
        if reasoning_effort is not None:
            console.print(f"[cyan]Using reasoning effort: {reasoning_effort}[/cyan]")
        if thinking_budget is not None:
            console.print(f"[cyan]Using thinking budget: {thinking_budget}[/cyan]")

    # Dry run mode - just validate
    if dry_run:
        console.print("[green]Configuration valid! (dry run - not executing)[/green]")
        console.print(f"  Model: {config.llm.model}")
        console.print(f"  Evaluation mode: {config.evaluation.mode}")
        console.print(f"  Max iterations: {config.convergence.max_iterations}")
        console.print(f"  Optimized agents: {', '.join(config.optimized_agents)}")
        return

    # Build verbose config
    verbose_config = build_verbose_config(
        verbose=verbose,
        verbose_iterations=verbose_iterations if verbose_iterations else None,
        verbose_bootstrap=verbose_bootstrap if verbose_bootstrap else None,
        verbose_llm=verbose_llm if verbose_llm else None,
        verbose_policy=verbose_policy if verbose_policy else None,
    )

    # Import runner here to avoid circular imports
    from payment_simulator.experiments.runner import GenericExperimentRunner

    # Create and run experiment
    console.print("[cyan]Starting experiment...[/cyan]")

    try:
        import asyncio

        runner = GenericExperimentRunner(
            config=config,
            verbose_config=verbose_config,
            config_dir=config_path.parent,  # Pass config directory for relative path resolution
            persist_bootstrap=persist_bootstrap,
        )

        # Print the experiment run ID for user reference (enables replay later)
        console.print(f"[cyan]Experiment run ID:[/cyan] {runner.run_id}")
        console.print()

        result = asyncio.run(runner.run())

        # Display results
        console.print()
        console.print("[green]Experiment completed![/green]")
        console.print(f"  Iterations: {result.num_iterations}")
        console.print(f"  Converged: {result.converged}")
        if result.convergence_reason:
            console.print(f"  Reason: {result.convergence_reason}")

        # Show costs (in dollars from cents)
        if result.final_costs:
            console.print("  Final costs:")
            for agent_id, cost in result.final_costs.items():
                console.print(f"    {agent_id}: ${cost / 100:.2f}")

    except Exception as e:
        console.print(f"[red]Error running experiment: {e}[/red]")
        raise typer.Exit(1) from e


@experiment_app.command("policy-evolution")
def policy_evolution(
    run_id: Annotated[
        str,
        typer.Argument(help="Experiment run ID (e.g., exp1-20251209-143022-a1b2c3)"),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    llm: Annotated[
        bool,
        typer.Option("--llm", help="Include LLM prompts and responses"),
    ] = False,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Filter by agent ID (e.g., BANK_A)"),
    ] = None,
    start: Annotated[
        int | None,
        typer.Option("--start", help="Start iteration (1-indexed, inclusive)"),
    ] = None,
    end: Annotated[
        int | None,
        typer.Option("--end", help="End iteration (1-indexed, inclusive)"),
    ] = None,
    pretty: Annotated[
        bool,
        typer.Option("--pretty", "-p", help="Pretty-print JSON output"),
    ] = False,
) -> None:
    """Extract policy evolution across experiment iterations.

    Returns JSON showing how policies evolved for each agent across iterations.
    Useful for analyzing optimization trajectories and understanding what the LLM
    changed at each step.

    Output structure:
        {
          "BANK_A": {
            "iteration_1": {
              "policy": {...},
              "diff": "~ threshold: 100 -> 200",
              "cost": 15000,
              "accepted": true,
              "llm": {...}  // only with --llm flag
            },
            ...
          }
        }

    Examples:
        # All agents, all iterations
        experiment policy-evolution exp1-20251209-143022-a1b2c3

        # Filter by agent
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --agent BANK_A

        # Include LLM prompts/responses
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --llm

        # Specific iteration range
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --start 2 --end 5

        # Pretty-print output
        experiment policy-evolution exp1-20251209-143022-a1b2c3 --pretty
    """
    import json

    from payment_simulator.experiments.analysis import (
        PolicyEvolutionService,
        build_evolution_output,
    )

    # Validate iteration range
    if start is not None and start < 1:
        console.print("[red]Error: --start must be >= 1[/red]")
        raise typer.Exit(1)

    if end is not None and end < 1:
        console.print("[red]Error: --end must be >= 1[/red]")
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

    try:
        # Create service and get evolution
        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution(
            run_id=run_id,
            include_llm=llm,
            agent_filter=agent,
            start_iteration=start,
            end_iteration=end,
        )

        # Build output structure
        output = build_evolution_output(evolutions, include_llm=llm)

        # Output as JSON
        indent = 2 if pretty else None
        print(json.dumps(output, indent=indent))

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    finally:
        repo.close()
