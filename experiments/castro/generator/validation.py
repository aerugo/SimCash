"""Policy validation wrapper.

Provides validation of generated policies using both:
1. Structural validation via Pydantic schemas
2. Semantic validation via the Rust CLI validator (when available)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter, ValidationError

from experiments.castro.schemas.tree import get_tree_model
from experiments.castro.schemas.actions import ACTIONS_BY_TREE_TYPE


@dataclass
class ValidationResult:
    """Result of policy validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(is_valid=True)

    @classmethod
    def failure(cls, errors: list[str]) -> "ValidationResult":
        """Create a failed validation result."""
        return cls(is_valid=False, errors=errors)


def validate_policy_structure(
    policy: dict[str, Any],
    tree_type: str,
    max_depth: int = 5,
) -> ValidationResult:
    """Validate policy structure using Pydantic schemas.

    Args:
        policy: The policy dict to validate
        tree_type: The type of tree (payment_tree, bank_tree, etc.)
        max_depth: Maximum tree depth allowed

    Returns:
        ValidationResult indicating success or failure with errors
    """
    errors: list[str] = []

    # Check basic structure
    if not isinstance(policy, dict):
        return ValidationResult.failure(["Policy must be a dict"])

    if "type" not in policy:
        return ValidationResult.failure(["Policy must have 'type' field"])

    node_type = policy.get("type")
    if node_type not in ("action", "condition"):
        return ValidationResult.failure([f"Invalid node type: {node_type}"])

    # For action nodes, validate action type
    if node_type == "action":
        action = policy.get("action")
        if not action:
            return ValidationResult.failure(["Action node must have 'action' field"])

        valid_actions = ACTIONS_BY_TREE_TYPE.get(tree_type, [])
        if action not in valid_actions:
            errors.append(f"Invalid action '{action}' for {tree_type}")
            return ValidationResult.failure(errors)

    # For condition nodes, validate structure
    if node_type == "condition":
        if "condition" not in policy:
            errors.append("Condition node must have 'condition' field")
        if "on_true" not in policy:
            errors.append("Condition node must have 'on_true' field")
        if "on_false" not in policy:
            errors.append("Condition node must have 'on_false' field")
        if errors:
            return ValidationResult.failure(errors)

        # Recursively validate children
        on_true_result = validate_policy_structure(
            policy["on_true"], tree_type, max_depth - 1
        )
        if not on_true_result.is_valid:
            errors.extend([f"on_true: {e}" for e in on_true_result.errors])

        on_false_result = validate_policy_structure(
            policy["on_false"], tree_type, max_depth - 1
        )
        if not on_false_result.is_valid:
            errors.extend([f"on_false: {e}" for e in on_false_result.errors])

        if errors:
            return ValidationResult.failure(errors)

    # Use TypeAdapter for full schema validation
    try:
        TreeType = get_tree_model(max_depth)
        adapter = TypeAdapter(TreeType)
        adapter.validate_python(policy)
    except ValidationError as e:
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")
        return ValidationResult.failure(errors)

    return ValidationResult.success()


def validate_policy_with_cli(
    policy: dict[str, Any],
    tree_type: str,
) -> ValidationResult:
    """Validate policy using the Rust CLI validator.

    This provides semantic validation beyond structural checks.
    Falls back to structural validation if CLI is unavailable.

    Args:
        policy: The policy dict to validate
        tree_type: The type of tree

    Returns:
        ValidationResult indicating success or failure
    """
    import json
    import subprocess
    import tempfile
    import os

    # First do structural validation
    struct_result = validate_policy_structure(policy, tree_type)
    if not struct_result.is_valid:
        return struct_result

    # Try CLI validation
    try:
        # Write policy to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(policy, f)
            temp_path = f.name

        try:
            # Run CLI validator
            result = subprocess.run(
                [
                    "payment-sim",
                    "validate-policy",
                    "--tree-type",
                    tree_type,
                    temp_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return ValidationResult.success()
            else:
                errors = result.stderr.strip().split("\n") if result.stderr else []
                if not errors:
                    errors = ["CLI validation failed (no error message)"]
                return ValidationResult.failure(errors)

        finally:
            os.unlink(temp_path)

    except FileNotFoundError:
        # CLI not available, return structural validation result
        return struct_result
    except subprocess.TimeoutExpired:
        return ValidationResult.failure(["CLI validation timed out"])
    except Exception as e:
        # CLI failed, return structural validation result with warning
        result = struct_result
        result.warnings.append(f"CLI validation unavailable: {e}")
        return result
