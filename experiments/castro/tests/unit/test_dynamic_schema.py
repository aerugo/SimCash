"""Unit tests for dynamic Pydantic model generation.

TDD: These tests define the expected behavior for dynamic schema generation.
Run with: pytest experiments/castro/tests/unit/test_dynamic_schema.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestCreateParameterModel:
    """Tests for create_parameter_model - generates dynamic parameter schema."""

    def test_single_parameter_accepts_valid_value(self) -> None:
        """Generated model accepts value within bounds."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=0,
                    max_value=20,
                    default=5,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        params = ParamModel(threshold=10.0)
        assert params.threshold == 10.0

    def test_single_parameter_uses_default(self) -> None:
        """Generated model uses default when parameter not specified."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=0,
                    max_value=20,
                    default=5,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        params = ParamModel()
        assert params.threshold == 5.0

    def test_rejects_value_above_max(self) -> None:
        """Generated model rejects value above max_value."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=0,
                    max_value=20,
                    default=5,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        with pytest.raises(ValidationError):
            ParamModel(threshold=25.0)  # Above max

    def test_rejects_value_below_min(self) -> None:
        """Generated model rejects value below min_value."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=5,
                    max_value=20,
                    default=10,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        with pytest.raises(ValidationError):
            ParamModel(threshold=3.0)  # Below min

    def test_rejects_extra_parameters(self) -> None:
        """Generated model forbids undefined parameters."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold",
                    min_value=0,
                    max_value=20,
                    default=5,
                    description="A threshold",
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        with pytest.raises(ValidationError):
            ParamModel(threshold=5.0, invented_param=10.0)  # Extra param!

    def test_multiple_parameters(self) -> None:
        """Generated model handles multiple parameters."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
                ParameterSpec(
                    name="buffer", min_value=0.5, max_value=3.0, default=1.0, description="Buffer"
                ),
                ParameterSpec(
                    name="split_size", min_value=0.1, max_value=0.9, default=0.5, description="Split"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        params = ParamModel(urgency=5.0, buffer=2.0, split_size=0.3)
        assert params.urgency == 5.0
        assert params.buffer == 2.0
        assert params.split_size == 0.3

    def test_empty_parameters_returns_empty_model(self) -> None:
        """Generated model for empty parameters has no fields."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_parameter_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamModel = create_parameter_model(constraints)
        params = ParamModel()
        # Should have no parameter fields
        assert params.model_dump() == {}


class TestCreateContextFieldModel:
    """Tests for create_context_field_model - generates field reference schema."""

    def test_accepts_allowed_field(self) -> None:
        """Generated model accepts field in allowed list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_context_field_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "effective_liquidity", "ticks_to_deadline"],
            allowed_actions=["Release"],
        )

        FieldModel = create_context_field_model(constraints)
        field_ref = FieldModel(field="balance")
        assert field_ref.field == "balance"

    def test_rejects_disallowed_field(self) -> None:
        """Generated model rejects field not in allowed list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_context_field_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "effective_liquidity"],
            allowed_actions=["Release"],
        )

        FieldModel = create_context_field_model(constraints)
        with pytest.raises(ValidationError):
            FieldModel(field="queue1_total_value")  # Not in allowed list


class TestCreateParamRefModel:
    """Tests for create_param_ref_model - generates parameter reference schema."""

    def test_accepts_defined_param(self) -> None:
        """Generated model accepts defined parameter name."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_param_ref_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
                ParameterSpec(
                    name="buffer", min_value=0.5, max_value=3.0, default=1.0, description="Buffer"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamRefModel = create_param_ref_model(constraints)
        ref = ParamRefModel(param="threshold")
        assert ref.param == "threshold"

    def test_rejects_undefined_param(self) -> None:
        """Generated model rejects undefined parameter name."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_param_ref_model

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="threshold", min_value=0, max_value=20, default=5, description="Threshold"
                ),
            ],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        ParamRefModel = create_param_ref_model(constraints)
        with pytest.raises(ValidationError):
            ParamRefModel(param="undefined_param")

    def test_returns_none_for_no_params(self) -> None:
        """Returns None when no parameters defined."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_param_ref_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release"],
        )

        result = create_param_ref_model(constraints)
        assert result is None


class TestCreateActionModel:
    """Tests for create_action_model - generates action type schema."""

    def test_accepts_allowed_action(self) -> None:
        """Generated model accepts action in allowed list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_action_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold", "Split"],
        )

        ActionModel = create_action_model(constraints)
        action = ActionModel(action="Release")
        assert action.action == "Release"

    def test_rejects_disallowed_action(self) -> None:
        """Generated model rejects action not in allowed list."""
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_action_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold"],
        )

        ActionModel = create_action_model(constraints)
        with pytest.raises(ValidationError):
            ActionModel(action="Split")  # Not in allowed list


