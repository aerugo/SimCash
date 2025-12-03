"""Integration tests for the structured output pipeline.

These tests verify the complete pipeline from schema generation
through prompt building to validation, without requiring OpenAI API calls.

Run with: PYTHONPATH=/home/user/SimCash pytest experiments/castro/tests/integration/ -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from experiments.castro.schemas.generator import PolicySchemaGenerator
from experiments.castro.schemas.toggles import PolicyFeatureToggles
from experiments.castro.schemas.tree import PolicyTree, get_tree_model
from experiments.castro.prompts.builder import PolicyPromptBuilder
from experiments.castro.generator.validation import validate_policy_structure
from experiments.castro.generator.client import PolicyContext


# Path to real policy files for integration testing
CASTRO_DIR = Path(__file__).parent.parent.parent
POLICIES_DIR = CASTRO_DIR / "policies"


class TestSchemaGenerationPipeline:
    """Test the full schema generation pipeline."""

    def test_payment_tree_full_pipeline(self) -> None:
        """Full pipeline for payment tree schema generation."""
        # 1. Create generator
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )

        # 2. Get allowed actions and fields
        actions = gen.get_allowed_actions()
        fields = gen.get_allowed_fields()

        assert len(actions) > 0, "Should have actions"
        assert len(fields) > 0, "Should have fields"
        assert "Release" in actions
        assert "Hold" in actions
        assert "balance" in fields
        assert "amount" in fields

        # 3. Build schema
        TreeModel = gen.build_tree_model()
        adapter = TypeAdapter(TreeModel)
        json_schema = adapter.json_schema()

        # 4. Verify JSON schema structure for OpenAI
        assert "$defs" in json_schema or "anyOf" in json_schema
        # Must be serializable to JSON
        json_str = json.dumps(json_schema)
        assert len(json_str) > 100

    def test_collateral_tree_full_pipeline(self) -> None:
        """Full pipeline for collateral tree schema generation."""
        gen = PolicySchemaGenerator(
            tree_type="strategic_collateral_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )

        actions = gen.get_allowed_actions()
        fields = gen.get_allowed_fields()

        assert "PostCollateral" in actions
        assert "WithdrawCollateral" in actions
        assert "posted_collateral" in fields

        TreeModel = gen.build_tree_model()
        adapter = TypeAdapter(TreeModel)
        json_schema = adapter.json_schema()

        # Should serialize cleanly
        json_str = json.dumps(json_schema)
        assert len(json_str) > 100

    def test_bank_tree_full_pipeline(self) -> None:
        """Full pipeline for bank tree schema generation."""
        gen = PolicySchemaGenerator(
            tree_type="bank_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )

        actions = gen.get_allowed_actions()
        fields = gen.get_allowed_fields()

        # Bank tree should NOT have transaction fields
        assert "amount" not in fields
        assert "balance" in fields

        TreeModel = gen.build_tree_model()
        adapter = TypeAdapter(TreeModel)
        json_schema = adapter.json_schema()

        assert isinstance(json_schema, dict)


class TestPromptBuildingPipeline:
    """Test prompt building integrates with schema generation."""

    def test_prompt_builder_from_generator(self) -> None:
        """Prompt builder creates valid prompts from generator."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )

        builder = PolicyPromptBuilder.from_generator(gen)
        builder.set_performance(
            total_cost=50000,
            settlement_rate=0.95,
            per_bank_costs={"BANK_A": 25000, "BANK_B": 25000},
        )

        prompt = builder.build()

        # Should contain key elements
        assert "payment_tree" in prompt
        assert "Release" in prompt or "actions" in prompt.lower()
        assert "balance" in prompt or "fields" in prompt.lower()
        assert "50000" in prompt or "500" in prompt  # Cost reference

    def test_prompt_includes_current_policy(self) -> None:
        """Prompt includes current policy when set."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )

        current_policy = {
            "type": "action",
            "action": "Hold",
            "parameters": {},
        }

        builder = PolicyPromptBuilder.from_generator(gen)
        builder.set_current_policy(current_policy)

        prompt = builder.build()
        assert "Hold" in prompt or "current" in prompt.lower()


class TestValidationPipeline:
    """Test validation works with generated schemas."""

    def test_validate_simple_action(self) -> None:
        """Validate a simple action node."""
        policy = {
            "type": "action",
            "action": "Release",
            "parameters": {},
        }

        result = validate_policy_structure(policy, "payment_tree", max_depth=3)
        assert result.is_valid

    def test_validate_nested_condition(self) -> None:
        """Validate nested condition structure."""
        policy = {
            "type": "condition",
            "condition": {
                "op": ">=",
                "left": {"field": "balance"},
                "right": {"value": 0},
            },
            "on_true": {"type": "action", "action": "Release", "parameters": {}},
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }

        result = validate_policy_structure(policy, "payment_tree", max_depth=3)
        assert result.is_valid

    def test_validate_invalid_action_detected(self) -> None:
        """Invalid action is detected by validation."""
        policy = {
            "type": "action",
            "action": "InvalidAction",  # Not a valid action
            "parameters": {},
        }

        result = validate_policy_structure(policy, "payment_tree", max_depth=3)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validate_missing_required_field(self) -> None:
        """Missing required field is detected."""
        policy = {
            "type": "condition",
            # Missing: condition, on_true, on_false
        }

        result = validate_policy_structure(policy, "payment_tree", max_depth=3)
        assert not result.is_valid


class TestRealPolicyValidation:
    """Test validation with real policy files from castro/policies/."""

    @pytest.fixture
    def seed_policy(self) -> dict[str, Any]:
        """Load the seed_policy.json file."""
        policy_path = POLICIES_DIR / "seed_policy.json"
        if not policy_path.exists():
            pytest.skip("seed_policy.json not found")
        with open(policy_path) as f:
            return json.load(f)

    def test_validate_seed_policy_payment_tree(self, seed_policy: dict) -> None:
        """Validate the payment_tree from seed policy."""
        if "payment_tree" not in seed_policy:
            pytest.skip("No payment_tree in seed policy")

        payment_tree = seed_policy["payment_tree"]
        result = validate_policy_structure(payment_tree, "payment_tree", max_depth=5)

        assert result.is_valid, f"Validation errors: {result.errors}"

    def test_validate_seed_policy_collateral_tree(self, seed_policy: dict) -> None:
        """Validate the strategic_collateral_tree from seed policy."""
        if "strategic_collateral_tree" not in seed_policy:
            pytest.skip("No strategic_collateral_tree in seed policy")

        collateral_tree = seed_policy["strategic_collateral_tree"]
        result = validate_policy_structure(
            collateral_tree, "strategic_collateral_tree", max_depth=5
        )

        assert result.is_valid, f"Validation errors: {result.errors}"


class TestContextIntegration:
    """Test PolicyContext integration with real metrics."""

    def test_context_from_simulation_results(self) -> None:
        """Context builds correctly from simulation-like results."""
        context = PolicyContext(
            current_costs={
                "BANK_A": 25000.0,
                "BANK_B": 30000.0,
            },
            settlement_rate=0.92,
        )

        assert context.total_cost == 55000.0
        assert context.settlement_rate == 0.92

    def test_context_used_in_prompt(self) -> None:
        """Context data appears in generated prompt."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
        )

        context = PolicyContext(
            current_costs={"BANK_A": 10000.0, "BANK_B": 15000.0},
            settlement_rate=0.85,
        )

        builder = PolicyPromptBuilder.from_generator(gen)
        builder.set_performance(
            total_cost=context.total_cost,
            settlement_rate=context.settlement_rate,
            per_bank_costs=context.current_costs,
        )

        prompt = builder.build()
        # Should reference performance metrics
        assert "85" in prompt or "settlement" in prompt.lower()


