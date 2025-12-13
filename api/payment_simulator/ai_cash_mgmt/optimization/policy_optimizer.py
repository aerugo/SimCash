"""LLM-based policy optimizer.

Generates improved policies using LLM with retry logic and validation.

Uses rich 50k+ token context with verbose output, cost breakdown,
iteration history with acceptance status, and optimization guidance.
This provides the LLM full visibility into what went right and wrong
in simulations for better optimization results.
"""

from __future__ import annotations

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
from payment_simulator.ai_cash_mgmt.prompts.system_prompt_builder import (
    build_system_prompt,
)
from payment_simulator.ai_cash_mgmt.prompts.user_prompt_builder import (
    UserPromptBuilder,
)

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.prompts.context_types import (
        SingleAgentIterationRecord,
    )


class DebugCallback(Protocol):
    """Protocol for debug callbacks during policy optimization.

    Implementations can log progress during the retry loop.
    """

    def on_attempt_start(self, agent_id: str, attempt: int, max_attempts: int) -> None:
        """Called when starting an LLM request attempt.

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum retry attempts.
        """
        ...

    def on_validation_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        errors: list[str],
    ) -> None:
        """Called when validation fails.

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum retry attempts.
            errors: List of validation error messages.
        """
        ...

    def on_llm_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        error: str,
    ) -> None:
        """Called when the LLM call fails.

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum retry attempts.
            error: Error message.
        """
        ...

    def on_validation_success(self, agent_id: str, attempt: int) -> None:
        """Called when validation succeeds.

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
        """
        ...

    def on_all_retries_exhausted(
        self,
        agent_id: str,
        max_attempts: int,
        final_errors: list[str],
    ) -> None:
        """Called when all retry attempts are exhausted.

        Args:
            agent_id: Agent being optimized.
            max_attempts: Maximum retry attempts.
            final_errors: Final validation errors.
        """
        ...


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
        ...     llm_model="gpt-5.2",
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


