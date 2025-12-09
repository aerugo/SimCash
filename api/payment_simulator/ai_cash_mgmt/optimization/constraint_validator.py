"""Constraint validator for LLM-generated policies.

Validates that generated policies respect scenario constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)


@dataclass
class ValidationResult:
    """Result of policy validation.

    Attributes:
        is_valid: Whether the policy is valid.
        errors: List of validation error messages.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)


class ConstraintValidator:
    """Validates policies against scenario constraints.

    The validator checks:
    - Parameters are known and within allowed ranges
    - Context fields are allowed
    - Actions are valid for their tree types
    - Nested conditions are recursively validated

    Example:
        >>> constraints = ScenarioConstraints(
        ...     allowed_parameters=[{"name": "threshold", "param_type": "int"}],
        ...     allowed_fields=["amount"],
        ...     allowed_actions={"payment_tree": ["submit", "queue"]},
        ... )
        >>> validator = ConstraintValidator(constraints)
        >>> result = validator.validate(policy)
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(error)
    """

    def __init__(self, constraints: ScenarioConstraints) -> None:
        """Initialize validator with constraints.

        Args:
            constraints: Scenario constraints to validate against.
        """
        self.constraints = constraints

    def validate(self, policy: dict[str, Any]) -> ValidationResult:
        """Validate a complete policy against constraints.

        Args:
            policy: Policy dict with tree definitions.

        Returns:
            ValidationResult with is_valid flag and error list.
        """
        errors: list[str] = []

        # Validate each tree type present in policy
        for tree_type in ["payment_tree", "bank_tree", "collateral_tree"]:
            if tree_type in policy:
                tree_errors = self._validate_tree(tree_type, policy[tree_type])
                errors.extend(tree_errors)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def _validate_tree(
        self, tree_type: str, tree: dict[str, Any]
    ) -> list[str]:
        """Validate a single decision tree.

        Args:
            tree_type: Type of tree (payment_tree, bank_tree, collateral_tree).
            tree: Tree definition dict.

        Returns:
            List of validation errors.
        """
        errors: list[str] = []

        # Validate parameters
        parameters = tree.get("parameters", {})
        for param_name, param_value in parameters.items():
            param_errors = self._validate_parameter(param_name, param_value)
            errors.extend(param_errors)

        # Validate tree nodes recursively
        root = tree.get("root", {})
        node_errors = self._validate_node(tree_type, root)
        errors.extend(node_errors)

        return errors

    def _validate_parameter(
        self, name: str, value: Any
    ) -> list[str]:
        """Validate a parameter name and value.

        Args:
            name: Parameter name.
            value: Parameter value.

        Returns:
            List of validation errors.
        """
        errors: list[str] = []

        # Check if parameter is allowed
        if not self.constraints.is_parameter_allowed(name):
            errors.append(f"Unknown parameter: {name}")
            return errors

        # Validate value against spec
        spec = self.constraints.get_parameter_spec(name)
        if spec:
            is_valid, error = spec.validate_value(value)
            if not is_valid and error:
                errors.append(error)

        return errors

    def _validate_node(
        self, tree_type: str, node: dict[str, Any]
    ) -> list[str]:
        """Recursively validate a decision tree node.

        Args:
            tree_type: Type of tree.
            node: Node definition dict.

        Returns:
            List of validation errors.
        """
        errors: list[str] = []

        if not node:
            return errors

        # If it's an action node
        if "action" in node:
            action = node["action"]
            if not self.constraints.is_action_allowed(tree_type, action):
                allowed = self.constraints.allowed_actions.get(tree_type, [])
                errors.append(
                    f"Invalid action '{action}' for {tree_type}. "
                    f"Allowed: {allowed}"
                )
            return errors

        # If it's a condition node
        if "field" in node:
            field = node["field"]
            if not self.constraints.is_field_allowed(field):
                errors.append(
                    f"Unknown field: {field}. "
                    f"Allowed: {self.constraints.allowed_fields}"
                )

        # Validate nested branches
        if "if_true" in node:
            errors.extend(self._validate_node(tree_type, node["if_true"]))
        if "if_false" in node:
            errors.extend(self._validate_node(tree_type, node["if_false"]))

        # Handle value references to parameters
        if "value" in node:
            value = node["value"]
            if isinstance(value, dict) and "param" in value:
                param_name = value["param"]
                if not self.constraints.is_parameter_allowed(param_name):
                    errors.append(f"Unknown parameter reference: {param_name}")

        return errors
