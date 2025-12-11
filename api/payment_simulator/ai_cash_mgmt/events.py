"""LLM optimization event types and creation helpers.

Provides event types and creation helpers for LLM-driven policy optimization
experiments. All events use the core EventRecord from experiments.persistence.

Phase 12, Task 12.1: Event System in Core

All costs are integer cents (INV-1 compliance).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from payment_simulator.experiments.persistence import EventRecord

# =============================================================================
# Event Type Constants
# =============================================================================

EVENT_EXPERIMENT_START = "experiment_start"
EVENT_ITERATION_START = "iteration_start"
EVENT_BOOTSTRAP_EVALUATION = "bootstrap_evaluation"
EVENT_LLM_CALL = "llm_call"
EVENT_LLM_INTERACTION = "llm_interaction"  # Full audit data for replay
EVENT_POLICY_CHANGE = "policy_change"
EVENT_POLICY_REJECTED = "policy_rejected"
EVENT_EXPERIMENT_END = "experiment_end"

ALL_EVENT_TYPES: list[str] = [
    EVENT_EXPERIMENT_START,
    EVENT_ITERATION_START,
    EVENT_BOOTSTRAP_EVALUATION,
    EVENT_LLM_CALL,
    EVENT_LLM_INTERACTION,
    EVENT_POLICY_CHANGE,
    EVENT_POLICY_REJECTED,
    EVENT_EXPERIMENT_END,
]


# =============================================================================
# Helper for ISO timestamps
# =============================================================================


def _now_iso() -> str:
    """Return current time as ISO format string."""
    return datetime.now().isoformat()


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
) -> EventRecord:
    """Create an experiment start event.

    Args:
        run_id: Unique run identifier
        experiment_name: Name of the experiment (exp1, exp2, exp3)
        description: Human-readable description
        model: LLM model string (e.g., "anthropic:claude-sonnet-4-5")
        max_iterations: Maximum optimization iterations
        num_samples: Bootstrap sample count

    Returns:
        EventRecord for experiment start
    """
    return EventRecord(
        run_id=run_id,
        iteration=0,  # Before first iteration
        event_type=EVENT_EXPERIMENT_START,
        event_data={
            "experiment_name": experiment_name,
            "description": description,
            "model": model,
            "max_iterations": max_iterations,
            "num_samples": num_samples,
        },
        timestamp=_now_iso(),
    )


def create_iteration_start_event(
    run_id: str,
    iteration: int,
    total_cost: int,
) -> EventRecord:
    """Create an iteration start event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        total_cost: Total cost at start of iteration (integer cents - INV-1)

    Returns:
        EventRecord for iteration start
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_ITERATION_START,
        event_data={
            "total_cost": total_cost,
        },
        timestamp=_now_iso(),
    )


def create_bootstrap_evaluation_event(
    run_id: str,
    iteration: int,
    seed_results: list[dict[str, Any]],
    mean_cost: int,
    std_cost: int,
) -> EventRecord:
    """Create a bootstrap evaluation event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        seed_results: List of per-seed results with keys:
            seed, cost, settled, total, settlement_rate
        mean_cost: Mean cost across seeds (integer cents - INV-1)
        std_cost: Standard deviation of costs (integer cents - INV-1)

    Returns:
        EventRecord for bootstrap evaluation
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_BOOTSTRAP_EVALUATION,
        event_data={
            "seed_results": seed_results,
            "mean_cost": mean_cost,
            "std_cost": std_cost,
        },
        timestamp=_now_iso(),
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
) -> EventRecord:
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
        EventRecord for LLM call
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_LLM_CALL,
        event_data={
            "agent_id": agent_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_seconds": latency_seconds,
            "context_summary": context_summary or {},
        },
        timestamp=_now_iso(),
    )


def create_llm_interaction_event(
    run_id: str,
    iteration: int,
    agent_id: str,
    system_prompt: str,
    user_prompt: str,
    raw_response: str,
    parsed_policy: dict[str, Any] | None,
    parsing_error: str | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_seconds: float,
) -> EventRecord:
    """Create an LLM interaction event for audit replay.

    This event captures the FULL LLM interaction for audit purposes:
    - Complete system and user prompts sent to the LLM
    - Raw response received (before parsing)
    - Parsed policy or parsing error

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent being optimized
        system_prompt: Full system prompt sent to LLM
        user_prompt: Full user prompt sent to LLM
        raw_response: Raw LLM response text before parsing
        parsed_policy: Parsed policy dict if successful, None if failed
        parsing_error: Error message if parsing failed, None if successful
        model: LLM model used
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        latency_seconds: API call latency

    Returns:
        EventRecord for LLM interaction audit
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_LLM_INTERACTION,
        event_data={
            "agent_id": agent_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": raw_response,
            "parsed_policy": parsed_policy,
            "parsing_error": parsing_error,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_seconds": latency_seconds,
        },
        timestamp=_now_iso(),
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
) -> EventRecord:
    """Create a policy change event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent whose policy changed
        old_policy: Previous policy
        new_policy: New policy
        old_cost: Cost with old policy (integer cents - INV-1)
        new_cost: Cost with new policy (integer cents - INV-1)
        accepted: Whether the change was accepted

    Returns:
        EventRecord for policy change
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_POLICY_CHANGE,
        event_data={
            "agent_id": agent_id,
            "old_policy": old_policy,
            "new_policy": new_policy,
            "old_cost": old_cost,
            "new_cost": new_cost,
            "accepted": accepted,
        },
        timestamp=_now_iso(),
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
) -> EventRecord:
    """Create a policy rejected event.

    Args:
        run_id: Unique run identifier
        iteration: Current iteration number
        agent_id: Agent whose policy was rejected
        proposed_policy: The rejected policy
        validation_errors: List of validation error messages
        rejection_reason: Reason for rejection (validation_failed, cost_not_improved)
        old_cost: Previous cost if applicable (integer cents - INV-1)
        new_cost: New cost if applicable (integer cents - INV-1)

    Returns:
        EventRecord for policy rejection
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_POLICY_REJECTED,
        event_data={
            "agent_id": agent_id,
            "proposed_policy": proposed_policy,
            "validation_errors": validation_errors,
            "rejection_reason": rejection_reason,
            "old_cost": old_cost,
            "new_cost": new_cost,
        },
        timestamp=_now_iso(),
    )


def create_experiment_end_event(
    run_id: str,
    iteration: int,
    final_cost: int,
    best_cost: int,
    converged: bool,
    convergence_reason: str,
    duration_seconds: float,
) -> EventRecord:
    """Create an experiment end event.

    Args:
        run_id: Unique run identifier
        iteration: Final iteration number
        final_cost: Final cost at end (integer cents - INV-1)
        best_cost: Best cost achieved (integer cents - INV-1)
        converged: Whether experiment converged
        convergence_reason: Reason for stopping
        duration_seconds: Total experiment duration

    Returns:
        EventRecord for experiment end
    """
    return EventRecord(
        run_id=run_id,
        iteration=iteration,
        event_type=EVENT_EXPERIMENT_END,
        event_data={
            "final_cost": final_cost,
            "best_cost": best_cost,
            "converged": converged,
            "convergence_reason": convergence_reason,
            "duration_seconds": duration_seconds,
        },
        timestamp=_now_iso(),
    )
