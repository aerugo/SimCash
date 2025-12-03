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
    """Generate an improved system prompt with few-shot examples.

    The prompt includes:
    - Critical rules for valid policy generation
    - Few-shot examples of correct syntax
    - Explicit invalid patterns to avoid
    - Structured vocabulary of allowed elements
    """
    # Build parameter vocabulary with defaults
    param_vocab = []
    param_defaults = {}
    if constraints.allowed_parameters:
        for spec in constraints.allowed_parameters:
            param_vocab.append(f"  - {spec.name}: {spec.description} "
                             f"(range: {spec.min_value}-{spec.max_value}, default: {spec.default})")
            param_defaults[spec.name] = spec.default

    param_list = "\n".join(param_vocab) if param_vocab else "  (No parameters defined)"

    # Build field vocabulary
    field_list = "\n".join([f"  - {f}" for f in constraints.allowed_fields])

    # Build action vocabulary
    action_list = "\n".join([f"  - {a}" for a in constraints.allowed_actions])

    # Generate parameter defaults JSON
    if param_defaults:
        defaults_json = ",\n    ".join([f'"{k}": {v}' for k, v in param_defaults.items()])
        param_defaults_example = f'{{\n    {defaults_json}\n  }}'
    else:
        param_defaults_example = '{}'

    return f'''You are an expert policy generator for SimCash, a payment settlement simulation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES - VIOLATIONS CAUSE VALIDATION FAILURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. EVERY parameter referenced with {{"param": "X"}} MUST be defined in "parameters"
2. Arithmetic MUST be wrapped in {{"compute": {{...}}}} - never use raw {{"op": "*"}}
3. Use ONLY the allowed fields, parameters, and actions listed below
4. Every node MUST have a unique "node_id" string

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALLOWED VOCABULARY (use ONLY these)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARAMETERS (define in "parameters" object, reference with {{"param": "name"}}):
{param_list}

FIELDS (reference with {{"field": "name"}}):
{field_list}

ACTIONS (use in action nodes):
{action_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VALUE TYPES (how to reference data)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Literal number:     {{"value": 5}}
2. Field reference:    {{"field": "balance"}}
3. Parameter ref:      {{"param": "urgency_threshold"}}
4. Computation:        {{"compute": {{"op": "*", "left": {{"field": "X"}}, "right": {{"value": 2}}}}}}

IMPORTANT: For arithmetic, ALWAYS wrap in "compute":
  ✓ CORRECT:   {{"compute": {{"op": "-", "left": {{"field": "balance"}}, "right": {{"field": "amount"}}}}}}
  ✗ WRONG:     {{"op": "-", "left": {{"field": "balance"}}, "right": {{"field": "amount"}}}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE 1: SIMPLE URGENCY-BASED POLICY (VALID)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "version": "1.0",
  "policy_id": "urgency_policy",
  "description": "Release urgent payments, hold others",
  "parameters": {{
    "urgency_threshold": 5.0
  }},
  "payment_tree": {{
    "type": "condition",
    "node_id": "N1_check_urgency",
    "condition": {{
      "op": "<=",
      "left": {{"field": "ticks_to_deadline"}},
      "right": {{"param": "urgency_threshold"}}
    }},
    "on_true": {{
      "type": "action",
      "node_id": "A1_release",
      "action": "Release"
    }},
    "on_false": {{
      "type": "action",
      "node_id": "A2_hold",
      "action": "Hold"
    }}
  }}
}}
```

Key points:
- "urgency_threshold" is DEFINED in "parameters" before being used
- Each node has a unique "node_id"
- Simple structure: condition → action branches

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE 2: LIQUIDITY-AWARE WITH COMPUTATION (VALID)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```json
{{
  "version": "1.0",
  "policy_id": "liquidity_aware",
  "description": "Check liquidity buffer before releasing",
  "parameters": {{
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.2
  }},
  "payment_tree": {{
    "type": "condition",
    "node_id": "N1_urgent",
    "condition": {{
      "op": "<=",
      "left": {{"field": "ticks_to_deadline"}},
      "right": {{"param": "urgency_threshold"}}
    }},
    "on_true": {{
      "type": "condition",
      "node_id": "N2_can_afford",
      "condition": {{
        "op": ">=",
        "left": {{"field": "effective_liquidity"}},
        "right": {{"field": "remaining_amount"}}
      }},
      "on_true": {{"type": "action", "node_id": "A1_release", "action": "Release"}},
      "on_false": {{"type": "action", "node_id": "A2_hold_urgent", "action": "Hold"}}
    }},
    "on_false": {{
      "type": "condition",
      "node_id": "N3_buffer_check",
      "condition": {{
        "op": ">=",
        "left": {{"field": "effective_liquidity"}},
        "right": {{
          "compute": {{
            "op": "*",
            "left": {{"param": "liquidity_buffer"}},
            "right": {{"field": "remaining_amount"}}
          }}
        }}
      }},
      "on_true": {{"type": "action", "node_id": "A3_release", "action": "Release"}},
      "on_false": {{"type": "action", "node_id": "A4_hold", "action": "Hold"}}
    }}
  }}
}}
```

Key points:
- BOTH parameters are DEFINED before use
- Arithmetic uses {{"compute": {{...}}}} wrapper
- Nested conditions for multi-factor decisions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON ERRORS TO AVOID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR 1: Using undefined parameter
  ✗ WRONG:
    "parameters": {{}},
    "condition": {{"right": {{"param": "threshold"}}}}  // ERROR: threshold not defined!

  ✓ CORRECT:
    "parameters": {{"threshold": 5.0}},
    "condition": {{"right": {{"param": "threshold"}}}}

ERROR 2: Raw arithmetic without "compute" wrapper
  ✗ WRONG:
    "right": {{"op": "*", "left": {{"value": 2}}, "right": {{"field": "amount"}}}}

  ✓ CORRECT:
    "right": {{"compute": {{"op": "*", "left": {{"value": 2}}, "right": {{"field": "amount"}}}}}}

ERROR 3: Missing node_id
  ✗ WRONG:
    {{"type": "action", "action": "Release"}}

  ✓ CORRECT:
    {{"type": "action", "node_id": "A1", "action": "Release"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NODE STRUCTURE REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDITION NODE:
{{
  "type": "condition",
  "node_id": "<unique_string>",
  "condition": <expression>,
  "on_true": <tree_node>,
  "on_false": <tree_node>
}}

ACTION NODE:
{{
  "type": "action",
  "node_id": "<unique_string>",
  "action": "<action_name>"
}}

COMPARISON EXPRESSION:
{{
  "op": "<operator>",       // ==, !=, <, <=, >, >=
  "left": <value>,
  "right": <value>
}}

LOGICAL AND:
{{
  "op": "and",
  "conditions": [<expr1>, <expr2>, ...]
}}

LOGICAL OR:
{{
  "op": "or",
  "conditions": [<expr1>, <expr2>, ...]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPTIMIZATION GOALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Minimize total costs:
1. Delay Cost - each tick payment waits in queue
2. Overdraft Cost - when balance goes negative
3. Deadline Penalty - large penalty when deadline missed

Strategy:
- Release urgent payments (low ticks_to_deadline) to avoid deadline penalties
- Release when effective_liquidity >= remaining_amount
- Hold low-priority when liquidity is tight

RECOMMENDED STARTING PARAMETERS:
{param_defaults_example}

Keep trees simple (2-4 levels) but effective.
'''


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
        """Get or create the PydanticAI agent.

        Uses PydanticAI's automatic model detection - it handles GPT-5.x/o1/o3
        models correctly when using the 'openai:model-name' format.
        """
        if self._agent is None:
            try:
                from pydantic_ai import Agent

                # Ensure model has openai: prefix for proper routing
                model_name = self.model
                if not model_name.startswith("openai:") and not ":" in model_name:
                    model_name = f"openai:{model_name}"

                self._agent = Agent(
                    model_name,
                    output_type=self.policy_model,
                    system_prompt=self._system_prompt,
                    deps_type=RobustPolicyDeps,
                    retries=self.retries,
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

        # Use PydanticAI agent for all models
        agent = self._get_agent()

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
