"""LLM-based policy optimizer for castro experiments.

Uses PydanticAI via RobustPolicyAgent for structured policy generation.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from experiments.castro.schemas.parameter_config import ScenarioConstraints


class LLMOptimizer:
    """LLM-based policy optimizer using PydanticAI structured output.

    This class wraps RobustPolicyAgent to generate validated policies
    using PydanticAI's structured output capabilities. This ensures:
    - Correct API usage for reasoning models (GPT-5.1, o1, etc.)
    - Structured JSON output with validation
    - Proper retry logic on validation failures
    - Extended thinking support for Anthropic Claude models
    - Castro paper alignment when castro_mode=True

    Usage:
        optimizer = LLMOptimizer(
            model="gpt-4o",
            reasoning_effort="high",
            castro_mode=True,
        )
        policy, tokens, latency = optimizer.generate_policy(
            instruction="Minimize delay costs",
            current_policy=old_policy,
            current_cost=1500,
        )
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        reasoning_effort: Literal["low", "medium", "high"] = "high",
        thinking_budget: int | None = None,
        verbose: bool = False,
        castro_mode: bool = False,
    ) -> None:
        """Initialize the LLM optimizer.

        Args:
            model: LLM model to use (e.g., "gpt-4o", "claude-3-5-sonnet")
            reasoning_effort: Reasoning level for API (low, medium, high)
            thinking_budget: Token budget for extended thinking (Claude only)
            verbose: Enable verbose output
            castro_mode: Use Castro paper constraints
        """
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS, STANDARD_CONSTRAINTS

        self.model = model
        self.reasoning_effort = reasoning_effort
        self.thinking_budget = thinking_budget
        self.verbose = verbose
        self.castro_mode = castro_mode

        # Select constraints based on mode
        constraints: ScenarioConstraints = CASTRO_CONSTRAINTS if castro_mode else STANDARD_CONSTRAINTS
        if verbose and castro_mode:
            print("[Castro Mode] Using CASTRO_CONSTRAINTS for policy generation")

        # Create RobustPolicyAgent with constraints
        self.agent = RobustPolicyAgent(
            constraints=constraints,
            model=model,
            reasoning_effort=reasoning_effort,
            thinking_budget=thinking_budget,
            verbose=verbose,
            castro_mode=castro_mode,
        )

        # Track last prompt for logging
        self._last_prompt: str = ""

    def create_prompt(
        self,
        experiment_name: str,
        iteration: int,
        policy_a: dict[str, Any],
        policy_b: dict[str, Any],
        metrics: dict[str, float | int],
        results: list[dict[str, Any]],
        cost_rates: dict[str, Any],
    ) -> str:
        """Create optimization prompt for LLM.

        Args:
            experiment_name: Name of the experiment
            iteration: Current iteration number
            policy_a: Current Bank A policy
            policy_b: Current Bank B policy
            metrics: Aggregated metrics from last iteration
            results: Raw simulation results
            cost_rates: Cost rate configuration

        Returns:
            Formatted prompt string
        """
        prompt = f"""# Policy Optimization - {experiment_name} - Iteration {iteration}

## Current Performance
- Mean Cost: ${metrics['total_cost_mean']:,.0f} ± ${metrics['total_cost_std']:,.0f}
- Settlement Rate: {metrics['settlement_rate_mean']*100:.1f}%
- Best/Worst: ${metrics['best_seed_cost']:,.0f} / ${metrics['worst_seed_cost']:,.0f}

## Cost Rates
{json.dumps(cost_rates, indent=2)}

## Task
Generate an improved policy that reduces total cost while maintaining 100% settlement.
Focus on optimizing the trade-off between collateral costs and delay costs.
"""
        self._last_prompt = prompt
        return prompt

    def generate_policy(
        self,
        instruction: str,
        current_policy: dict[str, Any] | None = None,
        current_cost: float = 0,
        settlement_rate: float = 1.0,
        iteration: int = 0,
        # Extended context parameters
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, int, float]:
        """Generate an optimized policy using PydanticAI with extended context.

        CRITICAL ISOLATION: This method receives ONLY the specified agent's data.
        The iteration_history must be pre-filtered to contain only this agent's
        policy history. No cross-agent information should be passed.

        Args:
            instruction: Natural language instruction for optimization
            current_policy: This agent's current policy
            current_cost: Approximate cost for this agent
            settlement_rate: Current settlement rate
            iteration: Current iteration number
            iteration_history: MUST be filtered for this agent only
            best_seed_output: Simulation output filtered for this agent
            worst_seed_output: Simulation output filtered for this agent
            best_seed: Best performing seed number
            worst_seed: Worst performing seed number
            best_seed_cost: Cost from best seed
            worst_seed_cost: Cost from worst seed
            cost_breakdown: Cost breakdown by type
            cost_rates: Cost rate configuration
            agent_id: Identifier of the agent being optimized

        Returns:
            tuple of (policy_dict or None, tokens_used, latency_seconds)
        """
        start_time = time.time()

        try:
            policy = self.agent.generate_policy(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
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

            latency = time.time() - start_time
            tokens = 2000  # Rough estimate

            return policy, tokens, latency

        except Exception as e:
            latency = time.time() - start_time
            if self.verbose:
                print(f"  Policy generation error: {e}")
            return None, 0, latency

    async def generate_policy_async(
        self,
        instruction: str,
        current_policy: dict[str, Any] | None = None,
        current_cost: float = 0,
        settlement_rate: float = 1.0,
        iteration: int = 0,
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
        stagger_delay: float = 0.0,
    ) -> tuple[dict[str, Any] | None, int, float]:
        """Async version of generate_policy for parallel execution.

        CRITICAL ISOLATION: Each agent's call is completely independent.
        No shared state between parallel calls.

        Args:
            stagger_delay: Initial delay before starting (for rate limit avoidance)
            ... (other args same as generate_policy)

        Returns:
            tuple of (policy_dict or None, tokens_used, latency_seconds)
        """
        # Apply staggered delay to avoid rate limits
        if stagger_delay > 0:
            await asyncio.sleep(stagger_delay)

        start_time = time.time()

        try:
            # Use the native async method from RobustPolicyAgent
            policy = await self.agent.generate_policy_async(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
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

            latency = time.time() - start_time
            tokens = 2000  # Rough estimate

            return policy, tokens, latency

        except Exception as e:
            latency = time.time() - start_time
            if self.verbose:
                print(f"  Policy generation error for {agent_id}: {e}")
            return None, 0, latency

    async def generate_policies_parallel(
        self,
        agent_configs: list[dict[str, Any]],
        stagger_interval: float = 0.5,
    ) -> list[tuple[str, dict[str, Any] | None, int, float]]:
        """Generate policies for multiple agents in parallel with staggered starts.

        CRITICAL ISOLATION: Each agent runs in complete isolation.
        - Separate coroutines with no shared state
        - Staggered starts to avoid rate limits
        - Independent error handling per agent

        Args:
            agent_configs: List of dicts, each containing:
                - agent_id: str (e.g., "BANK_A")
                - instruction: str
                - current_policy: dict
                - ... (all other generate_policy args)
            stagger_interval: Delay between starting each agent's call (seconds)

        Returns:
            List of (agent_id, policy, tokens, latency) tuples
        """
        tasks: list[tuple[str, asyncio.Task[tuple[dict[str, Any] | None, int, float]]]] = []

        for i, config in enumerate(agent_configs):
            agent_id = config.pop("agent_id")
            stagger_delay = i * stagger_interval

            # Create task with staggered start
            task = asyncio.create_task(
                self._generate_with_retry(
                    agent_id=agent_id,
                    stagger_delay=stagger_delay,
                    **config,
                )
            )
            tasks.append((agent_id, task))

        # Wait for all tasks to complete
        results: list[tuple[str, dict[str, Any] | None, int, float]] = []
        for agent_id, task in tasks:
            try:
                policy, tokens, latency = await task
                results.append((agent_id, policy, tokens, latency))
            except Exception as e:
                if self.verbose:
                    print(f"  Failed to generate policy for {agent_id}: {e}")
                results.append((agent_id, None, 0, 0.0))

        return results

    async def _generate_with_retry(
        self,
        agent_id: str,
        stagger_delay: float,
        max_retries: int = 3,
        base_backoff: float = 2.0,
        **kwargs: Any,
    ) -> tuple[dict[str, Any] | None, int, float]:
        """Generate policy with exponential backoff retry on rate limits.

        Args:
            agent_id: Agent identifier
            stagger_delay: Initial delay before first attempt
            max_retries: Maximum retry attempts
            base_backoff: Base delay for exponential backoff
            **kwargs: Arguments for generate_policy_async

        Returns:
            tuple of (policy, tokens, latency)
        """
        last_exception: Exception | None = None
        total_latency = 0.0

        for attempt in range(max_retries):
            try:
                # Add exponential backoff delay for retries
                if attempt > 0:
                    backoff_delay = base_backoff * (2 ** (attempt - 1))
                    if self.verbose:
                        print(
                            f"    [{agent_id}] Retry {attempt}/{max_retries}, "
                            f"waiting {backoff_delay:.1f}s..."
                        )
                    await asyncio.sleep(backoff_delay)

                policy, tokens, latency = await self.generate_policy_async(
                    agent_id=agent_id,
                    stagger_delay=stagger_delay if attempt == 0 else 0,
                    **kwargs,
                )
                total_latency += latency

                if policy is not None:
                    return policy, tokens, total_latency

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if "rate" in error_str or "429" in error_str or "limit" in error_str:
                    if self.verbose:
                        print(f"    [{agent_id}] Rate limit hit, will retry...")
                    continue
                else:
                    # Non-rate-limit error, don't retry
                    raise

        # All retries exhausted
        if last_exception and self.verbose:
            print(f"    [{agent_id}] All retries exhausted: {last_exception}")

        return None, 0, total_latency
