"""AI Game CLI commands for AI Cash Management module.

Commands for validating configs, generating templates, and viewing
schema information for the AI Cash Management system.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
import yaml

if TYPE_CHECKING:
    from pydantic import BaseModel


# Create the ai-game typer app
ai_game_app = typer.Typer(
    name="ai-game",
    help="AI Cash Management - LLM-based policy optimization commands",
    no_args_is_help=True,
)


def _echo(message: str) -> None:
    """Print message (testable output)."""
    typer.echo(message)


def _echo_error(message: str) -> None:
    """Print error message (testable output)."""
    typer.echo(f"Error: {message}", err=True)


@ai_game_app.command(name="validate")
def validate_config(
    config_path: Annotated[
        Path,
        typer.Argument(
            help="Path to game configuration YAML file",
            exists=False,  # We handle existence check ourselves for better error messages
        ),
    ],
) -> None:
    """Validate a game configuration file.

    Checks the configuration against the GameConfig schema and reports
    any validation errors.
    """
    from pydantic import ValidationError

    from payment_simulator.ai_cash_mgmt.config.game_config import GameConfig

    # Check file exists
    if not config_path.exists():
        _echo_error(f"Config file not found: {config_path}")
        raise typer.Exit(1)

    # Load YAML
    try:
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        _echo_error(f"Invalid YAML: {e}")
        raise typer.Exit(1) from None

    # Validate against schema
    try:
        config = GameConfig.model_validate(config_data)
        _echo("Configuration is valid!")
        _echo(f"Game ID: {config.game_id}")
        _echo(f"Master seed: {config.master_seed}")
        _echo(f"Optimized agents: {list(config.optimized_agents.keys())}")
    except ValidationError as e:
        _echo_error("Configuration validation failed:")
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            _echo(f"  • {loc}: {msg}")
        raise typer.Exit(1) from None


@ai_game_app.command(name="info")
def show_info() -> None:
    """Show information about the AI Cash Management module.

    Displays module capabilities, available game modes, and configuration options.
    """
    from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

    _echo("\nAI Cash Management Module")
    _echo("=" * 40)
    _echo("\nLLM-based policy optimization for payment settlement simulation.")

    _echo("\nAvailable Game Modes:")
    for mode in GameMode:
        _echo(f"  • {mode.value}")
        _echo(f"    {mode.description}\n")

    _echo("Key Features:")
    _echo("  • Monte Carlo evaluation of policies")
    _echo("  • Per-agent LLM configuration (different banks, different models)")
    _echo("  • Deterministic execution (same seed = same results)")
    _echo("  • Convergence detection with configurable thresholds")
    _echo("  • Transaction sampling from historical data")

    _echo("\nCommands:")
    _echo("  ai-game validate <config.yaml>  - Validate a config file")
    _echo("  ai-game config-template         - Generate a config template")
    _echo("  ai-game schema <type>           - Show JSON schema")


@ai_game_app.command(name="config-template")
def generate_config_template(
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (stdout if not specified)",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "-m",
            "--mode",
            help="Game mode (rl_optimization or campaign_learning)",
        ),
    ] = "rl_optimization",
) -> None:
    """Generate a configuration template file.

    Creates a YAML configuration template with sensible defaults
    and documentation comments.
    """
    template = {
        "game_id": "my_optimization_game",
        "scenario_config": "path/to/scenario.yaml",
        "master_seed": 42,
        "optimized_agents": {
            "BANK_A": {
                "llm_config": None,  # Uses default_llm_config
            },
            "BANK_B": {
                "llm_config": {
                    "provider": "anthropic",
                    "model": "claude-3-opus",
                    "reasoning_effort": "high",
                },
            },
        },
        "default_llm_config": {
            "provider": "openai",
            "model": "gpt-5.1",
            "reasoning_effort": "high",
            "temperature": 0.0,
            "max_retries": 3,
            "timeout_seconds": 120,
        },
        "optimization_schedule": {
            "type": "every_x_ticks" if mode == "rl_optimization" else "on_simulation_end",
            "interval_ticks": 50 if mode == "rl_optimization" else None,
        },
        "monte_carlo": {
            "num_samples": 20,
            "sample_method": "bootstrap",
            "evaluation_ticks": 100,
            "parallel_workers": 4,
        },
        "convergence": {
            "stability_threshold": 0.05,
            "stability_window": 3,
            "max_iterations": 50,
            "improvement_threshold": 0.01,
        },
    }

    yaml_content = yaml.dump(template, default_flow_style=False, sort_keys=False)

    if output:
        output.write_text(yaml_content)
        _echo(f"Template written to {output}")
    else:
        _echo(yaml_content)


@ai_game_app.command(name="schema")
def show_schema(
    schema_type: Annotated[
        str,
        typer.Argument(
            help="Schema type: game-config, llm-config, monte-carlo, convergence",
        ),
    ],
) -> None:
    """Output JSON schema for a configuration type.

    Useful for editor autocompletion and documentation generation.
    """
    from payment_simulator.ai_cash_mgmt.config.game_config import (
        BootstrapConfig,
        ConvergenceCriteria,
        GameConfig,
    )
    from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

    schemas: dict[str, type[BaseModel]] = {
        "game-config": GameConfig,
        "llm-config": LLMConfig,
        "bootstrap": BootstrapConfig,
        "convergence": ConvergenceCriteria,
    }

    if schema_type not in schemas:
        _echo_error(f"Unknown schema type: {schema_type}")
        _echo(f"Available types: {', '.join(schemas.keys())}")
        raise typer.Exit(1)

    model_class = schemas[schema_type]
    schema = model_class.model_json_schema()
    _echo(json.dumps(schema, indent=2))
