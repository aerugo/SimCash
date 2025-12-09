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
  "parameters": {
    "initial_liquidity_fraction": <float 0.0-1.0>,
    "urgency_threshold": <int 0-20>,
    "liquidity_buffer": <float 0.5-3.0>
  },
  "payment_tree": { decision tree for payment actions },
  "strategic_collateral_tree": { decision tree for collateral at t=0 }
}

Decision tree node types:
1. Action node: {"type": "action", "action": "Release" or "Hold"}
2. Condition node: {
     "type": "condition",
     "condition": {"op": "<operator>", "left": {...}, "right": {...}},
     "on_true": <node>,
     "on_false": <node>
   }

Condition operands:
- {"field": "<field_name>"} - context field
- {"param": "<param_name>"} - policy parameter
- {"value": <literal>} - literal value

Operators: "<", "<=", ">", ">=", "==", "!="

Rules:
- payment_tree actions: "Release" or "Hold" only
- collateral_tree actions: "PostCollateral" at tick 0, "HoldCollateral" otherwise
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

        # Type narrowing for mypy
        client: AsyncAnthropic = self._client  # type: ignore[assignment]

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
            return content.text  # type: ignore[no-any-return]
        msg = f"Unexpected response type: {type(content)}"
        raise ValueError(msg)

    async def _call_openai(self, system: str, user: str) -> str:
        """Call OpenAI API."""
        from openai import AsyncOpenAI

        # Type narrowing for mypy
        client: AsyncOpenAI = self._client  # type: ignore[assignment]

        response = await client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

        content = response.choices[0].message.content
        if content is None:
            msg = "Empty response from OpenAI"
            raise ValueError(msg)
        return content

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
            return policy
        except json.JSONDecodeError as e:
            msg = f"Failed to parse policy JSON: {e}"
            raise ValueError(msg) from e
