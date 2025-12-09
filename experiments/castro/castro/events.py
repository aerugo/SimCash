"""Event types for Castro experiment replay identity.

All verbose output is driven by events. Events are self-contained
and include ALL data needed for display (no joins required).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# =============================================================================
# Event Type Constants
# =============================================================================

EVENT_EXPERIMENT_START = "experiment_start"
EVENT_ITERATION_START = "iteration_start"
EVENT_MONTE_CARLO_EVALUATION = "monte_carlo_evaluation"
EVENT_LLM_CALL = "llm_call"
EVENT_POLICY_CHANGE = "policy_change"
EVENT_POLICY_REJECTED = "policy_rejected"
EVENT_EXPERIMENT_END = "experiment_end"

ALL_EVENT_TYPES: list[str] = [
    EVENT_EXPERIMENT_START,
    EVENT_ITERATION_START,
    EVENT_MONTE_CARLO_EVALUATION,
    EVENT_LLM_CALL,
    EVENT_POLICY_CHANGE,
    EVENT_POLICY_REJECTED,
    EVENT_EXPERIMENT_END,
]


# =============================================================================
# Core Event Class
# =============================================================================


@dataclass
class ExperimentEvent:
    """Base event for experiment replay.

    All events are self-contained - they include ALL data needed
    for display, not just references to be looked up later.

    Attributes:
        event_type: Type of event (one of EVENT_* constants)
        run_id: Unique run identifier
        iteration: Iteration number (0 for pre-iteration events)
        timestamp: When the event occurred
        details: Event-specific data (fully self-contained)
    """

    event_type: str
    run_id: str
    iteration: int
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to a dictionary for serialization.

        Returns:
            Dictionary representation with ISO timestamp
        """
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentEvent:
        """Create event from a dictionary.

        Args:
            data: Dictionary with event data

        Returns:
            ExperimentEvent instance
        """
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            event_type=data["event_type"],
            run_id=data["run_id"],
            iteration=data["iteration"],
            timestamp=timestamp,
            details=data.get("details", {}),
        )


# =============================================================================
# Event Creation Helpers
# =============================================================================


def create_experiment_start_event(
    run_id: str,
    experiment_name: str,
    description: str,
    model: str,
    max_iterations: int,
    num_samples: int,
) -> ExperimentEvent:
    """Create an experiment start event.

    Args:
        run_id: Unique run identifier
        experiment_name: Name of the experiment (exp1, exp2, exp3)
        description: Human-readable description
        model: LLM model string (e.g., "anthropic:claude-sonnet-4-5")
        max_iterations: Maximum optimization iterations
        num_samples: Monte Carlo sample count

    Returns:
        ExperimentEvent for experiment start
    """
    return ExperimentEvent(
        event_type=EVENT_EXPERIMENT_START,
        run_id=run_id,
        iteration=0,  # Before first iteration
        timestamp=datetime.now(),
        details={
            "experiment_name": experiment_name,
            "description": description,
            "model": model,
            "max_iterations": max_iterations,
            "num_samples": num_samples,
        },
    )


def create_iteration_start_event(
    run_id: str,
    iteration: int,
    total_cost: int,
) -> ExperimentEvent:
    """Create an iteration start event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        total_cost: Total cost at start of iteration (cents)

    Returns:
        ExperimentEvent for iteration start
    """
    return ExperimentEvent(
        event_type=EVENT_ITERATION_START,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "total_cost": total_cost,
        },
    )


def create_monte_carlo_event(
    run_id: str,
    iteration: int,
    seed_results: list[dict[str, Any]],
    mean_cost: int,
    std_cost: int,
) -> ExperimentEvent:
    """Create a Monte Carlo evaluation event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        seed_results: List of per-seed results with keys:
            seed, cost, settled, total, settlement_rate
        mean_cost: Mean cost across seeds (cents)
        std_cost: Standard deviation of costs (cents)

    Returns:
        ExperimentEvent for Monte Carlo evaluation
    """
    return ExperimentEvent(
        event_type=EVENT_MONTE_CARLO_EVALUATION,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "seed_results": seed_results,
            "mean_cost": mean_cost,
            "std_cost": std_cost,
        },
    )


def create_llm_call_event(
    run_id: str,
    iteration: int,
    agent_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_seconds: float,
    context_summary: dict[str, Any] | None = None,
) -> ExperimentEvent:
    """Create an LLM call event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent being optimized
        model: LLM model used
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        latency_seconds: API call latency
        context_summary: Optional summary of context provided to LLM

    Returns:
        ExperimentEvent for LLM call
    """
    return ExperimentEvent(
        event_type=EVENT_LLM_CALL,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "agent_id": agent_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_seconds": latency_seconds,
            "context_summary": context_summary or {},
        },
    )


def create_policy_change_event(
    run_id: str,
    iteration: int,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    old_cost: int,
    new_cost: int,
    accepted: bool,
) -> ExperimentEvent:
    """Create a policy change event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent whose policy changed
        old_policy: Previous policy
        new_policy: New policy
        old_cost: Cost with old policy (cents)
        new_cost: Cost with new policy (cents)
        accepted: Whether the change was accepted

    Returns:
        ExperimentEvent for policy change
    """
    return ExperimentEvent(
        event_type=EVENT_POLICY_CHANGE,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "agent_id": agent_id,
            "old_policy": old_policy,
            "new_policy": new_policy,
            "old_cost": old_cost,
            "new_cost": new_cost,
            "accepted": accepted,
        },
    )


def create_policy_rejected_event(
    run_id: str,
    iteration: int,
    agent_id: str,
    proposed_policy: dict[str, Any],
    validation_errors: list[str],
    rejection_reason: str,
    old_cost: int | None = None,
    new_cost: int | None = None,
) -> ExperimentEvent:
    """Create a policy rejected event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent whose policy was rejected
        proposed_policy: The rejected policy
        validation_errors: List of validation error messages
        rejection_reason: Reason for rejection (validation_failed, cost_not_improved)
        old_cost: Previous cost if applicable (cents)
        new_cost: New cost if applicable (cents)

    Returns:
        ExperimentEvent for policy rejection
    """
    return ExperimentEvent(
        event_type=EVENT_POLICY_REJECTED,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "agent_id": agent_id,
            "proposed_policy": proposed_policy,
            "validation_errors": validation_errors,
            "rejection_reason": rejection_reason,
            "old_cost": old_cost,
            "new_cost": new_cost,
        },
    )


def create_experiment_end_event(
    run_id: str,
    iteration: int,
    final_cost: int,
    best_cost: int,
    converged: bool,
    convergence_reason: str,
    duration_seconds: float,
) -> ExperimentEvent:
    """Create an experiment end event.

    Args:
        run_id: Unique run identifier
        iteration: Final iteration number
        final_cost: Final cost at end (cents)
        best_cost: Best cost achieved (cents)
        converged: Whether experiment converged
        convergence_reason: Reason for stopping
        duration_seconds: Total experiment duration

    Returns:
        ExperimentEvent for experiment end
    """
    return ExperimentEvent(
        event_type=EVENT_EXPERIMENT_END,
        run_id=run_id,
        iteration=iteration,
        timestamp=datetime.now(),
        details={
            "final_cost": final_cost,
            "best_cost": best_cost,
            "converged": converged,
            "convergence_reason": convergence_reason,
            "duration_seconds": duration_seconds,
        },
    )
