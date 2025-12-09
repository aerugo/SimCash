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
    pass  # Add any TYPE_CHECKING imports here as needed

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
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    OptimizationResult,
)
from payment_simulator.ai_cash_mgmt.prompts import (
    SingleAgentIterationRecord,
)
from payment_simulator.persistence.connection import DatabaseManager
from rich.console import Console

from castro.constraints import CASTRO_CONSTRAINTS
from castro.context_builder import MonteCarloContextBuilder
from castro.experiments import CastroExperiment
from castro.persistence import ExperimentEventRepository, ExperimentRunRecord
from castro.pydantic_llm_client import PydanticAILLMClient
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

        # LLM client - using PydanticAI
        self._llm_client = PydanticAILLMClient(self._model_config)

        # Simulation runner (initialized lazily)
        self._sim_runner: CastroSimulationRunner | None = None

        # State
        self._policies: dict[str, dict[str, Any]] = {}
        self._iteration_history: dict[str, list[SingleAgentIterationRecord]] = {}
        self._best_cost: float = float("inf")
        self._best_policies: dict[str, dict[str, Any]] = {}
        self._best_agent_costs: dict[str, int] = {}

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
            console.print(f"  Monte Carlo samples: {self._monte_carlo_config.num_samples}")
            console.print(f"  LLM model: {self._model_config.model}")
            console.print()

            # Optimization loop
            iteration = 0
            per_agent_costs: dict[str, int] = {}

            while iteration < self._convergence_config.max_iterations:
                iteration += 1
                console.print(f"[cyan]Iteration {iteration}[/cyan]")

                # 1. Evaluate current policies with verbose capture
                (
                    total_cost,
                    per_agent_costs,
                    context_builder,
                    seed_results,
                ) = await self._evaluate_policies(iteration, capture_verbose=True)
                console.print(f"  Total cost: ${total_cost / 100:.2f}")

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

                    # Evaluate new policy cost BEFORE accepting
                    actually_accepted = False
                    new_cost = result.old_cost
                    old_policy_for_logging = self._policies[agent_id].copy()

                    if result.was_accepted and result.new_policy:
                        # Temporarily apply new policy and evaluate
                        old_policy = self._policies[agent_id]
                        self._policies[agent_id] = result.new_policy

                        # Re-evaluate without verbose capture (performance optimization)
                        _eval_total, eval_per_agent, _, _ = await self._evaluate_policies(
                            iteration, capture_verbose=False
                        )
                        new_cost = eval_per_agent.get(agent_id, result.old_cost)

                        # Only accept if cost improved
                        if new_cost < result.old_cost:
                            actually_accepted = True
                            console.print(
                                f"    [green]Policy improved: "
                                f"${result.old_cost/100:.2f} → ${new_cost/100:.2f}[/green]"
                            )

                            # Verbose: Log accepted policy change
                            self._verbose_logger.log_policy_change(
                                agent_id=agent_id,
                                old_policy=old_policy_for_logging,
                                new_policy=result.new_policy,
                                old_cost=int(result.old_cost),
                                new_cost=int(new_cost),
                                accepted=True,
                            )
                        else:
                            # Revert to old policy
                            self._policies[agent_id] = old_policy
                            console.print(
                                f"    [yellow]Rejected: cost not improved "
                                f"(${result.old_cost/100:.2f} → ${new_cost/100:.2f})[/yellow]"
                            )

                            # Verbose: Log cost-rejected policy change
                            self._verbose_logger.log_policy_change(
                                agent_id=agent_id,
                                old_policy=old_policy_for_logging,
                                new_policy=result.new_policy,
                                old_cost=int(result.old_cost),
                                new_cost=int(new_cost),
                                accepted=False,
                            )
                            self._verbose_logger.log_rejection(
                                RejectionDetail(
                                    agent_id=agent_id,
                                    proposed_policy=result.new_policy,
                                    validation_errors=[],
                                    rejection_reason="cost_not_improved",
                                    old_cost=int(result.old_cost),
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

    async def _evaluate_policies(
        self,
        iteration: int,
        capture_verbose: bool = True,
    ) -> tuple[int, dict[str, int], MonteCarloContextBuilder, list[MonteCarloSeedResult]]:
        """Evaluate current policies across Monte Carlo samples.

        Runs Monte Carlo simulations with different seeds, captures verbose
        output, and builds a MonteCarloContextBuilder for per-agent context.

        Args:
            iteration: Current iteration number.
            capture_verbose: If True, capture tick-by-tick events for LLM context.

        Returns:
            Tuple of (total_cost, per_agent_costs, context_builder, seed_results).
        """
        if self._sim_runner is None:
            msg = "Simulation runner not initialized"
            raise RuntimeError(msg)

        num_samples = self._monte_carlo_config.num_samples
        total_costs: list[int] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self._experiment.optimized_agents
        }

        # Store all results and seeds for MonteCarloContextBuilder
        results: list[SimulationResult] = []
        seeds: list[int] = []

        # Run Monte Carlo evaluation
        for sample_idx in range(num_samples):
            seed = self._seed_manager.simulation_seed(iteration * 1000 + sample_idx)
            seeds.append(seed)

            # Use first agent's policy (in full implementation, would inject per-agent)
            policy = next(iter(self._policies.values()))
            result = self._sim_runner.run_simulation(
                policy=policy,
                seed=seed,
                ticks=self._monte_carlo_config.evaluation_ticks,
                capture_verbose=capture_verbose,
            )

            results.append(result)
            total_costs.append(result.total_cost)
            for agent_id, cost in result.per_agent_costs.items():
                if agent_id in per_agent_totals:
                    per_agent_totals[agent_id].append(cost)

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
        for seed, result in zip(seeds, results, strict=True):
            seed_results.append(
                MonteCarloSeedResult(
                    seed=seed,
                    cost=result.total_cost,
                    settled=result.transactions_settled,
                    total=result.transactions_settled + result.transactions_failed,
                    settlement_rate=result.settlement_rate,
                )
            )

        return mean_total, mean_per_agent, context_builder, seed_results

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
