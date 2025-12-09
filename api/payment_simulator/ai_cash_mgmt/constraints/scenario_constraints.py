"""Scenario constraints for policy generation.

Defines what parameters, fields, and actions are allowed in
policies generated for a specific scenario.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import ParameterSpec


class ScenarioConstraints(BaseModel):
    """Constraints derived from scenario configuration.

    These constraints limit what the LLM can generate to ensure
    valid policies that respect scenario-specific limitations.

    Example:
        >>> constraints = ScenarioConstraints(
        ...     allowed_parameters=[
        ...         ParameterSpec(name="threshold", param_type="int", min_value=0),
        ...     ],
        ...     allowed_fields=["amount", "priority", "sender_id"],
        ...     allowed_actions={
        ...         "payment_tree": ["submit", "queue", "hold"],
        ...         "bank_tree": ["borrow", "repay", "none"],
        ...     },
        ... )
    """

    allowed_parameters: list[ParameterSpec] = Field(
        default_factory=list,
        description="Allowed parameters with their specifications",
    )
    allowed_fields: list[str] = Field(
        default_factory=list,
        description="Allowed context fields for conditions",
    )
    allowed_actions: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Allowed actions per tree type (payment_tree, bank_tree, collateral_tree)",
    )

    @classmethod
    def _convert_parameters(
        cls, params: list[ParameterSpec | dict[str, Any]]
    ) -> list[ParameterSpec]:
        """Convert parameter dicts to ParameterSpec instances."""
        converted = []
        for param in params:
            if isinstance(param, dict):
                converted.append(ParameterSpec.model_validate(param))
            else:
                converted.append(param)
        return converted

    def model_post_init(self, __context: Any) -> None:
        """Convert parameter dicts to ParameterSpec instances after init."""
        # Re-process to handle dict inputs during validation
        converted = self._convert_parameters(
            self.allowed_parameters  # type: ignore[arg-type]
        )
        object.__setattr__(self, "allowed_parameters", converted)

    def get_parameter_spec(self, name: str) -> ParameterSpec | None:
        """Get parameter spec by name.

        Args:
            name: Parameter name.

        Returns:
            ParameterSpec if found, None otherwise.
        """
        for param in self.allowed_parameters:
            if param.name == name:
                return param
        return None

    def is_parameter_allowed(self, name: str) -> bool:
        """Check if a parameter name is allowed.

        Args:
            name: Parameter name.

        Returns:
            True if parameter is allowed.
        """
        return self.get_parameter_spec(name) is not None

    def is_field_allowed(self, field: str) -> bool:
        """Check if a context field is allowed.

        Args:
            field: Field name.

        Returns:
            True if field is allowed.
        """
        return field in self.allowed_fields

    def is_action_allowed(self, tree_type: str, action: str) -> bool:
        """Check if an action is allowed for a tree type.

        Args:
            tree_type: Tree type (payment_tree, bank_tree, collateral_tree).
            action: Action name.

        Returns:
            True if action is allowed for the tree type.
        """
        if tree_type not in self.allowed_actions:
            return True  # No constraints for this tree type
        return action in self.allowed_actions[tree_type]
