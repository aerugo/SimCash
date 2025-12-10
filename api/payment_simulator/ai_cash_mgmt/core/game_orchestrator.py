"""Game orchestrator for AI Cash Management.

Main controller that manages the game lifecycle, scheduling, and convergence.
"""

from __future__ import annotations

from typing import Any

from payment_simulator.ai_cash_mgmt.config.game_config import (
    GameConfig,
    OptimizationScheduleType,
)
from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)
from payment_simulator.ai_cash_mgmt.core.game_session import GameSession
from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
    ConstraintValidator,
)
from payment_simulator.ai_cash_mgmt.optimization.convergence_detector import (
    ConvergenceDetector,
)
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    OptimizationResult,
    PolicyOptimizer,
)
from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager
from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
    HistoricalTransaction,
    TransactionSampler,
)


class GameOrchestrator:
    """Main orchestrator for AI Cash Management game.

    Coordinates:
    - TransactionSampler: Creates bootstrap samples from historical data
    - PolicyOptimizer: Generates improved policies via LLM
    - PolicyEvaluator: Evaluates policies on bootstrap samples
    - ConvergenceDetector: Detects when optimization has stabilized

    Example:
        >>> orchestrator = GameOrchestrator(config=config, constraints=constraints)
        >>> session = orchestrator.create_session()
        >>> while not session.is_converged:
        ...     if orchestrator.should_optimize_at_tick(current_tick):
        ...         results = await orchestrator.run_optimization_step(
        ...             session=session,
        ...             transactions=historical_txns,
        ...             current_tick=current_tick,
        ...         )
    """

    def __init__(
        self,
        config: GameConfig,
        constraints: ScenarioConstraints,
    ) -> None:
        """Initialize the game orchestrator.

        Args:
            config: Game configuration.
            constraints: Scenario constraints for policy validation.
        """
        self._config = config
        self._constraints = constraints

        # Initialize components
        self._seed_manager = SeedManager(config.master_seed)
        self._validator = ConstraintValidator(constraints)
        self._convergence_detector = ConvergenceDetector(
            stability_threshold=config.convergence.stability_threshold,
            stability_window=config.convergence.stability_window,
            max_iterations=config.convergence.max_iterations,
            improvement_threshold=config.convergence.improvement_threshold,
        )

        # These will be injected/created as needed
        self._policy_optimizer: PolicyOptimizer | None = None

    @property
    def game_id(self) -> str:
        """Get game identifier."""
        return self._config.game_id

    @property
    def master_seed(self) -> int:
        """Get master seed."""
        return self._config.master_seed

    @property
    def seed_manager(self) -> SeedManager:
        """Get the seed manager."""
        return self._seed_manager

    @property
    def convergence_detector(self) -> ConvergenceDetector:
        """Get the convergence detector."""
        return self._convergence_detector

    def create_session(self) -> GameSession:
        """Create a new game session.

        Returns:
            Initialized GameSession.
        """
        return GameSession(config=self._config)

    def should_optimize_at_tick(self, tick: int) -> bool:
        """Check if optimization should occur at this tick.

        Only applies to EVERY_X_TICKS schedule type.

        Args:
            tick: Current simulation tick.

        Returns:
            True if optimization should be triggered.
        """
        schedule = self._config.optimization_schedule

        if schedule.type != OptimizationScheduleType.EVERY_X_TICKS:
            return False

        if schedule.interval_ticks is None:
            return False

        return tick > 0 and tick % schedule.interval_ticks == 0

    def should_optimize_after_eod(self, remaining_days: int) -> bool:
        """Check if optimization should occur after end of day.

        Only applies to AFTER_EOD schedule type.

        Args:
            remaining_days: Number of simulation days remaining.

        Returns:
            True if optimization should be triggered.
        """
        schedule = self._config.optimization_schedule

        if schedule.type != OptimizationScheduleType.AFTER_EOD:
            return False

        min_remaining = schedule.min_remaining_days or 1
        return remaining_days >= min_remaining

    def get_sampling_seed(self, iteration: int, agent_id: str) -> int:
        """Get deterministic sampling seed for an optimization.

        Args:
            iteration: Optimization iteration number.
            agent_id: Agent being optimized.

        Returns:
            Deterministic seed value.
        """
        return self._seed_manager.sampling_seed(iteration, agent_id)

    def record_iteration_metric(self, cost: float) -> None:
        """Record a metric value for convergence tracking.

        Args:
            cost: Total cost from this iteration.
        """
        self._convergence_detector.record_metric(cost)

    def check_convergence(self) -> dict[str, Any]:
        """Check current convergence status.

        Returns:
            Dict with convergence information.
        """
        return {
            "is_converged": self._convergence_detector.is_converged,
            "current_iteration": self._convergence_detector.current_iteration,
            "best_metric": self._convergence_detector.best_metric,
            "convergence_reason": self._convergence_detector.convergence_reason,
        }

    async def run_optimization_step(
        self,
        session: GameSession,
        transactions: list[HistoricalTransaction],
        current_tick: int,
    ) -> list[OptimizationResult]:
        """Run a single optimization step for all agents.

        Args:
            session: Current game session.
            transactions: Historical transactions for sampling.
            current_tick: Current simulation tick (for filtering).

        Returns:
            List of OptimizationResult for each agent.
        """
        results: list[OptimizationResult] = []
        iteration = session.current_iteration

        # Get sample method - may be SampleMethod enum or string
        method_raw = self._config.bootstrap.sample_method
        sample_method = method_raw.value if hasattr(method_raw, "value") else str(method_raw)

        for agent_id in self._config.optimized_agents:
            # Get agent-specific sampling seed
            sampling_seed = self.get_sampling_seed(iteration, agent_id)

            # Create sampler for this agent
            sampler = TransactionSampler(seed=sampling_seed)

            # Convert HistoricalTransaction to dict for collection
            tx_dicts = [
                {
                    "tx_id": tx.tx_id,
                    "sender_id": tx.sender_id,
                    "receiver_id": tx.receiver_id,
                    "amount": tx.amount,
                    "priority": tx.priority,
                    "arrival_tick": tx.arrival_tick,
                    "deadline_tick": tx.deadline_tick,
                    "is_divisible": tx.is_divisible,
                }
                for tx in transactions
            ]
            sampler.collect_transactions(tx_dicts)

            # Create bootstrap samples (used for evaluation when evaluator is set)
            _ = sampler.create_samples(
                agent_id=agent_id,
                num_samples=self._config.bootstrap.num_samples,
                max_tick=current_tick,
                method=sample_method,
            )

            # Get current policy
            current_policy = session.get_policy(agent_id) or {}

            # Note: Full evaluation requires scenario_config and simulation_runner
            # which would be provided in real usage. For now, use 0.0 as placeholder.
            # The samples are prepared above for future evaluation integration.
            current_cost = 0.0

            # Get agent history (filtered to this agent only)
            agent_history = session.get_agent_history(agent_id)

            # Generate optimized policy
            if self._policy_optimizer is not None:
                result = await self._policy_optimizer.optimize(
                    agent_id=agent_id,
                    current_policy=current_policy,
                    performance_history=agent_history,
                    llm_client=self._policy_optimizer._llm_client,  # type: ignore
                    llm_model=self._config.get_llm_config_for_agent(agent_id).model,
                    current_cost=current_cost,
                )
                results.append(result)

                # Update session if policy was accepted
                if result.was_accepted and result.new_policy is not None:
                    session.set_policy(agent_id, result.new_policy)

        return results
