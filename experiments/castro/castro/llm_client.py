"""LLM client for policy generation.

Implements LLMClientProtocol for Anthropic and OpenAI providers.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from payment_simulator.ai_cash_mgmt import LLMConfig, LLMProviderType

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI


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


class CastroLLMClient:
    """LLM client implementing ai_cash_mgmt's LLMClientProtocol.

    Supports Anthropic (Claude) and OpenAI (GPT) models.

    Example:
        >>> config = LLMConfig(
        ...     provider=LLMProviderType.ANTHROPIC,
        ...     model="claude-sonnet-4-5-20250929",
        ... )
        >>> client = CastroLLMClient(config)
        >>> policy = await client.generate_policy(prompt, current, context)
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the LLM client.

        Args:
            config: LLM configuration specifying provider and model.
        """
        self._config = config
        self._client: AsyncAnthropic | AsyncOpenAI

        if config.provider == LLMProviderType.ANTHROPIC:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic()
        elif config.provider == LLMProviderType.OPENAI:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI()
        else:
            msg = f"Unsupported provider: {config.provider}"
            raise ValueError(msg)

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

        if self._config.provider == LLMProviderType.ANTHROPIC:
            response = await self._call_anthropic(SYSTEM_PROMPT, user_prompt)
        else:
            response = await self._call_openai(SYSTEM_PROMPT, user_prompt)

        return self._parse_policy(response)

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

    async def _call_anthropic(self, system: str, user: str) -> str:
        """Call Anthropic API."""
        from anthropic import AsyncAnthropic

        # Type narrowing: we know self._client is AsyncAnthropic here
        client = self._client
        assert isinstance(client, AsyncAnthropic)

        response = await client.messages.create(
            model=self._config.model,
            max_tokens=4096,
            temperature=self._config.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        # Extract text from response
        content = response.content[0]
        if hasattr(content, "text"):
            return str(content.text)
        msg = f"Unexpected response type: {type(content)}"
        raise ValueError(msg)

    async def _call_openai(self, system: str, user: str) -> str:
        """Call OpenAI API with high reasoning for GPT-5.1."""
        from openai import AsyncOpenAI

        # Type narrowing: we know self._client is AsyncOpenAI here
        client = self._client
        assert isinstance(client, AsyncOpenAI)

        # Build request parameters
        params: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        # For GPT-5.1, use high reasoning effort
        if "gpt-5" in self._config.model:
            params["reasoning_effort"] = "high"
            params["max_completion_tokens"] = 16384  # More tokens for verbose output
        else:
            params["temperature"] = self._config.temperature
            params["max_tokens"] = 4096

        response = await client.chat.completions.create(**params)

        content = response.choices[0].message.content
        if content is None:
            msg = "Empty response from OpenAI"
            raise ValueError(msg)
        return str(content)

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
