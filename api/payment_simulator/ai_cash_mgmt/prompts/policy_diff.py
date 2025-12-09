"""Policy diff computation utilities.

This module provides functions for computing human-readable differences
between policies and tracking parameter evolution across iterations.

Functions:
    compute_policy_diff: Compute differences between two policies
    compute_parameter_trajectory: Extract parameter values across iterations
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.prompts.context_types import (
        SingleAgentIterationRecord,
    )


def compute_policy_diff(
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> list[str]:
    """Compute human-readable differences between two policies.

    Analyzes parameters, payment trees, and collateral trees to produce
    a list of change descriptions that help the LLM understand what
    changed between iterations.

    Args:
        old_policy: The previous policy.
        new_policy: The new policy to compare.

    Returns:
        List of human-readable change descriptions.

    Example:
        >>> old = {"parameters": {"threshold": 5.0}}
        >>> new = {"parameters": {"threshold": 3.0}}
        >>> diff = compute_policy_diff(old, new)
        >>> print(diff[0])
        "Changed 'threshold': 5.0 → 3.0 (↓2.00)"
    """
    changes: list[str] = []

    # Compare parameters
    old_params = old_policy.get("parameters", {})
    new_params = new_policy.get("parameters", {})

    # Added parameters
    for key in set(new_params.keys()) - set(old_params.keys()):
        changes.append(f"Added parameter '{key}' = {new_params[key]}")

    # Removed parameters
    for key in set(old_params.keys()) - set(new_params.keys()):
        changes.append(f"Removed parameter '{key}' (was {old_params[key]})")

    # Changed parameters
    for key in set(old_params.keys()) & set(new_params.keys()):
        if old_params[key] != new_params[key]:
            old_val = old_params[key]
            new_val = new_params[key]

            # Calculate delta for numeric values
            try:
                delta = float(new_val) - float(old_val)
                direction = "↑" if delta > 0 else "↓"
                changes.append(
                    f"Changed '{key}': {old_val} → {new_val} ({direction}{abs(delta):.2f})"
                )
            except (TypeError, ValueError):
                # Non-numeric values - just show the change
                changes.append(f"Changed '{key}': {old_val} → {new_val}")

    # Compare tree structure (simplified - check if trees are different)
    old_tree = json.dumps(old_policy.get("payment_tree", {}), sort_keys=True)
    new_tree = json.dumps(new_policy.get("payment_tree", {}), sort_keys=True)
    if old_tree != new_tree:
        changes.append("Modified payment_tree structure")

    # Compare collateral tree if present
    old_coll = json.dumps(
        old_policy.get("strategic_collateral_tree", {}), sort_keys=True
    )
    new_coll = json.dumps(
        new_policy.get("strategic_collateral_tree", {}), sort_keys=True
    )
    if old_coll != new_coll:
        changes.append("Modified strategic_collateral_tree structure")

    if not changes:
        changes.append("No changes from previous iteration")

    return changes


def compute_parameter_trajectory(
    history: list[SingleAgentIterationRecord],
    param_name: str,
) -> list[tuple[int, float]]:
    """Extract the trajectory of a parameter value across iterations.

    Scans through iteration history and extracts the value of a specific
    parameter at each iteration where it was present.

    Args:
        history: List of iteration records.
        param_name: Name of the parameter to track.

    Returns:
        List of (iteration, value) tuples in list order.

    Example:
        >>> trajectory = compute_parameter_trajectory(history, "threshold")
        >>> print(trajectory)
        [(1, 5.0), (2, 4.5), (3, 4.0)]
    """
    trajectory: list[tuple[int, float]] = []

    for record in history:
        params = record.policy.get("parameters", {})
        if param_name in params:
            trajectory.append((record.iteration, params[param_name]))

    return trajectory
