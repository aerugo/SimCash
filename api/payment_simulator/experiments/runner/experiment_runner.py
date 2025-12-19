"""Generic experiment runner.

Provides a complete experiment runner that works with any YAML configuration.
This eliminates the need for experiment-specific Python code.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.experiments.persistence import ExperimentRepository

from payment_simulator.experiments.runner.result import (
    ExperimentResult,
    ExperimentState,
)
from payment_simulator.experiments.runner.state_provider import (
    ExperimentStateProviderProtocol,
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
        persist_bootstrap: bool = False,
    ) -> None:
        """Initialize the experiment runner.

        Args:
            config: ExperimentConfig with all settings.
            verbose_config: Optional verbose logging configuration.
            run_id: Optional run ID. If not provided, one is generated.
            config_dir: Directory containing the experiment config (for resolving
                        relative scenario paths). If None, uses current directory.
            persist_bootstrap: If True, persist bootstrap sample simulations to database.
        """
        self._config = config
        self._verbose_config = verbose_config or VerboseConfig()
        self._run_id = run_id or _generate_run_id(config.name)
        self._config_dir = config_dir or Path.cwd()
        self._persist_bootstrap = persist_bootstrap

        # Get constraints from config (inline or module)
        self._constraints: ScenarioConstraints | None = config.get_constraints()

        # Initialize state
        self._state = ExperimentState(experiment_name=config.name)
        self._current_iteration = 0
        self._policies: dict[str, dict[str, Any]] = {}

        # Store reference to optimization loop for state_provider access
        self._loop: Any = None

        # Initialize repository if output configured
        self._repository: ExperimentRepository | None = None

        # Continuation mode attributes (set by continue_from_database)
        self._is_continuation: bool = False
        self._continuation_iterations: list[Any] = []

        if config.output and config.output.database:
            self._init_repository()

    def _init_repository(self) -> None:
        """Initialize the experiment repository for persistence.

        Creates output directory if needed and opens database connection.
        """
        from payment_simulator.experiments.persistence import ExperimentRepository

        # Type narrowing - this method is only called when output is configured
        assert self._config.output is not None

        output_dir = Path(self._config.output.directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        db_path = output_dir / self._config.output.database
        self._repository = ExperimentRepository(db_path)

    def _save_experiment_start(self) -> None:
        """Save experiment record at the start of run."""
        if self._repository is None:
            return

        from payment_simulator.experiments.persistence import ExperimentRecord

        # Convert config to dict for storage (complete for continuation support)
        config_dict = {
            "name": self._config.name,
            "description": self._config.description,
            "scenario_path": str(self._config.scenario_path),
            "master_seed": self._config.master_seed,
            "evaluation": {
                "mode": self._config.evaluation.mode,
                "ticks": self._config.evaluation.ticks,
                "num_samples": self._config.evaluation.num_samples,
            },
            "convergence": {
                "max_iterations": self._config.convergence.max_iterations,
                "stability_threshold": self._config.convergence.stability_threshold,
                "stability_window": self._config.convergence.stability_window,
                "improvement_threshold": self._config.convergence.improvement_threshold,
            },
            "optimized_agents": list(self._config.optimized_agents),
            "constraints_module": self._config.constraints_module,
            # LLM config for continuation
            "llm": {
                "model": self._config.llm.model,
                "temperature": self._config.llm.temperature,
                "max_retries": self._config.llm.max_retries,
                "timeout_seconds": self._config.llm.timeout_seconds,
                "thinking_budget": self._config.llm.thinking_budget,
                "reasoning_effort": self._config.llm.reasoning_effort,
                "system_prompt": self._config.llm.system_prompt,
            },
        }

        record = ExperimentRecord(
            run_id=self._run_id,
            experiment_name=self._config.name,
            experiment_type="generic",
            config=config_dict,
            created_at=datetime.now().isoformat(),
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        self._repository.save_experiment(record)

    def _save_experiment_completion(
        self,
        num_iterations: int,
        converged: bool,
        convergence_reason: str,
    ) -> None:
        """Update experiment record with completion info.

        Args:
            num_iterations: Total iterations run.
            converged: Whether convergence was reached.
            convergence_reason: Reason for termination.
        """
        if self._repository is None:
            return

        from payment_simulator.experiments.persistence import ExperimentRecord

        # Load existing record and update
        existing = self._repository.load_experiment(self._run_id)
        if existing is None:
            return

        updated = ExperimentRecord(
            run_id=existing.run_id,
            experiment_name=existing.experiment_name,
            experiment_type=existing.experiment_type,
            config=existing.config,
            created_at=existing.created_at,
            completed_at=datetime.now().isoformat(),
            num_iterations=num_iterations,
            converged=converged,
            convergence_reason=convergence_reason,
        )
        self._repository.save_experiment(updated)

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

    @property
    def state_provider(self) -> ExperimentStateProviderProtocol | None:
        """Get the state provider from the optimization loop.

        Returns the LiveStateProvider used during experiment execution.
        Available after run() has been called.

        Returns:
            ExperimentStateProviderProtocol or None if not yet run.
        """
        if self._loop is not None:
            provider: ExperimentStateProviderProtocol = self._loop._state_provider
            return provider
        return None

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

    @classmethod
    def continue_from_database(
        cls,
        run_id: str,
        repository: ExperimentRepository,
        verbose_config: VerboseConfig | None = None,
        config_dir: Path | None = None,
    ) -> GenericExperimentRunner:
        """Create a runner to continue an interrupted experiment.

        Loads the experiment state from the database and creates a runner
        configured to resume from the last completed iteration.

        Args:
            run_id: Run ID of the experiment to continue.
            repository: ExperimentRepository instance (keeps connection open).
            verbose_config: Optional verbose logging configuration.
            config_dir: Directory for resolving relative paths. If None, uses cwd.

        Returns:
            GenericExperimentRunner configured to continue the experiment.

        Raises:
            ValueError: If experiment not found, already completed, or has no iterations.
        """
        from payment_simulator.experiments.config import ExperimentConfig

        # Load continuation state
        continuation_state = repository.get_continuation_state(run_id)
        if continuation_state is None:
            # Check if it exists but is completed
            experiment = repository.load_experiment(run_id)
            if experiment is None:
                msg = f"Experiment not found: {run_id}"
                raise ValueError(msg)
            msg = f"Experiment already completed: {run_id}"
            raise ValueError(msg)

        experiment_record, iterations = continuation_state

        if not iterations:
            msg = f"No iterations found for experiment: {run_id}. Cannot continue."
            raise ValueError(msg)

        # Reconstruct ExperimentConfig from stored config dict
        config = ExperimentConfig.from_stored_dict(experiment_record.config)

        # Create runner with SAME run_id (not generating new)
        runner = cls(
            config=config,
            verbose_config=verbose_config,
            run_id=run_id,  # Use existing run_id
            config_dir=config_dir,
        )

        # Store reference to repository (for saving completion)
        runner._repository = repository

        # Mark as continuation mode
        runner._is_continuation = True
        runner._continuation_iterations = iterations

        return runner

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

        # Only save experiment record at start if NOT a continuation
        if not self._is_continuation:
            self._save_experiment_start()

        # Create optimization loop with config directory for relative path resolution,
        # verbose config for logging, run_id for consistency, and repository for persistence
        self._loop = OptimizationLoop(
            config=self._config,
            config_dir=self._config_dir,
            verbose_config=self._verbose_config,
            run_id=self._run_id,
            repository=self._repository,
            persist_bootstrap=self._persist_bootstrap,
        )

        # If this is a continuation, restore state from iterations
        if self._is_continuation and self._continuation_iterations:
            last_iteration = max(r.iteration for r in self._continuation_iterations)
            self._loop.restore_state(self._continuation_iterations, last_iteration)

        # Run optimization
        opt_result = await self._loop.run()

        duration = time.time() - start_time

        # Save experiment completion
        self._save_experiment_completion(
            num_iterations=opt_result.num_iterations,
            converged=opt_result.converged,
            convergence_reason=opt_result.convergence_reason,
        )

        # Build experiment result (using existing ExperimentResult fields)
        return ExperimentResult(
            experiment_name=self._config.name,
            num_iterations=opt_result.num_iterations,
            converged=opt_result.converged,
            convergence_reason=opt_result.convergence_reason,
            final_costs=opt_result.per_agent_costs,
            total_duration_seconds=duration,
        )
