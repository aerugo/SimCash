"""Generic experiment runner.

Provides a complete experiment runner that works with any YAML configuration.
This eliminates the need for experiment-specific Python code.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints

from payment_simulator.experiments.runner.result import (
    ExperimentResult,
    ExperimentState,
)
from payment_simulator.experiments.runner.verbose import VerboseConfig


def _generate_run_id(experiment_name: str) -> str:
    """Generate a unique run ID.

    Format: {experiment_name}-{timestamp}-{random_suffix}

    Args:
        experiment_name: Name of the experiment.

    Returns:
        Unique run ID string.
    """
    import secrets

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{experiment_name}-{timestamp}-{suffix}"


class GenericExperimentRunner:
    """Generic experiment runner that works with any YAML config.

    Implements ExperimentRunnerProtocol for running policy optimization
    experiments. All configuration is read from ExperimentConfig - no
    experiment-specific code is needed.

    Features:
    - Uses system_prompt from config.llm.system_prompt
    - Uses constraints from config.get_constraints()
    - Uses convergence from config.convergence
    - Generates unique run_id for each run
    - Supports verbose logging via VerboseConfig

    Example:
        >>> from payment_simulator.experiments.config import ExperimentConfig
        >>> config = ExperimentConfig.from_yaml(Path("exp1.yaml"))
        >>> runner = GenericExperimentRunner(config)
        >>> result = await runner.run()
        >>> print(f"Converged: {result.converged}")

        >>> # With verbose logging
        >>> verbose_config = VerboseConfig.all_enabled()
        >>> runner = GenericExperimentRunner(config, verbose_config=verbose_config)

        >>> # With custom run ID
        >>> runner = GenericExperimentRunner(config, run_id="my-custom-id")

    Attributes:
        run_id: Unique identifier for this run.
        experiment_name: Name from config.
        scenario_path: Path to scenario YAML.
        system_prompt: System prompt for LLM (from config).
        constraints: Policy constraints (from config).
    """

    def __init__(
        self,
        config: ExperimentConfig,
        verbose_config: VerboseConfig | None = None,
        run_id: str | None = None,
        config_dir: Path | None = None,
    ) -> None:
        """Initialize the experiment runner.

        Args:
            config: ExperimentConfig with all settings.
            verbose_config: Optional verbose logging configuration.
            run_id: Optional run ID. If not provided, one is generated.
            config_dir: Directory containing the experiment config (for resolving
                        relative scenario paths). If None, uses current directory.
        """
        self._config = config
        self._verbose_config = verbose_config or VerboseConfig()
        self._run_id = run_id or _generate_run_id(config.name)
        self._config_dir = config_dir or Path.cwd()

        # Get constraints from config (inline or module)
        self._constraints: ScenarioConstraints | None = config.get_constraints()

        # Initialize state
        self._state = ExperimentState(experiment_name=config.name)
        self._current_iteration = 0
        self._policies: dict[str, dict[str, Any]] = {}

    @property
    def run_id(self) -> str:
        """Get the unique run ID."""
        return self._run_id

    @property
    def experiment_name(self) -> str:
        """Get the experiment name from config."""
        return self._config.name

    @property
    def scenario_path(self) -> Path:
        """Get the scenario path from config."""
        return self._config.scenario_path

    @property
    def system_prompt(self) -> str | None:
        """Get the system prompt from config."""
        return self._config.llm.system_prompt

    @property
    def constraints(self) -> ScenarioConstraints | None:
        """Get the policy constraints from config."""
        return self._constraints

    async def run(self) -> ExperimentResult:
        """Run experiment to completion.

        Executes the full optimization loop until convergence
        or max iterations is reached.

        Returns:
            ExperimentResult with final state and metrics.

        Note:
            This base implementation provides the loop structure.
            Full simulation requires a SimulationRunner to be available.
        """
        import time

        from payment_simulator.experiments.runner.optimization import (
            OptimizationLoop,
        )

        start_time = time.time()

        # Create optimization loop with config directory for relative path resolution
        loop = OptimizationLoop(
            config=self._config,
            config_dir=self._config_dir,
        )

        # Run optimization
        opt_result = await loop.run()

        duration = time.time() - start_time

        # Build experiment result (using existing ExperimentResult fields)
        return ExperimentResult(
            experiment_name=self._config.name,
            num_iterations=opt_result.num_iterations,
            converged=opt_result.converged,
            convergence_reason=opt_result.convergence_reason,
            final_costs=opt_result.per_agent_costs,
            total_duration_seconds=duration,
        )

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state.

        Returns:
            ExperimentState snapshot of current progress.
        """
        return ExperimentState(
            experiment_name=self._config.name,
            current_iteration=self._current_iteration,
            is_converged=False,
            convergence_reason=None,
        )
