"""Unit tests for dynamic schema generation.

TDD: These tests are written BEFORE implementation.

The PolicySchemaGenerator dynamically generates Pydantic schemas based on:
- Tree type (payment_tree, bank_tree, collateral trees)
- Feature toggles (include/exclude categories)
- Max depth setting

Run with: pytest experiments/castro/tests/unit/test_schema_generator.py -v
"""

from __future__ import annotations

import pytest


class TestFieldRegistry:
    """Tests for field registry by tree type."""

    def test_payment_tree_has_transaction_fields(self) -> None:
        """Payment tree should have transaction-specific fields."""
        from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE

        fields = FIELDS_BY_TREE_TYPE["payment_tree"]
        assert "amount" in fields
        assert "remaining_amount" in fields
        assert "ticks_to_deadline" in fields
        assert "priority" in fields

    def test_payment_tree_has_agent_fields(self) -> None:
        """Payment tree should have agent fields too."""
        from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE

        fields = FIELDS_BY_TREE_TYPE["payment_tree"]
        assert "balance" in fields
        assert "effective_liquidity" in fields
        assert "credit_headroom" in fields

    def test_bank_tree_no_transaction_fields(self) -> None:
        """Bank tree should NOT have transaction-specific fields."""
        from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE

        fields = FIELDS_BY_TREE_TYPE["bank_tree"]
        assert "amount" not in fields
        assert "remaining_amount" not in fields
        assert "ticks_to_deadline" not in fields

    def test_bank_tree_has_agent_fields(self) -> None:
        """Bank tree should have agent-level fields."""
        from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE

        fields = FIELDS_BY_TREE_TYPE["bank_tree"]
        assert "balance" in fields
        assert "effective_liquidity" in fields
        assert "queue1_total_value" in fields

    def test_collateral_tree_has_collateral_fields(self) -> None:
        """Collateral trees should have collateral-specific fields."""
        from experiments.castro.schemas.registry import FIELDS_BY_TREE_TYPE

        fields = FIELDS_BY_TREE_TYPE["strategic_collateral_tree"]
        assert "posted_collateral" in fields
        assert "max_collateral_capacity" in fields
        assert "remaining_collateral_capacity" in fields

    def test_field_categories_defined(self) -> None:
        """Field categories should be defined for toggle filtering."""
        from experiments.castro.schemas.registry import FIELD_CATEGORIES

        # Check some key field categorizations
        assert FIELD_CATEGORIES["amount"] == "TransactionField"
        assert FIELD_CATEGORIES["balance"] == "AgentField"
        assert FIELD_CATEGORIES["posted_collateral"] == "CollateralField"
        assert FIELD_CATEGORIES["current_tick"] == "TimeField"


