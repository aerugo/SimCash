"""Experiment runner using ai_cash_mgmt.

Orchestrates the optimization loop for Castro experiments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.models import BootstrapSample

from payment_simulator.ai_cash_mgmt import (
    ConstraintValidator,
    ConvergenceDetector,
    GameRepository,
    GameSessionRecord,
    GameStatus,
    PolicyIterationRecord,
    PolicyOptimizer,
    SeedManager,
)
from payment_simulator.ai_cash_mgmt.bootstrap import (
    BootstrapPolicyEvaluator,
    BootstrapSampler,
    TransactionHistoryCollector,
)
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    DebugCallback,
    OptimizationResult,
)
from payment_simulator.ai_cash_mgmt.prompts import (
    SingleAgentIterationRecord,
)
from payment_simulator.persistence.connection import DatabaseManager
from rich.console import Console

from castro.constraints import CASTRO_CONSTRAINTS
from castro.context_builder import MonteCarloContextBuilder
from castro.events import create_llm_interaction_event
from castro.experiments import CastroExperiment
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord
from castro.pydantic_llm_client import (
    AuditCaptureLLMClient,
    PydanticAILLMClient,
)
from castro.run_id import generate_run_id
from castro.simulation import CastroSimulationRunner, SimulationResult
from castro.verbose_logging import (
    LLMCallMetadata,
    MonteCarloSeedResult,
    RejectionDetail,
    VerboseConfig,
    VerboseLogger,
)

console = Console()


class VerboseLoggerDebugCallback:
    """Adapter that implements DebugCallback protocol using VerboseLogger.

    Bridges the PolicyOptimizer's debug callback protocol to the
    VerboseLogger's debug methods.
    """

    def __init__(self, logger: VerboseLogger) -> None:
        """Initialize the debug callback adapter.

        Args:
            logger: VerboseLogger instance to delegate to.
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
        self._logger.log_debug_all_retries_exhausted(agent_id, max_attempts, final_errors)


@dataclass
class ExperimentResult:
    """Result of running an experiment.

    Captures the final state after optimization completes.

    Example:
        >>> result = ExperimentResult(
        ...     run_id="exp1-20251209-143022-a1b2c3",
        ...     experiment_name="exp1",
        ...     final_cost=15000,
        ...     best_cost=14500,
        ...     num_iterations=12,
        ...     converged=True,
        ...     convergence_reason="stability_reached",
        ...     per_agent_costs={"BANK_A": 7000, "BANK_B": 7500},
        ...     duration_seconds=45.2,
        ... )
    """

    run_id: str
    experiment_name: str
    final_cost: int
    best_cost: int
    num_iterations: int
    converged: bool
    convergence_reason: str
    per_agent_costs: dict[str, int]
    duration_seconds: float
    best_policies: dict[str, dict[str, Any]] = field(default_factory=dict)


