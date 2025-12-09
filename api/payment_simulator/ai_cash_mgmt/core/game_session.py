"""Game session state management for AI Cash Management.

Tracks the state of a single optimization game, including policies,
iterations, and convergence status.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from payment_simulator.ai_cash_mgmt.config.game_config import GameConfig

SessionStatus = Literal["initialized", "running", "completed", "failed"]


@dataclass
class PolicyEvaluation:
    """Record of a policy evaluation."""

    agent_id: str
    policy: dict[str, Any]
    mean_cost: float
    iteration: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IterationResult:
    """Result of a single optimization iteration."""

    iteration: int
    total_cost: float
    per_agent_costs: dict[str, float]
    settlement_rate: float
    timestamp: datetime = field(default_factory=datetime.now)


class GameSession:
    """Manages state for a single AI Cash Management game session.

    Tracks:
    - Current policies per agent
    - Best policies seen per agent
    - Iteration history
    - Convergence status

    Example:
        >>> session = GameSession(config=config)
        >>> session.set_policy("BANK_A", initial_policy)
        >>> session.start()
        >>> session.start_iteration()
        >>> # ... run optimization ...
        >>> session.record_iteration_result(cost, per_agent, rate)
        >>> session.complete_iteration()
    """

    def __init__(self, config: GameConfig) -> None:
        """Initialize a new game session.

        Args:
            config: Game configuration.
        """
        self._config = config
        self._session_id = str(uuid.uuid4())
        self._status: SessionStatus = "initialized"
        self._current_iteration = 0
        self._is_converged = False
        self._convergence_reason: str | None = None
        self._failure_reason: str | None = None
        self._created_at = datetime.now()
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

        # Policy tracking
        self._current_policies: dict[str, dict[str, Any]] = {}
        self._best_policies: dict[str, dict[str, Any]] = {}
        self._best_costs: dict[str, float] = {}
        self._best_iterations: dict[str, int] = {}

        # History tracking
        self._iteration_history: list[IterationResult] = []
        self._evaluation_history: list[PolicyEvaluation] = []

    @property
    def session_id(self) -> str:
        """Get unique session identifier."""
        return self._session_id

    @property
    def game_id(self) -> str:
        """Get game identifier from config."""
        return self._config.game_id

    @property
    def master_seed(self) -> int:
        """Get master seed from config."""
        return self._config.master_seed

    @property
    def current_iteration(self) -> int:
        """Get current iteration number."""
        return self._current_iteration

    @property
    def is_converged(self) -> bool:
        """Check if optimization has converged."""
        return self._is_converged

    @property
    def convergence_reason(self) -> str | None:
        """Get reason for convergence."""
        return self._convergence_reason

    @property
    def failure_reason(self) -> str | None:
        """Get reason for failure."""
        return self._failure_reason

    @property
    def status(self) -> SessionStatus:
        """Get current session status."""
        return self._status

    @property
    def config(self) -> GameConfig:
        """Get game configuration."""
        return self._config

    def start(self) -> None:
        """Start the game session."""
        self._status = "running"
        self._started_at = datetime.now()

    def start_iteration(self) -> None:
        """Start a new optimization iteration."""
        self._current_iteration += 1

    def complete_iteration(self) -> None:
        """Complete the current iteration."""
        pass  # State already updated via record_iteration_result

    def mark_converged(self, reason: str) -> None:
        """Mark the session as converged.

        Args:
            reason: Human-readable convergence reason.
        """
        self._is_converged = True
        self._convergence_reason = reason
        self._status = "completed"
        self._completed_at = datetime.now()

    def mark_failed(self, reason: str) -> None:
        """Mark the session as failed.

        Args:
            reason: Human-readable failure reason.
        """
        self._status = "failed"
        self._failure_reason = reason
        self._completed_at = datetime.now()

    def set_policy(self, agent_id: str, policy: dict[str, Any]) -> None:
        """Set current policy for an agent.

        Args:
            agent_id: Agent identifier.
            policy: Policy configuration dict.
        """
        self._current_policies[agent_id] = policy

    def get_policy(self, agent_id: str) -> dict[str, Any] | None:
        """Get current policy for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Policy dict or None if not set.
        """
        return self._current_policies.get(agent_id)

    def record_evaluation(
        self,
        agent_id: str,
        policy: dict[str, Any],
        mean_cost: float,
        iteration: int,
    ) -> None:
        """Record a policy evaluation result.

        Updates best policy if this is the best seen for the agent.

        Args:
            agent_id: Agent identifier.
            policy: The evaluated policy.
            mean_cost: Mean cost from Monte Carlo evaluation.
            iteration: Iteration number.
        """
        evaluation = PolicyEvaluation(
            agent_id=agent_id,
            policy=policy,
            mean_cost=mean_cost,
            iteration=iteration,
        )
        self._evaluation_history.append(evaluation)

        # Update best if this is better
        if agent_id not in self._best_costs or mean_cost < self._best_costs[agent_id]:
            self._best_policies[agent_id] = policy
            self._best_costs[agent_id] = mean_cost
            self._best_iterations[agent_id] = iteration

    def get_best_policy(self, agent_id: str) -> dict[str, Any] | None:
        """Get best policy seen for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Dict with 'policy', 'cost', 'iteration' keys, or None if no
            evaluations recorded for this agent.
        """
        if agent_id not in self._best_policies:
            return None

        return {
            "policy": self._best_policies[agent_id],
            "cost": self._best_costs[agent_id],
            "iteration": self._best_iterations[agent_id],
        }

    def record_iteration_result(
        self,
        total_cost: float,
        per_agent_costs: dict[str, float],
        settlement_rate: float,
    ) -> None:
        """Record results from an optimization iteration.

        Args:
            total_cost: Total cost across all agents.
            per_agent_costs: Cost breakdown per agent.
            settlement_rate: Settlement success rate.
        """
        result = IterationResult(
            iteration=self._current_iteration,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            settlement_rate=settlement_rate,
        )
        self._iteration_history.append(result)

    def get_iteration_history(self) -> list[dict[str, Any]]:
        """Get history of all iteration results.

        Returns:
            List of iteration result dicts.
        """
        return [
            {
                "iteration": r.iteration,
                "total_cost": r.total_cost,
                "per_agent_costs": r.per_agent_costs,
                "settlement_rate": r.settlement_rate,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in self._iteration_history
        ]

    def get_agent_history(self, agent_id: str) -> list[dict[str, Any]]:
        """Get evaluation history for a specific agent.

        IMPORTANT: Returns only the specified agent's data to prevent
        cross-agent information leakage.

        Args:
            agent_id: Agent identifier.

        Returns:
            List of evaluation dicts for this agent only.
        """
        return [
            {
                "agent_id": e.agent_id,
                "iteration": e.iteration,
                "cost": e.mean_cost,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self._evaluation_history
            if e.agent_id == agent_id
        ]