class TestPolicySchemaGenerator:
    """Tests for PolicySchemaGenerator class."""

    def test_generator_initialization(self) -> None:
        """Generator initializes with tree type and toggles."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        toggles = PolicyFeatureToggles()
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
            max_depth=3,
        )
        assert gen.tree_type == "payment_tree"
        assert gen.max_depth == 3

    def test_get_allowed_actions_for_payment_tree(self) -> None:
        """Get actions allowed for payment tree."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        actions = gen.get_allowed_actions()
        assert "Release" in actions
        assert "Hold" in actions
        assert "Split" in actions
        # Bank/collateral actions should not be included
        assert "PostCollateral" not in actions
        assert "SetState" not in actions

    def test_get_allowed_actions_for_collateral_tree(self) -> None:
        """Get actions allowed for collateral tree."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="strategic_collateral_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        actions = gen.get_allowed_actions()
        assert "PostCollateral" in actions
        assert "WithdrawCollateral" in actions
        assert "HoldCollateral" in actions
        # Payment actions should not be included
        assert "Release" not in actions

    def test_get_allowed_actions_with_exclude_toggle(self) -> None:
        """Feature toggle exclusions filter actions."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        # Exclude PaymentAction category - but we're on payment tree
        # so this would exclude all actions
        toggles = PolicyFeatureToggles(exclude=["PaymentAction"])
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
        )
        actions = gen.get_allowed_actions()
        # All payment actions should be excluded
        assert "Release" not in actions
        assert "Hold" not in actions

    def test_get_allowed_fields_for_payment_tree(self) -> None:
        """Get fields allowed for payment tree."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        fields = gen.get_allowed_fields()
        # Transaction fields available
        assert "amount" in fields
        assert "ticks_to_deadline" in fields
        # Agent fields also available
        assert "balance" in fields
        assert "effective_liquidity" in fields

    def test_get_allowed_fields_for_bank_tree(self) -> None:
        """Get fields allowed for bank tree (no transaction fields)."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="bank_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        fields = gen.get_allowed_fields()
        # Transaction fields NOT available
        assert "amount" not in fields
        assert "ticks_to_deadline" not in fields
        # Agent fields available
        assert "balance" in fields
        assert "queue1_total_value" in fields

    def test_get_allowed_fields_with_include_toggle(self) -> None:
        """Feature toggle inclusions filter fields."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        # Only include TransactionField and TimeField
        toggles = PolicyFeatureToggles(include=["TransactionField", "TimeField"])
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
        )
        fields = gen.get_allowed_fields()
        # Transaction fields included
        assert "amount" in fields
        # Time fields included
        assert "current_tick" in fields
        # Agent fields NOT included
        assert "balance" not in fields

    def test_get_allowed_fields_with_exclude_toggle(self) -> None:
        """Feature toggle exclusions filter fields."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        # Exclude CollateralField category
        toggles = PolicyFeatureToggles(exclude=["CollateralField"])
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
        )
        fields = gen.get_allowed_fields()
        # Collateral fields should be excluded
        assert "posted_collateral" not in fields
        assert "max_collateral_capacity" not in fields
        # Other fields still available
        assert "balance" in fields
        assert "amount" in fields


class TestSchemaBuilding:
    """Tests for building actual Pydantic schemas."""

    def test_build_schema_returns_type_adapter_compatible(self) -> None:
        """Generated schema can be used with TypeAdapter for validation."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from pydantic import TypeAdapter

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )
        TreeType = gen.build_tree_model()
        # Should work with TypeAdapter
        adapter = TypeAdapter(TreeType)
        assert adapter is not None

    def test_built_schema_accepts_valid_action(self) -> None:
        """Generated schema validates valid action nodes."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from pydantic import TypeAdapter

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )
        TreeType = gen.build_tree_model()
        adapter = TypeAdapter(TreeType)

        # Valid action should pass
        valid_action = {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }
        parsed = adapter.validate_python(valid_action)
        assert parsed.action == "Release"

    def test_built_schema_accepts_valid_condition(self) -> None:
        """Generated schema validates valid condition nodes."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from pydantic import TypeAdapter

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )
        TreeType = gen.build_tree_model()
        adapter = TypeAdapter(TreeType)

        # Valid condition with nested action
        valid_condition = {
            "type": "condition",
            "condition": {
                "op": ">=",
                "left": {"field": "balance"},
                "right": {"value": 0},
            },
            "on_true": {"type": "action", "action": "Release", "parameters": {}},
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }
        parsed = adapter.validate_python(valid_condition)
        assert parsed.type == "condition"

    def test_max_depth_limits_nesting(self) -> None:
        """Max depth setting limits allowed nesting."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles
        from experiments.castro.schemas.tree import get_tree_model

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )
        Model = gen.build_tree_model()
        # Model should be TreeNodeL2
        expected = get_tree_model(2)
        assert Model == expected


class TestSchemaMetadata:
    """Tests for schema metadata and documentation."""

    def test_get_allowed_actions_as_list(self) -> None:
        """Actions returned as list for prompt building."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        actions = gen.get_allowed_actions()
        assert isinstance(actions, list)
        assert len(actions) > 0

    def test_get_allowed_fields_as_list(self) -> None:
        """Fields returned as list for prompt building."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )
        fields = gen.get_allowed_fields()
        assert isinstance(fields, list)
        assert len(fields) > 0

    def test_get_schema_summary(self) -> None:
        """Get human-readable schema summary for prompts."""
        from experiments.castro.schemas.generator import PolicySchemaGenerator
        from experiments.castro.schemas.toggles import PolicyFeatureToggles

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )
        summary = gen.get_schema_summary()
        assert "payment_tree" in summary
        assert "Release" in summary or "actions" in summary.lower()
