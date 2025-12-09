"""LLM-based policy optimizer.

Generates improved policies using LLM with retry logic and validation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)
from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
    ConstraintValidator,
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
    ) -> OptimizationResult:
        """Generate an optimized policy via LLM.

        Attempts to generate a valid policy, retrying on validation
        failure up to max_retries times.

        Args:
            agent_id: The agent being optimized.
            current_policy: Current policy configuration.
            performance_history: History of costs per iteration.
            llm_client: LLM client for policy generation.
            llm_model: Model identifier for tracking.
            current_cost: Current policy's cost.

        Returns:
            OptimizationResult with new policy or None if failed.
        """
        validation_errors: list[str] = []
        total_tokens = 0
        start_time = time.monotonic()

        for attempt in range(self._max_retries):
            # Build prompt (include errors on retry)
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
