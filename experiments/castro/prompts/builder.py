"""Prompt builder for policy generation.

Builds context-aware prompts for LLM policy generation, including:
- Allowed actions and fields for the tree type
- Current policy to improve (if any)
- Performance metrics to optimize against
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from experiments.castro.prompts.templates import get_tree_context

if TYPE_CHECKING:
    from experiments.castro.schemas.generator import PolicySchemaGenerator


class PolicyPromptBuilder:
    """Builds prompts for policy generation.

    Creates detailed prompts that include:
    - Tree type and context
    - Allowed actions and their parameters
    - Allowed context fields
    - Current policy (to improve)
    - Performance metrics

    Usage:
        builder = PolicyPromptBuilder(
            tree_type="payment_tree",
            allowed_actions=["Release", "Hold"],
            allowed_fields=["balance", "amount"],
        )
        builder.set_current_policy(current)
        builder.set_performance(total_cost=1500, settlement_rate=0.95)
        prompt = builder.build()
    """

    def __init__(
        self,
        tree_type: str,
        allowed_actions: list[str],
        allowed_fields: list[str],
    ) -> None:
        """Initialize the builder.

        Args:
            tree_type: The type of tree to generate
            allowed_actions: List of allowed action types
            allowed_fields: List of allowed context fields
        """
        self.tree_type = tree_type
        self.allowed_actions = allowed_actions
        self.allowed_fields = allowed_fields

        self._current_policy: dict[str, Any] | None = None
        self._total_cost: float | None = None
        self._settlement_rate: float | None = None
        self._per_bank_costs: dict[str, float] | None = None
        self._optimization_goal: str | None = None

    @classmethod
    def from_generator(cls, generator: "PolicySchemaGenerator") -> "PolicyPromptBuilder":
        """Create a builder from a PolicySchemaGenerator.

        Args:
            generator: The schema generator to use

        Returns:
            Configured PolicyPromptBuilder
        """
        return cls(
            tree_type=generator.tree_type,
            allowed_actions=generator.get_allowed_actions(),
            allowed_fields=generator.get_allowed_fields(),
        )

    def set_current_policy(self, policy: dict[str, Any]) -> "PolicyPromptBuilder":
        """Set the current policy to improve.

        Args:
            policy: The current policy dict

        Returns:
            self for chaining
        """
        self._current_policy = policy
        return self

    def set_performance(
        self,
        total_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
    ) -> "PolicyPromptBuilder":
        """Set performance metrics to optimize against.

        Args:
            total_cost: Total cost from last simulation
            settlement_rate: Settlement rate (0-1)
            per_bank_costs: Cost breakdown by bank

        Returns:
            self for chaining
        """
        self._total_cost = total_cost
        self._settlement_rate = settlement_rate
        self._per_bank_costs = per_bank_costs
        return self

    def set_optimization_goal(self, goal: str) -> "PolicyPromptBuilder":
        """Set a specific optimization goal.

        Args:
            goal: Description of what to optimize for

        Returns:
            self for chaining
        """
        self._optimization_goal = goal
        return self

    def build(self) -> str:
        """Build the complete prompt.

        Returns:
            The formatted prompt string
        """
        sections = []

        # Tree type context
        sections.append(f"# Generate {self.tree_type} Policy\n")
        sections.append(get_tree_context(self.tree_type))

        # Allowed actions
        sections.append(self._build_actions_section())

        # Allowed fields
        sections.append(self._build_fields_section())

        # Performance context (if set)
        if self._total_cost is not None or self._settlement_rate is not None:
            sections.append(self._build_performance_section())

        # Current policy (if set)
        if self._current_policy is not None:
            sections.append(self._build_current_policy_section())

        # Optimization goal
        sections.append(self._build_goal_section())

        return "\n".join(sections)

    def _build_actions_section(self) -> str:
        """Build the allowed actions section."""
        lines = [
            "\n## Allowed Actions",
            f"The following actions are valid for {self.tree_type}:",
            "",
        ]
        for action in sorted(self.allowed_actions):
            lines.append(f"- **{action}**")
        return "\n".join(lines)

    def _build_fields_section(self) -> str:
        """Build the allowed fields section."""
        lines = [
            "\n## Available Context Fields",
            "Use these fields in your conditions:",
            "",
        ]
        # Group fields for readability (show first 30)
        for field in sorted(self.allowed_fields)[:30]:
            lines.append(f"- `{field}`")
        if len(self.allowed_fields) > 30:
            lines.append(f"... and {len(self.allowed_fields) - 30} more")
        return "\n".join(lines)

    def _build_performance_section(self) -> str:
        """Build the performance metrics section."""
        lines = [
            "\n## Current Performance",
            "The current policy achieved:",
            "",
        ]
        if self._total_cost is not None:
            lines.append(f"- Total Cost: {self._total_cost}")
        if self._settlement_rate is not None:
            pct = self._settlement_rate * 100
            lines.append(f"- Settlement Rate: {pct:.1f}%")
        if self._per_bank_costs:
            lines.append("- Cost by Bank:")
            for bank, cost in sorted(self._per_bank_costs.items()):
                lines.append(f"  - {bank}: {cost}")
        return "\n".join(lines)

    def _build_current_policy_section(self) -> str:
        """Build the current policy section."""
        lines = [
            "\n## Current Policy (to improve)",
            "```json",
            json.dumps(self._current_policy, indent=2),
            "```",
        ]
        return "\n".join(lines)

    def _build_goal_section(self) -> str:
        """Build the optimization goal section."""
        if self._optimization_goal:
            goal = self._optimization_goal
        else:
            goal = "Minimize total cost while maintaining high settlement rate"

        return f"""
## Optimization Goal
{goal}

## Instructions
Generate a valid {self.tree_type} policy tree that achieves the optimization goal.
Return only the JSON policy tree, no explanation needed.
"""
