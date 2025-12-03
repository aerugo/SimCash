"""Policy generation using PydanticAI.

This module provides a simple, direct integration with PydanticAI for
generating valid policy trees. PydanticAI handles all LLM provider
abstraction internally.

Usage:
    from experiments.castro.generator.policy_agent import PolicyAgent

    # Generate a payment policy with OpenAI GPT-5.1 (default, high reasoning)
    agent = PolicyAgent()
    policy = agent.generate("payment_tree", "Optimize for low delay costs")

    # Switch to Anthropic - just change the model string
    agent = PolicyAgent(model="anthropic:claude-3-5-sonnet-20241022")

    # Use with context from simulation results
    policy = agent.generate(
        "payment_tree",
        "Improve settlement rate",
        current_policy=existing_policy,
        total_cost=50000,
        settlement_rate=0.85,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from experiments.castro.schemas.tree import get_tree_model, PolicyTree
from experiments.castro.schemas.actions import ACTIONS_BY_TREE_TYPE
from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE
from experiments.castro.prompts.templates import SYSTEM_PROMPT

# Default model configuration
DEFAULT_MODEL = "gpt-5.1"
DEFAULT_REASONING_EFFORT: Literal["low", "medium", "high"] = "high"
DEFAULT_REASONING_SUMMARY: Literal["concise", "detailed"] = "detailed"


@dataclass
class PolicyDeps:
    """Dependencies injected into policy generation agent."""

    tree_type: str
    max_depth: int = 3
    current_policy: dict[str, Any] | None = None
    total_cost: float | None = None
    settlement_rate: float | None = None
    per_bank_costs: dict[str, float] | None = None


class PolicyAgent:
    """PydanticAI-based policy generator.

    This is a thin wrapper around PydanticAI's Agent that provides
    policy-specific functionality. PydanticAI handles all provider
    abstraction internally.

    Supported models (via PydanticAI):
        - gpt-5.1 (default, with high reasoning effort)
        - openai:gpt-4o, openai:gpt-4o-mini
        - anthropic:claude-3-5-sonnet-20241022
        - google-gla:gemini-1.5-pro
        - ollama:llama3.1:8b
        - groq:llama-3.1-70b-versatile
        - And many more: https://ai.pydantic.dev/models/

    Example:
        # Default GPT-5.1 with high reasoning
        agent = PolicyAgent()
        policy = agent.generate("payment_tree", "Prioritize high-value payments")

        # Custom model
        agent = PolicyAgent(model="anthropic:claude-3-5-sonnet-20241022")
    """

    def __init__(
        self,
        model: str | None = None,
        max_depth: int = 3,
        retries: int = 3,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
        reasoning_summary: Literal["concise", "detailed"] = DEFAULT_REASONING_SUMMARY,
    ) -> None:
        """Initialize policy agent.

        Args:
            model: PydanticAI model string. Defaults to GPT-5.1.
                   For OpenAI: "gpt-5.1", "gpt-4o", etc.
                   For others: "anthropic:claude-3-5-sonnet-20241022", etc.
            max_depth: Maximum tree depth for generated policies
            retries: Number of retries on validation failure
            reasoning_effort: Reasoning effort for GPT-5.1 ("low", "medium", "high")
            reasoning_summary: Reasoning summary verbosity ("concise", "detailed")
        """
        self.model = model or DEFAULT_MODEL
        self.max_depth = max_depth
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self._agents: dict[str, Agent[PolicyDeps, Any]] = {}
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
        """Get the appropriate model instance.

        For GPT-5.x models, returns an OpenAIResponsesModel with reasoning settings.
        For other models, returns the model string directly.
        """
        if self._is_gpt5_model():
            # Use OpenAIResponsesModel for GPT-5.x with reasoning support
            return OpenAIResponsesModel(self.model)
        return self.model

    def _get_agent(self, tree_type: str) -> Agent[PolicyDeps, Any]:
        """Get or create agent for tree type."""
        if tree_type not in self._agents:
            TreeModel = get_tree_model(self.max_depth)

            # Build dynamic system prompt with available actions/fields
            actions = ACTIONS_BY_TREE_TYPE.get(tree_type, [])
            fields = FIELDS_BY_TREE_TYPE.get(tree_type, [])

            system_prompt = f"""{SYSTEM_PROMPT}

