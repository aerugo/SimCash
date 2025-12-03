"""Robust Policy Agent using constrained schemas.

This module provides a RobustPolicyAgent that uses PydanticAI structured output
with constrained Pydantic models to PREVENT the LLM from generating invalid
policies. This eliminates ~94% of validation errors by enforcing constraints
at generation time rather than post-validation.

Key improvements over the original PolicyAgent:
1. Uses ConstrainedPolicy model that only allows 3 parameters
2. Enforces valid context field names via Literal types
3. Enforces correct operator structure (and/or use conditions array)
4. Includes comprehensive schema documentation in the system prompt

Usage:
    from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

    agent = RobustPolicyAgent()
    policy = agent.generate_policy(
        instruction="Optimize for low delay costs",
        current_cost=50000,
        settlement_rate=0.85,
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from experiments.castro.schemas.constrained import (
    ConstrainedPolicy,
    ConstrainedPolicyParameters,
    ConstrainedPaymentTreeL3,
    ConstrainedCollateralTreeL3,
    get_schema_aware_prompt_additions,
    ALLOWED_PARAMETERS,
)


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "gpt-5.1"
DEFAULT_REASONING_EFFORT: Literal["low", "medium", "high"] = "high"
DEFAULT_REASONING_SUMMARY: Literal["concise", "detailed"] = "detailed"


# ============================================================================
# System Prompt
# ============================================================================

ROBUST_SYSTEM_PROMPT = """You are an expert policy optimizer for a payment settlement simulation.

Your task is to generate or improve policy decision trees that minimize total costs
while maintaining high settlement rates. You are optimizing bank payment policies.

## Policy Structure

A policy consists of:
1. parameters: Numeric thresholds that control decision logic
2. strategic_collateral_tree: Decides collateral allocation at start of each tick
3. payment_tree: Decides whether to Release or Hold each pending payment

## Tree Node Types

CONDITION node: Tests a boolean expression and branches
    {
        "type": "condition",
        "condition": <expression>,
        "on_true": <tree_node>,
        "on_false": <tree_node>
    }

ACTION node: Terminal decision
    {"type": "action", "action": "Release"}
    {"type": "action", "action": "Hold"}
    {"type": "action", "action": "PostCollateral", "parameters": {"amount": <value>}}

""" + get_schema_aware_prompt_additions() + """

## Cost Components (minimize these)

1. Delay Cost: Incurred each tick a payment waits in queue
2. Overdraft Cost: Incurred when balance goes negative
3. Collateral Cost: Opportunity cost of posted collateral
4. Deadline Penalty: Large penalty when payment misses deadline

## Optimization Strategy

To reduce costs:
1. Release urgent payments (low ticks_to_deadline) to avoid deadline penalties
2. Post sufficient collateral for liquidity but not excessive (collateral cost)
3. Release payments when effective_liquidity > required amount
4. Hold low-priority payments when liquidity is tight

## Output Requirements

Generate a valid ConstrainedPolicy JSON object with:
- parameters: Only urgency_threshold, initial_liquidity_fraction, liquidity_buffer_factor
- strategic_collateral_tree: Decision tree for collateral management
- payment_tree: Decision tree for payment release

