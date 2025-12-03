"""Structured output client for policy generation.

Uses OpenAI's structured output feature with Pydantic schemas
to generate valid policy JSON.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter

from experiments.castro.schemas.generator import PolicySchemaGenerator
from experiments.castro.schemas.toggles import PolicyFeatureToggles
from experiments.castro.prompts.builder import PolicyPromptBuilder
from experiments.castro.prompts.templates import SYSTEM_PROMPT
from experiments.castro.generator.validation import (
    validate_policy_structure,
    ValidationResult,
)


@dataclass
class PolicyContext:
    """Context for policy generation including performance metrics."""

    current_costs: dict[str, float] = field(default_factory=dict)
    settlement_rate: float = 1.0
    total_settled: int = 0
    total_pending: int = 0
    additional_context: dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        """Compute total cost from per-bank costs."""
        return sum(self.current_costs.values())

    @classmethod
    def from_simulation_result(cls, result: dict[str, Any]) -> "PolicyContext":
        """Create context from simulation result dict."""
        return cls(
            current_costs=result.get("per_bank_costs", {}),
            settlement_rate=result.get("settlement_rate", 1.0),
            total_settled=result.get("total_settled", 0),
            total_pending=result.get("total_pending", 0),
        )


class StructuredPolicyGenerator:
    """Generate valid policies using OpenAI structured output.

    This class wraps the OpenAI API to generate policies that conform
    to our Pydantic schemas. It handles:
    - Schema generation based on tree type and feature toggles
    - Prompt construction with context
    - API calls with structured output
    - Validation and retry logic

    Usage:
        generator = StructuredPolicyGenerator()
        policy = await generator.generate_policy(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            context=PolicyContext(...),
        )
    """

    # Default model for structured output (must support response_format)
    DEFAULT_MODEL = "gpt-4o-2024-08-06"

    def __init__(
        self,
        model: str | None = None,
        max_depth: int = 5,
        max_retries: int = 3,
        api_key: str | None = None,
    ) -> None:
        """Initialize the generator.

        Args:
            model: OpenAI model to use (must support structured output)
            max_depth: Maximum tree depth for generated policies
            max_retries: Maximum retry attempts on validation failure
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.model = model or self.DEFAULT_MODEL
        self.max_depth = max_depth
        self.max_retries = max_retries
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def _get_client(self) -> Any:
        """Get OpenAI client lazily."""
        try:
            from openai import OpenAI
            return OpenAI(api_key=self._api_key)
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )

    def generate_policy(
        self,
        tree_type: str,
        feature_toggles: PolicyFeatureToggles | None = None,
        context: PolicyContext | None = None,
        current_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a valid policy tree.

        Args:
            tree_type: Type of tree to generate
            feature_toggles: Feature toggles for schema generation
            context: Performance context for optimization
            current_policy: Current policy to improve (if any)

        Returns:
            Generated policy dict

        Raises:
            ValueError: If generation fails after all retries
        """
        if feature_toggles is None:
            feature_toggles = PolicyFeatureToggles()

        if context is None:
            context = PolicyContext()

        # Build schema generator
        schema_gen = PolicySchemaGenerator(
            tree_type=tree_type,
            feature_toggles=feature_toggles,
            max_depth=self.max_depth,
        )

        # Build prompt
        prompt_builder = PolicyPromptBuilder.from_generator(schema_gen)
        if current_policy:
            prompt_builder.set_current_policy(current_policy)
        prompt_builder.set_performance(
            total_cost=context.total_cost,
            settlement_rate=context.settlement_rate,
            per_bank_costs=context.current_costs,
        )
        user_prompt = prompt_builder.build()

        # Get JSON schema for structured output
        TreeType = schema_gen.build_tree_model()
        adapter = TypeAdapter(TreeType)
        json_schema = adapter.json_schema()

        # Attempt generation with retries
        last_error: str | None = None
        for attempt in range(self.max_retries):
            try:
                policy = self._call_api(
                    user_prompt=user_prompt,
                    json_schema=json_schema,
                    last_error=last_error if attempt > 0 else None,
                )

                # Validate the generated policy
                validation = validate_policy_structure(
                    policy, tree_type, self.max_depth
                )
                if validation.is_valid:
                    return policy

                # Validation failed - prepare for retry
                last_error = "; ".join(validation.errors)

            except Exception as e:
                last_error = str(e)

        raise ValueError(
            f"Failed to generate valid policy after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _call_api(
        self,
        user_prompt: str,
        json_schema: dict[str, Any],
        last_error: str | None = None,
    ) -> dict[str, Any]:
        """Make API call with structured output.

        Args:
            user_prompt: The user message
            json_schema: JSON schema for response format
            last_error: Error from last attempt (for retry context)

        Returns:
            Parsed policy dict
        """
        client = self._get_client()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Add error context for retries
        if last_error:
            messages.append({
                "role": "user",
                "content": (
                    f"The previous attempt failed validation with: {last_error}\n"
                    "Please fix these issues and try again."
                ),
            })

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "policy_tree",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from API")

        return json.loads(content)

    def generate_all_trees(
        self,
        feature_toggles: PolicyFeatureToggles | None = None,
        context: PolicyContext | None = None,
        current_policies: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Generate all policy trees.

        Args:
            feature_toggles: Feature toggles for schema generation
            context: Performance context for optimization
            current_policies: Current policies by tree type

        Returns:
            Dict of tree_type -> policy
        """
        tree_types = [
            "payment_tree",
            "bank_tree",
            "strategic_collateral_tree",
            "end_of_tick_collateral_tree",
        ]

        if current_policies is None:
            current_policies = {}

        result = {}
        for tree_type in tree_types:
            current = current_policies.get(tree_type)
            result[tree_type] = self.generate_policy(
                tree_type=tree_type,
                feature_toggles=feature_toggles,
                context=context,
                current_policy=current,
            )

        return result