You are generating a {tree_type}.

Available actions: {', '.join(actions)}
Available context fields: {', '.join(fields[:20])}{'...' if len(fields) > 20 else ''}

Generate a policy tree that optimizes bank costs while maintaining high settlement rates.
"""

            model = self._get_model()
            self._agents[tree_type] = Agent(
                model,
                output_type=TreeModel,  # type: ignore
                system_prompt=system_prompt,
                deps_type=PolicyDeps,
                retries=self.retries,
                model_settings=self._model_settings,
            )

        return self._agents[tree_type]

    def generate(
        self,
        tree_type: str,
        instruction: str = "Generate an optimal policy",
        current_policy: dict[str, Any] | None = None,
        total_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Generate a policy tree.

        Args:
            tree_type: Type of tree (payment_tree, bank_tree, etc.)
            instruction: Natural language instruction for policy
            current_policy: Current policy to improve (optional)
            total_cost: Current total cost for context (optional)
            settlement_rate: Current settlement rate for context (optional)
            per_bank_costs: Per-bank costs for context (optional)

        Returns:
            Generated policy as dict
        """
        agent = self._get_agent(tree_type)

        # Build context-aware prompt
        prompt_parts = [instruction]

        if current_policy:
            import json
            prompt_parts.append(f"\nCurrent policy:\n```json\n{json.dumps(current_policy, indent=2)}\n```")

        if total_cost is not None:
            prompt_parts.append(f"\nCurrent total cost: ${total_cost:.0f}")

        if settlement_rate is not None:
            prompt_parts.append(f"\nCurrent settlement rate: {settlement_rate*100:.1f}%")

        if per_bank_costs:
            costs_str = ", ".join(f"{k}: ${v:.0f}" for k, v in per_bank_costs.items())
            prompt_parts.append(f"\nPer-bank costs: {costs_str}")

        prompt = "\n".join(prompt_parts)

        # Run agent
        deps = PolicyDeps(
            tree_type=tree_type,
            max_depth=self.max_depth,
            current_policy=current_policy,
            total_cost=total_cost,
            settlement_rate=settlement_rate,
            per_bank_costs=per_bank_costs,
        )

        result = agent.run_sync(prompt, deps=deps)

        # Convert to dict
        if hasattr(result.output, "model_dump"):
            return result.output.model_dump(exclude_none=True)
        return result.output

    async def generate_async(
        self,
        tree_type: str,
        instruction: str = "Generate an optimal policy",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Async version of generate."""
        agent = self._get_agent(tree_type)

        deps = PolicyDeps(
            tree_type=tree_type,
            max_depth=self.max_depth,
            current_policy=kwargs.get("current_policy"),
            total_cost=kwargs.get("total_cost"),
            settlement_rate=kwargs.get("settlement_rate"),
            per_bank_costs=kwargs.get("per_bank_costs"),
        )

        result = await agent.run(instruction, deps=deps)

        if hasattr(result.output, "model_dump"):
            return result.output.model_dump(exclude_none=True)
        return result.output


# Convenience function for one-off generation
def generate_policy(
    tree_type: str,
    instruction: str = "Generate an optimal policy",
    model: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate a policy tree with a single function call.

    Args:
        tree_type: Type of tree (payment_tree, bank_tree, etc.)
        instruction: Natural language instruction
        model: PydanticAI model string (defaults to GPT-5.1)
        reasoning_effort: Reasoning effort for GPT-5.1 ("low", "medium", "high")
        **kwargs: Additional context (current_policy, total_cost, etc.)

    Returns:
        Generated policy as dict

    Example:
        # Default GPT-5.1 with high reasoning
        policy = generate_policy(
            "payment_tree",
            "Minimize delay costs for high-priority payments",
        )

        # With Anthropic
        policy = generate_policy(
            "payment_tree",
            "Minimize delay costs",
            model="anthropic:claude-3-5-sonnet-20241022",
        )
    """
    agent = PolicyAgent(model=model, reasoning_effort=reasoning_effort)
    return agent.generate(tree_type, instruction, **kwargs)