Keep trees simple (2-3 levels deep) but effective.
"""


# ============================================================================
# Dependencies
# ============================================================================

@dataclass
class RobustPolicyDeps:
    """Dependencies for robust policy generation."""

    current_policy: dict[str, Any] | None = None
    current_cost: float | None = None
    settlement_rate: float | None = None
    per_bank_costs: dict[str, float] | None = None
    iteration: int = 0


# ============================================================================
# Robust Policy Agent
# ============================================================================

class RobustPolicyAgent:
    """Policy generator using constrained Pydantic models.

    This agent uses PydanticAI structured output with ConstrainedPolicy,
    which enforces all schema constraints at generation time. This eliminates
    the vast majority of validation errors seen with free-form generation.

    Key features:
    - Only 3 parameters allowed (urgency_threshold, initial_liquidity_fraction,
      liquidity_buffer_factor)
    - Only valid context fields allowed (no invented fields)
    - Correct operator structure enforced (and/or use conditions array)
    - Comprehensive schema documentation in system prompt

    Example:
        agent = RobustPolicyAgent()

        # Generate initial policy
        policy = agent.generate_policy(
            instruction="Optimize for minimal delay costs"
        )

        # Improve existing policy
        improved = agent.generate_policy(
            instruction="Reduce delay costs while maintaining settlement rate",
            current_policy=policy,
            current_cost=50000,
            settlement_rate=0.95,
        )
    """

    def __init__(
        self,
        model: str | None = None,
        retries: int = 3,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
        reasoning_summary: Literal["concise", "detailed"] = DEFAULT_REASONING_SUMMARY,
    ) -> None:
        """Initialize robust policy agent.

        Args:
            model: PydanticAI model string. Defaults to GPT-5.1.
            retries: Number of retries on validation failure
            reasoning_effort: Reasoning effort for GPT-5.1
            reasoning_summary: Reasoning summary verbosity
        """
        self.model = model or DEFAULT_MODEL
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self._agent: Agent[RobustPolicyDeps, ConstrainedPolicy] | None = None
        self._model_settings: OpenAIResponsesModelSettings | None = None

        # Configure model settings for GPT-5.1
        if self._is_gpt5_model():
            self._model_settings = OpenAIResponsesModelSettings(
                openai_reasoning_effort=reasoning_effort,
                openai_reasoning_summary=reasoning_summary,
            )

    def _is_gpt5_model(self) -> bool:
        """Check if using a GPT-5 series model."""
        return self.model.startswith("gpt-5") or self.model.startswith("openai:gpt-5")

    def _get_model(self) -> OpenAIResponsesModel | str:
        """Get the appropriate model instance."""
        if self._is_gpt5_model():
            return OpenAIResponsesModel(self.model)
        return self.model

    def _get_agent(self) -> Agent[RobustPolicyDeps, ConstrainedPolicy]:
        """Get or create the agent."""
        if self._agent is None:
            model = self._get_model()
            self._agent = Agent(
                model,
                output_type=ConstrainedPolicy,
                system_prompt=ROBUST_SYSTEM_PROMPT,
                deps_type=RobustPolicyDeps,
                retries=self.retries,
                model_settings=self._model_settings,
            )
        return self._agent

    def generate_policy(
        self,
        instruction: str = "Generate an optimal policy",
        current_policy: dict[str, Any] | None = None,
        current_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
        iteration: int = 0,
    ) -> dict[str, Any]:
        """Generate a constrained policy.

        Args:
            instruction: Natural language instruction for policy
            current_policy: Current policy to improve (optional)
            current_cost: Current total cost for context (optional)
            settlement_rate: Current settlement rate for context (optional)
            per_bank_costs: Per-bank costs for context (optional)
            iteration: Current optimization iteration (optional)

        Returns:
            Generated policy as dict (fully validated)
        """
        agent = self._get_agent()

        # Build context-aware prompt
        prompt_parts = [instruction]

        if current_policy:
            # Show current parameters
            params = current_policy.get("parameters", {})
            prompt_parts.append(f"\n## Current Policy Parameters")
            prompt_parts.append(f"- urgency_threshold: {params.get('urgency_threshold', 3.0)}")
            prompt_parts.append(f"- initial_liquidity_fraction: {params.get('initial_liquidity_fraction', 0.25)}")
            prompt_parts.append(f"- liquidity_buffer_factor: {params.get('liquidity_buffer_factor', 1.0)}")

        if current_cost is not None:
            prompt_parts.append(f"\n## Current Performance")
            prompt_parts.append(f"Total cost: ${current_cost:,.0f}")

        if settlement_rate is not None:
            prompt_parts.append(f"Settlement rate: {settlement_rate*100:.1f}%")

        if per_bank_costs:
            prompt_parts.append("\nPer-bank costs:")
            for bank, cost in per_bank_costs.items():
                prompt_parts.append(f"  - {bank}: ${cost:,.0f}")

        if iteration > 0:
            prompt_parts.append(f"\n## Iteration: {iteration}")
            prompt_parts.append("Based on the current performance, suggest improvements.")

        prompt = "\n".join(prompt_parts)

        # Run agent with structured output
        deps = RobustPolicyDeps(
            current_policy=current_policy,
            current_cost=current_cost,
            settlement_rate=settlement_rate,
            per_bank_costs=per_bank_costs,
            iteration=iteration,
        )

        result = agent.run_sync(prompt, deps=deps)

        # Convert Pydantic model to dict
        return result.output.model_dump(exclude_none=True)

    async def generate_policy_async(
        self,
        instruction: str = "Generate an optimal policy",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of generate_policy."""
        agent = self._get_agent()

        deps = RobustPolicyDeps(
            current_policy=kwargs.get("current_policy"),
            current_cost=kwargs.get("current_cost"),
            settlement_rate=kwargs.get("settlement_rate"),
            per_bank_costs=kwargs.get("per_bank_costs"),
            iteration=kwargs.get("iteration", 0),
        )

        result = await agent.run(instruction, deps=deps)
        return result.output.model_dump(exclude_none=True)


