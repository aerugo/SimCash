"""PydanticAI-based LLM client for policy generation.

Implements LLMClientProtocol using PydanticAI for unified multi-provider support.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic_ai import Agent

from castro.model_config import ModelConfig

# System prompt for policy generation
SYSTEM_PROMPT = """You are an expert in payment system optimization.
Generate valid JSON policies for the SimCash payment simulator.

Policy structure:
{
  "version": "2.0",
  "policy_id": "<unique_policy_name>",
  "parameters": {
    "initial_liquidity_fraction": <float 0.0-1.0>,
    "urgency_threshold": <float 0-20>,
    "liquidity_buffer_factor": <float 0.5-3.0>
  },
  "payment_tree": { decision tree for payment actions },
  "strategic_collateral_tree": { decision tree for collateral at t=0 }
}

CRITICAL: Every node MUST have a unique "node_id" string field!

Decision tree node types:
1. Action node: {"type": "action", "node_id": "<unique_id>", "action": "Release" or "Hold"}
2. Condition node: {
     "type": "condition",
     "node_id": "<unique_id>",
     "condition": {"op": "<operator>", "left": {...}, "right": {...}},
     "on_true": <node>,
     "on_false": <node>
   }
3. Collateral action node: {
     "type": "action",
     "node_id": "<unique_id>",
     "action": "PostCollateral" or "HoldCollateral",
     "parameters": {
       "amount": {"compute": {...} or "value": <number>},
       "reason": {"value": "InitialAllocation" or "LiquidityTopup"}
     }
   }

Condition operands:
- {"field": "<field_name>"} - context fields: ticks_to_deadline, system_tick_in_day,
  remaining_collateral_capacity
- {"param": "<param_name>"} - policy parameter reference
- {"value": <literal>} - literal number value

Operators: "<", "<=", ">", ">=", "==", "!="

Compute expressions: {"compute": {"op": "*", "left": {...}, "right": {...}}}

