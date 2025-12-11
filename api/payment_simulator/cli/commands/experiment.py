"""Experiment CLI commands for running LLM policy optimization experiments.

Commands for validating configs, generating templates, listing experiments,
and running experiment workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from payment_simulator.experiments.config.experiment_config import ExperimentConfig

# Create the experiment typer app
experiment_app = typer.Typer(
    name="experiment",
    help="Experiment Framework - Run LLM policy optimization experiments",
    no_args_is_help=True,
)


def _echo(message: str) -> None:
    """Print message (testable output)."""
    typer.echo(message)


def _echo_error(message: str) -> None:
    """Print error message (testable output)."""
    typer.echo(f"Error: {message}", err=True)


# ==============================================================================
# validate command
# ==============================================================================


@experiment_app.command(name="validate")
def validate_experiment(
    config_path: Annotated[
        Path,
        typer.Argument(
            help="Path to experiment configuration YAML file",
            exists=False,  # We handle existence check ourselves for better error messages
        ),
    ],
) -> None:
    """Validate an experiment configuration file.

    Checks the configuration against the ExperimentConfig schema and reports
    any validation errors.
    """
    # Check file exists
    if not config_path.exists():
        _echo_error(f"Config file not found: {config_path}")
        raise typer.Exit(1)

    # Load YAML
    try:
        with open(config_path) as f:
            yaml.safe_load(f)  # First check YAML is valid
    except yaml.YAMLError as e:
        _echo_error(f"Invalid YAML: {e}")
        raise typer.Exit(1) from None

    # Validate against schema
    try:
        config = ExperimentConfig.from_yaml(config_path)
        _echo("Configuration is valid!")
        _echo(f"Name: {config.name}")
        _echo(f"Description: {config.description}")
        _echo(f"Scenario: {config.scenario_path}")
        _echo(f"Evaluation mode: {config.evaluation.mode}")
        _echo(f"Optimized agents: {list(config.optimized_agents)}")
        _echo(f"Master seed: {config.master_seed}")
    except ValueError as e:
        _echo_error(f"Configuration validation failed: {e}")
        raise typer.Exit(1) from None


# ==============================================================================
# info command
# ==============================================================================


@experiment_app.command(name="info")
def show_experiment_info() -> None:
    """Show information about the Experiment Framework.

    Displays module capabilities, evaluation modes, and available commands.
    """
    _echo("\nExperiment Framework")
    _echo("=" * 40)
    _echo("\nYAML-driven LLM policy optimization experiments.")

    _echo("\nEvaluation Modes:")
    _echo("  • bootstrap - Bootstrap resampling for statistical validation")
    _echo("    Uses paired comparison: same samples, both policies")
    _echo("    Accepts new policy when mean_delta > 0")
    _echo("")
    _echo("  • deterministic - Single deterministic evaluation")
    _echo("    Faster but no statistical confidence")

    _echo("\nKey Features:")
    _echo("  • YAML configuration for experiments")
    _echo("  • Bootstrap paired comparison for policy acceptance")
    _echo("  • Configurable convergence criteria")
    _echo("  • Per-agent LLM configuration")
    _echo("  • Deterministic execution (same seed = same results)")

    _echo("\nCommands:")
    _echo("  experiment validate <config.yaml>  - Validate a config file")
    _echo("  experiment template                - Generate a config template")
    _echo("  experiment list <directory>        - List experiments in directory")
    _echo("  experiment run <config.yaml>       - Run an experiment")
    _echo("  experiment info                    - Show this information")


# ==============================================================================
# template command
# ==============================================================================


@experiment_app.command(name="template")
def generate_experiment_template(
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (stdout if not specified)",
        ),
    ] = None,
) -> None:
    """Generate an experiment configuration template file.

    Creates a YAML configuration template with sensible defaults
    and all required fields.
    """
    template = {
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

    yaml_content = yaml.dump(template, default_flow_style=False, sort_keys=False)

    if output:
        output.write_text(yaml_content)
        _echo(f"Template written to {output}")
    else:
        _echo(yaml_content)


# ==============================================================================
# list command
# ==============================================================================


@experiment_app.command(name="list")
def list_experiments(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Directory containing experiment YAML files",
            exists=False,  # We handle existence check ourselves
        ),
    ],
) -> None:
    """List all experiments in a directory.

    Scans the directory for .yaml files and displays experiment names
    and descriptions.
    """
    if not directory.exists():
        _echo_error(f"Directory not found: {directory}")
        raise typer.Exit(1)

    if not directory.is_dir():
        _echo_error(f"Not a directory: {directory}")
        raise typer.Exit(1)

    # Find all YAML files
    yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

    if not yaml_files:
        _echo(f"No experiment files found in {directory}")
        return

    _echo(f"\nExperiments in {directory}:")
    _echo("-" * 40)

    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if data and isinstance(data, dict) and "name" in data:
                name = data.get("name", yaml_file.stem)
                description = data.get("description", "")
                mode = data.get("evaluation", {}).get("mode", "unknown")
                agents = data.get("optimized_agents", [])

                _echo(f"\n  {yaml_file.name}")
                _echo(f"    Name: {name}")
                if description:
                    _echo(f"    Description: {description}")
                _echo(f"    Mode: {mode}")
                _echo(f"    Agents: {agents}")
        except (yaml.YAMLError, OSError) as e:
            _echo(f"\n  {yaml_file.name} - Error: {e}")

    _echo(f"\nTotal: {len(yaml_files)} experiment(s)")


# ==============================================================================
# run command
# ==============================================================================


@experiment_app.command(name="run")
def run_experiment(
    config_path: Annotated[
        Path,
        typer.Argument(
            help="Path to experiment configuration YAML file",
            exists=False,
        ),
    ],
    seed: Annotated[
        int | None,
        typer.Option(
            "--seed",
            "-s",
            help="Override master seed from config",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Validate config without running experiment",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """Run an experiment from a configuration file.

    Loads the experiment configuration, validates it, and runs the
    optimization loop until convergence or max iterations.
    """
    # Check file exists
    if not config_path.exists():
        _echo_error(f"Config file not found: {config_path}")
        raise typer.Exit(1)

    # Load and validate config
    try:
        config = ExperimentConfig.from_yaml(config_path)
    except (ValueError, yaml.YAMLError) as e:
        _echo_error(f"Invalid configuration: {e}")
        raise typer.Exit(1) from None

    _echo(f"Loaded experiment: {config.name}")
    _echo(f"  Description: {config.description}")
    _echo(f"  Evaluation: {config.evaluation.mode} ({config.evaluation.num_samples} samples)")
    _echo(f"  Agents: {list(config.optimized_agents)}")
    _echo(f"  Max iterations: {config.convergence.max_iterations}")

    if seed is not None:
        _echo(f"  Seed override: {seed}")

    if dry_run:
        _echo("\n[Dry run] Configuration is valid. Skipping execution.")
        return

    # Run the experiment (async wrapper)
    _run_experiment_async(config, seed=seed, verbose=verbose)


def _run_experiment_async(
    config: ExperimentConfig,
    *,
    seed: int | None = None,
    verbose: bool = False,
) -> None:
    """Run experiment asynchronously using GenericExperimentRunner.

    Args:
        config: Experiment configuration.
        seed: Optional seed override.
        verbose: Enable verbose output.
    """
    import asyncio

    from payment_simulator.experiments.runner import GenericExperimentRunner
    from payment_simulator.experiments.runner.verbose import VerboseConfig

    # Apply seed override if provided
    if seed is not None:
        config = config.with_seed(seed)

    # Build verbose config
    verbose_config = VerboseConfig(
        iterations=verbose,
        bootstrap=verbose,
        llm=verbose,
        policy=verbose,
        rejections=verbose,
    )

    # Create and run the experiment
    runner = GenericExperimentRunner(
        config=config,
        verbose_config=verbose_config,
    )

    try:
        result = asyncio.run(runner.run())

        _echo(f"\nExperiment completed!")
        _echo(f"  Iterations: {result.num_iterations}")
        _echo(f"  Converged: {result.converged}")
        if result.convergence_reason:
            _echo(f"  Reason: {result.convergence_reason}")

        if result.final_costs:
            _echo("  Final costs:")
            for agent_id, cost in result.final_costs.items():
                _echo(f"    {agent_id}: ${cost / 100:.2f}")
    except Exception as e:
        _echo_error(f"Experiment failed: {e}")
        raise typer.Exit(1) from None