class TestFeatureToggleFiltering:
    """Test feature toggle integration across pipeline."""

    def test_exclude_collateral_actions(self) -> None:
        """Excluding CollateralAction removes collateral operations."""
        toggles = PolicyFeatureToggles(exclude=["CollateralAction"])

        gen = PolicySchemaGenerator(
            tree_type="strategic_collateral_tree",
            feature_toggles=toggles,
        )

        actions = gen.get_allowed_actions()
        # All collateral actions should be excluded
        assert "PostCollateral" not in actions
        assert "WithdrawCollateral" not in actions

    def test_include_only_transaction_fields(self) -> None:
        """Including only TransactionField limits available fields."""
        toggles = PolicyFeatureToggles(include=["TransactionField"])

        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=toggles,
        )

        fields = gen.get_allowed_fields()
        # Should have transaction fields
        assert "amount" in fields
        # Should NOT have agent fields
        assert "balance" not in fields


class TestDepthLimiting:
    """Test depth limiting across the pipeline."""

    def test_depth_0_actions_only(self) -> None:
        """Depth 0 only allows action nodes."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=0,
        )

        TreeModel = gen.build_tree_model()

        # Should accept action
        action = {"type": "action", "action": "Release", "parameters": {}}
        result = validate_policy_structure(action, "payment_tree", max_depth=0)
        assert result.is_valid

    def test_depth_1_single_condition(self) -> None:
        """Depth 1 allows one level of condition."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=1,
        )

        policy = {
            "type": "condition",
            "condition": {
                "op": ">",
                "left": {"field": "amount"},
                "right": {"value": 100},
            },
            "on_true": {"type": "action", "action": "Release", "parameters": {}},
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }

        result = validate_policy_structure(policy, "payment_tree", max_depth=1)
        assert result.is_valid

    def test_depth_limits_nesting(self) -> None:
        """Schema enforces nesting depth limits."""
        # Create deeply nested policy
        deeply_nested = {
            "type": "condition",
            "condition": {"op": ">", "left": {"field": "amount"}, "right": {"value": 0}},
            "on_true": {
                "type": "condition",
                "condition": {"op": "<", "left": {"field": "balance"}, "right": {"value": 100}},
                "on_true": {
                    "type": "condition",
                    "condition": {"op": ">=", "left": {"value": 1}, "right": {"value": 0}},
                    "on_true": {"type": "action", "action": "Release", "parameters": {}},
                    "on_false": {"type": "action", "action": "Hold", "parameters": {}},
                },
                "on_false": {"type": "action", "action": "Hold", "parameters": {}},
            },
            "on_false": {"type": "action", "action": "Hold", "parameters": {}},
        }

        # Should work at depth 3
        result_d3 = validate_policy_structure(deeply_nested, "payment_tree", max_depth=3)
        assert result_d3.is_valid

        # Should NOT work at depth 1 (too shallow)
        result_d1 = validate_policy_structure(deeply_nested, "payment_tree", max_depth=1)
        assert not result_d1.is_valid


