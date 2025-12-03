"""Robust Policy Agent using dynamic constrained schemas.

This module provides a RobustPolicyAgent that uses PydanticAI structured output
with dynamically generated Pydantic models based on ScenarioConstraints.

The agent supports ANY parameters, fields, and actions that SimCash allows,
configured per-scenario via ScenarioConstraints.

Usage:
    from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
    from experiments.castro.schemas.parameter_config import (
        ParameterSpec,
        ScenarioConstraints,
    )

    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency threshold"),
            ParameterSpec("buffer", 0.5, 3.0, 1.0, "Liquidity buffer"),
        ],
        allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity"],
        allowed_actions=["Release", "Hold", "Split"],
    )

    agent = RobustPolicyAgent(constraints=constraints)
    policy = agent.generate_policy(
        instruction="Optimize for low delay costs",
        current_cost=50000,
        settlement_rate=0.85,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from experiments.castro.schemas.parameter_config import ScenarioConstraints
from experiments.castro.schemas.dynamic import create_constrained_policy_model


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "gpt-4o"
DEFAULT_REASONING_EFFORT: Literal["low", "medium", "high"] = "high"
DEFAULT_REASONING_SUMMARY: Literal["concise", "detailed"] = "detailed"


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
# System Prompt Generation
# ============================================================================


def generate_system_prompt(constraints: ScenarioConstraints) -> str:
    """Generate a system prompt from scenario constraints.

    The prompt includes:
    - Allowed parameters with bounds and descriptions
    - Allowed context fields
    - Allowed actions
    - Policy structure documentation
    """
    # Parameter section
    if constraints.allowed_parameters:
        param_lines = ["## Allowed Parameters\n"]
        param_lines.append("You can ONLY use these parameters:\n")
        for spec in constraints.allowed_parameters:
            param_lines.append(
                f"- **{spec.name}** (range: {spec.min_value} to {spec.max_value}, "
                f"default: {spec.default}): {spec.description}"
            )
        param_section = "\n".join(param_lines)
    else:
        param_section = "## Parameters\n\nNo parameters are defined for this scenario."

    # Fields section
    field_lines = ["## Available Context Fields\n"]
    field_lines.append("You can reference these fields in conditions:\n")
    for field in constraints.allowed_fields[:20]:  # Show first 20
        field_lines.append(f"- {field}")
    if len(constraints.allowed_fields) > 20:
        field_lines.append(f"- ... and {len(constraints.allowed_fields) - 20} more")
    fields_section = "\n".join(field_lines)

    # Actions section
    action_lines = ["## Allowed Actions\n"]
    action_lines.append("You can use these actions in tree nodes:\n")
    for action in constraints.allowed_actions:
        action_lines.append(f"- {action}")
    actions_section = "\n".join(action_lines)

    return f"""You are an expert policy optimizer for a payment settlement simulation.

Your task is to generate or improve policy decision trees that minimize total costs
while maintaining high settlement rates.

## Policy Structure

A policy consists of:
1. **parameters**: Numeric thresholds that control decision logic
2. **payment_tree**: Decision tree for each pending payment (Release/Hold)

## Tree Node Types

CONDITION node: Tests a boolean expression and branches
```json
{{
    "type": "condition",
    "condition": {{"op": "<=", "left": {{"field": "ticks_to_deadline"}}, "right": {{"param": "threshold"}}}},
    "on_true": <tree_node>,
    "on_false": <tree_node>
}}
```

ACTION node: Terminal decision
```json
{{"type": "action", "action": "Release"}}
{{"type": "action", "action": "Hold"}}
```

## Expression Operators

Comparison: ==, !=, <, <=, >, >=
Logical: and, or, not (use "conditions" array for and/or)

{param_section}

{fields_section}

{actions_section}

## Cost Components (minimize these)

1. **Delay Cost**: Incurred each tick a payment waits in queue
2. **Overdraft Cost**: Incurred when balance goes negative
3. **Collateral Cost**: Opportunity cost of posted collateral
4. **Deadline Penalty**: Large penalty when payment misses deadline

## Optimization Strategy

- Release urgent payments (low ticks_to_deadline) to avoid deadline penalties
- Release payments when effective_liquidity > required amount
- Hold low-priority payments when liquidity is tight

