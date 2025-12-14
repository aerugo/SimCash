"""Policy diff calculator for evolution tracking.

Computes human-readable diffs between consecutive policy iterations
to show what changed during optimization.
"""

from __future__ import annotations

from typing import Any


def compute_policy_diff(
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> str:
    """Compute human-readable diff between two policies.

    Returns a summary of what changed:
    - Parameter changes (with before/after values)
    - Tree structure changes (payment_tree, collateral_tree)

    Args:
        old_policy: Previous iteration's policy.
        new_policy: Current iteration's policy.

    Returns:
        Human-readable diff summary string. Empty string if identical.

    Example:
        >>> old = {"parameters": {"threshold": 100}}
        >>> new = {"parameters": {"threshold": 200}}
        >>> diff = compute_policy_diff(old, new)
        >>> "threshold" in diff
        True
    """
    changes = extract_parameter_changes(old_policy, new_policy)

    if not changes:
        return ""

    lines: list[str] = []
    for path, change in sorted(changes.items()):
        before = change.get("before")
        after = change.get("after")
        change_type = change.get("type", "changed")

        if change_type == "added":
            lines.append(f"+ {path}: {_format_value(after)}")
        elif change_type == "removed":
            lines.append(f"- {path}: {_format_value(before)}")
        else:
            lines.append(f"~ {path}: {_format_value(before)} -> {_format_value(after)}")

    return "\n".join(lines)


def extract_parameter_changes(
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract structured parameter changes between policies.

    Recursively compares policy dicts and returns all differences.

    Args:
        old_policy: Previous iteration's policy.
        new_policy: Current iteration's policy.

    Returns:
        Dict mapping dotted paths to change info:
        {
            "parameters.threshold": {
                "before": 100,
                "after": 200,
                "type": "changed"
            },
            "payment_tree.on_true.action": {
                "before": None,
                "after": "Submit",
                "type": "added"
            }
        }

    Example:
        >>> old = {"parameters": {"threshold": 100}}
        >>> new = {"parameters": {"threshold": 200}}
        >>> changes = extract_parameter_changes(old, new)
        >>> changes["parameters.threshold"]["before"]
        100
        >>> changes["parameters.threshold"]["after"]
        200
    """
    changes: dict[str, dict[str, Any]] = {}
    _compare_recursive(old_policy, new_policy, "", changes)
    return changes


def _compare_recursive(
    old: Any,
    new: Any,
    path: str,
    changes: dict[str, dict[str, Any]],
) -> None:
    """Recursively compare two values and record differences.

    Args:
        old: Old value (or None if added).
        new: New value (or None if removed).
        path: Current dotted path (e.g., "parameters.threshold").
        changes: Dict to accumulate changes into.
    """
    # Skip internal fields that shouldn't be compared
    skip_fields = {"policy_id", "version"}

    if old == new:
        return

    # Handle None cases (added/removed)
    if old is None:
        changes[path] = {"before": None, "after": new, "type": "added"}
        return
    if new is None:
        changes[path] = {"before": old, "after": None, "type": "removed"}
        return

    # Both are dicts - recurse
    if isinstance(old, dict) and isinstance(new, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            if key in skip_fields:
                continue
            new_path = f"{path}.{key}" if path else key
            old_val = old.get(key)
            new_val = new.get(key)
            _compare_recursive(old_val, new_val, new_path, changes)
        return

    # Both are lists - compare element-wise
    if isinstance(old, list) and isinstance(new, list):
        max_len = max(len(old), len(new))
        for i in range(max_len):
            new_path = f"{path}[{i}]"
            old_val = old[i] if i < len(old) else None
            new_val = new[i] if i < len(new) else None
            _compare_recursive(old_val, new_val, new_path, changes)
        return

    # Primitive values that differ
    changes[path] = {"before": old, "after": new, "type": "changed"}


def _format_value(value: Any) -> str:
    """Format a value for display in diff output.

    Args:
        value: Value to format.

    Returns:
        String representation suitable for diff display.
    """
    if value is None:
        return "(none)"
    if isinstance(value, str):
        # Truncate long strings
        if len(value) > 50:
            return f'"{value[:47]}..."'
        return f'"{value}"'
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, dict):
        return "{...}"
    if isinstance(value, list):
        return f"[{len(value)} items]"
    return str(value)