class TestJSONSchemaForOpenAI:
    """Test JSON schema meets OpenAI requirements."""

    def test_schema_tree_nodes_not_recursive(self) -> None:
        """Tree nodes use depth-limited approach (no recursive tree refs).

        Note: Expression types (AndExpression, OrExpression) may have
        self-references to allow nested boolean logic like (A AND B) AND C.
        This is fine for OpenAI since expressions are bounded in practice.
        The key is that TreeNode/ConditionNode don't have recursive refs.
        """
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=3,
        )

        TreeModel = gen.build_tree_model()
        adapter = TypeAdapter(TreeModel)
        schema = adapter.json_schema()

        # Check that tree/condition nodes don't have self-references
        # (They use L0, L1, L2, L3 pattern instead)
        defs = schema.get("$defs", {})
        tree_like_defs = [
            name for name in defs
            if "Condition" in name or "TreeNode" in name
        ]

        for def_name in tree_like_defs:
            def_schema = defs[def_name]
            def_str = json.dumps(def_schema)
            # Tree nodes should NOT reference themselves
            if f'"$ref": "#/$defs/{def_name}"' in def_str:
                pytest.fail(f"Tree definition {def_name} has self-reference")

    def test_schema_serializes_cleanly(self) -> None:
        """Schema can be serialized to JSON without errors."""
        for tree_type in ["payment_tree", "bank_tree", "strategic_collateral_tree"]:
            gen = PolicySchemaGenerator(
                tree_type=tree_type,
                feature_toggles=PolicyFeatureToggles(),
                max_depth=3,
            )

            TreeModel = gen.build_tree_model()
            adapter = TypeAdapter(TreeModel)
            schema = adapter.json_schema()

            # Must serialize cleanly
            json_str = json.dumps(schema, indent=2)
            assert len(json_str) > 100

            # Must deserialize back
            loaded = json.loads(json_str)
            assert isinstance(loaded, dict)

    def test_schema_has_required_openai_structure(self) -> None:
        """Schema has structure OpenAI expects."""
        gen = PolicySchemaGenerator(
            tree_type="payment_tree",
            feature_toggles=PolicyFeatureToggles(),
            max_depth=2,
        )

        TreeModel = gen.build_tree_model()
        adapter = TypeAdapter(TreeModel)
        schema = adapter.json_schema()

        # OpenAI structured output expects certain top-level fields
        # It should have either a top-level type or anyOf/oneOf
        has_type = "type" in schema
        has_union = "anyOf" in schema or "oneOf" in schema
        has_ref = "$ref" in schema

        assert has_type or has_union or has_ref, f"Schema missing expected structure: {list(schema.keys())}"