# ============================================================================
# Individual Tree Generators
# ============================================================================

class RobustPaymentTreeAgent:
    """Generate only the payment_tree with constraints."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.reasoning_effort = reasoning_effort
        self._agent: Agent[RobustPolicyDeps, ConstrainedPaymentTreeL3] | None = None

    def _get_agent(self) -> Agent[RobustPolicyDeps, ConstrainedPaymentTreeL3]:
        if self._agent is None:
            model_instance: OpenAIResponsesModel | str
            model_settings: OpenAIResponsesModelSettings | None = None

            if self.model.startswith("gpt-5"):
                model_instance = OpenAIResponsesModel(self.model)
                model_settings = OpenAIResponsesModelSettings(
                    openai_reasoning_effort=self.reasoning_effort,
                )
            else:
                model_instance = self.model

            prompt = """You are generating a payment_tree for a payment settlement simulation.

The payment_tree evaluates each pending payment and decides: Release or Hold.

""" + get_schema_aware_prompt_additions() + """

## Key Decision Factors
1. ticks_to_deadline: Release urgent payments (low ticks)
2. effective_liquidity vs remaining_amount: Release if enough liquidity
3. is_eod_rush: Release more aggressively at end of day

Generate a concise but effective decision tree (2-3 levels).
"""
            self._agent = Agent(
                model_instance,
                output_type=ConstrainedPaymentTreeL3,  # type: ignore[arg-type]
                system_prompt=prompt,
                deps_type=RobustPolicyDeps,
                retries=3,
                model_settings=model_settings,
            )
        return self._agent

    def generate(
        self,
        instruction: str = "Generate an optimal payment tree",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a payment tree."""
        agent = self._get_agent()
        deps = RobustPolicyDeps(**{k: v for k, v in kwargs.items() if k in RobustPolicyDeps.__dataclass_fields__})
        result = agent.run_sync(instruction, deps=deps)
        return result.output.model_dump(exclude_none=True) if hasattr(result.output, "model_dump") else result.output


class RobustCollateralTreeAgent:
    """Generate only the strategic_collateral_tree with constraints."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.reasoning_effort = reasoning_effort
        self._agent: Agent[RobustPolicyDeps, ConstrainedCollateralTreeL3] | None = None

    def _get_agent(self) -> Agent[RobustPolicyDeps, ConstrainedCollateralTreeL3]:
        if self._agent is None:
            model_instance: OpenAIResponsesModel | str
            model_settings: OpenAIResponsesModelSettings | None = None

            if self.model.startswith("gpt-5"):
                model_instance = OpenAIResponsesModel(self.model)
                model_settings = OpenAIResponsesModelSettings(
                    openai_reasoning_effort=self.reasoning_effort,
                )
            else:
                model_instance = self.model

            prompt = """You are generating a strategic_collateral_tree for a payment settlement simulation.

The collateral tree runs at start of each tick to manage collateral/liquidity.

Actions:
- PostCollateral: Increase credit limit by posting collateral
- WithdrawCollateral: Reduce collateral (save opportunity cost)
- HoldCollateral: No change

""" + get_schema_aware_prompt_additions() + """

## Key Decision Factors
1. system_tick_in_day == 0: Post initial collateral at start of day
2. queue1_liquidity_gap: Post more if queue exceeds liquidity
3. remaining_collateral_capacity: Don't exceed capacity

The amount for PostCollateral should use:
{"compute": {"op": "*", "left": {"field": "max_collateral_capacity"}, "right": {"param": "initial_liquidity_fraction"}}}

