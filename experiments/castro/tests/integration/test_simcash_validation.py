"""Integration tests for SimCash policy validation.

These tests verify that policies generated from dynamic models pass
SimCash's validate_policy() function.

Run with: pytest experiments/castro/tests/integration/test_simcash_validation.py -v

Note: Requires the Rust backend to be built. Tests will skip if unavailable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add API path for imports
API_PATH = Path(__file__).parent.parent.parent.parent.parent / "api"
sys.path.insert(0, str(API_PATH))

# Check if Rust backend is available
try:
    from payment_simulator.backends import validate_policy

    RUST_BACKEND_AVAILABLE = True
except ImportError:
    RUST_BACKEND_AVAILABLE = False
    validate_policy = None  # type: ignore

requires_rust_backend = pytest.mark.skipif(
    not RUST_BACKEND_AVAILABLE,
    reason="Rust backend not available",
)


class TestGeneratedPolicyValidation:
    """Tests that dynamically generated policies pass SimCash validation."""

    @requires_rust_backend
    def test_simple_action_policy_validates(self) -> None:
        """Simple action-only policy passes SimCash validation."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        PolicyModel = create_constrained_policy_model(constraints)
        policy = PolicyModel(
            policy_id="simple_action",
            version="2.0",
            parameters={},
            payment_tree={"type": "action", "action": "Release"},
        )

        # Validate with SimCash
        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        assert result["valid"] is True, f"Validation failed: {result.get('errors')}"

    @requires_rust_backend
    def test_conditional_policy_validates(self) -> None:
        """Conditional policy with parameters passes SimCash validation."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency_threshold",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Urgency threshold",
                ),
            ],
            allowed_fields=["ticks_to_deadline", "effective_liquidity", "remaining_amount"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)
        policy = PolicyModel(
            policy_id="conditional_policy",
            version="2.0",
            parameters={"urgency_threshold": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency_threshold"},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )

        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        assert result["valid"] is True, f"Validation failed: {result.get('errors')}"

    @requires_rust_backend
    def test_nested_conditions_validate(self) -> None:
        """Nested conditional policy passes SimCash validation."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
                ParameterSpec(
                    name="buffer", min_value=0.5, max_value=3.0, default=1.0, description="Buffer"
                ),
            ],
            allowed_fields=["ticks_to_deadline", "effective_liquidity", "remaining_amount"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)
        policy = PolicyModel(
            policy_id="nested_policy",
            version="2.0",
            parameters={"urgency": 5.0, "buffer": 1.5},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency"},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {
                    "type": "condition",
                    "condition": {
                        "op": ">=",
                        "left": {"field": "effective_liquidity"},
                        "right": {
                            "compute": {
                                "op": "*",
                                "left": {"field": "remaining_amount"},
                                "right": {"param": "buffer"},
                            }
                        },
                    },
                    "on_true": {"type": "action", "action": "Release"},
                    "on_false": {"type": "action", "action": "Hold"},
                },
            },
        )

        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        assert result["valid"] is True, f"Validation failed: {result.get('errors')}"

    @requires_rust_backend
    def test_policy_with_many_parameters_validates(self) -> None:
        """Policy with many parameters passes SimCash validation."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency_threshold",
                    min_value=0,
                    max_value=20,
                    default=3,
                    description="Urgency",
                ),
                ParameterSpec(
                    name="liquidity_buffer",
                    min_value=0.5,
                    max_value=3.0,
                    default=1.0,
                    description="Buffer",
                ),
                ParameterSpec(
                    name="split_threshold",
                    min_value=0.1,
                    max_value=0.9,
                    default=0.5,
                    description="Split",
                ),
                ParameterSpec(
                    name="eod_boost",
                    min_value=0,
                    max_value=10,
                    default=2,
                    description="EOD boost",
                ),
            ],
            allowed_fields=["ticks_to_deadline", "balance"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)
        policy = PolicyModel(
            policy_id="multi_param_policy",
            version="2.0",
            parameters={
                "urgency_threshold": 5.0,
                "liquidity_buffer": 1.5,
                "split_threshold": 0.3,
                "eod_boost": 3.0,
            },
            payment_tree={"type": "action", "action": "Release"},
        )

        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        assert result["valid"] is True, f"Validation failed: {result.get('errors')}"


class TestInvalidPolicyDetection:
    """Tests that SimCash catches invalid policies that dynamic models allow."""

    @requires_rust_backend
    def test_invalid_field_caught_by_simcash(self) -> None:
        """SimCash catches invalid field references."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        # Create model with limited fields
        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],  # Limited
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        # Create policy with invalid field (not caught by Pydantic)
        policy = PolicyModel(
            policy_id="invalid_field_policy",
            version="2.0",
            parameters={},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": ">=",
                    "left": {"field": "invented_field_xyz"},  # Invalid!
                    "right": {"value": 0},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )

        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        # SimCash should catch this
        assert result["valid"] is False
        assert any("InvalidFieldReference" in str(e) for e in result.get("errors", []))

    @requires_rust_backend
    def test_undefined_param_caught_by_simcash(self) -> None:
        """SimCash catches undefined parameter references."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
            ],
            allowed_fields=["ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        # Create policy with undefined param (not caught by Pydantic)
        policy = PolicyModel(
            policy_id="invalid_param_policy",
            version="2.0",
            parameters={"threshold": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "nonexistent_param"},  # Invalid!
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )

        policy_json = json.dumps(policy.model_dump())
        result = json.loads(validate_policy(policy_json))

        # SimCash should catch this
        assert result["valid"] is False
        assert any("InvalidParameterReference" in str(e) for e in result.get("errors", []))


class TestAllRegistryFieldsValid:
    """Tests that all registry fields are valid in SimCash."""

    @requires_rust_backend
    def test_all_payment_tree_fields_valid(self) -> None:
        """All payment tree fields from registry pass SimCash validation."""
        from experiments.castro.schemas.registry import PAYMENT_TREE_FIELDS
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        # Test a subset of critical fields
        test_fields = [
            "balance",
            "effective_liquidity",
            "ticks_to_deadline",
            "remaining_amount",
            "queue1_total_value",
            "current_tick",
        ]

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=test_fields,
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        for field in test_fields:
            policy = PolicyModel(
                policy_id=f"test_{field}",
                version="2.0",
                parameters={},
                payment_tree={
                    "type": "condition",
                    "condition": {
                        "op": ">=",
                        "left": {"field": field},
                        "right": {"value": 0},
                    },
                    "on_true": {"type": "action", "action": "Release"},
                    "on_false": {"type": "action", "action": "Hold"},
                },
            )

            policy_json = json.dumps(policy.model_dump())
            result = json.loads(validate_policy(policy_json))

            assert result["valid"] is True, f"Field '{field}' failed validation: {result.get('errors')}"
