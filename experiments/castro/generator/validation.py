"""Policy validation wrapper.

Provides validation of generated policies using both:
1. Structural validation via Pydantic schemas
2. Semantic validation via the Rust CLI validator (when available)
3. Castro-specific validation for paper alignment (when castro_mode=True)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter, ValidationError

from experiments.castro.schemas.tree import get_tree_model
from experiments.castro.schemas.actions import ACTIONS_BY_TREE_TYPE


# ============================================================================
# Castro-Specific Validation Constants
# ============================================================================

# Actions allowed in Castro mode for payment_tree
CASTRO_ALLOWED_PAYMENT_ACTIONS = {"Release", "Hold"}

# Actions allowed in Castro mode for collateral trees
CASTRO_ALLOWED_COLLATERAL_ACTIONS = {"PostCollateral", "HoldCollateral"}

# Actions that indicate mid-day collateral changes (not allowed in Castro mode)
CASTRO_FORBIDDEN_COLLATERAL_ACTIONS = {"WithdrawCollateral"}


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
        max_depth: Maximum tree depth allowed (0-5)

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

    # Use TypeAdapter for full schema validation
    # This validates the entire tree structure including depth
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


# ============================================================================
# Castro-Specific Validation
# ============================================================================


def _find_actions_in_tree(node: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Recursively find all actions in a tree with their path.

    Args:
        node: A tree node (action or condition)

    Returns:
        List of (action_name, path) tuples
    """
    actions: list[tuple[str, list[str]]] = []

    if not isinstance(node, dict):
        return actions

    node_type = node.get("type")
    node_id = node.get("node_id", "unknown")

    if node_type == "action":
        action = node.get("action", "unknown")
        actions.append((action, [node_id]))

    elif node_type == "condition":
        on_true = node.get("on_true", {})
        on_false = node.get("on_false", {})

        for action, path in _find_actions_in_tree(on_true):
            actions.append((action, [node_id, "on_true"] + path))
        for action, path in _find_actions_in_tree(on_false):
            actions.append((action, [node_id, "on_false"] + path))

    return actions


