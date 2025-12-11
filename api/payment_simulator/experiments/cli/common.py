"""Common utilities for experiment CLI commands.

Provides shared helpers for building verbose configurations and
other common operations across CLI commands.
"""

from __future__ import annotations

from payment_simulator.experiments.runner import VerboseConfig


def build_verbose_config(
    verbose: bool = False,
    verbose_iterations: bool | None = None,
    verbose_policy: bool | None = None,
    verbose_bootstrap: bool | None = None,
    verbose_llm: bool | None = None,
    verbose_rejections: bool | None = None,
    debug: bool = False,
) -> VerboseConfig:
    """Build VerboseConfig from CLI flag values.

    Args:
        verbose: Master flag that enables all main verbose outputs
        verbose_iterations: Show iteration start messages
        verbose_policy: Show policy parameter changes
        verbose_bootstrap: Show per-sample bootstrap results
        verbose_llm: Show LLM call metadata
        verbose_rejections: Show rejection analysis
        debug: Show debug output (validation errors, LLM retries)

    Returns:
        VerboseConfig with appropriate flags set

    Examples:
        >>> config = build_verbose_config(verbose=True)
        >>> config.iterations
        True
        >>> config = build_verbose_config(verbose_policy=True)
        >>> config.policy
        True
        >>> config.iterations
        False
    """
    return VerboseConfig.from_cli_flags(
        verbose=verbose,
        verbose_iterations=verbose_iterations,
        verbose_policy=verbose_policy,
        verbose_bootstrap=verbose_bootstrap,
        verbose_llm=verbose_llm,
        verbose_rejections=verbose_rejections,
        debug=debug,
    )
