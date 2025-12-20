"""Generic optimization loop for experiments.

Provides a config-driven optimization loop that can be used by any experiment.
All behavior is determined by ExperimentConfig - no hardcoded experiment logic.

Integrates sophisticated LLM context building:
- EnrichedBootstrapContextBuilder for per-agent best/worst seed analysis
- PolicyOptimizer for rich 50k+ token prompts
- Event capture for verbose tick-by-tick simulation output
- Iteration history tracking with acceptance status
"""

from __future__ import annotations

import secrets
import statistics as stats_module
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from rich.console import Console

    from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.experiments.persistence import ExperimentRepository

from payment_simulator._core import Orchestrator
from payment_simulator.ai_cash_mgmt import BootstrapConvergenceDetector, ConvergenceDetector
from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
    AgentSimulationContext,
    EnrichedBootstrapContextBuilder,
)
from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
    BootstrapEvent,
    CostBreakdown,
    EnrichedEvaluationResult,
)
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
    TransactionHistoryCollector,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import BootstrapSample
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    DebugCallback,
    PolicyOptimizer,
)
from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentIterationRecord,
)
from payment_simulator.ai_cash_mgmt.prompts.event_filter import (
    filter_events_for_agent,
    format_filtered_output,
)
from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider
from payment_simulator.cli.output import format_tick_range_as_text
from payment_simulator.config import SimulationConfig
from payment_simulator.config.policy_config_builder import StandardPolicyConfigBuilder
from payment_simulator.config.scenario_config_builder import StandardScenarioConfigBuilder
from payment_simulator.experiments.runner.bootstrap_support import (
    BootstrapLLMContext,
    InitialSimulationResult,
    SimulationResult,
)
from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker
from payment_simulator.experiments.runner.seed_matrix import SeedMatrix
from payment_simulator.experiments.runner.state_provider import LiveStateProvider
from payment_simulator.experiments.runner.statistics import compute_cost_statistics
from payment_simulator.experiments.runner.verbose import (
    BootstrapDeltaResult,
    BootstrapSampleResult,
    LLMCallMetadata,
    RejectionDetail,
    VerboseConfig,
    VerboseLogger,
)

# =============================================================================
# Policy Evaluation Dataclasses
# =============================================================================


@dataclass(frozen=True)
class SampleEvaluationResult:
    """Result of evaluating policy pair on a single sample.

    All costs in integer cents (INV-1).

    Attributes:
        sample_index: Index of the sample within the evaluation batch.
        seed: RNG seed used for this sample (for reproducibility).
        old_cost: Actual cost with old policy.
        new_cost: Actual cost with new policy.
        delta: old_cost - new_cost (positive = improvement).
    """

    sample_index: int
    seed: int
    old_cost: int
    new_cost: int
    delta: int


@dataclass(frozen=True)
class PolicyPairEvaluation:
    """Complete results from evaluating old vs new policy.

    All costs in integer cents (INV-1).

    Attributes:
        sample_results: List of per-sample evaluation results.
        delta_sum: Sum of deltas across samples.
        mean_old_cost: Mean of old_cost across samples.
        mean_new_cost: Mean of new_cost across samples.
        settlement_rate: System-wide settlement rate (0.0 to 1.0).
        avg_delay: System-wide average delay in ticks.
        cost_breakdown: Total cost breakdown by type.
        cost_std_dev: Standard deviation of costs in cents (bootstrap only).
        confidence_interval_95: 95% CI bounds [lower, upper] in cents (bootstrap only).
        agent_stats: Per-agent metrics keyed by agent_id.
    """

    sample_results: list[SampleEvaluationResult]
    delta_sum: int
    mean_old_cost: int
    mean_new_cost: int
    # Extended metrics for Phase 1: Extended Policy Evaluation Stats
    settlement_rate: float | None = None
    avg_delay: float | None = None
    cost_breakdown: dict[str, int] | None = None
    # Phase 3: Derived statistics (bootstrap only)
    cost_std_dev: int | None = None
    confidence_interval_95: list[int] | None = None
    agent_stats: dict[str, dict[str, Any]] | None = None

    @property
    def deltas(self) -> list[int]:
        """List of deltas for backward compatibility."""
        return [s.delta for s in self.sample_results]

    @property
    def num_samples(self) -> int:
        """Number of samples in evaluation."""
        return len(self.sample_results)


