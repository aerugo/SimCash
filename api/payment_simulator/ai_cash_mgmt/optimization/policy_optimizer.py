"""LLM-based policy optimizer.

Generates improved policies using LLM with retry logic and validation.

This module supports two modes of operation:
1. Basic mode: Uses simple prompt with just current policy and performance history
2. Extended mode: Uses rich 50k+ token context with verbose output, cost breakdown,
   iteration history with acceptance status, and optimization guidance

The extended mode provides significantly better optimization results by giving
the LLM full visibility into what went right and wrong in simulations.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)
from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
    ConstraintValidator,
)
from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
    build_single_agent_context,
)

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.prompts.context_types import (
        SingleAgentIterationRecord,
    )


@dataclass
class OptimizationResult:
    """Result of a policy optimization attempt.

    Captures the full context of an optimization attempt including
    the old and new policies, costs, and any validation errors.

    Example:
        >>> result = OptimizationResult(
        ...     agent_id="BANK_A",
        ...     iteration=5,
        ...     old_policy={"payment_tree": {"root": {"action": "queue"}}},
        ...     new_policy={"payment_tree": {"root": {"action": "submit"}}},
        ...     old_cost=1000.0,
        ...     new_cost=800.0,
        ...     was_accepted=True,
        ...     validation_errors=[],
        ...     llm_latency_seconds=1.5,
        ...     tokens_used=500,
        ...     llm_model="gpt-5.1",
        ... )
    """

    agent_id: str
    iteration: int
    old_policy: dict[str, Any]
    new_policy: dict[str, Any] | None
    old_cost: float
    new_cost: float | None
    was_accepted: bool
    validation_errors: list[str]
    llm_latency_seconds: float
    tokens_used: int
    llm_model: str


class LLMClientProtocol(Protocol):
    """Protocol for LLM clients.

    Implementations must provide generate_policy() which takes
    a prompt and returns a policy dict.
    """

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a policy from prompt and context.

        Args:
            prompt: The optimization prompt.
            current_policy: The current policy being optimized.
            context: Additional context (performance history, etc).

        Returns:
            Generated policy dict.
        """
        ...


def build_optimization_prompt(
    agent_id: str,
    current_policy: dict[str, Any],
    performance_history: list[dict[str, Any]],
    validation_errors: list[str] | None = None,
) -> str:
    """Build an optimization prompt for the LLM.

    Args:
        agent_id: The agent being optimized.
        current_policy: Current policy configuration.
        performance_history: History of costs per iteration.
        validation_errors: Errors from previous attempt (for retries).

    Returns:
        Prompt string for the LLM.
    """
    lines = [
        f"Optimize the payment policy for agent {agent_id}.",
        "",
        "Current Policy:",
        json.dumps(current_policy, indent=2),
        "",
    ]

    if performance_history:
        lines.append("Performance History:")
        for entry in performance_history[-5:]:  # Last 5 entries
            iteration = entry.get("iteration", "?")
            cost = entry.get("cost", "?")
            lines.append(f"  - Iteration {iteration}: cost = {cost}")
        lines.append("")

    if validation_errors:
        lines.append("PREVIOUS ATTEMPT FAILED with these errors:")
        for error in validation_errors:
            lines.append(f"  - {error}")
        lines.append("")
        lines.append("Please fix these issues in your response.")
        lines.append("")

    lines.extend([
        "Generate an improved policy that reduces total cost.",
        "The policy must be valid JSON matching the decision tree schema.",
    ])

    return "\n".join(lines)


