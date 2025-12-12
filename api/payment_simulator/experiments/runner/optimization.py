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
from payment_simulator.ai_cash_mgmt import ConvergenceDetector
from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
    AgentSimulationContext,
    EnrichedBootstrapContextBuilder,
)
from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
    BootstrapEvent,
    CostBreakdown,
    EnrichedEvaluationResult,
)
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    DebugCallback,
    PolicyOptimizer,
)
from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentIterationRecord,
)
from payment_simulator.cli.filters import EventFilter
from payment_simulator.config import SimulationConfig
from payment_simulator.experiments.runner.seed_matrix import SeedMatrix
from payment_simulator.experiments.runner.state_provider import LiveStateProvider
from payment_simulator.experiments.runner.verbose import (
    BootstrapDeltaResult,
    BootstrapSampleResult,
    LLMCallMetadata,
    RejectionDetail,
    VerboseConfig,
    VerboseLogger,
)


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

    def on_attempt_start(
        self, agent_id: str, attempt: int, max_attempts: int
    ) -> None:
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
        self._logger.log_debug_all_retries_exhausted(agent_id, max_attempts, final_errors)


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
        """
        self._config = config
        self._config_dir = config_dir or Path.cwd()
        self._run_id = run_id or _generate_run_id(config.name)
        self._repository: ExperimentRepository | None = repository

        # Get convergence settings
        conv = config.convergence
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

        # Track per_agent_costs for final result
        per_agent_costs: dict[str, int] = {}

        # Optimization loop
        while self._current_iteration < self.max_iterations:
            self._current_iteration += 1

            # Reset accepted changes for this iteration
            self._accepted_changes = {agent_id: False for agent_id in self.optimized_agents}

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
                self._best_policies = {
                    k: v.copy() for k, v in self._policies.items()
                }

            # Save iteration record to repository persistence
            self._save_iteration_record(per_agent_costs)

            # Check convergence
            if self._convergence.is_converged:
                break

            # Optimize each agent
            for agent_id in self.optimized_agents:
                await self._optimize_agent(agent_id, per_agent_costs.get(agent_id, 0))

        # Get final cost
        final_cost = self._iteration_history[-1] if self._iteration_history else 0
        converged = self._convergence.is_converged
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
        self, seed: int, sample_idx: int
    ) -> EnrichedEvaluationResult:
        """Run a simulation and capture events for LLM context.

        This method captures tick-by-tick events during simulation,
        extracts cost breakdowns, and returns an EnrichedEvaluationResult
        suitable for use with EnrichedBootstrapContextBuilder.

        Args:
            seed: RNG seed for this simulation.
            sample_idx: Index of this sample in the bootstrap set.

        Returns:
            EnrichedEvaluationResult with event trace and cost breakdown.
        """
        # Build config with current policies
        ffi_config = self._build_simulation_config()

        # Override seed
        ffi_config["rng_seed"] = seed

        # Extract cost rates for LLM context (only once)
        if not self._cost_rates and "cost_config" in ffi_config:
            self._cost_rates = ffi_config["cost_config"]

        # Create orchestrator
        orch = Orchestrator.new(ffi_config)

        # Run simulation and capture events
        total_ticks = self._config.evaluation.ticks
        all_events: list[BootstrapEvent] = []

        for tick in range(total_ticks):
            orch.tick()

            # Capture events for this tick
            try:
                tick_events = orch.get_tick_events(tick)
                for event in tick_events:
                    # Convert to BootstrapEvent
                    bootstrap_event = BootstrapEvent(
                        tick=tick,
                        event_type=event.get("event_type", "unknown"),
                        details=event,
                    )
                    all_events.append(bootstrap_event)
            except Exception:
                # If event capture fails, continue without events
                pass

        # Extract total cost and cost breakdown
        # NOTE: Field names must match Rust FFI keys:
        # - liquidity_cost (not overdraft_cost)
        # - total_settlements (not settled_count)
        # - total_arrivals (not total_transactions)
        # - avg_delay_ticks (not avg_settlement_delay)
        total_cost = 0
        delay_cost = 0
        liquidity_cost = 0  # FFI key is "liquidity_cost", not "overdraft_cost"
        deadline_penalty = 0
        collateral_cost = 0  # FFI provides this

        for agent_id in self.optimized_agents:
            try:
                agent_costs = orch.get_agent_accumulated_costs(agent_id)
                total_cost += int(agent_costs.get("total_cost", 0))
                delay_cost += int(agent_costs.get("delay_cost", 0))
                liquidity_cost += int(agent_costs.get("liquidity_cost", 0))
                deadline_penalty += int(agent_costs.get("deadline_penalty", 0))
                collateral_cost += int(agent_costs.get("collateral_cost", 0))
            except Exception:
                pass

        # Calculate settlement rate
        try:
            metrics = orch.get_system_metrics()
            # FFI returns "total_settlements" and "total_arrivals", not legacy keys
            settled = metrics.get("total_settlements", 0)
            total = metrics.get("total_arrivals", 1)
            settlement_rate = settled / total if total > 0 else 1.0
            avg_delay = float(metrics.get("avg_delay_ticks", 0.0))
        except Exception:
            settlement_rate = 1.0
            avg_delay = 0.0

        return EnrichedEvaluationResult(
            sample_idx=sample_idx,
            seed=seed,
            total_cost=total_cost,
            settlement_rate=settlement_rate,
            avg_delay=avg_delay,
            event_trace=tuple(all_events),
            cost_breakdown=CostBreakdown(
                delay_cost=delay_cost,
                # Model uses "overdraft_cost" but FFI returns "liquidity_cost"
                # These are the same concept (cost of negative balance)
                overdraft_cost=liquidity_cost,
                deadline_penalty=deadline_penalty,
                # FFI doesn't separate eod_penalty from deadline_penalty
                # The Rust cost model combines them into total_penalty_cost
                eod_penalty=0,
            ),
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

        return agent_contexts

    async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
        """Evaluate current policies by running simulation(s).

        For deterministic mode: runs a single simulation.
        For bootstrap mode: runs N simulations with different seeds, captures
        events for LLM context, and builds per-agent contexts.

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.

        Side effects:
            - Sets self._current_enriched_results for LLM context
            - Sets self._current_agent_contexts for per-agent optimization
        """
        eval_mode = self._config.evaluation.mode
        num_samples = self._config.evaluation.num_samples or 1

        if eval_mode == "deterministic" or num_samples <= 1:
            # Single simulation - deterministic mode
            # Use constant seed for reproducibility (same seed each iteration)
            # This ensures policy changes are the ONLY variable affecting cost
            seed = self._config.master_seed
            enriched = self._run_simulation_with_events(seed, sample_idx=0)

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

        # Bootstrap mode: run multiple simulations with event capture
        enriched_results: list[EnrichedEvaluationResult] = []
        total_costs: list[int] = []
        seed_results: list[dict[str, Any]] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self.optimized_agents
        }
        bootstrap_results: list[BootstrapSampleResult] = []

        for sample_idx in range(num_samples):
            # Use deterministic seed derivation for reproducibility
            seed = self._derive_sample_seed(sample_idx)

            # Run simulation with event capture
            enriched = self._run_simulation_with_events(seed, sample_idx)
            enriched_results.append(enriched)

            cost = enriched.total_cost
            total_costs.append(cost)

            # Extract per-agent costs (use total_cost as proxy for now)
            # In full implementation, would track per-agent separately
            for agent_id in self.optimized_agents:
                # Divide evenly for multi-agent scenarios
                agent_cost = cost // len(self.optimized_agents)
                per_agent_totals[agent_id].append(agent_cost)

            # Collect bootstrap sample result for verbose logging
            bootstrap_results.append(
                BootstrapSampleResult(
                    seed=seed,
                    cost=cost,
                    settled=int(enriched.settlement_rate * 100),
                    total=100,
                    settlement_rate=enriched.settlement_rate,
                    baseline_cost=None,  # First iteration has no baseline
                )
            )

            # Track seed results for bootstrap event (state provider)
            seed_results.append({
                "seed": seed,
                "cost": cost,
                "settled": int(enriched.settlement_rate * 100),
                "total": 100,
                "settlement_rate": enriched.settlement_rate,
            })

        # Store enriched results for LLM context
        self._current_enriched_results = enriched_results
        self._current_agent_contexts = self._build_agent_contexts(enriched_results)

        # Compute mean and std costs (as integers)
        mean_total = int(sum(total_costs) / len(total_costs))
        variance = sum((c - mean_total) ** 2 for c in total_costs) / len(total_costs)
        std_total = int(variance ** 0.5)
        mean_per_agent = {
            agent_id: int(sum(costs) / len(costs))
            for agent_id, costs in per_agent_totals.items()
        }

        # Log bootstrap evaluation summary (verbose logging)
        if self._verbose_logger and self._verbose_config.bootstrap and bootstrap_results:
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

    def _derive_sample_seed(self, sample_idx: int) -> int:
        """Derive a deterministic seed for a bootstrap sample.

        Uses SHA-256 for deterministic derivation, ensuring same
        sample_idx always produces the same seed (reproducibility).

        Args:
            sample_idx: Sample index.

        Returns:
            Derived seed for this sample.
        """
        import hashlib

        key = f"{self._config.master_seed}:sample:{sample_idx}"
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)

    def _evaluate_policy_on_samples(
        self, policy: dict[str, Any], agent_id: str, num_samples: int
    ) -> list[int]:
        """Evaluate a policy on multiple samples for paired comparison.

        For deterministic mode (num_samples=1): uses master_seed directly
        For bootstrap mode (num_samples>1): uses derived seeds for each sample

        Args:
            policy: Policy dict to evaluate.
            agent_id: Agent to evaluate for.
            num_samples: Number of samples to run.

        Returns:
            List of costs (one per sample).
        """

        # Temporarily set the policy for evaluation
        original_policy = self._policies.get(agent_id)
        self._policies[agent_id] = policy

        costs: list[int] = []
        eval_mode = self._config.evaluation.mode

        for sample_idx in range(num_samples):
            # For deterministic mode, use master_seed directly
            # This ensures consistency with _evaluate_policies
            if eval_mode == "deterministic" or num_samples == 1:
                seed = self._config.master_seed
            else:
                seed = self._derive_sample_seed(sample_idx)

            _, agent_costs = self._run_single_simulation(seed)
            costs.append(agent_costs.get(agent_id, 0))

        # Restore original policy
        if original_policy is not None:
            self._policies[agent_id] = original_policy
        elif agent_id in self._policies:
            del self._policies[agent_id]

        return costs

    def _evaluate_policy_pair(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
    ) -> tuple[list[int], int]:
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
            Tuple of (deltas, delta_sum) where:
            - deltas: list of (old_cost - new_cost) per sample
            - delta_sum: sum of deltas (positive = new is cheaper = improvement)
        """
        # Use 0-indexed iteration for SeedMatrix
        iteration_idx = self._current_iteration - 1
        num_samples = self._config.evaluation.num_samples or 1

        # Handle deterministic mode (single sample)
        if self._config.evaluation.mode == "deterministic" or num_samples <= 1:
            # Use iteration seed directly
            seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

            # Evaluate old policy
            self._policies[agent_id] = old_policy
            _, old_costs = self._run_single_simulation(seed)
            old_cost = old_costs.get(agent_id, 0)

            # Evaluate new policy
            self._policies[agent_id] = new_policy
            _, new_costs = self._run_single_simulation(seed)
            new_cost = new_costs.get(agent_id, 0)

            delta = old_cost - new_cost
            return [delta], delta

        # Bootstrap mode: use agent-specific bootstrap seeds
        bootstrap_seeds = self._seed_matrix.get_bootstrap_seeds(iteration_idx, agent_id)

        deltas: list[int] = []

        for seed in bootstrap_seeds:
            # Evaluate old policy
            self._policies[agent_id] = old_policy
            _, old_costs = self._run_single_simulation(seed)
            old_cost = old_costs.get(agent_id, 0)

            # Evaluate new policy
            self._policies[agent_id] = new_policy
            _, new_costs = self._run_single_simulation(seed)
            new_cost = new_costs.get(agent_id, 0)

            # Delta: positive means new is cheaper (improvement)
            deltas.append(old_cost - new_cost)

        delta_sum = sum(deltas)
        return deltas, delta_sum

    async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
        """Optimize policy for a single agent using PolicyOptimizer with rich context.

        Uses PolicyOptimizer to generate improved policies with:
        - Best/worst seed verbose outputs for LLM analysis
        - Cost breakdown by type (delay, collateral, overdraft, etc.)
        - Full iteration history with acceptance status
        - Parameter trajectory visualization

        Args:
            agent_id: Agent to optimize.
            current_cost: Current cost for this agent in integer cents.
        """
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

        # Build cost breakdown dict for LLM context
        cost_breakdown: dict[str, int] | None = None
        # Extract events from enriched results for agent isolation filtering
        # Events are converted from BootstrapEvent to dict format
        collected_events: list[dict[str, Any]] | None = None
        if self._current_enriched_results:
            # Aggregate cost breakdown across all samples
            total_delay = sum(r.cost_breakdown.delay_cost for r in self._current_enriched_results)
            total_overdraft = sum(r.cost_breakdown.overdraft_cost for r in self._current_enriched_results)
            total_deadline = sum(r.cost_breakdown.deadline_penalty for r in self._current_enriched_results)
            total_eod = sum(r.cost_breakdown.eod_penalty for r in self._current_enriched_results)
            num_samples = len(self._current_enriched_results)
            cost_breakdown = {
                "delay_cost": total_delay // num_samples,
                "overdraft_cost": total_overdraft // num_samples,
                "deadline_penalty": total_deadline // num_samples,
                "eod_penalty": total_eod // num_samples,
            }

            # Extract events from all enriched results
            # These will be filtered by agent in the PolicyOptimizer
            collected_events = []
            for result in self._current_enriched_results:
                for event in result.event_trace:
                    collected_events.append({
                        "tick": event.tick,
                        "event_type": event.event_type,
                        **event.details,
                    })

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
                    best_seed_output=agent_context.best_seed_output,
                    worst_seed_output=agent_context.worst_seed_output,
                    best_seed=agent_context.best_seed,
                    worst_seed=agent_context.worst_seed,
                    best_seed_cost=agent_context.best_seed_cost,
                    worst_seed_cost=agent_context.worst_seed_cost,
                    cost_breakdown=cost_breakdown,
                    cost_rates=self._cost_rates,
                    debug_callback=debug_callback,
                )

                # Log LLM call metadata (verbose logging)
                if self._verbose_logger and self._verbose_config.llm:
                    self._verbose_logger.log_llm_call(
                        LLMCallMetadata(
                            agent_id=agent_id,
                            model=self._config.llm.model,
                            prompt_tokens=opt_result.tokens_used,
                            completion_tokens=0,
                            latency_seconds=opt_result.llm_latency_seconds,
                            context_summary={
                                "current_cost": current_cost,
                                "best_seed_cost": agent_context.best_seed_cost,
                                "worst_seed_cost": agent_context.worst_seed_cost,
                                "has_verbose_output": agent_context.best_seed_output is not None,
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
            # Returns (should_accept, old_cost, new_cost, deltas, delta_sum)
            (
                should_accept,
                eval_old_cost,
                eval_new_cost,
                deltas,
                delta_sum,
            ) = await self._should_accept_policy(
                agent_id=agent_id,
                old_policy=current_policy,
                new_policy=new_policy,
                current_cost=current_cost,
            )

            # Track delta history for progress monitoring
            self._delta_history.append({
                "iteration": self._current_iteration,
                "agent_id": agent_id,
                "deltas": deltas,
                "delta_sum": delta_sum,
                "accepted": should_accept,
            })

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
                elif isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                    delta = new_val - old_val
                    arrow = "↑" if delta > 0 else "↓"
                    changes.append(f"Changed '{key}': {old_val} → {new_val} ({arrow}{abs(delta):.2f})")
                else:
                    changes.append(f"Changed '{key}': {old_val} → {new_val}")

        return changes

    async def _should_accept_policy(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
        current_cost: int,
    ) -> tuple[bool, int, int, list[int], int]:
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
            Tuple of (should_accept, old_cost, new_cost, deltas, delta_sum) where:
            - should_accept: True if delta_sum > 0 (new policy is cheaper)
            - old_cost: Mean cost with old policy (for display)
            - new_cost: Mean cost with new policy (for display)
            - deltas: List of per-sample (old_cost - new_cost) deltas
            - delta_sum: Sum of deltas (positive = improvement)
        """
        # Use the new _evaluate_policy_pair which uses SeedMatrix
        deltas, delta_sum = self._evaluate_policy_pair(
            agent_id=agent_id,
            old_policy=old_policy,
            new_policy=new_policy,
        )

        # Compute mean costs for display/logging
        # Note: These are approximations based on deltas and current_cost
        # For accurate display, we'd need to track costs during evaluation
        num_samples = len(deltas)
        mean_delta = delta_sum / num_samples if num_samples > 0 else 0

        # Estimate old/new costs for display
        # old_cost ≈ current_cost (from context simulation)
        # new_cost ≈ old_cost - mean_delta
        old_cost = current_cost
        new_cost = current_cost - mean_delta

        # Accept if delta_sum > 0 (new policy is cheaper overall)
        # Note: Using delta_sum (not mean_delta) for acceptance
        # This means total improvement across all samples, not average
        should_accept = delta_sum > 0

        return (should_accept, int(old_cost), int(new_cost), deltas, delta_sum)

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

        Creates a simple Release-always policy with collateral posting at tick 0.
        The initial_liquidity_fraction parameter controls how much collateral
        is posted at the start of day.

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
                # Post collateral at tick 0 based on initial_liquidity_fraction
                "type": "condition",
                "node_id": "check_tick_0",
                "condition": {
                    "op": "==",
                    "left": {"field": "system_tick_in_day"},
                    "right": {"value": 0},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "post_initial_collateral",
                    "action": "PostCollateral",
                    "parameters": {
                        "amount": {
                            "compute": {
                                "op": "*",
                                "left": {"param": "initial_liquidity_fraction"},
                                "right": {"field": "remaining_collateral_capacity"},
                            }
                        },
                        "reason": {"value": "InitialAllocation"},
                    },
                },
                "on_false": {
                    "type": "action",
                    "node_id": "hold_collateral",
                    "action": "HoldCollateral",
                },
            },
        }