Keep decision trees simple (2-3 levels deep) but effective.
"""


# ============================================================================
# Robust Policy Agent
# ============================================================================


class RobustPolicyAgent:
    """Policy generator using dynamic constrained schemas.

    This agent uses PydanticAI structured output with dynamically generated
    Pydantic models based on ScenarioConstraints. This ensures:

    - Only allowed parameters can be used (with enforced bounds)
    - Only allowed context fields can be referenced
    - Only allowed actions can be used
    - Correct policy structure is enforced

    Example:
        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec("urgency", 0, 20, 3, "Urgency"),
            ],
            allowed_fields=["balance", "ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        policy = agent.generate_policy("Minimize delay costs")
    """

    def __init__(
        self,
        constraints: ScenarioConstraints,
        model: str | None = None,
        retries: int = 3,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
        reasoning_summary: Literal["concise", "detailed"] = DEFAULT_REASONING_SUMMARY,
    ) -> None:
        """Initialize robust policy agent.

        Args:
            constraints: Scenario constraints defining allowed elements
            model: PydanticAI model string. Defaults to GPT-4o.
            retries: Number of retries on validation failure
            reasoning_effort: Reasoning effort for GPT models
            reasoning_summary: Reasoning summary verbosity
        """
        self.constraints = constraints
        self.model = model or DEFAULT_MODEL
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary

        # Generate dynamic policy model from constraints
        self.policy_model = create_constrained_policy_model(constraints)

        # Generate system prompt from constraints
        self._system_prompt = generate_system_prompt(constraints)

        # Lazy-initialized PydanticAI agent
        self._agent: Any | None = None

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return self._system_prompt

    def _get_agent(self) -> Any:
        """Get or create the PydanticAI agent."""
        if self._agent is None:
            try:
                from pydantic_ai import Agent
                from pydantic_ai.models.openai import (
                    OpenAIResponsesModel,
                    OpenAIResponsesModelSettings,
                )

                # Configure model
                model_instance: Any
                model_settings: Any = None

                if self.model.startswith("gpt-5") or self.model.startswith("openai:gpt-5"):
                    model_instance = OpenAIResponsesModel(self.model)
                    model_settings = OpenAIResponsesModelSettings(
                        openai_reasoning_effort=self.reasoning_effort,
                        openai_reasoning_summary=self.reasoning_summary,
                    )
                else:
                    model_instance = self.model

                self._agent = Agent(
                    model_instance,
                    output_type=self.policy_model,
                    system_prompt=self._system_prompt,
                    deps_type=RobustPolicyDeps,
                    retries=self.retries,
                    model_settings=model_settings,
                )
            except ImportError as e:
                raise ImportError(
                    "PydanticAI is required for RobustPolicyAgent. "
                    "Install with: pip install pydantic-ai"
                ) from e

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
            params = current_policy.get("parameters", {})
            prompt_parts.append("\n## Current Policy Parameters")
            for name, value in params.items():
                prompt_parts.append(f"- {name}: {value}")

        if current_cost is not None:
            prompt_parts.append(f"\n## Current Performance")
            prompt_parts.append(f"Total cost: ${current_cost:,.0f}")

        if settlement_rate is not None:
            prompt_parts.append(f"Settlement rate: {settlement_rate * 100:.1f}%")

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
        if hasattr(result.output, "model_dump"):
            return result.output.model_dump(exclude_none=True)
        return dict(result.output)

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

        if hasattr(result.output, "model_dump"):
            return result.output.model_dump(exclude_none=True)
        return dict(result.output)


# ============================================================================
# Convenience Functions
# ============================================================================


def generate_robust_policy(
    constraints: ScenarioConstraints,
    instruction: str = "Generate an optimal policy",
    model: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate a policy with a single function call.

    Args:
        constraints: Scenario constraints defining allowed elements
        instruction: Natural language instruction
        model: PydanticAI model string (defaults to GPT-4o)
        reasoning_effort: Reasoning effort for GPT models
        **kwargs: Additional context (current_policy, current_cost, etc.)

    Returns:
        Generated policy as dict (fully validated)

    Example:
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec, ScenarioConstraints
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec("urgency", 0, 20, 3, "Urgency"),
            ],
            allowed_fields=["balance", "ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        policy = generate_robust_policy(
            constraints,
            "Minimize delay costs while maintaining 95% settlement",
            current_cost=50000,
            settlement_rate=0.85,
        )
    """
    agent = RobustPolicyAgent(
        constraints=constraints,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    return agent.generate_policy(instruction, **kwargs)
