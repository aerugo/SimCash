"""Policy validation with scenario feature toggle support.

This module provides the core validation function that checks if a policy
is valid for a given scenario's feature toggles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from payment_simulator.backends import validate_policy as rust_validate_policy
from payment_simulator.config import load_config
from payment_simulator.config.schemas import SimulationConfig
from payment_simulator.policy.analysis import extract_categories_from_policy


@dataclass
class PolicyValidationResult:
    """Result of policy validation.

    Attributes:
        valid: Whether the policy passed validation.
        policy_id: The policy ID from the JSON.
        version: The policy version from the JSON.
        description: The policy description from the JSON.
        errors: List of validation errors (each with type and message).
        forbidden_categories: List of categories that are forbidden by scenario.
        forbidden_elements: List of specific elements using forbidden categories.
    """

    valid: bool
    policy_id: str | None = None
    version: str | None = None
    description: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    forbidden_categories: list[str] = field(default_factory=list)
    forbidden_elements: list[str] = field(default_factory=list)


def validate_policy_for_scenario(
    policy_json: str,
    scenario_path: Path | None = None,
    scenario_config: SimulationConfig | None = None,
) -> PolicyValidationResult:
    """Validate a policy against scenario feature toggles.

    This function performs two-stage validation:
    1. Base policy validation using the Rust validator
    2. If scenario provided, checks policy doesn't use forbidden categories

    Args:
        policy_json: The policy JSON content as a string.
        scenario_path: Path to scenario YAML file (will be loaded).
        scenario_config: Pre-loaded scenario config (takes precedence).

    Returns:
        PolicyValidationResult with validation outcome.

    Note:
        If neither scenario_path nor scenario_config provided,
        only performs base policy validation (no toggle checks).
    """
    # Stage 1: Rust validation
    try:
        rust_result_json = rust_validate_policy(policy_json)
        rust_result = json.loads(rust_result_json)
    except Exception as e:
        return PolicyValidationResult(
            valid=False,
            errors=[{"type": "ParseError", "message": str(e)}],
        )

    # If Rust validation failed, return those errors
    if not rust_result.get("valid", False):
        return PolicyValidationResult(
            valid=False,
            policy_id=rust_result.get("policy_id"),
            version=rust_result.get("version"),
            description=rust_result.get("description"),
            errors=rust_result.get("errors", []),
        )

    # Extract policy metadata
    policy_id = rust_result.get("policy_id")
    version = rust_result.get("version")
    description = rust_result.get("description")

    # Stage 2: Load scenario config if needed
    config: SimulationConfig | None = scenario_config
    if config is None and scenario_path is not None:
        try:
            config = load_config(str(scenario_path))
        except Exception as e:
            return PolicyValidationResult(
                valid=False,
                policy_id=policy_id,
                version=version,
                description=description,
                errors=[{"type": "ScenarioLoadError", "message": str(e)}],
            )

    # If no scenario or no feature toggles, policy is valid
    if config is None or config.policy_feature_toggles is None:
        return PolicyValidationResult(
            valid=True,
            policy_id=policy_id,
            version=version,
            description=description,
        )

    # Stage 3: Check against feature toggles
    try:
        categories_used = extract_categories_from_policy(policy_json)
    except ValueError as e:
        return PolicyValidationResult(
            valid=False,
            policy_id=policy_id,
            version=version,
            description=description,
            errors=[{"type": "CategoryExtractionError", "message": str(e)}],
        )

    toggles = config.policy_feature_toggles
    forbidden_used = []

    for category in categories_used:
        if not toggles.is_category_allowed(category):
            forbidden_used.append(category)

    if forbidden_used:
        error_message = (
            f"Policy uses forbidden categories: {', '.join(sorted(forbidden_used))}. "
        )
        if toggles.include is not None:
            error_message += f"Allowed categories: {', '.join(sorted(toggles.include))}."
        else:
            error_message += (
                f"Excluded categories: {', '.join(sorted(toggles.exclude or []))}."
            )

        return PolicyValidationResult(
            valid=False,
            policy_id=policy_id,
            version=version,
            description=description,
            errors=[{"type": "ForbiddenCategory", "message": error_message}],
            forbidden_categories=sorted(forbidden_used),
        )

    return PolicyValidationResult(
        valid=True,
        policy_id=policy_id,
        version=version,
        description=description,
    )