class ExperimentRunner:
    """Runs Castro experiments using ai_cash_mgmt components.

    Orchestrates the full optimization loop:
    1. Load seed policies
    2. Evaluate policies via Monte Carlo simulation
    3. Generate improved policies via LLM
    4. Validate and accept/reject
    5. Repeat until convergence

    Example:
        >>> from castro.experiments import create_exp1
        >>> exp = create_exp1()
        >>> runner = ExperimentRunner(exp)
        >>> result = asyncio.run(runner.run())
        >>> print(f"Final cost: ${result.final_cost / 100:.2f}")
    """

    def __init__(
        self,
        experiment: CastroExperiment,
        verbose_config: VerboseConfig | None = None,
        run_id: str | None = None,
    ) -> None:
        """Initialize the experiment runner.

        Args:
            experiment: CastroExperiment configuration.
            verbose_config: Optional verbose logging configuration.
            run_id: Optional run ID. If not provided, one will be generated.
        """
        self._experiment = experiment
        self._run_id = run_id or generate_run_id(experiment.name)
        self._verbose_config = verbose_config or VerboseConfig()
        self._verbose_logger = VerboseLogger(self._verbose_config, console)
        self._debug_callback: DebugCallback | None = (
            VerboseLoggerDebugCallback(self._verbose_logger)
            if self._verbose_config.debug
            else None
        )
        self._convergence_config = experiment.get_convergence_criteria()
        self._monte_carlo_config = experiment.get_monte_carlo_config()
        self._model_config = experiment.get_model_config()

        # Core components
        self._seed_manager = SeedManager(experiment.master_seed)
        self._convergence = ConvergenceDetector(
            stability_threshold=self._convergence_config.stability_threshold,
            stability_window=self._convergence_config.stability_window,
            max_iterations=self._convergence_config.max_iterations,
            improvement_threshold=self._convergence_config.improvement_threshold,
        )
        self._validator = ConstraintValidator(CASTRO_CONSTRAINTS)
        self._optimizer = PolicyOptimizer(
            constraints=CASTRO_CONSTRAINTS,
            max_retries=self._model_config.max_retries,
        )

        # LLM client - using PydanticAI with audit capture wrapper
        self._base_llm_client = PydanticAILLMClient(self._model_config)
        self._llm_client = AuditCaptureLLMClient(self._base_llm_client)

        # Simulation runner (initialized lazily)
        self._sim_runner: CastroSimulationRunner | None = None

        # State
        self._policies: dict[str, dict[str, Any]] = {}
        self._iteration_history: dict[str, list[SingleAgentIterationRecord]] = {}
        self._best_cost: float = float("inf")
        self._best_policies: dict[str, dict[str, Any]] = {}
        self._best_agent_costs: dict[str, int] = {}
        # Baseline costs per seed (for delta comparison across iterations)
        # Key: seed, Value: cost from iteration 1
        self._baseline_costs: dict[int, int] = {}

        # Bootstrap evaluation state
        self._bootstrap_sampler: BootstrapSampler | None = None
        self._bootstrap_evaluator: BootstrapPolicyEvaluator | None = None
        self._transaction_history: dict[str, Any] = {}  # Agent ID -> AgentTransactionHistory

    async def run(self) -> ExperimentResult:
        """Run the experiment to convergence.

        Returns:
            ExperimentResult with final costs and metrics.
        """
        start_time = datetime.now()

        # Initialize simulation runner
        scenario_path = self._get_scenario_path()
        self._sim_runner = CastroSimulationRunner.from_yaml(scenario_path)

        # Initialize database
        output_config = self._experiment.get_output_config()
        db_path = Path(output_config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with DatabaseManager(str(db_path)) as db:
            repo = GameRepository(db.conn)
            repo.initialize_schema()

            # Load seed policies
            self._load_seed_policies()

            # Save initial session
            session_record = self._create_session_record()
            repo.save_game_session(session_record)

            # Initialize experiment event database (for replay)
            import duckdb

            castro_db_path = db_path.parent / "castro.db"
            castro_conn = duckdb.connect(str(castro_db_path))
            exp_repo = ExperimentEventRepository(castro_conn)
            exp_repo.initialize_schema()

            # Create experiment run record
            exp_run_record = ExperimentRunRecord(
                run_id=self._run_id,
                experiment_name=self._experiment.name,
                started_at=start_time,
                status="running",
                model=self._model_config.model,
                master_seed=self._experiment.master_seed,
            )
            exp_repo.save_run_record(exp_run_record)

            console.print(f"\n[bold cyan]Starting {self._experiment.name}[/bold cyan]")
            console.print(f"  [bold]Run ID: {self._run_id}[/bold]")
            console.print(f"  Description: {self._experiment.description}")
            console.print(f"  Max iterations: {self._convergence_config.max_iterations}")
            if self._monte_carlo_config.deterministic:
                console.print("  Evaluation mode: [cyan]Deterministic[/cyan] (single evaluation)")
            else:
                console.print(
                    f"  Evaluation mode: [green]Bootstrap[/green] "
                    f"({self._monte_carlo_config.num_samples} samples)"
                )
            console.print(f"  LLM model: {self._model_config.model}")
            console.print()

            # Initialize bootstrap components for policy evaluation
            self._initialize_bootstrap()

            # Optimization loop
            iteration = 0
            per_agent_costs: dict[str, int] = {}

            while iteration < self._convergence_config.max_iterations:
                iteration += 1
                console.print(f"[cyan]Iteration {iteration}[/cyan]")

                # 1. Evaluate current policies using bootstrap sampling
                # CRITICAL: samples_per_agent MUST be reused for paired comparison
                (
                    total_cost,
                    per_agent_costs,
                    context_builder,
                    seed_results,
                    samples_per_agent,
                ) = await self._evaluate_policies(iteration, capture_verbose=True)
                console.print(f"  Total cost: ${total_cost / 100:.2f}")

                # Store baseline costs on iteration 1 for delta comparison
                is_baseline_run = iteration == 1
                if is_baseline_run:
                    for result in seed_results:
                        self._baseline_costs[result.seed] = result.cost

                # Verbose: Log Monte Carlo results
                if seed_results:
                    import math
                    costs = [r.cost for r in seed_results]
                    mean_cost = sum(costs) // len(costs) if costs else 0
                    variance = sum((c - mean_cost) ** 2 for c in costs) / len(costs) if costs else 0
                    std_cost = int(math.sqrt(variance))
                    self._verbose_logger.log_monte_carlo_evaluation(
                        seed_results=seed_results,
                        mean_cost=mean_cost,
                        std_cost=std_cost,
                        deterministic=self._monte_carlo_config.deterministic,
                        is_baseline_run=is_baseline_run,
                    )

                # Track best
                if total_cost < self._best_cost:
                    self._best_cost = total_cost
                    self._best_policies = {k: v.copy() for k, v in self._policies.items()}
                    console.print("  [green]New best![/green]")

                # 2. Check convergence
                self._convergence.record_metric(total_cost)
                if self._convergence.is_converged:
                    console.print(
                        f"[green]Converged: {self._convergence.convergence_reason}[/green]"
                    )
                    break

                # 3. Optimize each agent
                for agent_id in self._experiment.optimized_agents:
                    console.print(f"  Optimizing {agent_id}...")

                    agent_cost = per_agent_costs.get(agent_id, 0)

                    # Get per-agent context from MonteCarloContextBuilder
                    agent_sim_context = context_builder.get_agent_simulation_context(agent_id)

                    current_metrics = {
                        "total_cost_mean": agent_sim_context.mean_cost,
                        "total_cost_std": agent_sim_context.cost_std,
                        "settlement_rate_mean": context_builder._compute_mean_settlement_rate(),
                    }

                    result = await self._optimizer.optimize(
                        agent_id=agent_id,
                        current_policy=self._policies[agent_id],
                        current_iteration=iteration,
                        current_metrics=current_metrics,
                        llm_client=self._llm_client,
                        llm_model=self._model_config.model,
                        current_cost=float(agent_cost),
                        iteration_history=self._iteration_history.get(agent_id, []),
                        # Pass verbose context from MonteCarloContextBuilder
                        best_seed_output=agent_sim_context.best_seed_output,
                        worst_seed_output=agent_sim_context.worst_seed_output,
                        best_seed=agent_sim_context.best_seed,
                        worst_seed=agent_sim_context.worst_seed,
                        best_seed_cost=agent_sim_context.best_seed_cost,
                        worst_seed_cost=agent_sim_context.worst_seed_cost,
                        # Debug callback for retry logging
                        debug_callback=self._debug_callback,
                    )

                    # Verbose: Log LLM call metadata
                    if result.llm_latency_seconds is not None:
                        self._verbose_logger.log_llm_call(
                            LLMCallMetadata(
                                agent_id=agent_id,
                                model=result.llm_model or self._model_config.model,
                                prompt_tokens=result.tokens_used or 0,
                                completion_tokens=0,  # Not tracked separately currently
                                latency_seconds=result.llm_latency_seconds,
                                context_summary={
                                    "iteration_history_count": len(
                                        self._iteration_history.get(agent_id, [])
                                    ),
                                    "current_cost": int(agent_cost),
                                    "best_seed_cost": agent_sim_context.best_seed_cost,
                                    "worst_seed_cost": agent_sim_context.worst_seed_cost,
                                },
                            )
                        )

                    # Emit LLM interaction event for audit replay
                    last_interaction = self._llm_client.get_last_interaction()
                    if last_interaction is not None:
                        llm_event = create_llm_interaction_event(
                            run_id=self._run_id,
                            iteration=iteration,
                            agent_id=agent_id,
                            system_prompt=last_interaction.system_prompt,
                            user_prompt=last_interaction.user_prompt,
                            raw_response=last_interaction.raw_response,
                            parsed_policy=last_interaction.parsed_policy,
                            parsing_error=last_interaction.parsing_error,
                            model=result.llm_model or self._model_config.model,
                            prompt_tokens=last_interaction.prompt_tokens,
                            completion_tokens=last_interaction.completion_tokens,
                            latency_seconds=last_interaction.latency_seconds,
                        )
                        exp_repo.save_event(llm_event)

                    # Evaluate new policy using PAIRED COMPARISON
                    # CRITICAL FIX: Use compute_paired_deltas() with SAME samples
                    actually_accepted = False
                    new_cost = result.old_cost
                    old_policy_for_logging = self._policies[agent_id].copy()
                    mean_delta = 0.0

                    if result.was_accepted and result.new_policy:
                        old_policy = self._policies[agent_id]

                        # Get the bootstrap samples generated for this agent this iteration
                        agent_samples = samples_per_agent.get(agent_id, [])

                        if agent_samples and self._bootstrap_evaluator is not None:
                            # PAIRED COMPARISON: Evaluate BOTH policies on SAME samples
                            # delta = cost_old - cost_new, positive means new is cheaper
                            deltas = self._bootstrap_evaluator.compute_paired_deltas(
                                samples=agent_samples,
                                policy_a=old_policy,
                                policy_b=result.new_policy,
                            )
                            mean_delta = self._bootstrap_evaluator.compute_mean_delta(
                                deltas
                            )

                            # Calculate mean costs from deltas for logging
                            old_cost_mean = (
                                sum(d.cost_a for d in deltas) // len(deltas)
                                if deltas
                                else int(result.old_cost)
                            )
                            new_cost = (
                                sum(d.cost_b for d in deltas) // len(deltas)
                                if deltas
                                else int(result.old_cost)
                            )

                            # Accept if new policy is cheaper (delta > 0 means A costs more than B)
                            if mean_delta > 0:
                                actually_accepted = True
                                self._policies[agent_id] = result.new_policy
                                console.print(
                                    f"    [green]Policy improved: "
                                    f"mean delta ${mean_delta/100:.2f} "
                                    f"(${old_cost_mean/100:.2f} → ${new_cost/100:.2f})[/green]"
                                )

                                # Verbose: Log accepted policy change
                                self._verbose_logger.log_policy_change(
                                    agent_id=agent_id,
                                    old_policy=old_policy_for_logging,
                                    new_policy=result.new_policy,
                                    old_cost=old_cost_mean,
                                    new_cost=int(new_cost),
                                    accepted=True,
                                )
                            else:
                                # Keep old policy (don't need to revert, never changed)
                                console.print(
                                    f"    [yellow]Rejected: paired comparison "
                                    f"mean delta ${mean_delta/100:.2f} "
                                    f"(${old_cost_mean/100:.2f} → ${new_cost/100:.2f})[/yellow]"
                                )

                                # Verbose: Log cost-rejected policy change
                                self._verbose_logger.log_policy_change(
                                    agent_id=agent_id,
                                    old_policy=old_policy_for_logging,
                                    new_policy=result.new_policy,
                                    old_cost=old_cost_mean,
                                    new_cost=int(new_cost),
                                    accepted=False,
                                )
                                self._verbose_logger.log_rejection(
                                    RejectionDetail(
                                        agent_id=agent_id,
                                        proposed_policy=result.new_policy,
                                        validation_errors=[],
                                        rejection_reason="paired_comparison_not_improved",
                                        old_cost=old_cost_mean,
                                        new_cost=int(new_cost),
                                    )
                                )

                    # Update result for database record
                    result.was_accepted = actually_accepted
                    result.new_cost = new_cost

                    # Save iteration record
                    self._save_iteration(repo, result, iteration)

                    if not actually_accepted and result.validation_errors:
                        errors_str = ", ".join(result.validation_errors[:2])
                        console.print(f"    [yellow]Rejected: {errors_str}[/yellow]")

                        # Verbose: Log validation rejection
                        self._verbose_logger.log_rejection(
                            RejectionDetail(
                                agent_id=agent_id,
                                proposed_policy=result.new_policy or {},
                                validation_errors=result.validation_errors,
                            )
                        )

                    # Track if this is the best cost for this agent
                    is_best_so_far = agent_cost < self._best_agent_costs.get(
                        agent_id, float("inf")
                    )
                    if is_best_so_far:
                        self._best_agent_costs[agent_id] = agent_cost

                    # Update iteration history with SingleAgentIterationRecord
                    if agent_id not in self._iteration_history:
                        self._iteration_history[agent_id] = []

                    # Build comparison message
                    comparison_msg = ""
                    if is_best_so_far and agent_cost > 0:
                        best = self._best_agent_costs[agent_id]
                        pct = (best - agent_cost) / agent_cost * 100
                        comparison_msg = f"Cost improved by {pct:.1f}%"

                    iteration_record = SingleAgentIterationRecord(
                        iteration=iteration,
                        metrics=current_metrics,
                        policy=self._policies[agent_id].copy(),
                        was_accepted=actually_accepted,
                        is_best_so_far=is_best_so_far,
                        comparison_to_best=comparison_msg,
                    )
                    self._iteration_history[agent_id].append(iteration_record)

                console.print()

            # Finalize
            duration = (datetime.now() - start_time).total_seconds()
            converged = self._convergence.is_converged
            convergence_reason = self._convergence.convergence_reason or "max_iterations"

            # Update session record
            repo.update_game_session_status(
                game_id=self._experiment.name,
                status=GameStatus.CONVERGED.value if converged else GameStatus.COMPLETED.value,
                completed_at=datetime.now(),
                total_iterations=iteration,
                converged=converged,
                final_cost=self._best_cost,
            )

            # Update experiment run record for replay
            exp_repo.update_run_status(
                run_id=self._run_id,
                status="completed",
                completed_at=datetime.now(),
                final_cost=int(self._best_cost),
                best_cost=int(self._best_cost),
                num_iterations=iteration,
                converged=converged,
                convergence_reason=convergence_reason,
            )

            # Close experiment event database connection
            castro_conn.close()

            return ExperimentResult(
                run_id=self._run_id,
                experiment_name=self._experiment.name,
                final_cost=int(self._best_cost),
                best_cost=int(self._best_cost),
                num_iterations=iteration,
                converged=converged,
                convergence_reason=convergence_reason,
                per_agent_costs={k: int(v) for k, v in per_agent_costs.items()},
                duration_seconds=duration,
                best_policies=self._best_policies,
            )

    def _get_scenario_path(self) -> Path:
        """Get the full path to the scenario config file.

        Returns:
            Path to scenario YAML file.
        """
        # Scenario path is relative to the castro package
        base_dir = Path(__file__).parent.parent
        return base_dir / self._experiment.scenario_path

    def _load_seed_policies(self) -> None:
        """Load initial seed policies for all agents."""
        # Default seed policy - release urgent, hold otherwise
        # Note: Each node requires a node_id field for the Rust parser
        #
        # Use remaining_collateral_capacity instead of max_collateral_capacity
        # for the compute expression, as it correctly accounts for the agent's
        # configured capacity at runtime.
        seed_policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "seed_policy",
            "parameters": {
                "initial_liquidity_fraction": 0.25,
                "urgency_threshold": 3.0,
                "liquidity_buffer_factor": 1.0,
            },
            "payment_tree": {
                "type": "condition",
                "node_id": "urgency_check",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency_threshold"},
                },
                "on_true": {"type": "action", "node_id": "release", "action": "Release"},
                "on_false": {"type": "action", "node_id": "hold", "action": "Hold"},
            },
            "strategic_collateral_tree": {
                "type": "condition",
                "node_id": "tick_zero_check",
                "condition": {
                    "op": "==",
                    "left": {"field": "system_tick_in_day"},
                    "right": {"value": 0.0},
                },
                "on_true": {
                    "type": "action",
                    "node_id": "post_initial",
                    "action": "PostCollateral",
                    "parameters": {
                        "amount": {
                            "compute": {
                                "op": "*",
                                "left": {"field": "remaining_collateral_capacity"},
                                "right": {"param": "initial_liquidity_fraction"},
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

        for agent_id in self._experiment.optimized_agents:
            # Deep copy for each agent
            self._policies[agent_id] = json.loads(json.dumps(seed_policy))

    def _initialize_bootstrap(self) -> None:
        """Initialize bootstrap components for bootstrap evaluation mode.

        Runs a full simulation to collect transaction history, then sets up
        the bootstrap sampler and evaluator for subsequent policy evaluations.
        """
        if self._sim_runner is None:
            msg = "Simulation runner not initialized"
            raise RuntimeError(msg)

        console.print("  [dim]Initializing bootstrap: running base simulation...[/dim]")

        # Run a full simulation with seed policy to collect transaction history
        policy = next(iter(self._policies.values()))
        seed = self._seed_manager.simulation_seed(0)

        result = self._sim_runner.run_simulation(
            policy=policy,
            seed=seed,
            ticks=self._monte_carlo_config.evaluation_ticks,
            capture_verbose=True,  # Need events for history collection
        )

        # Collect transaction history from events
        collector = TransactionHistoryCollector()
        if result.verbose_output is not None:
            all_events: list[dict[str, Any]] = []
            for tick_events in result.verbose_output.events_by_tick.values():
                all_events.extend(tick_events)
            collector.process_events(all_events)

        # Store history for each optimized agent
        for agent_id in self._experiment.optimized_agents:
            self._transaction_history[agent_id] = collector.get_agent_history(agent_id)

        # Get agent configuration from scenario for opening balance and credit limit
        agents_config = self._sim_runner._base_config.get("agents", [])
        agent_balance = 1_000_000_00  # Default: $1M in cents
        agent_credit = 500_000_00  # Default: $500K in cents

        for agent_cfg in agents_config:
            if agent_cfg.get("id") in self._experiment.optimized_agents:
                agent_balance = agent_cfg.get("opening_balance", agent_balance)
                agent_credit = agent_cfg.get("unsecured_cap", agent_credit)
                break

        # Initialize bootstrap sampler and evaluator
        self._bootstrap_sampler = BootstrapSampler(seed=self._experiment.master_seed)
        self._bootstrap_evaluator = BootstrapPolicyEvaluator(
            opening_balance=agent_balance,
            credit_limit=agent_credit,
        )

        console.print(
            f"  [dim]Bootstrap initialized: "
            f"{sum(len(h.outgoing) for h in self._transaction_history.values())} "
            f"outgoing transactions collected[/dim]"
        )

    async def _evaluate_policies(
        self,
        iteration: int,
        capture_verbose: bool = True,
    ) -> tuple[
        int,
        dict[str, int],
        MonteCarloContextBuilder,
        list[MonteCarloSeedResult],
        dict[str, list[BootstrapSample]],
    ]:
        """Evaluate current policies using bootstrap sampling.

        Bootstrap evaluation:
        1. Generates bootstrap samples from collected transaction history
        2. Evaluates policies on 3-agent sandbox (SOURCE, TARGET, SINK)
        3. Computes mean costs across samples for policy comparison

        Args:
            iteration: Current iteration number.
            capture_verbose: If True, capture tick-by-tick events (not used in bootstrap).

        Returns:
            Tuple of (total_cost, per_agent_costs, context_builder, seed_results, samples_per_agent).
            The samples_per_agent dict maps agent_id to list of BootstrapSamples,
            which MUST be reused for paired comparison when evaluating new policies.
        """
        if self._bootstrap_sampler is None or self._bootstrap_evaluator is None:
            msg = "Bootstrap components not initialized"
            raise RuntimeError(msg)

        num_samples = self._monte_carlo_config.num_samples
        total_costs: list[int] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self._experiment.optimized_agents
        }

        # For MonteCarloContextBuilder compatibility, we need SimulationResults
        # We'll create minimal results from bootstrap evaluation
        results: list[SimulationResult] = []
        seeds: list[int] = []

        # CRITICAL: Store samples for paired comparison
        # These MUST be reused when comparing old vs new policy
        samples_per_agent: dict[str, list[BootstrapSample]] = {}

        # Evaluate each agent using bootstrap
        for agent_id in self._experiment.optimized_agents:
            history = self._transaction_history.get(agent_id)
            if history is None:
                continue

            # Get policy for this agent
            policy = self._policies.get(agent_id, {})

            # Generate bootstrap samples ONCE per iteration
            samples = self._bootstrap_sampler.generate_samples(
                agent_id=agent_id,
                n_samples=num_samples,
                outgoing_records=history.outgoing,
                incoming_records=history.incoming,
                total_ticks=self._monte_carlo_config.evaluation_ticks,
            )

            # Store samples for paired comparison
            samples_per_agent[agent_id] = samples

            # Evaluate on each sample
            agent_costs: list[int] = []
            for sample in samples:
                eval_result = self._bootstrap_evaluator.evaluate_sample(
                    sample=sample,
                    policy=policy,
                )
                agent_costs.append(eval_result.total_cost)

            per_agent_totals[agent_id] = agent_costs

        # Compute per-sample totals (sum across agents)
        for sample_idx in range(num_samples):
            sample_total = sum(
                per_agent_totals[agent_id][sample_idx]
                for agent_id in self._experiment.optimized_agents
                if sample_idx < len(per_agent_totals.get(agent_id, []))
            )
            total_costs.append(sample_total)

            # Build seed from sample_idx for consistency
            sample_seed = self._seed_manager.simulation_seed(sample_idx)
            seeds.append(sample_seed)

            # Create minimal SimulationResult for context builder
            results.append(
                SimulationResult(
                    total_cost=sample_total,
                    per_agent_costs={
                        agent_id: per_agent_totals[agent_id][sample_idx]
                        for agent_id in self._experiment.optimized_agents
                        if sample_idx < len(per_agent_totals.get(agent_id, []))
                    },
                    settlement_rate=1.0,  # Bootstrap samples are pre-filtered
                    transactions_settled=0,  # Not tracked in bootstrap
                    transactions_failed=0,
                )
            )

        # Compute means
        mean_total = sum(total_costs) // len(total_costs) if total_costs else 0
        mean_per_agent = {
            agent_id: sum(costs) // len(costs) if costs else 0
            for agent_id, costs in per_agent_totals.items()
        }

        # Build context builder for per-agent context
        context_builder = MonteCarloContextBuilder(results=results, seeds=seeds)

        # Build MonteCarloSeedResult list for verbose logging
        seed_results: list[MonteCarloSeedResult] = []
        for i, (seed, result) in enumerate(zip(seeds, results, strict=True)):
            baseline_cost = self._baseline_costs.get(seed)
            seed_results.append(
                MonteCarloSeedResult(
                    seed=seed,
                    cost=result.total_cost,
                    settled=result.transactions_settled,
                    total=result.transactions_settled + result.transactions_failed,
                    settlement_rate=result.settlement_rate,
                    baseline_cost=baseline_cost,
                )
            )

        return mean_total, mean_per_agent, context_builder, seed_results, samples_per_agent

    def _create_session_record(self) -> GameSessionRecord:
        """Create initial session record.

        Returns:
            GameSessionRecord for database persistence.
        """
        return GameSessionRecord(
            game_id=self._experiment.name,
            scenario_config=str(self._experiment.scenario_path),
            master_seed=self._experiment.master_seed,
            game_mode="campaign_learning",
            config_json=json.dumps({
                "num_samples": self._monte_carlo_config.num_samples,
                "evaluation_ticks": self._monte_carlo_config.evaluation_ticks,
                "max_iterations": self._convergence_config.max_iterations,
            }),
            started_at=datetime.now(),
            status=GameStatus.RUNNING.value,
            optimized_agents=self._experiment.optimized_agents,
            # These are populated on completion
            completed_at=None,
            total_iterations=0,
            converged=False,
            final_cost=None,
        )

    def _save_iteration(
        self,
        repo: GameRepository,
        result: OptimizationResult,
        iteration: int,
    ) -> None:
        """Save iteration record to database.

        Args:
            repo: GameRepository instance.
            result: OptimizationResult from PolicyOptimizer.
            iteration: Current iteration number.
        """
        record = PolicyIterationRecord(
            game_id=self._experiment.name,
            agent_id=result.agent_id,
            iteration_number=iteration,
            trigger_tick=iteration * self._monte_carlo_config.evaluation_ticks,
            old_policy_json=json.dumps(result.old_policy),
            new_policy_json=json.dumps(result.new_policy) if result.new_policy else "{}",
            old_cost=result.old_cost,
            new_cost=result.new_cost if result.new_cost is not None else result.old_cost,
            cost_improvement=(
                result.old_cost - result.new_cost
                if result.new_cost is not None
                else 0.0
            ),
            was_accepted=result.was_accepted,
            validation_errors=result.validation_errors,
            llm_model=result.llm_model,
            llm_latency_seconds=result.llm_latency_seconds,
            tokens_used=result.tokens_used,
            created_at=datetime.now(),
        )
        repo.save_policy_iteration(record)


async def run_experiment(experiment: CastroExperiment) -> ExperimentResult:
    """Convenience function to run an experiment.

    Args:
        experiment: CastroExperiment configuration.

    Returns:
        ExperimentResult with final costs and metrics.
    """
    runner = ExperimentRunner(experiment)
    return await runner.run()