def _generate_run_id(experiment_name: str) -> str:
    """Generate a unique run ID.

    Format: {experiment_name}-{timestamp}-{random_suffix}

    Args:
        experiment_name: Name of the experiment.

    Returns:
        Unique run ID string.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{experiment_name}-{timestamp}-{suffix}"


class _VerboseDebugCallback:
    """Debug callback that bridges VerboseLogger with DebugCallback protocol.

    Used to log PolicyOptimizer progress via VerboseLogger when debug mode
    is enabled.
    """

    def __init__(self, logger: VerboseLogger) -> None:
        """Initialize with a VerboseLogger.

        Args:
            logger: VerboseLogger to use for output.
        """
        self._logger = logger

    def on_attempt_start(self, agent_id: str, attempt: int, max_attempts: int) -> None:
        """Called when starting an LLM request attempt."""
        self._logger.log_debug_llm_request_start(agent_id, attempt)

    def on_validation_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        errors: list[str],
    ) -> None:
        """Called when validation fails."""
        self._logger.log_debug_validation_error(agent_id, attempt, max_attempts, errors)

    def on_llm_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        error: str,
    ) -> None:
        """Called when the LLM call fails."""
        self._logger.log_debug_llm_error(agent_id, attempt, max_attempts, error)

    def on_validation_success(self, agent_id: str, attempt: int) -> None:
        """Called when validation succeeds."""
        self._logger.log_debug_validation_success(agent_id, attempt)

    def on_all_retries_exhausted(
        self,
        agent_id: str,
        max_attempts: int,
        final_errors: list[str],
    ) -> None:
        """Called when all retry attempts are exhausted."""
        self._logger.log_debug_all_retries_exhausted(
            agent_id, max_attempts, final_errors
        )


@dataclass(frozen=True)
class OptimizationResult:
    """Result of running the optimization loop.

    Captures the final state after optimization completes.
    All costs are integer cents (INV-1).

    Attributes:
        num_iterations: Total iterations executed.
        converged: Whether optimization converged.
        convergence_reason: Reason for convergence (stability, max_iterations, etc).
        final_cost: Final total cost in integer cents.
        best_cost: Best (lowest) cost achieved in integer cents.
        per_agent_costs: Final cost per agent in integer cents.
        final_policies: Final policy dict per agent.
        iteration_history: History of costs per iteration.

    Example:
        >>> result = OptimizationResult(
        ...     num_iterations=10,
        ...     converged=True,
        ...     convergence_reason="stability_reached",
        ...     final_cost=15000,  # $150.00 in cents
        ...     best_cost=14500,
        ...     per_agent_costs={"BANK_A": 7500, "BANK_B": 7000},
        ...     final_policies={"BANK_A": {...}, "BANK_B": {...}},
        ...     iteration_history=[15000, 14800, 14500],
        ... )
    """

    num_iterations: int
    converged: bool
    convergence_reason: str
    final_cost: int  # INV-1: Integer cents
    best_cost: int  # INV-1: Integer cents
    per_agent_costs: dict[str, int]  # INV-1: Integer cents
    final_policies: dict[str, dict[str, Any]]
    iteration_history: list[int] = field(default_factory=list)


class OptimizationLoop:
    """Generic optimization loop for experiments.

    Executes the standard policy optimization algorithm:
    1. Evaluate current policies via simulation
    2. Check convergence criteria
    3. For each agent, generate new policy via LLM
    4. Accept/reject based on paired comparison
    5. Repeat until converged or max iterations

    All configuration is read from ExperimentConfig:
    - system_prompt: Dynamically built from constraints (schema-filtered)
    - constraints: From config.get_constraints()
    - convergence: From config.convergence
    - agents: From config.optimized_agents

    Example:
        >>> from payment_simulator.experiments.config import ExperimentConfig
        >>> config = ExperimentConfig.from_yaml(Path("exp1.yaml"))
        >>> loop = OptimizationLoop(config=config)
        >>> result = await loop.run()
        >>> print(f"Converged: {result.converged}")

    Note:
        The actual LLM calls and simulation require external dependencies.
        This class provides the loop structure; actual execution needs
        a SimulationRunner to be injected or created from config.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        config_dir: Path | None = None,
        verbose_config: VerboseConfig | None = None,
        console: Console | None = None,
        run_id: str | None = None,
        repository: ExperimentRepository | None = None,
        persist_bootstrap: bool = False,
    ) -> None:
        """Initialize the optimization loop.

        Args:
            config: ExperimentConfig with all settings.
            config_dir: Directory containing the experiment config (for resolving
                        relative scenario paths). If None, uses current directory.
            verbose_config: Optional verbose logging configuration.
            console: Optional Rich console for verbose output.
            run_id: Optional run ID. If not provided, one is generated.
            repository: Optional ExperimentRepository for persistence.
            persist_bootstrap: If True, persist bootstrap sample simulations to database.
        """
        self._config = config
        self._config_dir = config_dir or Path.cwd()
        self._run_id = run_id or _generate_run_id(config.name)
        self._repository: ExperimentRepository | None = repository
        self._persist_bootstrap = persist_bootstrap

        # Get convergence settings - use mode-appropriate detector
        conv = config.convergence
        if config.evaluation.is_bootstrap:
            # Bootstrap mode uses improved detector with CV, trend, and regret criteria
            self._convergence: ConvergenceDetector | BootstrapConvergenceDetector = (
                BootstrapConvergenceDetector(
                    cv_threshold=conv.cv_threshold,
                    window_size=conv.stability_window,
                    regret_threshold=conv.regret_threshold,
                    max_iterations=conv.max_iterations,
                )
            )
        else:
            # Deterministic modes use original simple detector
            self._convergence = ConvergenceDetector(
                stability_threshold=conv.stability_threshold,
                stability_window=conv.stability_window,
                max_iterations=conv.max_iterations,
                improvement_threshold=conv.improvement_threshold,
            )

        # Get constraints from config
        self._constraints: ScenarioConstraints | None = config.get_constraints()

        # Initialize state
        self._current_iteration = 0
        self._policies: dict[str, dict[str, Any]] = {}
        self._best_cost: int = 0
        self._best_policies: dict[str, dict[str, Any]] = {}
        self._iteration_history: list[int] = []

        # Track accepted changes per iteration
        self._accepted_changes: dict[str, bool] = {}

        # Temporal mode tracking: previous iteration costs for comparison
        # Used by deterministic-temporal mode to compare cost across iterations
        self._previous_iteration_costs: dict[str, int] = {}

        # Previous policies for revert capability in temporal mode
        # If cost increases, we revert to the previous policy
        self._previous_policies: dict[str, dict[str, Any]] = {}

        # Policy stability tracker for multi-agent convergence detection
        # Tracks initial_liquidity_fraction history per agent
        # Used by deterministic-temporal mode for convergence detection
        self._stability_tracker = PolicyStabilityTracker()

        # Load scenario config once
        self._scenario_dict: dict[str, Any] | None = None

        # LLM client (lazy initialized)
        self._llm_client: Any = None

        # PolicyOptimizer for rich context (lazy initialized)
        self._policy_optimizer: PolicyOptimizer | None = None

        # Per-agent iteration history for LLM context
        self._agent_iteration_history: dict[str, list[SingleAgentIterationRecord]] = {
            agent_id: [] for agent_id in config.optimized_agents
        }

        # Per-agent best costs for tracking is_best_so_far
        self._agent_best_costs: dict[str, int] = {}

        # Enriched evaluation results from current iteration (for LLM context)
        self._current_enriched_results: list[EnrichedEvaluationResult] = []

        # Per-agent contexts from current iteration (for LLM optimization)
        self._current_agent_contexts: dict[str, AgentSimulationContext] = {}

        # Cost rates from scenario (for LLM context)
        self._cost_rates: dict[str, Any] = {}

        # Policy config builder for canonical parameter extraction
        # Ensures identical policy interpretation across all evaluation paths
        # (Policy Evaluation Identity invariant)
        self._policy_builder = StandardPolicyConfigBuilder()

        # Scenario config builder for canonical agent configuration extraction
        # Ensures identical scenario interpretation across all code paths
        # (Scenario Config Interpretation Identity invariant - INV-10)
        self._scenario_builder: StandardScenarioConfigBuilder | None = None

        # Verbose logging
        self._verbose_config = verbose_config or VerboseConfig()
        self._verbose_logger: VerboseLogger | None = None
        if self._verbose_config.any:
            self._verbose_logger = VerboseLogger(self._verbose_config, console=console)

        # Initialize state provider for event capture (replay identity)
        self._state_provider = LiveStateProvider(
            experiment_name=config.name,
            experiment_type="generic",
            config={
                "master_seed": config.master_seed,
                "max_iterations": config.convergence.max_iterations,
                "evaluation_mode": config.evaluation.mode,
                "num_samples": config.evaluation.num_samples,
            },
            run_id=self._run_id,
        )

        # Initialize seed matrix for deterministic per-agent bootstrap evaluation
        # Seeds are pre-generated for reproducibility and agent isolation
        self._seed_matrix = SeedMatrix(
            master_seed=config.master_seed,
            max_iterations=config.convergence.max_iterations,
            agents=list(config.optimized_agents),
            num_bootstrap_samples=config.evaluation.num_samples or 1,
        )

        # Track delta history for progress (sum of (old_cost - new_cost) per sample)
        # Positive delta sum = new policy is cheaper = improvement
        self._delta_history: list[dict[str, Any]] = []

        # Bootstrap evaluation state (for real bootstrap mode)
        # These are initialized once by _run_initial_simulation()
        self._initial_sim_result: InitialSimulationResult | None = None
        self._bootstrap_samples: dict[str, list[BootstrapSample]] = {}
        self._bootstrap_sampler: BootstrapSampler | None = None
        self._bootstrap_llm_contexts: dict[str, BootstrapLLMContext] = {}

        # Track simulation IDs for all simulations run during this experiment
        # This enables replay of individual simulations
        self._simulation_ids: list[str] = []
        self._simulation_counter: int = 0

    @property
    def max_iterations(self) -> int:
        """Get max iterations from config."""
        return self._config.convergence.max_iterations

    @property
    def stability_threshold(self) -> float:
        """Get stability threshold from config."""
        return self._config.convergence.stability_threshold

    @property
    def is_converged(self) -> bool:
        """Check if optimization has converged."""
        return self._convergence.is_converged

    @property
    def optimized_agents(self) -> tuple[str, ...]:
        """Get list of agents being optimized."""
        return self._config.optimized_agents

    @property
    def current_policies(self) -> dict[str, dict[str, Any]]:
        """Get current policies per agent."""
        return self._policies.copy()

    @property
    def master_seed(self) -> int:
        """Get master seed for determinism."""
        return self._config.master_seed

    @property
    def current_iteration(self) -> int:
        """Get current iteration count."""
        return self._current_iteration

    @property
    def simulation_ids(self) -> list[str]:
        """Get list of all simulation IDs run during this experiment.

        These IDs can be used to replay individual simulations.

        Returns:
            List of simulation ID strings.
        """
        return self._simulation_ids.copy()

    def _generate_simulation_id(self, purpose: str) -> str:
        """Generate a unique simulation ID.

        Format: {run_id}-sim-{counter:03d}-{purpose}

        Args:
            purpose: Short description of simulation purpose
                    (e.g., "init", "eval", "pair").

        Returns:
            Unique simulation ID string.
        """
        self._simulation_counter += 1
        sim_id = f"{self._run_id}-sim-{self._simulation_counter:03d}-{purpose}"
        self._simulation_ids.append(sim_id)
        return sim_id

    def _run_simulation(
        self,
        seed: int,
        purpose: str,
        *,
        iteration: int | None = None,
        sample_idx: int | None = None,
        persist: bool | None = None,
        is_primary: bool = False,
    ) -> SimulationResult:
        """Run a single simulation and capture all output.

        This is the ONE method that runs simulations. All callers use this
        and transform the result as needed.

        ONE method runs simulations → ONE result type → callers transform.

        Args:
            seed: RNG seed for this simulation.
            purpose: Purpose tag for simulation ID (e.g., "init", "eval", "bootstrap").
            iteration: Current iteration number (for logging/persistence).
            sample_idx: Bootstrap sample index (for logging/persistence).
            persist: Override persistence. If None, uses default based on is_primary.
            is_primary: If True, this is a primary simulation (main scenario run)
                that should persist by default when repository is present.
                If False, this is a bootstrap sample that only persists
                when persist=True explicitly (via --persist-bootstrap).

        Returns:
            SimulationResult with all simulation output.

        Note:
            All costs are integer cents (INV-1: Money is ALWAYS i64).
            Same seed produces identical results (INV-2: Determinism is Sacred).
        """
        # 1. Generate simulation ID
        sim_id = self._generate_simulation_id(purpose)

        # 2. Log to terminal if verbose
        if self._verbose_logger:
            self._verbose_logger.log_simulation_start(
                simulation_id=sim_id,
                purpose=purpose,
                iteration=iteration,
                seed=seed,
            )

        # 3. Build config and run simulation
        ffi_config = self._build_simulation_config()
        ffi_config["rng_seed"] = seed

        # Extract cost rates for LLM context (only once)
        if not self._cost_rates and "cost_rates" in ffi_config:
            self._cost_rates = ffi_config["cost_rates"]

        orch = Orchestrator.new(ffi_config)
        total_ticks = self._config.evaluation.ticks
        all_events: list[dict[str, Any]] = []

        for tick in range(total_ticks):
            orch.tick()
            try:
                tick_events = orch.get_tick_events(tick)
                all_events.extend(tick_events)
            except Exception:
                # If event capture fails, continue without events for this tick
                pass

        # 4. Extract costs and metrics
        total_cost = 0
        per_agent_costs: dict[str, int] = {}
        delay_cost = 0
        liquidity_cost = 0
        deadline_penalty = 0

        for agent_id in self.optimized_agents:
            try:
                agent_costs = orch.get_agent_accumulated_costs(agent_id)
                cost = int(agent_costs.get("total_cost", 0))
                per_agent_costs[agent_id] = cost
                total_cost += cost
                delay_cost += int(agent_costs.get("delay_cost", 0))
                liquidity_cost += int(agent_costs.get("liquidity_cost", 0))
                deadline_penalty += int(agent_costs.get("deadline_penalty", 0))
            except Exception:
                per_agent_costs[agent_id] = 0

        # 5. Calculate settlement rate and avg delay
        try:
            metrics = orch.get_system_metrics()
            # FFI returns "total_settlements" and "total_arrivals"
            settled = metrics.get("total_settlements", 0)
            total = metrics.get("total_arrivals", 1)
            settlement_rate = settled / total if total > 0 else 1.0
            avg_delay = float(metrics.get("avg_delay_ticks", 0.0))
        except Exception:
            settlement_rate = 1.0
            avg_delay = 0.0

        # 5.5. Capture verbose output using the same formatting as CLI run/replay
        # This happens BEFORE the orchestrator is discarded, so we can use its state
        verbose_output: str | None = None
        try:
            # Group events by tick for tick-by-tick formatting
            events_by_tick: dict[int, list[dict[str, Any]]] = {}
            for event in all_events:
                tick = event.get("tick", 0)
                if tick not in events_by_tick:
                    events_by_tick[tick] = []
                events_by_tick[tick].append(event)

            # Create StateProvider from orchestrator (while it's still alive)
            provider = OrchestratorStateProvider(orch)

            # Format using the SINGLE SOURCE OF TRUTH for verbose output
            verbose_output = format_tick_range_as_text(
                provider=provider,
                tick_events_by_tick=events_by_tick,
                agent_ids=list(self.optimized_agents),
            )
        except Exception:
            # If pretty formatting fails, fall back to None
            # The old _format_events_for_llm is kept as fallback in InitialSimulationResult
            verbose_output = None

        # 6. Persist if appropriate
        # INV-11: Use SimulationPersistenceProvider for unified persistence
        # Primary simulations persist by default; bootstrap samples only with flag
        if persist is not None:
            should_persist = persist
        elif is_primary:
            # Primary simulations persist by default when repository exists
            should_persist = self._repository is not None
        else:
            # Bootstrap samples only persist with explicit --persist-bootstrap flag
            should_persist = self._persist_bootstrap
        if self._repository and should_persist:
            from payment_simulator.experiments.persistence import EventRecord

            # Get ticks_per_day from FFI config (set by scenario config)
            ticks_per_day = ffi_config.get("ticks_per_day", 100)

            # Get SimulationPersistenceProvider from repository
            sim_provider = self._repository.get_simulation_persistence_provider(
                ticks_per_day=ticks_per_day
            )

            # 6a. Persist simulation start to simulations table
            # IMPORTANT: Store the original scenario config (YAML format), NOT the FFI config.
            # Replay expects YAML format with 'agents' and 'simulation' keys.
            # FFI format has 'agent_configs' and 'ticks_per_day' at root - incompatible with replay.
            scenario_config = self._load_scenario_config()
            sim_provider.persist_simulation_start(
                simulation_id=sim_id,
                config=scenario_config,
                experiment_run_id=self._run_id,
                experiment_iteration=iteration,
            )

            # 6b. Persist all events to simulation_events table
            # Group events by tick for proper persistence
            events_by_tick: dict[int, list[dict[str, Any]]] = {}
            for event in all_events:
                tick = event.get("tick", 0)
                if tick not in events_by_tick:
                    events_by_tick[tick] = []
                events_by_tick[tick].append(event)

            # Persist events per tick
            for tick, tick_events in sorted(events_by_tick.items()):
                sim_provider.persist_tick_events(sim_id, tick, tick_events)

            # 6c. Persist simulation complete with metrics
            sim_provider.persist_simulation_complete(
                simulation_id=sim_id,
                metrics={
                    "total_arrivals": metrics.get("total_arrivals", 0),
                    "total_settlements": metrics.get("total_settlements", 0),
                    "total_cost_cents": total_cost,
                    "duration_seconds": 0.0,  # Duration not tracked in experiment runner
                },
            )

            # 6d. Also save summary to experiment_events (WITHOUT full events array)
            # This maintains backward compatibility with experiment replay
            summary_event = EventRecord(
                run_id=self._run_id,
                iteration=iteration or 0,
                event_type="simulation_run",
                event_data={
                    "simulation_id": sim_id,
                    "purpose": purpose,
                    "seed": seed,
                    "ticks": total_ticks,
                    "total_cost": total_cost,
                    "per_agent_costs": per_agent_costs,
                    "num_events": len(all_events),
                    # Events now in simulation_events table, not here (INV-11)
                },
                timestamp=datetime.now().isoformat(),
            )
            self._repository.save_event(summary_event)

        # 7. Return SimulationResult
        return SimulationResult(
            seed=seed,
            simulation_id=sim_id,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            events=tuple(all_events),
            cost_breakdown=CostBreakdown(
                delay_cost=delay_cost,
                # Model uses "overdraft_cost" but FFI returns "liquidity_cost"
                # These are the same concept (cost of negative balance)
                overdraft_cost=liquidity_cost,
                deadline_penalty=deadline_penalty,
                # FFI doesn't separate eod_penalty from deadline_penalty
                eod_penalty=0,
            ),
            settlement_rate=settlement_rate,
            avg_delay=avg_delay,
            verbose_output=verbose_output,
        )

    async def run(self) -> OptimizationResult:
        """Run the optimization loop to convergence.

        Returns:
            OptimizationResult with final state and metrics.

        Note:
            This base implementation provides the loop structure.
            Subclasses or the GenericExperimentRunner should implement
            actual evaluation and policy generation.
        """
        # Record experiment start event
        self._state_provider.record_event(
            iteration=0,
            event_type="experiment_start",
            event_data={
                "experiment_name": self._config.name,
                "max_iterations": self.max_iterations,
                "num_samples": self._config.evaluation.num_samples,
                "model": self._config.llm.model,
                "evaluation_mode": self._config.evaluation.mode,
            },
        )

        # Initialize policies if not set
        for agent_id in self.optimized_agents:
            if agent_id not in self._policies:
                self._policies[agent_id] = self._create_default_policy(agent_id)

        # For real bootstrap mode: run initial simulation ONCE to collect history
        # This provides the empirical distribution from which bootstrap samples are drawn
        if self._config.evaluation.mode == "bootstrap":
            self._initial_sim_result = self._run_initial_simulation()
            self._create_bootstrap_samples()

            # Record initial simulation event
            self._state_provider.record_event(
                iteration=0,
                event_type="initial_simulation_complete",
                event_data={
                    "total_cost": self._initial_sim_result.total_cost,
                    "per_agent_costs": self._initial_sim_result.per_agent_costs,
                    "num_events": len(self._initial_sim_result.events),
                    "num_samples_per_agent": {
                        agent_id: len(samples)
                        for agent_id, samples in self._bootstrap_samples.items()
                    },
                },
            )

        # Track per_agent_costs for final result
        per_agent_costs: dict[str, int] = {}

        # Optimization loop
        while self._current_iteration < self.max_iterations:
            self._current_iteration += 1

            # Reset accepted changes for this iteration
            self._accepted_changes = dict.fromkeys(self.optimized_agents, False)

            # Evaluate current policies
            total_cost, per_agent_costs = await self._evaluate_policies()

            # Log iteration start with cost (verbose logging)
            if self._verbose_logger and self._verbose_config.iterations:
                self._verbose_logger.log_iteration_start(
                    self._current_iteration, total_cost
                )

            # Record iteration start event via state provider
            self._state_provider.record_event(
                iteration=self._current_iteration - 1,  # 0-indexed
                event_type="iteration_start",
                event_data={
                    "iteration": self._current_iteration,
                    "total_cost": total_cost,
                },
            )

            # Record iteration data for state provider
            self._state_provider.record_iteration(
                iteration=self._current_iteration - 1,  # 0-indexed
                costs_per_agent=per_agent_costs,
                accepted_changes={},  # Updated after optimization
                policies=self._policies.copy(),
            )

            # Save evaluation event to repository persistence
            self._save_evaluation_event(total_cost, per_agent_costs)

            # Record metrics
            self._convergence.record_metric(float(total_cost))
            self._iteration_history.append(total_cost)

            # Track best
            if self._best_cost == 0 or total_cost < self._best_cost:
                self._best_cost = total_cost
                self._best_policies = {k: v.copy() for k, v in self._policies.items()}

            # Save iteration record to repository persistence
            self._save_iteration_record(per_agent_costs)

            # Check convergence
            if self._convergence.is_converged:
                break

            # Optimize each agent
            for agent_id in self.optimized_agents:
                await self._optimize_agent(agent_id, per_agent_costs.get(agent_id, 0))

            # Check multi-agent convergence for temporal mode
            # This is based on policy stability (all agents unchanged for stability_window)
            if self._config.evaluation.is_deterministic_temporal:
                if self._check_multiagent_convergence():
                    # Override convergence state for proper reporting
                    # Note: temporal mode always uses ConvergenceDetector, not Bootstrap
                    if isinstance(self._convergence, ConvergenceDetector):
                        self._convergence._converged_by_stability = True
                    break

        # Get final cost
        final_cost = self._iteration_history[-1] if self._iteration_history else 0
        converged = self._convergence.is_converged

        # Determine convergence reason
        # For temporal mode, check policy stability first
        if (
            self._config.evaluation.is_deterministic_temporal
            and self._check_multiagent_convergence()
        ):
            convergence_reason = "policy_stability"
        else:
            convergence_reason = self._convergence.convergence_reason or "max_iterations"

        # Record experiment end event
        self._state_provider.record_event(
            iteration=self._current_iteration - 1,
            event_type="experiment_end",
            event_data={
                "final_cost": final_cost,
                "best_cost": self._best_cost,
                "converged": converged,
                "convergence_reason": convergence_reason,
                "num_iterations": self._current_iteration,
            },
        )

        # Set final result in provider
        self._state_provider.set_final_result(
            final_cost=final_cost,
            best_cost=self._best_cost,
            converged=converged,
            convergence_reason=convergence_reason,
        )

        return OptimizationResult(
            num_iterations=self._current_iteration,
            converged=converged,
            convergence_reason=convergence_reason,
            final_cost=final_cost,
            best_cost=self._best_cost,
            per_agent_costs=per_agent_costs,
            final_policies=self._policies.copy(),
            iteration_history=self._iteration_history.copy(),
        )

    def _save_iteration_record(self, per_agent_costs: dict[str, int]) -> None:
        """Save iteration record to repository.

        Args:
            per_agent_costs: Costs per agent in integer cents.
        """
        if self._repository is None:
            return

        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id=self._run_id,
            iteration=self._current_iteration - 1,  # 0-indexed in storage
            costs_per_agent=per_agent_costs,
            accepted_changes=self._accepted_changes.copy(),
            policies={k: v.copy() for k, v in self._policies.items()},
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_iteration(record)

    def _save_evaluation_event(
        self, total_cost: int, per_agent_costs: dict[str, int]
    ) -> None:
        """Save evaluation event to repository.

        Args:
            total_cost: Total cost in integer cents.
            per_agent_costs: Costs per agent in integer cents.
        """
        if self._repository is None:
            return

        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id=self._run_id,
            iteration=self._current_iteration - 1,  # 0-indexed
            event_type="evaluation",
            event_data={
                "total_cost": total_cost,
                "per_agent_costs": per_agent_costs,
            },
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_event(event)

    def _save_policy_evaluation(
        self,
        agent_id: str,
        evaluation_mode: str,
        proposed_policy: dict[str, Any],
        old_cost: int,
        new_cost: int,
        context_simulation_cost: int,
        accepted: bool,
        acceptance_reason: str,
        delta_sum: int,
        num_samples: int,
        sample_details: list[dict[str, Any]] | None,
        scenario_seed: int | None,
        # Extended metrics (Phase 2: Metrics Capture)
        settlement_rate: float | None = None,
        avg_delay: float | None = None,
        cost_breakdown: dict[str, int] | None = None,
        cost_std_dev: int | None = None,
        confidence_interval_95: list[int] | None = None,
        agent_stats: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Save policy evaluation record to repository.

        Persists the complete evaluation results including actual computed costs.
        This enables accurate chart generation and experiment analysis.

        Args:
            agent_id: Agent that was evaluated.
            evaluation_mode: "deterministic" or "bootstrap".
            proposed_policy: The proposed policy that was evaluated.
            old_cost: ACTUAL mean cost with old policy (from evaluation).
            new_cost: ACTUAL mean cost with new policy (from evaluation).
            context_simulation_cost: Cost from context simulation (for comparison).
            accepted: Whether the policy was accepted.
            acceptance_reason: Reason for acceptance/rejection.
            delta_sum: Sum of deltas across samples.
            num_samples: Number of samples in evaluation (1 for deterministic).
            sample_details: Per-sample details for bootstrap mode (None for deterministic).
            scenario_seed: Seed used for deterministic mode (None for bootstrap).
            settlement_rate: System-wide settlement rate (0.0 to 1.0).
            avg_delay: System-wide average delay in ticks.
            cost_breakdown: Total cost breakdown by type.
            cost_std_dev: Standard deviation of costs (bootstrap only).
            confidence_interval_95: 95% CI bounds [lower, upper] (bootstrap only).
            agent_stats: Per-agent metrics keyed by agent_id.
        """
        if self._repository is None:
            return

        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id=self._run_id,
            iteration=self._current_iteration - 1,  # 0-indexed in storage
            agent_id=agent_id,
            evaluation_mode=evaluation_mode,
            proposed_policy=proposed_policy,
            old_cost=old_cost,
            new_cost=new_cost,
            context_simulation_cost=context_simulation_cost,
            accepted=accepted,
            acceptance_reason=acceptance_reason,
            delta_sum=delta_sum,
            num_samples=num_samples,
            sample_details=sample_details,
            scenario_seed=scenario_seed,
            timestamp=datetime.now().isoformat(),
            # Extended metrics
            settlement_rate=settlement_rate,
            avg_delay=avg_delay,
            cost_breakdown=cost_breakdown,
            cost_std_dev=cost_std_dev,
            confidence_interval_95=confidence_interval_95,
            agent_stats=agent_stats,
        )
        self._repository.save_policy_evaluation(record)

    def _save_llm_interaction_event(self, agent_id: str) -> None:
        """Save LLM interaction event for audit replay.

        Extracts the last interaction from the LLM client and persists it
        to the repository for audit replay purposes.

        Args:
            agent_id: Agent that was optimized.
        """
        if self._repository is None:
            return

        if self._llm_client is None:
            return

        # Get the last interaction from the LLM client
        interaction = self._llm_client.get_last_interaction()
        if interaction is None:
            return

        from payment_simulator.ai_cash_mgmt.events import create_llm_interaction_event

        event = create_llm_interaction_event(
            run_id=self._run_id,
            iteration=self._current_iteration - 1,  # 0-indexed
            agent_id=agent_id,
            system_prompt=interaction.system_prompt,
            user_prompt=interaction.user_prompt,
            raw_response=interaction.raw_response,
            parsed_policy=interaction.parsed_policy,
            parsing_error=interaction.parsing_error,
            model=self._config.llm.model,
            prompt_tokens=interaction.prompt_tokens,
            completion_tokens=interaction.completion_tokens,
            latency_seconds=interaction.latency_seconds,
        )

        # Persist to database
        self._repository.save_event(event)

        # Also record in state provider for live retrieval
        self._state_provider.record_event(
            iteration=self._current_iteration - 1,
            event_type="llm_interaction",
            event_data={
                "agent_id": agent_id,
                "system_prompt": interaction.system_prompt,
                "user_prompt": interaction.user_prompt,
                "raw_response": interaction.raw_response,
                "parsed_policy": interaction.parsed_policy,
                "parsing_error": interaction.parsing_error,
                "model": self._config.llm.model,
                "prompt_tokens": interaction.prompt_tokens,
                "completion_tokens": interaction.completion_tokens,
                "latency_seconds": interaction.latency_seconds,
            },
        )

    def _load_scenario_config(self) -> dict[str, Any]:
        """Load scenario configuration from YAML file.

        Resolves the scenario path relative to the experiment config directory.

        Returns:
            Scenario configuration dictionary.

        Raises:
            FileNotFoundError: If scenario file doesn't exist.
        """
        if self._scenario_dict is not None:
            return self._scenario_dict

        scenario_path = self._config.scenario_path
        if not scenario_path.is_absolute():
            scenario_path = self._config_dir / scenario_path

        if not scenario_path.exists():
            msg = f"Scenario file not found: {scenario_path}"
            raise FileNotFoundError(msg)

        with open(scenario_path) as f:
            self._scenario_dict = yaml.safe_load(f)

        return self._scenario_dict

    def _get_scenario_builder(self) -> StandardScenarioConfigBuilder:
        """Get the scenario config builder, creating it lazily if needed.

        Uses StandardScenarioConfigBuilder for canonical agent configuration extraction.
        This ensures identical scenario interpretation across all code paths
        (Scenario Config Interpretation Identity invariant - INV-10).

        Returns:
            StandardScenarioConfigBuilder instance.
        """
        if self._scenario_builder is None:
            scenario = self._load_scenario_config()
            self._scenario_builder = StandardScenarioConfigBuilder(scenario)
        return self._scenario_builder

    def _build_simulation_config(self) -> dict[str, Any]:
        """Build FFI-compatible simulation config with current policies.

        Merges the base scenario config with current agent policies.

        Returns:
            FFI-compatible configuration dictionary.
        """
        import copy
        import json

        # Deep copy to avoid mutating the cached scenario config
        scenario_dict = copy.deepcopy(self._load_scenario_config())

        # Update agent policies in the scenario
        if "agents" in scenario_dict:
            for agent_config in scenario_dict["agents"]:
                agent_id = agent_config.get("id")
                if agent_id in self._policies:
                    policy = self._policies[agent_id]

                    # Extract policy parameters using canonical builder
                    # (Policy Evaluation Identity invariant)
                    if isinstance(policy, dict):
                        liquidity_config = self._policy_builder.extract_liquidity_config(
                            policy=policy,
                            agent_config=agent_config,
                        )
                        # Apply extracted fraction if present
                        fraction = liquidity_config.get("liquidity_allocation_fraction")
                        if fraction is not None:
                            agent_config["liquidity_allocation_fraction"] = fraction

                    # Wrap tree policy in InlineJsonPolicy format for Pydantic
                    # Tree policies have "payment_tree" field; simple policies have "type"
                    if isinstance(policy, dict) and "payment_tree" in policy:
                        agent_config["policy"] = {
                            "type": "InlineJson",
                            "json_string": json.dumps(policy),
                        }
                    else:
                        agent_config["policy"] = policy

        # Convert to FFI format
        sim_config = SimulationConfig.from_dict(scenario_dict)
        return sim_config.to_ffi_dict()

    def _format_events_for_llm(
        self,
        events: list[dict[str, Any]],
        max_events: int = 500,
    ) -> str:
        """Format simulation events into human-readable verbose output for LLM.

        Creates a compact but informative text representation of simulation events
        suitable for LLM context. Prioritizes informative events (policy decisions,
        cost accruals, settlements) over routine events.

        Args:
            events: List of event dicts from simulation.
            max_events: Maximum events to include (prevents context bloat).

        Returns:
            Formatted string with one event per line.
        """
        if not events:
            return "(No events captured)"

        # Priority map for event informativeness (higher = more important)
        priority_map = {
            "PolicyDecision": 100,
            "DelayCostAccrual": 80,
            "OverdraftCostAccrual": 80,
            "DeadlinePenalty": 90,
            "EndOfDayPenalty": 90,
            "RtgsImmediateSettlement": 50,
            "Queue2LiquidityRelease": 50,
            "LsmBilateralOffset": 50,
            "LsmCycleSettlement": 50,
            "TransactionArrival": 30,
            "Arrival": 30,
        }

        def get_priority(event: dict[str, Any]) -> int:
            return priority_map.get(event.get("event_type", ""), 10)

        # Sort by priority, take top N, then sort chronologically
        sorted_events = sorted(events, key=get_priority, reverse=True)[:max_events]
        sorted_events = sorted(sorted_events, key=lambda e: e.get("tick", 0))

        # Format each event
        lines = []
        for event in sorted_events:
            tick = event.get("tick", "?")
            event_type = event.get("event_type", "Unknown")
            details = self._format_event_details_for_llm(event)
            lines.append(f"[tick {tick}] {event_type}: {details}")

        return "\n".join(lines)

    def _format_event_details_for_llm(self, event: dict[str, Any]) -> str:
        """Format event details into a compact string for LLM.

        Args:
            event: Event dict to format.

        Returns:
            Compact string representation of key event details.
        """
        # Key fields to show (most informative for LLM)
        key_fields = [
            "tx_id",
            "action",
            "amount",
            "cost",
            "agent_id",
            "sender_id",
            "receiver_id",
        ]
        parts = []

        for key in key_fields:
            if key in event:
                value = event[key]
                # Format amounts/costs as currency (integer cents -> dollars)
                if key in ("amount", "cost") and isinstance(value, int):
                    parts.append(f"{key}=${value / 100:.2f}")
                else:
                    parts.append(f"{key}={value}")

        # If no key fields found, show first few available fields
        if not parts:
            other_keys = [k for k in event if k not in ("tick", "event_type")][:3]
            parts = [f"{k}={event[k]}" for k in other_keys]

        return ", ".join(parts) if parts else "(no details)"

    def _run_initial_simulation(self) -> InitialSimulationResult:
        """Run ONE initial simulation to collect historical transactions.

        This method runs ONCE at the start of optimization (not every iteration)
        for bootstrap mode. It:
        1. Runs a full simulation with stochastic arrivals (via _run_simulation)
        2. Collects ALL events that occurred
        3. Builds transaction history for each agent using TransactionHistoryCollector
        4. Returns data needed for bootstrap resampling

        Returns:
            InitialSimulationResult with events, history, and costs.

        Note:
            This is different from _run_single_simulation() which is used for
            Monte Carlo sampling. The initial simulation provides the empirical
            distribution from which bootstrap samples are drawn.
        """
        # Run simulation using unified method
        # _run_simulation handles: ID generation, verbose logging, event capture,
        # cost extraction, and persistence
        # This IS a primary simulation - persists by default when repository exists
        result = self._run_simulation(
            seed=self._config.master_seed,
            purpose="init",
            iteration=0,
            is_primary=True,
        )

        # Build transaction history from events (initial simulation specific)
        collector = TransactionHistoryCollector()
        collector.process_events(list(result.events))

        # Get history per agent
        agent_histories = {
            agent_id: collector.get_agent_history(agent_id)
            for agent_id in self.optimized_agents
        }

        # Use verbose output from SimulationResult (pretty-formatted by format_tick_range_as_text)
        # Fall back to old formatting if pretty formatting is not available
        verbose_output = result.verbose_output
        if verbose_output is None:
            # Fallback: use legacy formatting
            verbose_output = self._format_events_for_llm(list(result.events))

        return InitialSimulationResult(
            events=result.events,
            agent_histories=agent_histories,
            total_cost=result.total_cost,
            per_agent_costs=result.per_agent_costs,
            verbose_output=verbose_output,
        )

    def _create_bootstrap_samples(self) -> None:
        """Create bootstrap samples from initial simulation history.

        This is called once after _run_initial_simulation() completes.
        It uses the BootstrapSampler to create resampled transaction schedules
        for each agent.
        """
        if self._initial_sim_result is None:
            msg = "Cannot create bootstrap samples without initial simulation result"
            raise RuntimeError(msg)

        # Create sampler with deterministic seed
        self._bootstrap_sampler = BootstrapSampler(seed=self._config.master_seed)

        num_samples = self._config.evaluation.num_samples or 1
        total_ticks = self._config.evaluation.ticks

        for agent_id in self.optimized_agents:
            history = self._initial_sim_result.agent_histories.get(agent_id)
            if history is None:
                self._bootstrap_samples[agent_id] = []
                continue

            # Generate bootstrap samples for this agent
            samples = self._bootstrap_sampler.generate_samples(
                agent_id=agent_id,
                n_samples=num_samples,
                outgoing_records=history.outgoing,
                incoming_records=history.incoming,
                total_ticks=total_ticks,
            )
            self._bootstrap_samples[agent_id] = list(samples)

    def _run_single_simulation(self, seed: int) -> tuple[int, dict[str, int]]:
        """Run a single simulation with the given seed.

        Args:
            seed: RNG seed for this simulation.

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.
        """
        # Build config with current policies
        ffi_config = self._build_simulation_config()

        # Override seed
        ffi_config["rng_seed"] = seed

        # Create orchestrator
        orch = Orchestrator.new(ffi_config)

        # Run simulation for the configured number of ticks
        total_ticks = self._config.evaluation.ticks
        for _ in range(total_ticks):
            orch.tick()

        # Extract total cost and per-agent costs
        total_cost = 0
        per_agent_costs: dict[str, int] = {}

        for agent_id in self.optimized_agents:
            try:
                agent_costs = orch.get_agent_accumulated_costs(agent_id)
                agent_total = int(agent_costs.get("total_cost", 0))
                per_agent_costs[agent_id] = agent_total
                total_cost += agent_total
            except Exception:
                per_agent_costs[agent_id] = 0

        return total_cost, per_agent_costs

    def _run_simulation_with_events(
        self,
        seed: int,
        sample_idx: int,
        *,
        purpose: str | None = None,
        is_primary: bool = False,
    ) -> EnrichedEvaluationResult:
        """Run a simulation and capture events for LLM context.

        This method delegates to _run_simulation() for the core simulation
        execution, then transforms the result into an EnrichedEvaluationResult
        suitable for use with EnrichedBootstrapContextBuilder.

        Args:
            seed: RNG seed for this simulation.
            sample_idx: Index of this sample in the bootstrap set.
            purpose: Purpose tag for simulation ID. If None, derives from
                evaluation mode ("eval" for deterministic, "bootstrap" for
                bootstrap mode).
            is_primary: If True, this is a primary simulation that should
                persist by default. If False, only persists with --persist-bootstrap.

        Returns:
            EnrichedEvaluationResult with event trace and cost breakdown.
        """
        # Derive purpose from evaluation mode if not specified
        if purpose is None:
            eval_mode = self._config.evaluation.mode
            # All deterministic modes (deterministic-temporal, deterministic-pairwise) use "eval"
            purpose = "eval" if eval_mode.startswith("deterministic") else "bootstrap"

        # Run simulation using unified method
        result = self._run_simulation(
            seed=seed,
            purpose=purpose,
            sample_idx=sample_idx,
            is_primary=is_primary,
        )

        # Transform raw events to BootstrapEvent objects
        bootstrap_events: list[BootstrapEvent] = []
        for event in result.events:
            bootstrap_event = BootstrapEvent(
                tick=event.get("tick", 0),
                event_type=event.get("event_type", "unknown"),
                details=event,
            )
            bootstrap_events.append(bootstrap_event)

        # Return EnrichedEvaluationResult with transformed events
        return EnrichedEvaluationResult(
            sample_idx=sample_idx,
            seed=seed,
            total_cost=result.total_cost,
            settlement_rate=result.settlement_rate,
            avg_delay=result.avg_delay,
            event_trace=tuple(bootstrap_events),
            cost_breakdown=result.cost_breakdown,
            per_agent_costs=result.per_agent_costs,  # Pass through for accurate per-agent reporting
        )

    def _build_agent_contexts(
        self, enriched_results: list[EnrichedEvaluationResult]
    ) -> dict[str, AgentSimulationContext]:
        """Build per-agent contexts from enriched evaluation results.

        Uses EnrichedBootstrapContextBuilder to create AgentSimulationContext
        for each optimized agent, which includes best/worst seed identification
        and formatted event traces for LLM consumption.

        Args:
            enriched_results: List of EnrichedEvaluationResult from bootstrap samples.

        Returns:
            Dict mapping agent_id to AgentSimulationContext.
        """
        agent_contexts: dict[str, AgentSimulationContext] = {}

        for agent_id in self.optimized_agents:
            try:
                # Create context builder for this agent
                builder = EnrichedBootstrapContextBuilder(
                    results=enriched_results,
                    agent_id=agent_id,
                )

                # Build the context (includes best/worst seed analysis)
                context = builder.build_agent_context()
                agent_contexts[agent_id] = context

            except Exception:
                # If building fails, create a minimal context
                agent_contexts[agent_id] = AgentSimulationContext(
                    agent_id=agent_id,
                    best_seed=0,
                    best_seed_cost=0,
                    best_seed_output=None,
                    worst_seed=0,
                    worst_seed_cost=0,
                    worst_seed_output=None,
                    mean_cost=0,
                    cost_std=0,
                )

        # Build BootstrapLLMContext combining initial simulation with best/worst
        # This provides 3 streams for LLM: initial sim (Stream 1), best (Stream 2), worst (Stream 3)
        if self._initial_sim_result is not None:
            for agent_id, agent_ctx in agent_contexts.items():
                # Get initial simulation cost for this agent
                initial_cost = self._initial_sim_result.per_agent_costs.get(agent_id, 0)

                # CRITICAL: Filter initial simulation events for agent isolation
                # Agent X must ONLY see their own events, not other agents' events
                initial_events = list(self._initial_sim_result.events)
                filtered_events = filter_events_for_agent(agent_id, initial_events)
                filtered_output = format_filtered_output(
                    agent_id, filtered_events, include_tick_headers=True
                )

                self._bootstrap_llm_contexts[agent_id] = BootstrapLLMContext(
                    agent_id=agent_id,
                    initial_simulation_output=filtered_output,
                    initial_simulation_cost=initial_cost,
                    best_seed=agent_ctx.best_seed,
                    best_seed_cost=agent_ctx.best_seed_cost,
                    best_seed_output=agent_ctx.best_seed_output,
                    worst_seed=agent_ctx.worst_seed,
                    worst_seed_cost=agent_ctx.worst_seed_cost,
                    worst_seed_output=agent_ctx.worst_seed_output,
                    mean_cost=agent_ctx.mean_cost,
                    cost_std=agent_ctx.cost_std,
                    num_samples=len(enriched_results),
                )

        return agent_contexts

    async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
        """Evaluate current policies using bootstrap resampling.

        For deterministic mode: runs a single simulation.
        For bootstrap mode: evaluates policy on pre-computed bootstrap samples
        (resampled from the initial simulation's transaction history).

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.
            In bootstrap mode, these are the MEAN costs across all samples.

        Side effects:
            - Sets self._current_enriched_results for LLM context
            - Sets self._current_agent_contexts for per-agent optimization
        """
        eval_mode = self._config.evaluation.mode
        num_samples = self._config.evaluation.num_samples or 1

        if eval_mode.startswith("deterministic") or num_samples <= 1:
            # Single simulation - deterministic mode (temporal or pairwise)
            # Use iteration seed for consistency with _evaluate_policy_pair
            # (INV-9: Policy Evaluation Identity - displayed cost must match acceptance cost)
            iteration_idx = self._current_iteration - 1  # 0-indexed
            # Use first optimized agent for seed derivation in single-agent case
            # For multi-agent, this provides consistent baseline across all agents
            agent_id = self.optimized_agents[0]
            seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)
            # This IS the primary simulation - should persist by default
            enriched = self._run_simulation_with_events(
                seed, sample_idx=0, is_primary=True
            )

            # Store for LLM context
            self._current_enriched_results = [enriched]
            self._current_agent_contexts = self._build_agent_contexts([enriched])

            # Extract per-agent costs
            per_agent_costs: dict[str, int] = {}
            for agent_id in self.optimized_agents:
                # Use cost breakdown for per-agent costs in deterministic mode
                ctx = self._current_agent_contexts.get(agent_id)
                if ctx:
                    per_agent_costs[agent_id] = ctx.mean_cost
                else:
                    per_agent_costs[agent_id] = 0

            return enriched.total_cost, per_agent_costs

        # Bootstrap mode: evaluate current policy on pre-computed bootstrap samples
        # These samples were created from the initial simulation's transaction history
        # by _create_bootstrap_samples() at experiment start.
        enriched_results: list[EnrichedEvaluationResult] = []
        total_costs: list[int] = []
        seed_results: list[dict[str, Any]] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self.optimized_agents
        }
        bootstrap_results: list[BootstrapSampleResult] = []

        # Evaluate each agent's current policy on their bootstrap samples
        for agent_id in self.optimized_agents:
            samples = self._bootstrap_samples.get(agent_id, [])
            if not samples:
                continue

            # Get current policy for this agent
            current_policy = self._policies.get(agent_id, {})

            # Create evaluator with agent config (same as in _evaluate_policy_pair)
            agent_config = self._get_scenario_builder().extract_agent_config(agent_id)
            evaluator = BootstrapPolicyEvaluator(
                opening_balance=agent_config.opening_balance,
                credit_limit=agent_config.credit_limit,
                cost_rates=self._cost_rates,
                max_collateral_capacity=agent_config.max_collateral_capacity,
                liquidity_pool=agent_config.liquidity_pool,
            )

            # Evaluate current policy on all bootstrap samples
            eval_results = evaluator.evaluate_samples(samples, current_policy)

            # Collect results for this agent
            for result in eval_results:
                cost = result.total_cost
                total_costs.append(cost)
                per_agent_totals[agent_id].append(cost)

                # Build EnrichedEvaluationResult for context building
                # Note: event_trace is empty - LLM context comes from initial simulation
                enriched = EnrichedEvaluationResult(
                    sample_idx=result.sample_idx,
                    seed=result.seed,
                    total_cost=cost,
                    settlement_rate=result.settlement_rate,
                    avg_delay=result.avg_delay,
                    event_trace=(),  # Events come from initial simulation
                    cost_breakdown=None,
                    per_agent_costs={agent_id: cost},
                )
                enriched_results.append(enriched)

                # Collect for verbose logging
                bootstrap_results.append(
                    BootstrapSampleResult(
                        seed=result.seed,
                        cost=cost,
                        settled=int(result.settlement_rate * 100),
                        total=100,
                        settlement_rate=result.settlement_rate,
                        baseline_cost=None,
                    )
                )

                # Track for state provider event
                seed_results.append(
                    {
                        "seed": result.seed,
                        "cost": cost,
                        "settled": int(result.settlement_rate * 100),
                        "total": 100,
                        "settlement_rate": result.settlement_rate,
                    }
                )

        # Store enriched results for LLM context
        # Note: _build_agent_contexts uses self._initial_sim_result for event traces
        self._current_enriched_results = enriched_results
        self._current_agent_contexts = self._build_agent_contexts(enriched_results)

        # Compute mean and std costs (as integers)
        mean_total = int(sum(total_costs) / len(total_costs))
        variance = sum((c - mean_total) ** 2 for c in total_costs) / len(total_costs)
        std_total = int(variance**0.5)
        mean_per_agent = {
            agent_id: int(sum(costs) / len(costs))
            for agent_id, costs in per_agent_totals.items()
        }

        # Log bootstrap evaluation summary (verbose logging)
        if (
            self._verbose_logger
            and self._verbose_config.bootstrap
            and bootstrap_results
        ):
            std_cost = (
                int(stats_module.stdev(total_costs)) if len(total_costs) > 1 else 0
            )
            self._verbose_logger.log_bootstrap_evaluation(
                seed_results=bootstrap_results,
                mean_cost=mean_total,
                std_cost=std_cost,
                deterministic=False,
                is_baseline_run=(self._current_iteration == 1),
            )

        # Record bootstrap evaluation event (state provider)
        self._state_provider.record_event(
            iteration=self._current_iteration - 1,  # 0-indexed
            event_type="bootstrap_evaluation",
            event_data={
                "seed_results": seed_results,
                "mean_cost": mean_total,
                "std_cost": std_total,
            },
        )

        return mean_total, mean_per_agent

    def _evaluate_policy_pair(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
    ) -> PolicyPairEvaluation:
        """Evaluate old vs new policy with paired bootstrap samples.

        Uses SeedMatrix to get agent-specific bootstrap seeds for the current
        iteration. Each sample is run twice (once with old policy, once with new)
        to compute paired deltas.

        This method MUST be called AFTER policy generation (not before).

        Args:
            agent_id: Agent to evaluate for.
            old_policy: Current policy to compare against.
            new_policy: Proposed new policy from LLM.

        Returns:
            PolicyPairEvaluation with actual computed costs (not estimates).
        """
        # Use 0-indexed iteration for SeedMatrix
        iteration_idx = self._current_iteration - 1
        num_samples = self._config.evaluation.num_samples or 1

        # Handle deterministic mode (temporal or pairwise) - single sample
        if self._config.evaluation.mode.startswith("deterministic") or num_samples <= 1:
            # Use iteration seed directly
            seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

            # Evaluate old policy
            self._policies[agent_id] = old_policy
            _, old_costs = self._run_single_simulation(seed)
            old_cost = old_costs.get(agent_id, 0)

            # Evaluate new policy - use _run_simulation to get extended metrics
            # This is a policy comparison simulation, NOT a primary simulation
            self._policies[agent_id] = new_policy
            new_sim_result = self._run_simulation(
                seed=seed,
                purpose="eval",
                iteration=iteration_idx,
                sample_idx=0,
                is_primary=False,  # Policy comparison - only persists with --persist-bootstrap
            )
            new_cost = new_sim_result.per_agent_costs.get(agent_id, 0)

            # CRITICAL: Restore old policy - caller will set new policy if accepted
            self._policies[agent_id] = old_policy

            delta = old_cost - new_cost

            # Extract extended metrics from the new policy simulation result
            cost_breakdown = {
                "delay_cost": new_sim_result.cost_breakdown.delay_cost,
                "overdraft_cost": new_sim_result.cost_breakdown.overdraft_cost,
                "deadline_penalty": new_sim_result.cost_breakdown.deadline_penalty,
                "eod_penalty": new_sim_result.cost_breakdown.eod_penalty,
            }

            # Build per-agent stats (deterministic: no std_dev or CI)
            agent_stats: dict[str, dict[str, Any]] = {}
            for aid, cost in new_sim_result.per_agent_costs.items():
                agent_stats[aid] = {
                    "cost": cost,
                    "settlement_rate": new_sim_result.settlement_rate,
                    "avg_delay": new_sim_result.avg_delay,
                    "cost_breakdown": cost_breakdown,  # Same as total for single agent
                    "std_dev": None,  # N=1, no std_dev
                    "ci_95_lower": None,  # N=1, no CI
                    "ci_95_upper": None,  # N=1, no CI
                }

            # Return PolicyPairEvaluation with ACTUAL costs and extended metrics
            return PolicyPairEvaluation(
                sample_results=[
                    SampleEvaluationResult(
                        sample_index=0,
                        seed=seed,
                        old_cost=old_cost,
                        new_cost=new_cost,
                        delta=delta,
                    )
                ],
                delta_sum=delta,
                mean_old_cost=old_cost,
                mean_new_cost=new_cost,
                settlement_rate=new_sim_result.settlement_rate,
                avg_delay=new_sim_result.avg_delay,
                cost_breakdown=cost_breakdown,
                agent_stats=agent_stats,
            )

        # Real bootstrap mode: use pre-computed bootstrap samples
        # This is the correct bootstrap approach - resampling from historical data
        # Design decision: NO fallback to Monte Carlo (see phase_7b.md)
        if self._bootstrap_samples and agent_id in self._bootstrap_samples:
            samples = self._bootstrap_samples[agent_id]
            if samples:
                # Use ScenarioConfigBuilder for canonical agent config extraction
                # Ensures identical scenario interpretation (INV-10)
                agent_config = self._get_scenario_builder().extract_agent_config(agent_id)
                evaluator = BootstrapPolicyEvaluator(
                    opening_balance=agent_config.opening_balance,
                    credit_limit=agent_config.credit_limit,
                    cost_rates=self._cost_rates,
                    max_collateral_capacity=agent_config.max_collateral_capacity,
                    liquidity_pool=agent_config.liquidity_pool,
                )
                paired_deltas = evaluator.compute_paired_deltas(
                    samples=samples,
                    policy_a=old_policy,
                    policy_b=new_policy,
                )

                # Build sample results with ACTUAL costs from bootstrap evaluation
                sample_results = [
                    SampleEvaluationResult(
                        sample_index=pd.sample_idx,
                        seed=pd.seed,
                        old_cost=pd.cost_a,  # cost_a = old policy cost
                        new_cost=pd.cost_b,  # cost_b = new policy cost
                        delta=pd.delta,
                    )
                    for pd in paired_deltas
                ]

                n = len(paired_deltas)
                delta_sum = sum(pd.delta for pd in paired_deltas)
                mean_old_cost = sum(pd.cost_a for pd in paired_deltas) // n
                mean_new_cost = sum(pd.cost_b for pd in paired_deltas) // n

                # Extract extended metrics from initial simulation (representative)
                # Note: Per-sample metrics not captured per user request
                boot_settlement_rate: float | None = None
                boot_avg_delay: float | None = None
                boot_cost_breakdown: dict[str, int] | None = None

                if self._initial_sim_result:
                    # Use initial simulation as representative for system metrics
                    init_result = self._initial_sim_result
                    boot_settlement_rate = getattr(init_result, "settlement_rate", None)
                    boot_avg_delay = getattr(init_result, "avg_delay", None)

                # Phase 3: Compute derived statistics from sample costs
                new_costs = [pd.cost_b for pd in paired_deltas]
                cost_stats = compute_cost_statistics(new_costs)

                boot_cost_std_dev = cost_stats["std_dev"]
                boot_confidence_interval_95: list[int] | None = None
                ci_lower = cost_stats["ci_95_lower"]
                ci_upper = cost_stats["ci_95_upper"]
                if ci_lower is not None and ci_upper is not None:
                    boot_confidence_interval_95 = [ci_lower, ci_upper]

                # Build per-agent stats for bootstrap mode with computed statistics
                boot_agent_stats: dict[str, dict[str, Any]] = {}

                for aid in self.optimized_agents:
                    # Get per-agent costs from samples if available
                    agent_mean_cost = mean_new_cost  # Default to total mean
                    boot_agent_stats[aid] = {
                        "cost": agent_mean_cost,
                        "settlement_rate": boot_settlement_rate,
                        "avg_delay": boot_avg_delay,
                        "cost_breakdown": None,  # Not available per-agent
                        "std_dev": boot_cost_std_dev,  # Same as total (single agent)
                        "ci_95_lower": cost_stats["ci_95_lower"],
                        "ci_95_upper": cost_stats["ci_95_upper"],
                    }

                return PolicyPairEvaluation(
                    sample_results=sample_results,
                    delta_sum=delta_sum,
                    mean_old_cost=mean_old_cost,
                    mean_new_cost=mean_new_cost,
                    settlement_rate=boot_settlement_rate,
                    avg_delay=boot_avg_delay,
                    cost_breakdown=boot_cost_breakdown,
                    cost_std_dev=boot_cost_std_dev,
                    confidence_interval_95=boot_confidence_interval_95,
                    agent_stats=boot_agent_stats,
                )

        # No samples available - this is an error in bootstrap mode
        # Bootstrap samples should be created by _run_initial_simulation() at start
        msg = f"No bootstrap samples available for agent {agent_id}"
        raise RuntimeError(msg)

    async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
        """Optimize policy for a single agent using PolicyOptimizer with rich context.

        Uses PolicyOptimizer to generate improved policies with:
        - Best/worst seed verbose outputs for LLM analysis
        - Cost breakdown by type (delay, collateral, overdraft, etc.)
        - Full iteration history with acceptance status
        - Parameter trajectory visualization

        In temporal mode, uses cross-iteration comparison instead of within-iteration
        paired evaluation. This is simpler and matches game-like learning.

        Args:
            agent_id: Agent to optimize.
            current_cost: Current cost for this agent in integer cents.
        """
        # Handle temporal mode separately (simpler flow)
        if self._config.evaluation.is_deterministic_temporal:
            await self._optimize_agent_temporal(agent_id, current_cost)
            return

        # Skip LLM optimization if no constraints (required for dynamic prompt)
        if self._constraints is None:
            return

        # Lazy initialize LLM client and PolicyOptimizer
        if self._llm_client is None:
            from payment_simulator.experiments.runner.llm_client import (
                ExperimentLLMClient,
            )

            self._llm_client = ExperimentLLMClient(self._config.llm)

        if self._policy_optimizer is None:
            self._policy_optimizer = PolicyOptimizer(
                constraints=self._constraints,
                max_retries=self._config.llm.max_retries,
            )

        # Get agent-specific customization (if configured)
        agent_customization: str | None = None
        if self._config.prompt_customization is not None:
            agent_customization = self._config.prompt_customization.get_for_agent(
                agent_id
            )

        # Build and inject dynamic system prompt with agent-specific customization
        dynamic_prompt = self._policy_optimizer.get_system_prompt(
            cost_rates=self._cost_rates,
            customization=agent_customization,
        )
        self._llm_client.set_system_prompt(dynamic_prompt)

        # Get current policy
        current_policy = self._policies.get(
            agent_id, self._create_default_policy(agent_id)
        )

        # Get agent context from current evaluation (includes best/worst seed)
        agent_context = self._current_agent_contexts.get(agent_id)

        # INV-12: LLM Context Identity - All modes show only best_seed_output
        # This ensures identical context format across bootstrap, pairwise, and temporal.
        # The initial simulation stream was removed as it's stale after iteration 1
        # and creates inconsistency with deterministic modes.
        combined_best_output: str | None = None
        if agent_context and agent_context.best_seed_output:
            combined_best_output = agent_context.best_seed_output

        # Build cost breakdown dict for LLM context
        cost_breakdown: dict[str, int] | None = None
        # Extract events from enriched results for agent isolation filtering
        # Events are converted from BootstrapEvent to dict format
        collected_events: list[dict[str, Any]] | None = None
        if self._current_enriched_results:
            # Aggregate cost breakdown across all samples
            total_delay = sum(
                r.cost_breakdown.delay_cost for r in self._current_enriched_results
            )
            total_overdraft = sum(
                r.cost_breakdown.overdraft_cost for r in self._current_enriched_results
            )
            total_deadline = sum(
                r.cost_breakdown.deadline_penalty
                for r in self._current_enriched_results
            )
            total_eod = sum(
                r.cost_breakdown.eod_penalty for r in self._current_enriched_results
            )
            num_samples = len(self._current_enriched_results)
            cost_breakdown = {
                "delay_cost": total_delay // num_samples,
                "overdraft_cost": total_overdraft // num_samples,
                "deadline_penalty": total_deadline // num_samples,
                "eod_penalty": total_eod // num_samples,
            }

            # Extract events from ONLY best and worst samples (not all 50)
            # This prevents LLM context from exceeding token limits
            # Events are filtered by agent in the PolicyOptimizer
            collected_events = []
            best_result = min(
                self._current_enriched_results, key=lambda r: r.total_cost
            )
            worst_result = max(
                self._current_enriched_results, key=lambda r: r.total_cost
            )
            for result in [best_result, worst_result]:
                for event in result.event_trace:
                    collected_events.append(
                        {
                            "tick": event.tick,
                            "event_type": event.event_type,
                            **event.details,
                        }
                    )

        # Build current metrics dict
        current_metrics = {
            "total_cost_mean": current_cost,
            "iteration": self._current_iteration,
        }
        if agent_context:
            current_metrics["best_seed_cost"] = agent_context.best_seed_cost
            current_metrics["worst_seed_cost"] = agent_context.worst_seed_cost
            current_metrics["cost_std"] = agent_context.cost_std

        # Create debug callback if verbose logging enabled
        debug_callback: DebugCallback | None = None
        if self._verbose_logger and self._verbose_config.debug:
            debug_callback = _VerboseDebugCallback(self._verbose_logger)

        try:
            # Use PolicyOptimizer if available (provides rich context)
            if self._policy_optimizer is not None and agent_context is not None:
                # INV-12: All modes show ONE simulation trace only
                # worst_seed_output is not passed - variance is in statistics
                opt_result = await self._policy_optimizer.optimize(
                    agent_id=agent_id,
                    current_policy=current_policy,
                    current_iteration=self._current_iteration,
                    current_metrics=current_metrics,
                    llm_client=self._llm_client,
                    llm_model=self._config.llm.model,
                    current_cost=float(current_cost),
                    iteration_history=self._agent_iteration_history.get(agent_id),
                    events=collected_events,  # Pass events for agent isolation filtering
                    simulation_trace=combined_best_output,  # INV-12: Single simulation trace
                    sample_seed=agent_context.sample_seed,
                    sample_cost=agent_context.sample_cost,
                    mean_cost=agent_context.mean_cost,
                    cost_std=agent_context.cost_std,
                    cost_breakdown=cost_breakdown,
                    cost_rates=self._cost_rates,
                    debug_callback=debug_callback,
                )

                # Log LLM call metadata (verbose logging)
                if self._verbose_logger and self._verbose_config.llm:
                    # Get actual token counts from LLM client's last interaction
                    interaction = self._llm_client.get_last_interaction()
                    if interaction:
                        prompt_tokens = interaction.prompt_tokens
                        completion_tokens = interaction.completion_tokens
                    else:
                        # Fallback if no interaction recorded
                        prompt_tokens = opt_result.tokens_used
                        completion_tokens = 0

                    self._verbose_logger.log_llm_call(
                        LLMCallMetadata(
                            agent_id=agent_id,
                            model=self._config.llm.model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            latency_seconds=opt_result.llm_latency_seconds,
                            context_summary={
                                "current_cost": current_cost,
                                "best_seed_cost": agent_context.best_seed_cost,
                                "worst_seed_cost": agent_context.worst_seed_cost,
                                "has_verbose_output": agent_context.best_seed_output
                                is not None,
                            },
                        )
                    )

                new_policy = opt_result.new_policy
                validation_errors = opt_result.validation_errors

                # Check if we got a valid policy
                if new_policy is None:
                    # Save LLM interaction even for failed validation (for audit)
                    self._save_llm_interaction_event(agent_id)

                    # Log rejection (verbose logging)
                    if self._verbose_logger and self._verbose_config.rejections:
                        self._verbose_logger.log_rejection(
                            RejectionDetail(
                                agent_id=agent_id,
                                proposed_policy={},
                                validation_errors=validation_errors,
                                rejection_reason="validation_failed",
                            )
                        )
                    return

            else:
                # Fallback to simple LLM call without PolicyOptimizer
                prompt = f"""Optimize policy for agent {agent_id}.
Current cost: ${current_cost / 100:.2f}
Iteration: {self._current_iteration}

Your goal is to minimize total cost while ensuring payments are settled on time.
"""
                context: dict[str, Any] = {
                    "iteration": self._current_iteration,
                    "history": [
                        {"iteration": i + 1, "cost": cost}
                        for i, cost in enumerate(self._iteration_history)
                    ],
                }
                new_policy = await self._llm_client.generate_policy(
                    prompt=prompt,
                    current_policy=current_policy,
                    context=context,
                )

            # Save LLM interaction for audit replay (after both paths)
            self._save_llm_interaction_event(agent_id)

            # Accept/reject based on paired bootstrap evaluation of new policy
            # This runs AFTER policy generation using agent-specific seeds
            # Returns (should_accept, old_cost, new_cost, deltas, delta_sum, evaluation)
            (
                should_accept,
                eval_old_cost,
                eval_new_cost,
                deltas,
                delta_sum,
                evaluation,
            ) = await self._should_accept_policy(
                agent_id=agent_id,
                old_policy=current_policy,
                new_policy=new_policy,
                current_cost=current_cost,
            )

            # Determine mode and mode-specific fields for persistence
            # Both deterministic-temporal and deterministic-pairwise are "deterministic" for storage
            is_deterministic = self._config.evaluation.mode.startswith("deterministic")
            evaluation_mode = "deterministic" if is_deterministic else "bootstrap"

            # Persist policy evaluation with ACTUAL costs and extended metrics
            self._save_policy_evaluation(
                agent_id=agent_id,
                evaluation_mode=evaluation_mode,
                proposed_policy=new_policy,
                old_cost=eval_old_cost,
                new_cost=eval_new_cost,
                context_simulation_cost=current_cost,
                accepted=should_accept,
                acceptance_reason="cost_improved" if should_accept else "cost_not_improved",
                delta_sum=delta_sum,
                num_samples=evaluation.num_samples,
                sample_details=[
                    {
                        "index": s.sample_index,
                        "seed": s.seed,
                        "old_cost": s.old_cost,
                        "new_cost": s.new_cost,
                        "delta": s.delta,
                    }
                    for s in evaluation.sample_results
                ] if not is_deterministic else None,
                scenario_seed=evaluation.sample_results[0].seed if is_deterministic else None,
                # Extended metrics from evaluation (Phase 2: Metrics Capture)
                settlement_rate=evaluation.settlement_rate,
                avg_delay=evaluation.avg_delay,
                cost_breakdown=evaluation.cost_breakdown,
                # Phase 3: Derived statistics (bootstrap only)
                cost_std_dev=evaluation.cost_std_dev,
                confidence_interval_95=evaluation.confidence_interval_95,
                agent_stats=evaluation.agent_stats,
            )

            # Track delta history for progress monitoring
            self._delta_history.append(
                {
                    "iteration": self._current_iteration,
                    "agent_id": agent_id,
                    "deltas": deltas,
                    "delta_sum": delta_sum,
                    "accepted": should_accept,
                }
            )

            # Log bootstrap delta evaluation (verbose logging)
            if self._verbose_logger and self._verbose_config.bootstrap:
                self._verbose_logger.log_bootstrap_deltas(
                    BootstrapDeltaResult(
                        agent_id=agent_id,
                        deltas=deltas,
                        delta_sum=delta_sum,
                        accepted=should_accept,
                        old_policy_mean_cost=eval_old_cost,
                        new_policy_mean_cost=eval_new_cost,
                    )
                )

            if should_accept:
                # Update iteration history BEFORE accepting
                self._record_iteration_history(
                    agent_id=agent_id,
                    policy=new_policy,
                    cost=eval_new_cost,
                    was_accepted=True,
                )
                self._policies[agent_id] = new_policy
                self._accepted_changes[agent_id] = True

                # Log policy change (verbose logging)
                if self._verbose_logger and self._verbose_config.policy:
                    self._verbose_logger.log_policy_change(
                        agent_id=agent_id,
                        old_policy=current_policy,
                        new_policy=new_policy,
                        old_cost=eval_old_cost,
                        new_cost=eval_new_cost,
                        accepted=True,
                    )
            else:
                # Record rejection in history
                self._record_iteration_history(
                    agent_id=agent_id,
                    policy=current_policy,
                    cost=current_cost,
                    was_accepted=False,
                )

                if self._verbose_logger and self._verbose_config.rejections:
                    self._verbose_logger.log_rejection(
                        RejectionDetail(
                            agent_id=agent_id,
                            proposed_policy=new_policy,
                            rejection_reason="cost_not_improved",
                            old_cost=eval_old_cost,
                            new_cost=eval_new_cost,
                        )
                    )

        except Exception as e:
            # Log error - don't silently swallow LLM failures
            error_msg = str(e)

            # Try to save any LLM interaction that occurred before the error
            self._save_llm_interaction_event(agent_id)

            # Record error event (state provider)
            self._state_provider.record_event(
                iteration=self._current_iteration - 1,
                event_type="llm_error",
                event_data={
                    "agent_id": agent_id,
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            # Log error for visibility (verbose or first occurrence)
            if self._verbose_logger and self._verbose_config.llm:
                from rich.console import Console as RichConsole

                console = RichConsole()
                console.print(f"[red]LLM error for {agent_id}: {error_msg}[/red]")

            # Track if this is a critical error (e.g., missing pydantic_ai)
            if "pydantic_ai" in error_msg.lower():
                import warnings

                warnings.warn(
                    f"LLM optimization requires pydantic_ai: {error_msg}. "
                    "Install with: pip install pydantic-ai",
                    stacklevel=2,
                )
            elif "api" in error_msg.lower() or "key" in error_msg.lower():
                import warnings

                warnings.warn(
                    f"LLM API error for {agent_id}: {error_msg}. "
                    "Check your API key configuration.",
                    stacklevel=2,
                )

    async def _optimize_agent_temporal(self, agent_id: str, current_cost: int) -> None:
        """Optimize agent using temporal mode with policy stability tracking.

        In multi-agent temporal mode, policies are always accepted (no cost-based
        rejection). Convergence is detected when ALL agents' initial_liquidity_fraction
        has been stable for stability_window iterations.

        This approach accounts for the fact that the cost landscape changes as
        counterparty policies evolve. A policy that was "optimal" given the old
        counterparty policy may not be optimal after the counterparty changes.

        Flow:
        1. Store current policy for history tracking
        2. Track current policy's initial_liquidity_fraction for stability detection
        3. Generate new policy via LLM (if constraints available)
        4. Always accept the new policy

        Convergence is checked separately via _check_multiagent_convergence() after
        all agents have been optimized for an iteration.

        Args:
            agent_id: Agent to optimize.
            current_cost: Current cost from _evaluate_policies() in integer cents.
        """
        # Get current policy
        current_policy = self._policies.get(
            agent_id, self._create_default_policy(agent_id)
        )

        # Step 1: Store current policy for history (even though we always accept)
        self._previous_policies[agent_id] = current_policy.copy()

        # Step 2: Track the policy fraction for stability detection
        self._track_policy_fraction(agent_id, current_policy)

        # Step 3: Log cost for analysis (but don't use for acceptance)
        self._previous_iteration_costs[agent_id] = current_cost

        # Step 4: Skip LLM if no constraints
        if self._constraints is None:
            self._accepted_changes[agent_id] = True
            return

        # Step 5: Lazy initialize LLM client
        if self._llm_client is None:
            from payment_simulator.experiments.runner.llm_client import (
                ExperimentLLMClient,
            )

            self._llm_client = ExperimentLLMClient(self._config.llm)

        if self._policy_optimizer is None:
            self._policy_optimizer = PolicyOptimizer(
                constraints=self._constraints,
                max_retries=self._config.llm.max_retries,
            )

        # Build and inject dynamic system prompt
        dynamic_prompt = self._policy_optimizer.get_system_prompt(
            cost_rates=self._cost_rates,
            customization=None,  # Temporal mode doesn't use agent customization
        )
        self._llm_client.set_system_prompt(dynamic_prompt)

        # INV-12: LLM Context Identity - Temporal mode MUST provide simulation
        # context to the LLM, just like bootstrap and pairwise modes do.
        # Get agent context from current evaluation (populated by _evaluate_policies)
        agent_context = self._current_agent_contexts.get(agent_id)

        # Build simulation output for LLM (same as deterministic-pairwise fallback)
        # Temporal mode has no bootstrap initial simulation, so just use best_seed_output
        combined_best_output: str | None = None
        if agent_context and agent_context.best_seed_output:
            combined_best_output = agent_context.best_seed_output

        # Build cost breakdown from enriched results
        cost_breakdown: dict[str, int] | None = None
        collected_events: list[dict[str, Any]] | None = None
        if self._current_enriched_results:
            # Aggregate cost breakdown (for single sample, this is just the sample's breakdown)
            total_delay = sum(
                r.cost_breakdown.delay_cost for r in self._current_enriched_results
            )
            total_overdraft = sum(
                r.cost_breakdown.overdraft_cost for r in self._current_enriched_results
            )
            total_deadline = sum(
                r.cost_breakdown.deadline_penalty
                for r in self._current_enriched_results
            )
            total_eod = sum(
                r.cost_breakdown.eod_penalty for r in self._current_enriched_results
            )
            num_samples = len(self._current_enriched_results)
            cost_breakdown = {
                "delay_cost": total_delay // num_samples,
                "overdraft_cost": total_overdraft // num_samples,
                "deadline_penalty": total_deadline // num_samples,
                "eod_penalty": total_eod // num_samples,
            }

            # Extract events for agent isolation filtering
            collected_events = []
            for result in self._current_enriched_results:
                for event in result.event_trace:
                    collected_events.append(
                        {
                            "tick": event.tick,
                            "event_type": event.event_type,
                            **event.details,
                        }
                    )

        # Build current metrics dict
        current_metrics = {
            "total_cost_mean": current_cost,
            "iteration": self._current_iteration,
        }
        if agent_context:
            current_metrics["best_seed_cost"] = agent_context.best_seed_cost
            current_metrics["worst_seed_cost"] = agent_context.worst_seed_cost
            current_metrics["cost_std"] = agent_context.cost_std

        try:
            # Generate new policy via LLM with full simulation context
            # Guard: only call optimize if we have agent context with simulation output
            if agent_context is None:
                # No context available - skip LLM optimization
                self._accepted_changes[agent_id] = True
                return

            # INV-12: All modes show ONE simulation trace only
            opt_result = await self._policy_optimizer.optimize(
                agent_id=agent_id,
                current_policy=current_policy,
                current_iteration=self._current_iteration,
                current_metrics=current_metrics,
                llm_client=self._llm_client,
                llm_model=self._config.llm.model,
                current_cost=float(current_cost),
                iteration_history=self._agent_iteration_history.get(agent_id),
                events=collected_events,  # INV-12: Pass events for agent isolation
                simulation_trace=combined_best_output,  # INV-12: Single simulation trace
                sample_seed=agent_context.sample_seed,
                sample_cost=agent_context.sample_cost,
                mean_cost=agent_context.mean_cost,
                cost_std=agent_context.cost_std,
                cost_breakdown=cost_breakdown,
                cost_rates=self._cost_rates,
                debug_callback=None,
            )

            new_policy = opt_result.new_policy

            if new_policy is None:
                # Validation failed - keep current policy
                self._accepted_changes[agent_id] = True
                return

            # Save LLM interaction event for audit
            self._save_llm_interaction_event(agent_id)

            # Step 6: Always accept the new policy
            self._record_iteration_history(
                agent_id=agent_id,
                policy=new_policy,
                cost=current_cost,
                was_accepted=True,
            )
            self._policies[agent_id] = new_policy
            self._accepted_changes[agent_id] = True

            # Step 7: Update stability tracker with the NEW policy's fraction
            # (We already tracked the current policy earlier, now update with new)
            self._track_policy_fraction(agent_id, new_policy)

            # Log policy change if verbose
            if self._verbose_logger and self._verbose_config.policy:
                self._verbose_logger.log_policy_change(
                    agent_id=agent_id,
                    old_policy=current_policy,
                    new_policy=new_policy,
                    old_cost=self._previous_iteration_costs.get(agent_id, current_cost),
                    new_cost=current_cost,
                    accepted=True,
                )

        except Exception as e:
            # Log error but don't crash
            error_msg = str(e)
            self._save_llm_interaction_event(agent_id)

            if self._verbose_logger and self._verbose_config.llm:
                from rich.console import Console as RichConsole

                console = RichConsole()
                console.print(f"[red]LLM error for {agent_id}: {error_msg}[/red]")

            # On error, keep current state
            self._accepted_changes[agent_id] = True

    def _record_iteration_history(
        self,
        agent_id: str,
        policy: dict[str, Any],
        cost: int,
        was_accepted: bool,
    ) -> None:
        """Record an iteration in the agent's history for LLM context.

        Tracks policy changes, acceptance status, and whether this is
        the best policy so far for this agent.

        Args:
            agent_id: Agent ID.
            policy: Policy used in this iteration.
            cost: Cost achieved in this iteration.
            was_accepted: Whether this policy was accepted.
        """
        # Check if this is the best cost so far for this agent
        previous_best = self._agent_best_costs.get(agent_id)
        is_best_so_far = previous_best is None or cost < previous_best

        if is_best_so_far:
            self._agent_best_costs[agent_id] = cost

        # Compute policy changes from previous iteration
        policy_changes: list[str] = []
        history = self._agent_iteration_history.get(agent_id, [])
        if history:
            prev_policy = history[-1].policy
            policy_changes = self._compute_policy_changes(prev_policy, policy)

        # Build comparison to best
        comparison_to_best = ""
        if previous_best is not None:
            delta = cost - previous_best
            if delta > 0:
                comparison_to_best = f"+${delta / 100:.2f} vs best"
            elif delta < 0:
                comparison_to_best = f"-${abs(delta) / 100:.2f} vs best (NEW BEST)"
            else:
                comparison_to_best = "same as best"

        # Create record
        record = SingleAgentIterationRecord(
            iteration=self._current_iteration,
            metrics={
                "total_cost_mean": cost,
            },
            policy=policy.copy(),
            policy_changes=policy_changes,
            was_accepted=was_accepted,
            is_best_so_far=is_best_so_far,
            comparison_to_best=comparison_to_best,
        )

        # Add to history
        if agent_id not in self._agent_iteration_history:
            self._agent_iteration_history[agent_id] = []
        self._agent_iteration_history[agent_id].append(record)

    def _compute_policy_changes(
        self,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
    ) -> list[str]:
        """Compute human-readable description of policy changes.

        Args:
            old_policy: Previous policy.
            new_policy: New policy.

        Returns:
            List of change descriptions.
        """
        changes: list[str] = []

        # Compare parameters
        old_params = old_policy.get("parameters", {})
        new_params = new_policy.get("parameters", {})

        all_keys = set(old_params.keys()) | set(new_params.keys())
        for key in sorted(all_keys):
            old_val = old_params.get(key)
            new_val = new_params.get(key)

            if old_val != new_val:
                if old_val is None:
                    changes.append(f"Added '{key}': {new_val}")
                elif new_val is None:
                    changes.append(f"Removed '{key}' (was {old_val})")
                elif isinstance(old_val, (int, float)) and isinstance(
                    new_val, (int, float)
                ):
                    delta = new_val - old_val
                    arrow = "↑" if delta > 0 else "↓"
                    changes.append(
                        f"Changed '{key}': {old_val} → {new_val} ({arrow}{abs(delta):.2f})"
                    )
                else:
                    changes.append(f"Changed '{key}': {old_val} → {new_val}")

        return changes

    async def _should_accept_policy(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
        current_cost: int,
    ) -> tuple[bool, int, int, list[int], int, PolicyPairEvaluation]:
        """Determine whether to accept a new policy using paired bootstrap evaluation.

        Uses SeedMatrix for agent-specific bootstrap seeds, ensuring:
        - Each agent gets isolated seed stream
        - Seeds are deterministic per iteration×agent
        - Old and new policies evaluated on SAME samples for fair comparison

        This method MUST be called AFTER policy generation (not before).

        Args:
            agent_id: Agent being optimized.
            old_policy: Current policy.
            new_policy: Proposed new policy.
            current_cost: Current cost for this agent (from context simulation).

        Returns:
            Tuple of (should_accept, old_cost, new_cost, deltas, delta_sum, evaluation):
            - should_accept: True if delta_sum > 0 (new policy is cheaper)
            - old_cost: ACTUAL mean cost with old policy (from evaluation)
            - new_cost: ACTUAL mean cost with new policy (from evaluation)
            - deltas: List of per-sample (old_cost - new_cost) deltas
            - delta_sum: Sum of deltas (positive = improvement)
            - evaluation: Full PolicyPairEvaluation for persistence
        """
        # Get full evaluation with ACTUAL costs (not estimates)
        evaluation = self._evaluate_policy_pair(
            agent_id=agent_id,
            old_policy=old_policy,
            new_policy=new_policy,
        )

        # Accept if delta_sum > 0 (new policy is cheaper overall)
        # Note: Using delta_sum (not mean_delta) for acceptance
        # This means total improvement across all samples, not average
        should_accept = evaluation.delta_sum > 0

        # Return ACTUAL costs from evaluation, not estimates
        return (
            should_accept,
            evaluation.mean_old_cost,  # ACTUAL, not current_cost
            evaluation.mean_new_cost,  # ACTUAL, not estimate
            evaluation.deltas,
            evaluation.delta_sum,
            evaluation,
        )

    def _evaluate_temporal_acceptance(
        self,
        agent_id: str,
        current_cost: int,
    ) -> bool:
        """Evaluate policy acceptance using temporal comparison.

        Compares current iteration cost to previous iteration cost.
        First iteration always accepts (no baseline to compare).

        This is used by deterministic-temporal mode, which compares cost
        across iterations rather than old vs new policy within the same iteration.

        Args:
            agent_id: Agent being evaluated.
            current_cost: Cost from current iteration (integer cents, INV-1).

        Returns:
            True if policy should be accepted, False to reject/revert.

        Side effects:
            Updates _previous_iteration_costs if accepted.
        """
        previous_cost = self._previous_iteration_costs.get(agent_id)

        # First iteration: always accept (no baseline to compare)
        if previous_cost is None:
            self._previous_iteration_costs[agent_id] = current_cost
            return True

        # Compare: accept if cost decreased or stayed same
        # Equal cost is accepted to allow exploration without penalty
        accepted = current_cost <= previous_cost

        # Update stored cost only if accepted
        # If rejected, keep previous cost as baseline for next iteration
        if accepted:
            self._previous_iteration_costs[agent_id] = current_cost

        return accepted

    def _track_policy_fraction(self, agent_id: str, policy: dict[str, Any]) -> None:
        """Extract and track initial_liquidity_fraction from policy.

        Records the fraction for the current iteration to enable multi-agent
        convergence detection based on policy stability.

        Args:
            agent_id: Agent identifier.
            policy: Policy dict containing parameters.
        """
        # Extract fraction with default of 0.5
        parameters = policy.get("parameters", {})
        fraction = parameters.get("initial_liquidity_fraction", 0.5)

        # Record to stability tracker
        self._stability_tracker.record_fraction(
            agent_id=agent_id,
            iteration=self._current_iteration,
            fraction=fraction,
        )

    def _check_multiagent_convergence(self) -> bool:
        """Check if all agents have converged based on policy stability.

        Uses the stability_window from convergence config to determine
        how many consecutive iterations of unchanged initial_liquidity_fraction
        are required for convergence.

        In multi-agent scenarios, convergence requires ALL agents to have
        stable policies simultaneously - this indicates a potential equilibrium
        where no agent wants to unilaterally change their strategy.

        Returns:
            True if all optimized agents are stable for stability_window iterations.
        """
        stability_window = self._config.convergence.stability_window

        return self._stability_tracker.all_agents_stable(
            agents=list(self._config.optimized_agents),
            window=stability_window,
        )

    def _evaluate_policy_with_seed(
        self, policy: dict[str, Any], agent_id: str, seed: int
    ) -> int:
        """Evaluate a policy with a specific seed.

        Args:
            policy: Policy dict to evaluate.
            agent_id: Agent to evaluate for.
            seed: RNG seed to use.

        Returns:
            Cost for the specified agent in cents.
        """
        # Temporarily set the policy for evaluation
        original_policy = self._policies.get(agent_id)
        self._policies[agent_id] = policy

        # Run simulation and get agent's cost
        _, agent_costs = self._run_single_simulation(seed)
        cost = agent_costs.get(agent_id, 0)

        # Restore original policy
        if original_policy is not None:
            self._policies[agent_id] = original_policy
        elif agent_id in self._policies:
            del self._policies[agent_id]

        return cost

    def _create_default_policy(self, agent_id: str) -> dict[str, Any]:
        """Create a default/seed policy for an agent.

        Creates a simple Release-always policy with 50% initial liquidity allocation.

        The initial_liquidity_fraction parameter controls how much of the
        liquidity_pool is allocated at simulation start. This is extracted by
        StandardPolicyConfigBuilder.extract_liquidity_config() and applied at
        simulation startup - NOT through tree evaluation.

        Note: strategic_collateral_tree is set to HoldCollateral (no-op) because
        liquidity allocation in liquidity_pool mode happens at simulation start,
        not through collateral posting. Collateral trees are only relevant when
        using max_collateral_capacity mode.

        Args:
            agent_id: Agent ID.

        Returns:
            Default policy dict.
        """
        return {
            "version": "2.0",
            "policy_id": f"{agent_id}_default",
            "parameters": {
                "initial_liquidity_fraction": 0.5,
            },
            "payment_tree": {
                "type": "action",
                "node_id": "default_release",
                "action": "Release",
            },
            "strategic_collateral_tree": {
                # No-op: liquidity allocation happens at simulation start via
                # the initial_liquidity_fraction parameter, not through this tree.
                # This tree is only relevant for collateral mode (max_collateral_capacity).
                "type": "action",
                "node_id": "hold_collateral",
                "action": "HoldCollateral",
            },
        }
