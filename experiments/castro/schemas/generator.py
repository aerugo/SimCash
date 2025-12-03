"""Dynamic schema generation for policy trees.

The PolicySchemaGenerator creates Pydantic models dynamically based on:
- Tree type (which determines available actions and fields)
- Feature toggles (which can include/exclude categories)
- Max depth (which determines the tree model depth level)

This allows generating schemas tailored to specific scenarios,
ensuring LLMs can only generate valid policies for that context.
"""

from __future__ import annotations

from experiments.castro.schemas.registry import (
    FIELDS_BY_TREE_TYPE,
    FIELD_CATEGORIES,
    ACTIONS_BY_TREE_TYPE,
    ACTION_CATEGORIES,
)
from experiments.castro.schemas.tree import get_tree_model
from experiments.castro.schemas.toggles import PolicyFeatureToggles


class PolicySchemaGenerator:
    """Generates Pydantic schemas for policy trees based on context.

    This class is the core of the dynamic schema generation system.
    It filters actions and fields based on:
    - Tree type (payment_tree, bank_tree, collateral trees)
    - Feature toggles from scenario configuration
    - Maximum tree depth

    Usage:
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=scenario_config.policy_feature_toggles,
            max_depth=3,
        )
        allowed_actions = gen.get_allowed_actions()
        allowed_fields = gen.get_allowed_fields()
        TreeModel = gen.build_tree_model()
    """

    def __init__(
        self,
        tree_type: str,
        feature_toggles: PolicyFeatureToggles,
        max_depth: int = 5,
    ) -> None:
        """Initialize the generator.

        Args:
            tree_type: The type of tree (payment_tree, bank_tree, etc.)
            feature_toggles: PolicyFeatureToggles from scenario config
            max_depth: Maximum depth for the tree model (0-5, default 5)
        """
        self.tree_type = tree_type
        self.toggles = feature_toggles
        self.max_depth = max_depth

        # Cache computed values
        self._allowed_actions: list[str] | None = None
        self._allowed_fields: list[str] | None = None

    def get_allowed_actions(self) -> list[str]:
        """Get list of actions allowed for this tree type and toggles.

        Returns:
            List of action type names that are valid for generation.
        """
        if self._allowed_actions is not None:
            return self._allowed_actions

        # Get base actions for this tree type
        base_actions = ACTIONS_BY_TREE_TYPE.get(self.tree_type, [])

        # Filter by feature toggles
        allowed = []
        for action in base_actions:
            category = ACTION_CATEGORIES.get(action)
            if category and self.toggles.is_category_allowed(category):
                allowed.append(action)

        self._allowed_actions = allowed
        return allowed

    def get_allowed_fields(self) -> list[str]:
        """Get list of fields allowed for this tree type and toggles.

        Returns:
            List of field names that are valid for generation.
        """
        if self._allowed_fields is not None:
            return self._allowed_fields

        # Get base fields for this tree type
        base_fields = FIELDS_BY_TREE_TYPE.get(self.tree_type, [])

        # Filter by feature toggles
        allowed = []
        for field in base_fields:
            category = FIELD_CATEGORIES.get(field)
            if category and self.toggles.is_category_allowed(category):
                allowed.append(field)

        self._allowed_fields = allowed
        return allowed

    def build_tree_model(self) -> type:
        """Build the Pydantic model for this tree configuration.

        Returns:
            The appropriate TreeNodeLN type for the max_depth setting.
            Currently returns the pre-built depth-limited types.
        """
        return get_tree_model(self.max_depth)

    def get_schema_summary(self) -> str:
        """Get a human-readable summary of the schema for prompts.

        Returns:
            String summary describing the allowed actions and fields.
        """
        actions = self.get_allowed_actions()
        fields = self.get_allowed_fields()

        lines = [
            f"Schema for {self.tree_type} (max depth: {self.max_depth})",
            "",
            f"Allowed Actions ({len(actions)}):",
        ]
        for action in sorted(actions):
            lines.append(f"  - {action}")

        lines.append("")
        lines.append(f"Allowed Fields ({len(fields)}):")
        # Group fields by first 10 characters for readability
        for field in sorted(fields)[:20]:  # Limit to first 20 for summary
            lines.append(f"  - {field}")
        if len(fields) > 20:
            lines.append(f"  ... and {len(fields) - 20} more")

        return "\n".join(lines)

    def get_json_schema(self) -> dict:
        """Get the JSON schema for OpenAI structured output.

        Returns:
            The JSON schema dict from the tree model.
        """
        Model = self.build_tree_model()
        return Model.model_json_schema()  # type: ignore[union-attr]


def create_generator_for_scenario(
    tree_type: str,
    scenario_config: object,
    max_depth: int = 5,
) -> PolicySchemaGenerator:
    """Create a generator from a scenario configuration.

    This is a convenience function that extracts feature toggles
    from a SimulationConfig object.

    Args:
        tree_type: The type of tree to generate
        scenario_config: SimulationConfig object with policy_feature_toggles
        max_depth: Maximum tree depth

    Returns:
        Configured PolicySchemaGenerator
    """
    from experiments.castro.schemas.toggles import get_feature_toggles

    toggles = get_feature_toggles(scenario_config)

    return PolicySchemaGenerator(
        tree_type=tree_type,
        feature_toggles=toggles,
        max_depth=max_depth,
    )