Rules:
- EVERY node must have a unique node_id field (REQUIRED by parser)
- payment_tree actions: "Release" or "Hold" only
- strategic_collateral_tree: Post collateral at tick 0, hold otherwise
- Use remaining_collateral_capacity field for collateral amount calculations
- All numeric values must respect parameter bounds
- Output ONLY valid JSON, no markdown or explanation"""


class PydanticAILLMClient:
    """LLM client using PydanticAI.

    Implements LLMClientProtocol for compatibility with ai_cash_mgmt's
    PolicyOptimizer. Uses PydanticAI Agent for unified multi-provider support.

    Supported Providers:
        - anthropic: Claude models with optional extended thinking
        - openai: GPT models with optional reasoning effort
        - google: Gemini models with optional thinking config

    Example:
        >>> config = ModelConfig("anthropic:claude-sonnet-4-5")
        >>> client = PydanticAILLMClient(config)
        >>> policy = await client.generate_policy(prompt, current, context)

        >>> # With extended thinking
        >>> config = ModelConfig("anthropic:claude-sonnet-4-5", thinking_budget=8000)
        >>> client = PydanticAILLMClient(config)

        >>> # With high reasoning
        >>> config = ModelConfig("openai:gpt-5.1", reasoning_effort="high")
        >>> client = PydanticAILLMClient(config)
    """

    def __init__(self, config: ModelConfig) -> None:
        """Initialize the PydanticAI LLM client.

        Args:
            config: Model configuration with provider:model string.
        """
        self._config = config
        self._agent = Agent(
            config.full_model_string,
            system_prompt=SYSTEM_PROMPT,
        )

    @property
    def model(self) -> str:
        """Get the model string for tracking."""
        return self._config.model

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate improved policy via LLM.

        Args:
            prompt: The optimization prompt.
            current_policy: The current policy being optimized.
            context: Additional context (performance history, etc).

        Returns:
            Generated policy dict.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.
        """
        user_prompt = self._build_user_prompt(prompt, current_policy, context)

        # Run the agent with provider-specific settings
        result = await self._agent.run(
            user_prompt,
            model_settings=self._config.to_model_settings(),  # type: ignore[call-overload]
        )

        # Parse the response
        response_text = str(result.output)
        return self._parse_policy(response_text)

    def _build_user_prompt(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """Build the user prompt with policy and history."""
        history = context.get("history", [])
        history_str = ""
        if history:
            for entry in history[-5:]:
                iteration = entry.get("iteration", "?")
                cost = entry.get("cost", "?")
                history_str += f"  Iteration {iteration}: cost=${cost / 100:.2f}\n"

        return f"""{prompt}

Current policy:
{json.dumps(current_policy, indent=2)}

Performance history:
{history_str or '  (none)'}

Generate an improved policy that reduces total cost.
Output ONLY the JSON policy, no explanation."""

    def _parse_policy(self, response: str) -> dict[str, Any]:
        """Parse LLM response as JSON policy.

        Handles markdown code blocks if present.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed policy dict.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.
        """
        text = response.strip()

        # Strip markdown code blocks if present
        if text.startswith("```"):
            # Find the end of the code block
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
            else:
                # Fallback: strip first and last lines
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)

        try:
            policy: dict[str, Any] = json.loads(text)
            # Ensure required fields
            self._ensure_required_fields(policy)
            # Ensure all nodes have node_ids
            self._ensure_node_ids(policy)
            return policy
        except json.JSONDecodeError as e:
            msg = f"Failed to parse policy JSON: {e}"
            raise ValueError(msg) from e

    def _ensure_required_fields(self, policy: dict[str, Any]) -> None:
        """Ensure policy has required top-level fields.

        Args:
            policy: Policy dict to modify in place.
        """
        if "version" not in policy:
            policy["version"] = "2.0"
        if "policy_id" not in policy:
            import uuid

            policy["policy_id"] = f"llm_policy_{uuid.uuid4().hex[:8]}"

    def _ensure_node_ids(self, policy: dict[str, Any]) -> None:
        """Ensure all tree nodes have node_id fields.

        Adds missing node_ids with auto-generated unique names.

        Args:
            policy: Policy dict to modify in place.
        """
        counter = [0]  # Use list to allow mutation in nested function

        def add_node_id(node: dict[str, Any], prefix: str) -> None:
            """Recursively add node_ids to a tree."""
            if not isinstance(node, dict):
                return

            # Add node_id if missing
            if "type" in node and "node_id" not in node:
                counter[0] += 1
                node["node_id"] = f"{prefix}_node_{counter[0]}"

            # Recurse into child nodes
            if "on_true" in node:
                add_node_id(node["on_true"], prefix)
            if "on_false" in node:
                add_node_id(node["on_false"], prefix)

        # Process both trees
        if "payment_tree" in policy:
            add_node_id(policy["payment_tree"], "payment")
        if "strategic_collateral_tree" in policy:
            add_node_id(policy["strategic_collateral_tree"], "collateral")


# Convenience function for creating a client
def create_llm_client(
    model: str,
    *,
    temperature: float = 0.0,
    thinking_budget: int | None = None,
    reasoning_effort: str | None = None,
) -> PydanticAILLMClient:
    """Create a PydanticAI LLM client.

    Convenience function for creating an LLM client with common options.

    Args:
        model: Model string in provider:model format.
        temperature: Sampling temperature.
        thinking_budget: Anthropic thinking token budget.
        reasoning_effort: OpenAI reasoning effort level.

    Returns:
        Configured PydanticAILLMClient instance.

    Examples:
        >>> client = create_llm_client("anthropic:claude-sonnet-4-5")
        >>> client = create_llm_client("openai:gpt-5.1", reasoning_effort="high")
    """
    config = ModelConfig(
        model=model,
        temperature=temperature,
        thinking_budget=thinking_budget,
        reasoning_effort=reasoning_effort,
    )
    return PydanticAILLMClient(config)