class TestCreateConstrainedPolicyModel:
    """Tests for create_constrained_policy_model - full policy model."""

    def test_accepts_valid_simple_policy(self) -> None:
        """Generated model accepts a valid simple policy."""
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
            ],
            allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        policy = PolicyModel(
            policy_id="test_policy",
            version="2.0",
            parameters={"urgency": 5.0},
            payment_tree={
                "type": "action",
                "action": "Release",
            },
        )
        assert policy.policy_id == "test_policy"
        assert policy.parameters["urgency"] == 5.0

    def test_accepts_policy_with_condition(self) -> None:
        """Generated model accepts policy with condition node."""
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
            ],
            allowed_fields=["ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        policy = PolicyModel(
            policy_id="conditional_policy",
            version="2.0",
            parameters={"urgency": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency"},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )
        assert policy.policy_id == "conditional_policy"

    def test_deep_field_validation_deferred_to_simcash(self) -> None:
        """Deep tree field validation is deferred to SimCash.

        Note: Dynamic Pydantic models enforce top-level constraints.
        Deep validation of field references in nested trees happens
        via SimCash's validate_policy() in Phase 3 integration tests.
        This is by design - SimCash is the source of truth for validation.
        """
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
            ],
            allowed_fields=["ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        # Model accepts this - SimCash validation catches invalid fields
        policy = PolicyModel(
            policy_id="policy_with_unvalidated_field",
            version="2.0",
            parameters={"urgency": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": ">=",
                    "left": {"field": "balance"},  # SimCash will validate
                    "right": {"value": 0},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )
        # Pydantic model accepts; SimCash validation catches in Phase 3
        assert policy.policy_id == "policy_with_unvalidated_field"

    def test_deep_param_validation_deferred_to_simcash(self) -> None:
        """Deep tree param validation is deferred to SimCash.

        Note: Dynamic Pydantic models enforce parameter value bounds.
        Deep validation of param references in nested trees happens
        via SimCash's validate_policy() in Phase 3 integration tests.
        """
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
            ],
            allowed_fields=["ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        # Model accepts - SimCash validation catches invalid param refs
        policy = PolicyModel(
            policy_id="policy_with_unvalidated_param",
            version="2.0",
            parameters={"urgency": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "undefined_param"},  # SimCash will catch
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )
        assert policy.policy_id == "policy_with_unvalidated_param"

    def test_deep_action_validation_deferred_to_simcash(self) -> None:
        """Deep tree action validation is deferred to SimCash.

        Note: Dynamic Pydantic models enforce top-level structure.
        Deep validation of actions in nested trees happens
        via SimCash's validate_policy() in Phase 3 integration tests.
        """
        from experiments.castro.schemas.parameter_config import ScenarioConstraints
        from experiments.castro.schemas.dynamic import create_constrained_policy_model

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        # Model accepts - SimCash validation catches invalid actions
        policy = PolicyModel(
            policy_id="policy_with_unvalidated_action",
            version="2.0",
            parameters={},
            payment_tree={
                "type": "action",
                "action": "Split",  # SimCash will validate this
            },
        )
        assert policy.policy_id == "policy_with_unvalidated_action"

    def test_json_serialization(self) -> None:
        """Generated policy model serializes to valid JSON."""
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec,
            ScenarioConstraints,
        )
        from experiments.castro.schemas.dynamic import create_constrained_policy_model
        import json

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(
                    name="urgency", min_value=0, max_value=20, default=3, description="Urgency"
                ),
            ],
            allowed_fields=["ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        PolicyModel = create_constrained_policy_model(constraints)

        policy = PolicyModel(
            policy_id="test",
            version="2.0",
            parameters={"urgency": 5.0},
            payment_tree={"type": "action", "action": "Release"},
        )

        # Should serialize without error
        json_str = policy.model_dump_json()
        data = json.loads(json_str)
        assert data["policy_id"] == "test"
        assert data["parameters"]["urgency"] == 5.0