class PolicyOptimizer:
    """LLM-based policy optimizer with retry logic.

    Generates improved policies via LLM, validates them against
    scenario constraints, and retries on validation failure.

    Example:
        >>> optimizer = PolicyOptimizer(
        ...     constraints=scenario_constraints,
        ...     max_retries=3,
        ... )
        >>> result = await optimizer.optimize(
        ...     agent_id="BANK_A",
        ...     current_policy=current,
        ...     performance_history=history,
        ...     llm_client=client,
        ...     llm_model="gpt-5.1",
        ... )
    """

    def __init__(
        self,
        constraints: ScenarioConstraints,
        max_retries: int = 3,
    ) -> None:
        """Initialize the optimizer.

        Args:
            constraints: Scenario constraints for validation.
            max_retries: Maximum retry attempts on validation failure.
        """
        self._constraints = constraints
        self._max_retries = max_retries
        self._validator = ConstraintValidator(constraints)

    async def optimize(
        self,
        agent_id: str,
        current_policy: dict[str, Any],
        performance_history: list[dict[str, Any]],
        llm_client: LLMClientProtocol,
        llm_model: str,
        current_cost: float = 0.0,
        # Extended context parameters (optional)
        iteration_history: list[SingleAgentIterationRecord] | None = None,
        current_metrics: dict[str, Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """Generate an optimized policy via LLM.

        Attempts to generate a valid policy, retrying on validation
        failure up to max_retries times.

        Supports two modes:
        - Basic mode: Pass only required params for simple prompts
        - Extended mode: Pass iteration_history and other extended params
          for rich 50k+ token context prompts

        Args:
            agent_id: The agent being optimized.
            current_policy: Current policy configuration.
            performance_history: History of costs per iteration (basic mode).
            llm_client: LLM client for policy generation.
            llm_model: Model identifier for tracking.
            current_cost: Current policy's cost.
            iteration_history: Full iteration records for extended context.
            current_metrics: Current metrics dict for extended context.
            best_seed_output: Verbose output from best performing seed.
            worst_seed_output: Verbose output from worst performing seed.
            best_seed: Best performing seed number.
            worst_seed: Worst performing seed number.
            best_seed_cost: Cost from best seed.
            worst_seed_cost: Cost from worst seed.
            cost_breakdown: Breakdown of costs by type (delay, collateral, etc).
            cost_rates: Cost rate configuration from simulation.

        Returns:
            OptimizationResult with new policy or None if failed.
        """
        validation_errors: list[str] = []
        total_tokens = 0
        start_time = time.monotonic()

        # Determine if we should use extended context mode
        use_extended_context = iteration_history is not None

        for attempt in range(self._max_retries):
            # Build prompt (include errors on retry)
            if use_extended_context:
                # Extended context mode - rich 50k+ token prompt
                prompt = build_single_agent_context(
                    current_iteration=len(iteration_history) if iteration_history else 0,
                    current_policy=current_policy,
                    current_metrics=current_metrics or {},
                    iteration_history=iteration_history,
                    best_seed_output=best_seed_output,
                    worst_seed_output=worst_seed_output,
                    best_seed=best_seed,
                    worst_seed=worst_seed,
                    best_seed_cost=best_seed_cost,
                    worst_seed_cost=worst_seed_cost,
                    cost_breakdown=cost_breakdown,
                    cost_rates=cost_rates,
                    agent_id=agent_id,
                )
                # Add validation errors for retry
                if attempt > 0 and validation_errors:
                    prompt += "\n\n## VALIDATION ERROR - PLEASE FIX\n\n"
                    prompt += "Your previous attempt failed validation:\n"
                    for error in validation_errors:
                        prompt += f"  - {error}\n"
                    prompt += "\nPlease fix these issues in your response."
            else:
                # Basic mode - simple prompt
                prompt = build_optimization_prompt(
                    agent_id=agent_id,
                    current_policy=current_policy,
                    performance_history=performance_history,
                    validation_errors=validation_errors if attempt > 0 else None,
                )

            # Generate policy from LLM
            try:
                new_policy = await llm_client.generate_policy(
                    prompt=prompt,
                    current_policy=current_policy,
                    context={"history": performance_history},
                )
            except Exception as e:
                validation_errors = [f"LLM error: {e!s}"]
                continue

            # Validate the generated policy
            result = self._validator.validate(new_policy)

            if result.is_valid:
                # Success!
                elapsed = time.monotonic() - start_time
                return OptimizationResult(
                    agent_id=agent_id,
                    iteration=len(performance_history),
                    old_policy=current_policy,
                    new_policy=new_policy,
                    old_cost=current_cost,
                    new_cost=None,  # Not evaluated yet
                    was_accepted=True,  # Pending evaluation
                    validation_errors=[],
                    llm_latency_seconds=elapsed,
                    tokens_used=total_tokens,
                    llm_model=llm_model,
                )

            # Validation failed - collect errors for retry
            validation_errors = result.errors

        # All retries exhausted
        elapsed = time.monotonic() - start_time
        return OptimizationResult(
            agent_id=agent_id,
            iteration=len(performance_history),
            old_policy=current_policy,
            new_policy=None,
            old_cost=current_cost,
            new_cost=None,
            was_accepted=False,
            validation_errors=validation_errors,
            llm_latency_seconds=elapsed,
            tokens_used=total_tokens,
            llm_model=llm_model,
        )
