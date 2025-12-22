"""Generic experiment LLM client.

Provides a config-driven LLM client for experiment optimization.
The system prompt is read from config, not hardcoded.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.llm import LLMConfig


@dataclass(frozen=True)
class LLMInteraction:
    """Full LLM interaction record for audit purposes.

    Captures all data needed for audit replay:
    - Complete prompts sent to the LLM
    - Raw response received
    - Parsed policy or error

    All fields are immutable (frozen dataclass) for audit integrity.

    Attributes:
        system_prompt: Full system prompt sent to LLM.
        user_prompt: Full user prompt sent to LLM.
        raw_response: Raw LLM response text before parsing.
        parsed_policy: Parsed policy dict if successful.
        parsing_error: Error message if parsing failed.
        prompt_tokens: Number of input tokens (estimated).
        completion_tokens: Number of output tokens (estimated).
        latency_seconds: API call latency in seconds.

    Example:
        >>> interaction = LLMInteraction(
        ...     system_prompt="You are a policy optimizer.",
        ...     user_prompt="Improve this policy...",
        ...     raw_response='{"policy_id": "test"}',
        ...     parsed_policy={"policy_id": "test"},
        ... )
        >>> interaction.system_prompt
        'You are a policy optimizer.'
    """

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None = None
    parsing_error: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_seconds: float = 0.0


class ExperimentLLMClient:
    """Generic LLM client for experiment optimization.

    Reads system_prompt from LLMConfig instead of using hardcoded prompts.
    This enables YAML-only experiments where the prompt is defined in config.

    Features:
    - Config-driven system prompt
    - Interaction capture for audit replay
    - Policy JSON parsing with markdown handling
    - Auto-generation of missing policy fields

    Example:
        >>> from payment_simulator.llm import LLMConfig
        >>> config = LLMConfig(
        ...     model="anthropic:claude-sonnet-4-5",
        ...     system_prompt="You are a payment optimizer.",
        ... )
        >>> client = ExperimentLLMClient(config)
        >>> client.system_prompt
        'You are a payment optimizer.'

        >>> # Without system prompt
        >>> config = LLMConfig(model="openai:gpt-4o")
        >>> client = ExperimentLLMClient(config)
        >>> client.system_prompt is None
        True
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the experiment LLM client.

        Args:
            config: LLMConfig with model and optional system_prompt.
        """
        self._config = config
        self._last_interaction: LLMInteraction | None = None
        self._interactions: list[LLMInteraction] = []
        self._system_prompt_override: str | None = None

    def set_system_prompt(self, prompt: str) -> None:
        """Set a dynamic system prompt, overriding config.

        This allows the optimizer to inject a schema-filtered prompt
        built at runtime rather than using a static YAML config prompt.

        Args:
            prompt: The dynamic system prompt to use.
        """
        self._system_prompt_override = prompt

    @property
    def system_prompt(self) -> str | None:
        """Get system prompt, preferring dynamic override.

        Returns:
            Dynamic system prompt if set, else config system prompt.
        """
        if self._system_prompt_override is not None:
            return self._system_prompt_override
        return self._config.system_prompt

    @property
    def model(self) -> str:
        """Get model string.

        Returns:
            Model specification in provider:model format.
        """
        return self._config.model

    @property
    def max_retries(self) -> int:
        """Get max retries from config.

        Returns:
            Maximum retry attempts on failure.
        """
        return self._config.max_retries

    @property
    def temperature(self) -> float:
        """Get temperature from config.

        Returns:
            Sampling temperature (0.0 for deterministic).
        """
        return self._config.temperature

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate improved policy via LLM.

        This method captures the full interaction for audit replay.

        Args:
            prompt: The optimization prompt.
            current_policy: The current policy being optimized.
            context: Additional context (performance history, etc).

        Returns:
            Generated policy dict.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.
            RuntimeError: If LLM call fails (requires pydantic_ai).
        """
        import time

        try:
            from pydantic_ai import Agent  # type: ignore[import-not-found]
        except ImportError as e:
            msg = "pydantic_ai required for LLM calls: pip install pydantic-ai"
            raise RuntimeError(msg) from e

        # Build user prompt
        user_prompt = self._build_user_prompt(prompt, current_policy, context)

        # Create agent with system prompt if configured
        system_prompt = self.system_prompt or ""
        agent = Agent(
            self._config.full_model_string,
            system_prompt=system_prompt,
        )

        # Track timing
        start_time = time.time()

        # Run the agent
        result = await agent.run(
            user_prompt,
            model_settings=self._config.to_model_settings(),
        )

        latency = time.time() - start_time
        raw_response = str(result.output)

        # Estimate token counts (simple word-based approximation)
        prompt_tokens = len(system_prompt.split()) + len(user_prompt.split())
        completion_tokens = len(raw_response.split())

        # Try to parse the response
        parsed_policy: dict[str, Any] | None = None
        parsing_error: str | None = None

        try:
            parsed_policy = self.parse_policy(raw_response)
        except ValueError as e:
            parsing_error = str(e)

        # Create and store interaction
        interaction = LLMInteraction(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=raw_response,
            parsed_policy=parsed_policy,
            parsing_error=parsing_error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_seconds=latency,
        )
        self._last_interaction = interaction
        self._interactions.append(interaction)

        # Return parsed policy or raise
        if parsed_policy is not None:
            return parsed_policy
        else:
            msg = parsing_error or "Failed to parse policy"
            raise ValueError(msg)

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction result.

        Returns:
            The last LLMInteraction, or None if no calls have been made.
        """
        return self._last_interaction

    def get_all_interactions(self) -> list[LLMInteraction]:
        """Get all recorded interactions.

        Returns:
            List of all LLMInteraction objects in order.
        """
        return self._interactions.copy()

    def clear_interactions(self) -> None:
        """Clear all recorded interactions."""
        self._last_interaction = None
        self._interactions.clear()

    def parse_policy(self, response: str) -> dict[str, Any]:
        """Parse LLM response as JSON policy.

        Handles markdown code blocks if present.
        Adds missing required fields (version, policy_id).
        Ensures all tree nodes have node_ids.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed policy dict.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.

        Example:
            >>> client = ExperimentLLMClient(config)
            >>> policy = client.parse_policy('{"policy_id": "test"}')
            >>> policy["policy_id"]
            'test'
        """
        text = response.strip()

        # Strip markdown code blocks if present (anywhere in text)
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
            elif text.startswith("```"):
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

    def _build_user_prompt(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        _context: dict[str, Any],
    ) -> str:
        """Build the user prompt with policy.

        Note: Iteration history is already included in the rich prompt via
        build_single_agent_context(). This method just appends the current
        policy and final instruction.

        Args:
            prompt: Base optimization prompt (includes iteration history).
            current_policy: Current policy dict.
            _context: Additional context dict (unused, kept for compatibility).

        Returns:
            Complete user prompt string.
        """
        return f"""{prompt}

Current policy:
{json.dumps(current_policy, indent=2)}

Generate an improved policy that reduces total cost.
Output ONLY the JSON policy, no explanation."""

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

        # Process known tree types
        for tree_name in [
            "payment_tree",
            "strategic_collateral_tree",
            "collateral_tree",
            "bank_tree",
        ]:
            if tree_name in policy:
                add_node_id(policy[tree_name], tree_name.replace("_tree", ""))