class PolicyOptimizer:
    """LLM-based policy optimizer with retry logic.

    Generates improved policies via LLM using rich extended context,
    validates them against scenario constraints, and retries on
    validation failure.

    Example:
        >>> optimizer = PolicyOptimizer(
        ...     constraints=scenario_constraints,
        ...     max_retries=3,
        ... )
        >>> result = await optimizer.optimize(
        ...     agent_id="BANK_A",
        ...     current_policy=current,
        ...     current_iteration=5,
        ...     current_metrics={"total_cost_mean": 12500},
        ...     llm_client=client,
        ...     llm_model="gpt-5.2",
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
        # Cache for system prompt (built once per session)
        self._system_prompt: str | None = None
        self._cost_rates: dict[str, Any] | None = None
        # Track current customization for cache invalidation
        self._current_customization: str | None = None

    def get_system_prompt(
        self,
        cost_rates: dict[str, Any] | None = None,
        customization: str | None = None,
    ) -> str:
        """Get or build the system prompt with optional customization.

        The system prompt contains schema-filtered documentation. When
        customization changes, the prompt is rebuilt.

        Args:
            cost_rates: Optional cost rate configuration.
            customization: Optional experiment-specific customization text.
                          If different from cached customization, rebuilds prompt.

        Returns:
            Complete system prompt string.
        """
        # Check if we need to rebuild (either no cache or customization changed)
        need_rebuild = (
            self._system_prompt is None
            or self._current_customization != customization
        )

        if need_rebuild:
            self._system_prompt = build_system_prompt(
                constraints=self._constraints,
                cost_rates=cost_rates or self._cost_rates,
                customization=customization,
            )
            self._current_customization = customization

        # At this point, _system_prompt is guaranteed to be set
        assert self._system_prompt is not None
        return self._system_prompt

    def set_cost_rates(self, rates: dict[str, Any]) -> None:
        """Set cost rates for system prompt generation.

        Args:
            rates: Cost rate configuration.
        """
        self._cost_rates = rates
        # Invalidate cached system prompt
        self._system_prompt = None

    async def optimize(
        self,
        agent_id: str,
        current_policy: dict[str, Any],
        current_iteration: int,
        current_metrics: dict[str, Any],
        llm_client: LLMClientProtocol,
        llm_model: str,
        current_cost: float = 0.0,
        iteration_history: list[SingleAgentIterationRecord] | None = None,
        events: list[dict[str, Any]] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        debug_callback: DebugCallback | None = None,
    ) -> OptimizationResult:
        """Generate an optimized policy via LLM.

        Attempts to generate a valid policy using rich extended context,
        retrying on validation failure up to max_retries times.

        Args:
            agent_id: The agent being optimized.
            current_policy: Current policy configuration.
            current_iteration: Current iteration number.
            current_metrics: Aggregated metrics from current iteration.
            llm_client: LLM client for policy generation.
            llm_model: Model identifier for tracking.
            current_cost: Current policy's cost.
            iteration_history: Full iteration records for context.
            best_seed_output: Verbose output from best performing seed.
            worst_seed_output: Verbose output from worst performing seed.
            best_seed: Best performing seed number.
            worst_seed: Worst performing seed number.
            best_seed_cost: Cost from best seed.
            worst_seed_cost: Cost from worst seed.
            cost_breakdown: Breakdown of costs by type (delay, collateral, etc).
            cost_rates: Cost rate configuration from simulation.
            debug_callback: Optional callback for debug logging during retries.
            events: Raw simulation events to be filtered by agent. When provided,
                events are filtered to only show the target agent's data:
                - Outgoing transactions FROM the agent
                - Incoming liquidity events TO the agent
                - Agent-specific state changes and costs
                This enforces agent isolation: Agent X never sees Agent Y's data.

        Returns:
            OptimizationResult with new policy or None if failed.
        """
        validation_errors: list[str] = []
        total_tokens = 0
        start_time = time.monotonic()

        for attempt in range(self._max_retries):
            # Debug: Log attempt start
            if debug_callback is not None:
                debug_callback.on_attempt_start(
                    agent_id, attempt + 1, self._max_retries
                )

            # Build rich extended context prompt
            prompt = build_single_agent_context(
                current_iteration=current_iteration,
                current_policy=current_policy,
                current_metrics=current_metrics,
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

            # Add full current policy using UserPromptBuilder
            # This ensures the LLM sees the complete policy tree (not just parameters)
            user_prompt_builder = UserPromptBuilder(agent_id, current_policy)

            # Always include the full policy section
            policy_section = user_prompt_builder._build_policy_section()
            prompt += f"\n\n{policy_section}"

            # NOTE: Simulation events are already included in the single-agent context
            # via best_seed_output and worst_seed_output (Section 4: SIMULATION OUTPUT).
            # Adding _build_simulation_section() here would DUPLICATE the events.

            # Add validation errors for retry
            if attempt > 0 and validation_errors:
                prompt += "\n\n## VALIDATION ERROR - PLEASE FIX\n\n"
                prompt += "Your previous attempt failed validation:\n"
                for error in validation_errors:
                    prompt += f"  - {error}\n"
                prompt += "\nPlease fix these issues in your response."

            # Generate policy from LLM
            try:
                new_policy = await llm_client.generate_policy(
                    prompt=prompt,
                    current_policy=current_policy,
                    context={"iteration": current_iteration},
                )
            except Exception as e:
                validation_errors = [f"LLM error: {e!s}"]
                # Debug: Log LLM error
                if debug_callback is not None:
                    debug_callback.on_llm_error(
                        agent_id, attempt + 1, self._max_retries, str(e)
                    )
                continue

            # Validate the generated policy
            result = self._validator.validate(new_policy)

            if result.is_valid:
                # Debug: Log validation success
                if debug_callback is not None:
                    debug_callback.on_validation_success(agent_id, attempt + 1)

                # Success!
                elapsed = time.monotonic() - start_time
                return OptimizationResult(
                    agent_id=agent_id,
                    iteration=current_iteration,
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

            # Debug: Log validation error
            if debug_callback is not None:
                debug_callback.on_validation_error(
                    agent_id, attempt + 1, self._max_retries, validation_errors
                )

        # All retries exhausted
        if debug_callback is not None:
            debug_callback.on_all_retries_exhausted(
                agent_id, self._max_retries, validation_errors
            )

        elapsed = time.monotonic() - start_time
        return OptimizationResult(
            agent_id=agent_id,
            iteration=current_iteration,
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