def _is_tick_zero_guarded_collateral_tree(node: dict[str, Any]) -> tuple[bool, str]:
    """Check if a collateral tree only allows posting at tick 0.

    The Castro paper requires that collateral (initial liquidity) is ONLY
    allocated at t=0. This function validates that the strategic_collateral_tree
    follows this pattern:
    - PostCollateral is only reachable when system_tick_in_day == 0
    - All other branches lead to HoldCollateral

    Args:
        node: The strategic_collateral_tree root node

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(node, dict):
        return False, "Collateral tree must be a dict"

    node_type = node.get("type")

    # If it's just an action, it must be HoldCollateral (no posting ever)
    # or PostCollateral with a guard (but we can't check guard from action alone)
    if node_type == "action":
        action = node.get("action")
        if action == "PostCollateral":
            # PostCollateral at root without condition means it posts every tick
            return False, (
                "Castro mode: PostCollateral cannot be at root without tick==0 guard. "
                "Wrap in condition: if system_tick_in_day == 0 then PostCollateral else HoldCollateral"
            )
        # HoldCollateral at root is fine (never posts)
        return True, ""

    if node_type == "condition":
        condition = node.get("condition", {})

        # Check if this is a tick-zero guard
        is_tick_zero_guard = _is_tick_zero_condition(condition)

        on_true = node.get("on_true", {})
        on_false = node.get("on_false", {})

        if is_tick_zero_guard:
            # If guarded by tick == 0:
            # - on_true can have PostCollateral
            # - on_false should NOT have PostCollateral (or be guarded again)
            false_actions = _find_actions_in_tree(on_false)
            for action, path in false_actions:
                if action == "PostCollateral":
                    return False, (
                        f"Castro mode: PostCollateral found in non-tick-0 branch "
                        f"at path {' -> '.join(path)}. Only post collateral at tick 0."
                    )
            return True, ""
        else:
            # Not a tick-zero guard - neither branch should have PostCollateral
            # unless they have their own tick-zero guard
            all_actions = _find_actions_in_tree(node)
            for action, path in all_actions:
                if action == "PostCollateral":
                    # Check if there's a tick-zero guard in the path
                    # For now, reject any PostCollateral without top-level tick-zero guard
                    return False, (
                        f"Castro mode: PostCollateral at path {' -> '.join(path)} "
                        f"is not guarded by system_tick_in_day == 0 at tree root. "
                        f"Initial liquidity must only be set at tick 0."
                    )
            return True, ""

    return True, ""


def _is_tick_zero_condition(condition: dict[str, Any]) -> bool:
    """Check if a condition is checking for tick 0.

    Recognizes patterns like:
    - {"op": "==", "left": {"field": "system_tick_in_day"}, "right": 0}
    - {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}}
    - {"op": "==", "left": {"field": "current_tick"}, "right": 0}
    """
    if not isinstance(condition, dict):
        return False

    op = condition.get("op")
    if op != "==":
        return False

    left = condition.get("left", {})
    right = condition.get("right", {})

    # Check if left is a tick field
    tick_fields = {"system_tick_in_day", "current_tick"}
    left_field = left.get("field", "") if isinstance(left, dict) else ""
    right_field = right.get("field", "") if isinstance(right, dict) else ""

    # Check if comparing tick field to 0
    def is_zero(val: Any) -> bool:
        if isinstance(val, (int, float)) and val == 0:
            return True
        if isinstance(val, dict):
            v = val.get("value")
            return v == 0 or v == 0.0
        return False

    if left_field in tick_fields and is_zero(right):
        return True
    if right_field in tick_fields and is_zero(left):
        return True

    return False


def validate_castro_policy(
    policy: dict[str, Any],
    strict: bool = True,
) -> ValidationResult:
    """Validate a complete policy for Castro paper alignment.

    This validates that a policy conforms to Castro et al. (2025) rules:
    1. Initial liquidity decision at t=0 only (strategic_collateral_tree guarded)
    2. No mid-day collateral changes (no WithdrawCollateral, no reactive tree)
    3. Payment actions are only Release/Hold (no Split, no ReleaseWithCredit)
    4. Bank tree is minimal (NoAction only)

    Args:
        policy: Complete policy dict with all trees
        strict: If True, enforce all Castro rules strictly

    Returns:
        ValidationResult with any Castro-specific violations
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Validate strategic_collateral_tree (initial liquidity at t=0 only)
    strategic_tree = policy.get("strategic_collateral_tree")
    if strategic_tree:
        is_valid, error_msg = _is_tick_zero_guarded_collateral_tree(strategic_tree)
        if not is_valid:
            if strict:
                errors.append(error_msg)
            else:
                warnings.append(error_msg)

    # 2. Check for forbidden collateral actions in strategic tree
    if strategic_tree:
        actions = _find_actions_in_tree(strategic_tree)
        for action, path in actions:
            if action in CASTRO_FORBIDDEN_COLLATERAL_ACTIONS:
                msg = (
                    f"Castro mode: {action} is not allowed. "
                    f"Found at path {' -> '.join(path)}. "
                    f"Castro model only allows PostCollateral at t=0 and HoldCollateral."
                )
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # 3. Reject end_of_tick_collateral_tree (no reactive collateral in Castro)
    eot_tree = policy.get("end_of_tick_collateral_tree")
    if eot_tree:
        # Check if it does anything other than HoldCollateral
        actions = _find_actions_in_tree(eot_tree)
        for action, path in actions:
            if action != "HoldCollateral":
                msg = (
                    f"Castro mode: end_of_tick_collateral_tree should not modify collateral. "
                    f"Found {action} at path {' -> '.join(path)}. "
                    f"Castro model has no reactive collateral changes."
                )
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # 4. Validate payment_tree uses only Release/Hold
    payment_tree = policy.get("payment_tree")
    if payment_tree:
        actions = _find_actions_in_tree(payment_tree)
        for action, path in actions:
            if action not in CASTRO_ALLOWED_PAYMENT_ACTIONS:
                msg = (
                    f"Castro mode: payment action '{action}' is not allowed. "
                    f"Found at path {' -> '.join(path)}. "
                    f"Only Release (x_t=1) and Hold (x_t=0) are valid in Castro model."
                )
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # 5. Validate bank_tree is minimal
    bank_tree = policy.get("bank_tree")
    if bank_tree:
        actions = _find_actions_in_tree(bank_tree)
        for action, path in actions:
            if action != "NoAction":
                msg = (
                    f"Castro mode: bank_tree action '{action}' is not allowed. "
                    f"Found at path {' -> '.join(path)}. "
                    f"Castro model does not have bank-level budgeting."
                )
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    if errors:
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
    else:
        result = ValidationResult.success()
        result.warnings = warnings
        return result


def validate_castro_collateral_tree(tree: dict[str, Any]) -> ValidationResult:
    """Validate a strategic_collateral_tree for Castro alignment.

    Convenience function that validates just the collateral tree.

    Args:
        tree: The strategic_collateral_tree dict

    Returns:
        ValidationResult
    """
    is_valid, error_msg = _is_tick_zero_guarded_collateral_tree(tree)
    if not is_valid:
        return ValidationResult.failure([error_msg])

    # Also check for forbidden actions
    errors: list[str] = []
    actions = _find_actions_in_tree(tree)
    for action, path in actions:
        if action in CASTRO_FORBIDDEN_COLLATERAL_ACTIONS:
            errors.append(
                f"Castro mode: {action} is not allowed at path {' -> '.join(path)}."
            )

    if errors:
        return ValidationResult.failure(errors)
    return ValidationResult.success()
