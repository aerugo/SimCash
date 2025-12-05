#!/usr/bin/env python3
"""CLI for Castro experiments.

A modern Typer-based CLI for running Castro et al. replication experiments.

Usage:
    # Run an experiment
    python cli.py run exp1

    # Run with specific model and extended thinking
    python cli.py run exp2 --model anthropic:claude-sonnet-4-5-20250929 --thinking-budget 32000

    # List available experiments
    python cli.py list

    # Generate charts from existing database
    python cli.py charts results/exp1/experiment.db
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from experiments.castro.castro.experiment.definitions import EXPERIMENTS, get_experiment_summary
from experiments.castro.castro.visualization import generate_all_charts

# Create the CLI app
app = typer.Typer(
    name="castro",
    help="Castro et al. replication experiments for payment system optimization",
    add_completion=False,
    rich_markup_mode="rich",
)


# ============================================================================
# Type Definitions for CLI Arguments
# ============================================================================


ExperimentArg = Annotated[
    str,
    typer.Argument(
        help="Experiment key to run (e.g., exp1, exp2, exp3)",
    ),
]

OutputOption = Annotated[
    str,
    typer.Option(
        "--output", "-o",
        help="Output database filename (will be created in results/{experiment_id}/)",
    ),
]

ModelOption = Annotated[
    str,
    typer.Option(
        "--model", "-m",
        help="LLM model to use (e.g., gpt-4o, anthropic:claude-sonnet-4-5-20250929)",
    ),
]

ReasoningOption = Annotated[
    str,
    typer.Option(
        "--reasoning",
        help="Reasoning effort level (none, low, medium, high)",
    ),
]

ThinkingBudgetOption = Annotated[
    int | None,
    typer.Option(
        "--thinking-budget",
        help="Token budget for Anthropic Claude extended thinking (min 1024, recommended 10000-32000)",
    ),
]

MaxIterOption = Annotated[
    int | None,
    typer.Option(
        "--max-iter",
        help="Override maximum iterations",
    ),
]

MasterSeedOption = Annotated[
    int | None,
    typer.Option(
        "--master-seed",
        help="Master seed for reproducibility (pre-generates all iteration seeds)",
    ),
]

SimcashRootOption = Annotated[
    Path | None,
    typer.Option(
        "--simcash-root",
        help="SimCash root directory (default: auto-detected)",
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose", "-v",
        help="Enable verbose output with detailed progress and validation errors",
    ),
]

DbPathArg = Annotated[
    Path,
    typer.Argument(
        help="Path to experiment database file",
        exists=True,
    ),
]

ChartOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output", "-o",
        help="Output directory for charts (default: same as database directory)",
    ),
]


# ============================================================================
# Commands
# ============================================================================


@app.command()
def run(
    experiment: ExperimentArg,
    output: OutputOption = "experiment.db",
    model: ModelOption = "gpt-4o",
    reasoning: ReasoningOption = "high",
    thinking_budget: ThinkingBudgetOption = None,
    max_iter: MaxIterOption = None,
    master_seed: MasterSeedOption = None,
    simcash_root: SimcashRootOption = None,
    verbose: VerboseOption = False,
) -> None:
    """Run a Castro replication experiment.

    Examples:
        # Run Experiment 1 (Two-Period, Castro-Aligned)
        python cli.py run exp1

        # Run with Claude and extended thinking
        python cli.py run exp2 --model anthropic:claude-sonnet-4-5-20250929 --thinking-budget 32000

        # Run with specific master seed for reproducibility
        python cli.py run exp1 --master-seed 42
    """
    # Validate experiment key
    if experiment not in EXPERIMENTS:
        available = ", ".join(sorted(EXPERIMENTS.keys()))
        typer.echo(f"Error: Unknown experiment '{experiment}'. Available: {available}", err=True)
        raise typer.Exit(1)

    # Validate reasoning choice
    valid_reasoning = {"none", "low", "medium", "high"}
    if reasoning not in valid_reasoning:
        typer.echo(f"Error: Invalid reasoning level '{reasoning}'. Use: {valid_reasoning}", err=True)
        raise typer.Exit(1)

    # Validate thinking_budget with model
    if thinking_budget is not None and not model.startswith("anthropic:"):
        typer.echo(
            f"Warning: --thinking-budget is only supported for Anthropic models (anthropic:*). "
            f"Current model: {model}"
        )
        typer.echo("Ignoring --thinking-budget.")
        thinking_budget = None

    # Override max_iter if specified
    if max_iter is not None:
        EXPERIMENTS[experiment]["max_iterations"] = max_iter

    # Determine SimCash root
    if simcash_root is None:
        # Default: 4 levels up from this file
        simcash_root = Path(__file__).parent.parent.parent

    # Import here to avoid circular imports and slow startup
    from experiments.castro.castro.experiment.runner import ReproducibleExperiment

    typer.echo(f"\n[bold]Starting {EXPERIMENTS[experiment]['name']}[/bold]\n")

    # Run experiment
    exp = ReproducibleExperiment(
        experiment_key=experiment,
        db_path=output,
        simcash_root=str(simcash_root),
        model=model,
        reasoning_effort=reasoning,
        master_seed=master_seed,
        verbose=verbose,
        thinking_budget=thinking_budget,
    )

    exp.run()


@app.command("list")
def list_experiments() -> None:
    """List available experiments."""
    typer.echo("\n[bold]Available Experiments[/bold]")
    typer.echo("=" * 60)

    for key, exp in sorted(EXPERIMENTS.items()):
        typer.echo(f"\n[cyan]{key}[/cyan]:")
        typer.echo(f"  Name: {exp['name']}")
        typer.echo(f"  Description: {exp.get('description', 'N/A')}")
        typer.echo(f"  Config: {exp['config_path']}")
        typer.echo(f"  Seeds: {exp['num_seeds']}")
        typer.echo(f"  Max iterations: {exp['max_iterations']}")
        castro_mode = exp.get("castro_mode", False)
        typer.echo(f"  Castro mode: {'Yes' if castro_mode else 'No'}")


@app.command()
def charts(
    db_path: DbPathArg,
    output: ChartOutputOption = None,
) -> None:
    """Generate charts from an existing experiment database.

    Examples:
        # Generate charts in same directory as database
        python cli.py charts results/exp1_2024-01-01/experiment.db

        # Generate charts to specific directory
        python cli.py charts results/exp1/experiment.db --output ./charts
    """
    generate_all_charts(str(db_path), output_dir=output)


@app.command()
def summary(
    db_path: DbPathArg,
) -> None:
    """Show summary of an existing experiment database.

    Displays:
    - Experiment configuration
    - Iteration metrics
    - Best policy found
    - Validation error summary
    """
    from experiments.castro.castro.db.repository import ExperimentRepository

    repo = ExperimentRepository(str(db_path))

    try:
        summary_data = repo.export_summary()
        typer.echo("\n[bold]Experiment Summary[/bold]")
        typer.echo("=" * 60)

        for exp in summary_data.get("experiments", []):
            typer.echo(f"\nExperiment: {exp['experiment_name']}")
            typer.echo(f"  ID: {exp['experiment_id']}")
            typer.echo(f"  Created: {exp['created_at']}")
            typer.echo(f"  Model: {exp['model_name']}")
            typer.echo(f"  Seeds: {exp['num_seeds']}")
            typer.echo(f"  Iterations: {len(exp['iterations'])}")

            if exp["iterations"]:
                last = exp["iterations"][-1]
                typer.echo(f"\n  Final Iteration ({last['iteration']}):")
                typer.echo(f"    Mean Cost: ${last['mean_cost']:,.0f}")
                typer.echo(f"    Settlement Rate: {last['settlement_rate']*100:.1f}%")
                typer.echo(f"    Converged: {'Yes' if last['converged'] else 'No'}")

        # Validation error summary
        error_summary = repo.get_validation_error_summary()
        if error_summary["total_errors"] > 0:
            typer.echo("\n[yellow]Validation Errors[/yellow]")
            typer.echo(f"  Total: {error_summary['total_errors']}")
            typer.echo(f"  Fixed: {error_summary['fixed_count']} ({error_summary['fix_rate']:.1f}%)")
            typer.echo(f"  Avg fix attempts: {error_summary['avg_fix_attempts']:.1f}")

            if error_summary["by_category"]:
                typer.echo("  By category:")
                for cat, count in sorted(error_summary["by_category"].items()):
                    typer.echo(f"    {cat}: {count}")

    finally:
        repo.close()


# ============================================================================
# Entry Point
# ============================================================================


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
