"""Generic experiment CLI module.

Provides reusable CLI commands for experiment replay and results listing
that work with any experiment type via the StateProvider pattern.

Components:
    - experiment_app: Typer app with replay and results commands
    - build_verbose_config: Helper for building VerboseConfig from CLI flags

Example:
    >>> from payment_simulator.experiments.cli import experiment_app
    >>> # Add as subcommand to main CLI:
    >>> main_app.add_typer(experiment_app, name="experiments")
"""

from payment_simulator.experiments.cli.commands import experiment_app
from payment_simulator.experiments.cli.common import build_verbose_config

__all__ = [
    "experiment_app",
    "build_verbose_config",
]