Generate a concise but effective decision tree (2-3 levels).
"""
            self._agent = Agent(
                model_instance,
                output_type=ConstrainedCollateralTreeL3,  # type: ignore[arg-type]
                system_prompt=prompt,
                deps_type=RobustPolicyDeps,
                retries=3,
                model_settings=model_settings,
            )
        return self._agent

    def generate(
        self,
        instruction: str = "Generate an optimal collateral tree",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a collateral tree."""
        agent = self._get_agent()
        deps = RobustPolicyDeps(**{k: v for k, v in kwargs.items() if k in RobustPolicyDeps.__dataclass_fields__})
        result = agent.run_sync(instruction, deps=deps)
        return result.output.model_dump(exclude_none=True) if hasattr(result.output, "model_dump") else result.output


class RobustParameterAgent:
    """Generate only the policy parameters with constraints."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.reasoning_effort = reasoning_effort
        self._agent: Agent[RobustPolicyDeps, ConstrainedPolicyParameters] | None = None

    def _get_agent(self) -> Agent[RobustPolicyDeps, ConstrainedPolicyParameters]:
        if self._agent is None:
            model_instance: OpenAIResponsesModel | str
            model_settings: OpenAIResponsesModelSettings | None = None

            if self.model.startswith("gpt-5"):
                model_instance = OpenAIResponsesModel(self.model)
                model_settings = OpenAIResponsesModelSettings(
                    openai_reasoning_effort=self.reasoning_effort,
                )
            else:
                model_instance = self.model

            prompt = """You are optimizing policy parameters for a payment settlement simulation.

## The ONLY Three Parameters

1. urgency_threshold (float, 0-20)
   - Ticks before deadline when a payment is considered urgent
   - Higher = release payments earlier (reduces deadline penalties)
   - Lower = wait longer (saves collateral costs but risks deadlines)

2. initial_liquidity_fraction (float, 0-1)
   - Fraction of max_collateral_capacity to post at day start
   - Higher = more initial liquidity (good for high volume)
   - Lower = less collateral cost (good for low volume)

3. liquidity_buffer_factor (float, 0.5-3.0)
   - Multiplier for required liquidity before releasing
   - Higher = more conservative (hold more payments)
   - Lower = more aggressive (release more payments)

DO NOT invent new parameters! Only return these three.

## Optimization Strategy

Based on current costs and settlement rate:
- High delay costs → Increase urgency_threshold
- High collateral costs → Decrease initial_liquidity_fraction
- Low settlement rate → Decrease liquidity_buffer_factor
- High overdraft costs → Increase initial_liquidity_fraction
"""
            self._agent = Agent(
                model_instance,
                output_type=ConstrainedPolicyParameters,
                system_prompt=prompt,
                deps_type=RobustPolicyDeps,
                retries=3,
                model_settings=model_settings,
            )
        return self._agent

    def generate(
        self,
        instruction: str = "Optimize the policy parameters",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate optimized parameters."""
        agent = self._get_agent()

        prompt_parts = [instruction]
        if kwargs.get("current_cost"):
            prompt_parts.append(f"\nCurrent total cost: ${kwargs['current_cost']:,.0f}")
        if kwargs.get("settlement_rate"):
            prompt_parts.append(f"Settlement rate: {kwargs['settlement_rate']*100:.1f}%")

        deps = RobustPolicyDeps(**{k: v for k, v in kwargs.items() if k in RobustPolicyDeps.__dataclass_fields__})
        result = agent.run_sync("\n".join(prompt_parts), deps=deps)
        return result.output.model_dump(exclude_none=True)


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_robust_policy(
    instruction: str = "Generate an optimal policy",
    model: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate a policy with a single function call.

    This is the recommended way to generate policies. It uses constrained
    schemas to prevent validation errors.

    Args:
        instruction: Natural language instruction
        model: PydanticAI model string (defaults to GPT-5.1)
        reasoning_effort: Reasoning effort for GPT-5.1
        **kwargs: Additional context (current_policy, current_cost, etc.)

    Returns:
        Generated policy as dict (fully validated)

    Example:
        policy = generate_robust_policy(
            "Minimize delay costs while maintaining 95% settlement",
            current_cost=50000,
            settlement_rate=0.85,
        )
    """
    agent = RobustPolicyAgent(model=model, reasoning_effort=reasoning_effort)
    return agent.generate_policy(instruction, **kwargs)
