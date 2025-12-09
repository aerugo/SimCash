"""Experiment runner using ai_cash_mgmt.

Orchestrates the optimization loop for Castro experiments.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

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
from payment_simulator.persistence.connection import DatabaseManager

from castro.constraints import CASTRO_CONSTRAINTS
from castro.experiments import CastroExperiment
from castro.llm_client import CastroLLMClient
from castro.simulation import CastroSimulationRunner

console = Console()


@dataclass
class ExperimentResult:
    """Result of running an experiment.

    Captures the final state after optimization completes.

    Example:
        >>> result = ExperimentResult(
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

    def __init__(self, experiment: CastroExperiment) -> None:
        """Initialize the experiment runner.

        Args:
            experiment: CastroExperiment configuration.
        """
        self._experiment = experiment
        self._convergence_config = experiment.get_convergence_criteria()
        self._monte_carlo_config = experiment.get_monte_carlo_config()
        self._llm_config = experiment.get_llm_config()

        # Core components
        self._seed_manager = SeedManager(experiment.master_seed)
        self._convergence = ConvergenceDetector(self._convergence_config)
        self._validator = ConstraintValidator(CASTRO_CONSTRAINTS)
        self._optimizer = PolicyOptimizer(
            constraints=CASTRO_CONSTRAINTS,
            max_retries=self._llm_config.max_retries,
        )

        # LLM client
        self._llm_client = CastroLLMClient(self._llm_config)

        # Simulation runner (initialized lazily)
        self._sim_runner: CastroSimulationRunner | None = None

        # State
        self._policies: dict[str, dict[str, Any]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._best_cost: float = float("inf")
        self._best_policies: dict[str, dict[str, Any]] = {}

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

            console.print(f"\n[bold cyan]Starting {self._experiment.name}[/bold cyan]")
            console.print(f"  Description: {self._experiment.description}")
            console.print(f"  Max iterations: {self._convergence_config.max_iterations}")
            console.print(f"  Monte Carlo samples: {self._monte_carlo_config.num_samples}")
            console.print(f"  LLM model: {self._llm_config.model}")
            console.print()

            # Optimization loop
            iteration = 0
            per_agent_costs: dict[str, int] = {}

            while iteration < self._convergence_config.max_iterations:
                iteration += 1
                console.print(f"[cyan]Iteration {iteration}[/cyan]")

                # 1. Evaluate current policies
                total_cost, per_agent_costs = await self._evaluate_policies(iteration)
                console.print(f"  Total cost: ${total_cost / 100:.2f}")

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

                    result = await self._optimizer.optimize(
                        agent_id=agent_id,
                        current_policy=self._policies[agent_id],
                        performance_history=self._history.get(agent_id, []),
                        llm_client=self._llm_client,
                        llm_model=self._llm_config.model,
                        current_cost=float(per_agent_costs.get(agent_id, 0)),
                    )

                    # Save iteration record
                    self._save_iteration(repo, result, iteration)

                    if result.was_accepted and result.new_policy:
                        self._policies[agent_id] = result.new_policy
                        console.print("    [green]Policy updated[/green]")
                    else:
                        errors_str = ", ".join(result.validation_errors[:2])
                        console.print(f"    [yellow]Rejected: {errors_str}[/yellow]")

                    # Update history
                    if agent_id not in self._history:
                        self._history[agent_id] = []
                    self._history[agent_id].append({
                        "iteration": iteration,
                        "cost": per_agent_costs.get(agent_id, 0),
                    })

                console.print()

            # Finalize
            duration = (datetime.now() - start_time).total_seconds()
            converged = self._convergence.is_converged

            # Update session record
            repo.update_game_session_status(
                game_id=self._experiment.name,
                status=GameStatus.CONVERGED.value if converged else GameStatus.COMPLETED.value,
                completed_at=datetime.now(),
                total_iterations=iteration,
                converged=converged,
                final_cost=self._best_cost,
            )

            return ExperimentResult(
                experiment_name=self._experiment.name,
                final_cost=int(self._best_cost),
                best_cost=int(self._best_cost),
                num_iterations=iteration,
                converged=converged,
                convergence_reason=self._convergence.convergence_reason or "max_iterations",
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
        seed_policy: dict[str, Any] = {
            "version": "2.0",
            "parameters": {
                "initial_liquidity_fraction": 0.25,
                "urgency_threshold": 3,
                "liquidity_buffer": 1.0,
            },
            "payment_tree": {
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency_threshold"},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
            "strategic_collateral_tree": {
                "type": "condition",
                "condition": {
                    "op": "==",
                    "left": {"field": "system_tick_in_day"},
                    "right": {"value": 0},
                },
                "on_true": {
                    "type": "action",
                    "action": "PostCollateral",
                    "params": {"fraction": {"param": "initial_liquidity_fraction"}},
                },
                "on_false": {"type": "action", "action": "HoldCollateral"},
            },
        }

        for agent_id in self._experiment.optimized_agents:
            # Deep copy for each agent
            self._policies[agent_id] = json.loads(json.dumps(seed_policy))

    async def _evaluate_policies(
        self, iteration: int
    ) -> tuple[int, dict[str, int]]:
        """Evaluate current policies across Monte Carlo samples.

        Args:
            iteration: Current iteration number.

        Returns:
            Tuple of (total_cost, per_agent_costs).
        """
        if self._sim_runner is None:
            msg = "Simulation runner not initialized"
            raise RuntimeError(msg)

        num_samples = self._monte_carlo_config.num_samples
        total_costs: list[int] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self._experiment.optimized_agents
        }

        # Run Monte Carlo evaluation
        for sample_idx in range(num_samples):
            seed = self._seed_manager.simulation_seed(iteration * 1000 + sample_idx)

            # Use first agent's policy (in full implementation, would inject per-agent)
            policy = list(self._policies.values())[0]
            result = self._sim_runner.run_simulation(
                policy=policy,
                seed=seed,
                ticks=self._monte_carlo_config.evaluation_ticks,
            )

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

        return mean_total, mean_per_agent

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
        )

    def _save_iteration(
        self,
        repo: GameRepository,
        result: Any,
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
