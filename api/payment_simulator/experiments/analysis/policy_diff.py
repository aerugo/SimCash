"""Policy diff calculator.

Computes human-readable diffs between policy dictionaries.
Used for showing how policies evolved across experiment iterations.

Example:
    >>> old = {"parameters": {"threshold": 100}}
    >>> new = {"parameters": {"threshold": 200}}
    >>> print(compute_policy_diff(old, new))
    Changed: parameters.threshold (100 -> 200)
"""

from __future__ import annotations

from typing import Any


def compute_policy_diff(
    old_policy: dict[str, Any] | None,
    new_policy: dict[str, Any],
) -> str:
    """Compute human-readable diff between two policies.

    Produces a text description of what changed between two policy versions.
    Used for the `diff` field in policy evolution output.

    Args:
        old_policy: Previous iteration's policy (None for first iteration).
        new_policy: Current iteration's policy.

    Returns:
        Human-readable diff summary. Empty string if policies are identical
        or if old_policy is None (first iteration).

    Example:
        >>> compute_policy_diff(
        ...     {"parameters": {"threshold": 100}},
        ...     {"parameters": {"threshold": 200}}
        ... )
        'Changed: parameters.threshold (100 -> 200)'
    """
    if old_policy is None:
        return ""

    changes = extract_parameter_changes(old_policy, new_policy)

    if not changes:
        return ""

    lines: list[str] = []

    for key, change in sorted(changes.items()):
        before = change.get("before")
        after = change.get("after")

        if before is None:
            # Field was added
            lines.append(f"Added: {key} = {_format_value(after)}")
        elif after is None:
            # Field was removed
            lines.append(f"Removed: {key}")
        else:
            # Field was changed
            lines.append(
                f"Changed: {key} ({_format_value(before)} -> {_format_value(after)})"
            )

    return "\n".join(lines)


def extract_parameter_changes(
    old_policy: dict[str, Any] | None,
    new_policy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract structured parameter changes.

    Returns a dictionary mapping changed parameter paths to their
    before/after values. Useful for programmatic analysis of changes.

    Args:
        old_policy: Previous iteration's policy (None for first iteration).
        new_policy: Current iteration's policy.

    Returns:
        Dict mapping parameter path (dot-notation) to change info:
        {
            "parameters.threshold": {
                "before": 100,
                "after": 200
            }
        }
        Returns empty dict if old_policy is None or policies are identical.

    Example:
        >>> extract_parameter_changes(
        ...     {"parameters": {"threshold": 100}},
        ...     {"parameters": {"threshold": 200}}
        ... )
        {'parameters.threshold': {'before': 100, 'after': 200}}
    """
    if old_policy is None:
        return {}

    old_flat = _flatten_dict(old_policy)
    new_flat = _flatten_dict(new_policy)

    changes: dict[str, dict[str, Any]] = {}

    # Find all keys (union of old and new)
    all_keys = set(old_flat.keys()) | set(new_flat.keys())

    for key in all_keys:
        old_value = old_flat.get(key)
        new_value = new_flat.get(key)

        if old_value != new_value:
            changes[key] = {
                "before": old_value,
                "after": new_value,
            }

    return changes


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dictionary with dot-separated keys.

    Recursively flattens a nested dictionary into a single-level dictionary
    with dot-separated keys for nested paths.

    Args:
        d: Dictionary to flatten.
        prefix: Current key prefix (for recursion).

    Returns:
        Flattened dictionary with dot-notation keys.

    Example:
        >>> _flatten_dict({"a": {"b": 1, "c": 2}})
        {'a.b': 1, 'a.c': 2}
    """
    result: dict[str, Any] = {}

    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            # Recurse into nested dict
            nested = _flatten_dict(value, full_key)
            result.update(nested)
        else:
            # Leaf value (including lists)
            result[full_key] = value

    return result


def _format_value(value: Any) -> str:
    """Format a value for human-readable display.

    Handles special formatting for:
    - Floats: Limit to 4 decimal places
    - Booleans: Show as True/False
    - Lists: Show abbreviated representation
    - None: Show as 'None'

    Args:
        value: Value to format.

    Returns:
        Human-readable string representation.
    """
    if value is None:
        return "None"
    if isinstance(value, float):
        # Format floats to reasonable precision
        return f"{value:.4g}"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        if len(value) > 3:
            # Abbreviate long lists
            return f"[{value[0]!r}, {value[1]!r}, ... ({len(value)} items)]"
        return repr(value)
    return str(value)
