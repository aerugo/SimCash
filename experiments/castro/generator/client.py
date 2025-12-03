"""Structured output client for policy generation.

Uses a provider-agnostic interface to generate valid policy JSON
with any LLM that supports structured output.

Usage:
    # Default (OpenAI)
    generator = StructuredPolicyGenerator()
    policy = generator.generate_policy("payment_tree")

    # With specific provider
    from experiments.castro.generator.providers import AnthropicProvider
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
    generator = StructuredPolicyGenerator(provider=provider)
"""

from __future__ import annotations

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
from experiments.castro.generator.providers import (
    LLMProvider,
    OpenAIProvider,
    StructuredOutputRequest,
    StructuredOutputResponse,
    get_provider,
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


@dataclass
class GenerationResult:
    """Result from policy generation including metadata."""

    policy: dict[str, Any]
    provider: str
    attempts: int
    usage: dict[str, int] | None = None


class StructuredPolicyGenerator:
    """Generate valid policies using LLM structured output.

    This class wraps any LLM provider to generate policies that conform
    to our Pydantic schemas. It handles:
    - Schema generation based on tree type and feature toggles
    - Prompt construction with context
    - Provider-agnostic API calls with structured output
    - Validation and retry logic

    Usage:
        # With default OpenAI provider
        generator = StructuredPolicyGenerator()
        policy = generator.generate_policy(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            context=PolicyContext(...),
        )

        # With custom provider
        from experiments.castro.generator.providers import AnthropicProvider
        provider = AnthropicProvider()
        generator = StructuredPolicyGenerator(provider=provider)
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        max_depth: int = 5,
        max_retries: int = 3,
        temperature: float = 0.7,
    ) -> None:
        """Initialize the generator.

        Args:
            provider: LLM provider to use (defaults to OpenAI)
            max_depth: Maximum tree depth for generated policies
            max_retries: Maximum retry attempts on validation failure
            temperature: Sampling temperature for generation
        """
        self.provider = provider or OpenAIProvider()
        self.max_depth = max_depth
        self.max_retries = max_retries
        self.temperature = temperature

    @classmethod
    def with_provider(
        cls,
        provider_type: str,
        model: str | None = None,
        max_depth: int = 5,
        max_retries: int = 3,
        **provider_kwargs: Any,
    ) -> "StructuredPolicyGenerator":
        """Create generator with a specific provider type.

        Args:
            provider_type: One of "openai", "anthropic", "google", "ollama"
            model: Model name (optional, uses provider default)
            max_depth: Maximum tree depth for generated policies
            max_retries: Maximum retry attempts on validation failure
            **provider_kwargs: Additional provider-specific arguments

        Returns:
            Configured StructuredPolicyGenerator

        Example:
            generator = StructuredPolicyGenerator.with_provider(
                "anthropic",
                model="claude-3-5-sonnet-20241022"
            )
        """
        provider = get_provider(provider_type, model=model, **provider_kwargs)
        return cls(
            provider=provider,
            max_depth=max_depth,
            max_retries=max_retries,
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
        result = self.generate_policy_with_metadata(
            tree_type=tree_type,
            feature_toggles=feature_toggles,
            context=context,
            current_policy=current_policy,
        )
        return result.policy

    def generate_policy_with_metadata(
        self,
        tree_type: str,
        feature_toggles: PolicyFeatureToggles | None = None,
        context: PolicyContext | None = None,
        current_policy: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Generate a valid policy tree with generation metadata.

        Args:
            tree_type: Type of tree to generate
            feature_toggles: Feature toggles for schema generation
            context: Performance context for optimization
            current_policy: Current policy to improve (if any)

        Returns:
            GenerationResult with policy and metadata

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

        # Build base request
        request = StructuredOutputRequest(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=json_schema,
            schema_name=f"{tree_type}_schema",
            temperature=self.temperature,
        )

        # Attempt generation with retries
        last_error: str | None = None
        total_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for attempt in range(self.max_retries):
            try:
                # Add error context for retries
                if last_error and attempt > 0:
                    request = StructuredOutputRequest(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=(
                            f"{user_prompt}\n\n"
                            f"IMPORTANT: The previous attempt failed validation with: {last_error}\n"
                            "Please fix these issues."
                        ),
                        json_schema=json_schema,
                        schema_name=f"{tree_type}_schema",
                        temperature=self.temperature,
                    )

                response = self.provider.generate_structured(request)

                # Track usage
                if response.usage:
                    for key in total_usage:
                        total_usage[key] += response.usage.get(key, 0)

                policy = response.content

                # Validate the generated policy
                validation = validate_policy_structure(
                    policy, tree_type, self.max_depth
                )
                if validation.is_valid:
                    return GenerationResult(
                        policy=policy,
                        provider=self.provider.name,
                        attempts=attempt + 1,
                        usage=total_usage if any(total_usage.values()) else None,
                    )

                # Validation failed - prepare for retry
                last_error = "; ".join(validation.errors)

            except Exception as e:
                last_error = str(e)

        raise ValueError(
            f"Failed to generate valid policy after {self.max_retries} attempts "
            f"using {self.provider.name}. Last error: {last_error}"
        )

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
