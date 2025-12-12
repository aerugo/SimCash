"""Tests for schema injection helpers.

These helpers format policy and cost schemas for LLM prompts,
filtered by scenario constraints.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import ParameterSpec


# Import the functions we'll implement (TDD - tests written first)
# These imports will fail until we implement the module
from payment_simulator.ai_cash_mgmt.prompts.schema_injection import (
    format_action_list,
    format_field_list,
    format_parameter_bounds,
    get_filtered_cost_schema,
    get_filtered_policy_schema,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_constraints() -> ScenarioConstraints:
    """Minimal constraints with just Release/Hold."""
    return ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0,
                max_value=20,
                description="Ticks before deadline when payment becomes urgent",
            ),
        ],
        allowed_fields=["balance", "ticks_to_deadline", "remaining_amount"],
        allowed_actions={"payment_tree": ["Release", "Hold"]},
    )


@pytest.fixture
def castro_constraints() -> ScenarioConstraints:
    """Castro-style constraints with collateral but limited actions."""
    return ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec(
                name="initial_liquidity_fraction",
                param_type="float",
                min_value=0.0,
                max_value=1.0,
                description="Fraction of collateral to post at t=0",
            ),
            ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0,
                max_value=20,
                description="Ticks before deadline when payment becomes urgent",
            ),
            ParameterSpec(
                name="liquidity_buffer",
                param_type="float",
                min_value=0.5,
                max_value=3.0,
                description="Liquidity safety margin multiplier",
            ),
        ],
        allowed_fields=[
            "balance",
            "effective_liquidity",
            "ticks_to_deadline",
            "remaining_amount",
            "system_tick_in_day",
            "max_collateral_capacity",
            "posted_collateral",
        ],
        allowed_actions={
            "payment_tree": ["Release", "Hold"],
            "strategic_collateral_tree": ["PostCollateral", "HoldCollateral"],
        },
    )


@pytest.fixture
def full_constraints() -> ScenarioConstraints:
    """Full constraints with all tree types enabled."""
    return ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0,
                max_value=20,
                description="Ticks before deadline",
            ),
            ParameterSpec(
                name="liquidity_buffer",
                param_type="float",
                min_value=0.5,
                max_value=3.0,
                description="Liquidity multiplier",
            ),
            ParameterSpec(
                name="split_count",
                param_type="int",
                min_value=2,
                max_value=10,
                description="Number of parts for split",
            ),
        ],
        allowed_fields=[
            "balance",
            "effective_liquidity",
            "ticks_to_deadline",
            "remaining_amount",
            "priority",
            "queue1_total_value",
            "system_tick_in_day",
        ],
        allowed_actions={
            "payment_tree": ["Release", "Hold", "Split"],
            "bank_tree": ["SetReleaseBudget", "NoAction"],
            "strategic_collateral_tree": ["PostCollateral", "HoldCollateral"],
        },
    )


# =============================================================================
# Test Group 1: Policy Schema Filtering
# =============================================================================


class TestPolicySchemaFiltering:
    """Tests for filtering policy schema by scenario constraints."""

    def test_filter_actions_by_tree_type_payment(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Only allowed payment actions are included."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Allowed actions should be present
        assert "Release" in schema
        assert "Hold" in schema

        # Disallowed actions should NOT be present
        assert "Split" not in schema
        assert "PaceAndRelease" not in schema
        assert "StaggerSplit" not in schema

    def test_filter_actions_by_tree_type_bank(
        self, full_constraints: ScenarioConstraints
    ) -> None:
        """Bank tree actions filtered correctly."""
        schema = get_filtered_policy_schema(full_constraints)

        # Allowed bank actions
        assert "SetReleaseBudget" in schema
        assert "NoAction" in schema

        # Disallowed bank actions
        assert "SetState" not in schema
        assert "AddState" not in schema

    def test_filter_actions_excludes_disabled_trees(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Disabled trees have no actions in schema."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Bank tree is not in allowed_actions, so its actions should not appear
        assert "SetReleaseBudget" not in schema
        assert "SetState" not in schema

        # Collateral tree is also not enabled
        assert "PostCollateral" not in schema

    def test_filter_collateral_actions(
        self, castro_constraints: ScenarioConstraints
    ) -> None:
        """Collateral tree actions filtered correctly."""
        schema = get_filtered_policy_schema(castro_constraints)

        # Allowed collateral actions
        assert "PostCollateral" in schema
        assert "HoldCollateral" in schema

        # Disallowed collateral action
        assert "WithdrawCollateral" not in schema

    def test_includes_allowed_fields(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Only allowed fields are documented."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Allowed fields
        assert "balance" in schema
        assert "ticks_to_deadline" in schema
        assert "remaining_amount" in schema

        # Fields NOT in allowed list should not appear (as field references)
        # Note: We need to be careful here - some field names might appear
        # in action descriptions, so we check for the specific context
        # The schema should not list credit_limit as an allowed field
        lines = schema.lower().split("\n")
        # Check there's no "credit_limit" in allowed fields section
        in_fields_section = False
        for line in lines:
            if "allowed fields" in line or "field:" in line:
                in_fields_section = True
            if in_fields_section and "credit_limit" in line:
                pytest.fail("credit_limit should not be in allowed fields")
            if in_fields_section and line.strip() and not line.startswith(" "):
                # New section started
                in_fields_section = False

    def test_includes_parameter_bounds(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Parameters include bounds in documentation."""
        schema = get_filtered_policy_schema(minimal_constraints)

        assert "urgency_threshold" in schema
        # Check bounds are mentioned
        assert "0" in schema
        assert "20" in schema

    def test_includes_parameter_descriptions(
        self, castro_constraints: ScenarioConstraints
    ) -> None:
        """Parameter descriptions are included."""
        schema = get_filtered_policy_schema(castro_constraints)

        # Check that description content appears
        assert "deadline" in schema.lower() or "urgent" in schema.lower()
        assert "collateral" in schema.lower() or "liquidity" in schema.lower()

    def test_schema_includes_expressions(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Schema includes expression operators (always needed)."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Comparison operators should be included
        assert "==" in schema or "Equal" in schema
        assert "<" in schema or "LessThan" in schema

        # Logical operators
        assert "and" in schema.lower()
        assert "or" in schema.lower()

    def test_schema_includes_value_types(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Schema includes value types (field, param, value, compute)."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Value types should be documented
        assert "field" in schema.lower()
        assert "param" in schema.lower()
        assert "value" in schema.lower()
        assert "compute" in schema.lower()


# =============================================================================
# Test Group 2: Cost Schema Formatting
# =============================================================================


class TestCostSchemaFormatting:
    """Tests for formatting cost schema documentation."""

    def test_cost_schema_includes_all_rates(self) -> None:
        """All relevant cost rates are documented."""
        schema = get_filtered_cost_schema()

        # Per-tick costs
        assert "overdraft" in schema.lower()
        assert "delay" in schema.lower()

        # One-time penalties
        assert "deadline" in schema.lower()

        # EOD penalty
        assert "eod" in schema.lower() or "end-of-day" in schema.lower()

    def test_cost_schema_includes_formulas(self) -> None:
        """Cost formulas are documented."""
        schema = get_filtered_cost_schema()

        # Should include formula explanations
        assert "formula" in schema.lower() or "calculation" in schema.lower()

    def test_cost_schema_includes_examples(self) -> None:
        """Cost examples are included."""
        schema = get_filtered_cost_schema()

        # Should include example calculations with dollar amounts or cents
        assert "$" in schema or "cents" in schema.lower()

    def test_cost_schema_with_rates(self) -> None:
        """Format cost schema with specific rate values."""
        rates: dict[str, Any] = {
            "overdraft_bps_per_tick": 0.001,
            "delay_cost_per_tick_per_cent": 0.0001,
            "deadline_penalty": 50000,
            "eod_penalty_per_transaction": 10000,
        }
        schema = get_filtered_cost_schema(cost_rates=rates)

        # Should include the actual values
        assert "0.001" in schema
        assert "0.0001" in schema
        assert "50000" in schema or "50,000" in schema

    def test_cost_schema_categories(self) -> None:
        """Cost schema organizes costs by category."""
        schema = get_filtered_cost_schema()

        # Categories should be mentioned
        per_tick_present = "per tick" in schema.lower() or "per-tick" in schema.lower()
        one_time_present = "one-time" in schema.lower() or "penalty" in schema.lower()

        assert per_tick_present, "Per-tick costs should be documented"
        assert one_time_present, "One-time costs should be documented"


# =============================================================================
# Test Group 3: Parameter Bounds Formatting
# =============================================================================


class TestParameterBoundsFormatting:
    """Tests for formatting parameter specifications."""

    def test_format_parameter_table(self) -> None:
        """Parameters formatted as readable output."""
        params = [
            ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0,
                max_value=20,
                description="Ticks before deadline",
            ),
            ParameterSpec(
                name="liquidity_buffer",
                param_type="float",
                min_value=0.5,
                max_value=3.0,
                description="Liquidity safety margin",
            ),
        ]
        formatted = format_parameter_bounds(params)

        # Should include all parameter names
        assert "urgency_threshold" in formatted
        assert "liquidity_buffer" in formatted

        # Should include ranges
        assert "0" in formatted
        assert "20" in formatted
        assert "0.5" in formatted
        assert "3.0" in formatted

        # Should include descriptions
        assert "deadline" in formatted.lower()
        assert "liquidity" in formatted.lower()

    def test_format_single_parameter(self) -> None:
        """Single parameter formatted correctly."""
        params = [
            ParameterSpec(
                name="threshold",
                param_type="int",
                min_value=1,
                max_value=10,
                description="A threshold value",
            ),
        ]
        formatted = format_parameter_bounds(params)

        assert "threshold" in formatted
        assert "1" in formatted
        assert "10" in formatted

    def test_format_empty_parameters(self) -> None:
        """Empty parameter list returns appropriate message or empty string."""
        formatted = format_parameter_bounds([])

        # Should either be empty or indicate no parameters
        assert formatted == "" or "no parameters" in formatted.lower()

    def test_format_parameter_with_default(self) -> None:
        """Parameter with default value is formatted with default."""
        # Note: ParameterSpec doesn't have a default field currently,
        # but this test documents the expected behavior if we add it
        params = [
            ParameterSpec(
                name="urgency_threshold",
                param_type="float",
                min_value=0,
                max_value=20,
                description="Ticks before deadline",
            ),
        ]
        formatted = format_parameter_bounds(params)

        # Should include the parameter
        assert "urgency_threshold" in formatted


# =============================================================================
# Test Group 4: Action List Formatting
# =============================================================================


class TestActionListFormatting:
    """Tests for formatting action lists per tree type."""

    def test_format_payment_actions(self) -> None:
        """Payment tree actions formatted correctly."""
        actions = ["Release", "Hold", "Split"]
        formatted = format_action_list("payment_tree", actions)

        assert "Release" in formatted
        assert "Hold" in formatted
        assert "Split" in formatted

    def test_format_bank_actions(self) -> None:
        """Bank tree actions formatted correctly."""
        actions = ["SetReleaseBudget", "NoAction"]
        formatted = format_action_list("bank_tree", actions)

        assert "SetReleaseBudget" in formatted
        assert "NoAction" in formatted

    def test_format_collateral_actions(self) -> None:
        """Collateral tree actions formatted correctly."""
        actions = ["PostCollateral", "HoldCollateral"]
        formatted = format_action_list("strategic_collateral_tree", actions)

        assert "PostCollateral" in formatted
        assert "HoldCollateral" in formatted

    def test_format_disabled_tree(self) -> None:
        """Disabled tree indicated clearly."""
        formatted = format_action_list("bank_tree", [])

        # Should indicate tree is disabled or not enabled
        assert "disabled" in formatted.lower() or "not enabled" in formatted.lower()

    def test_format_includes_tree_type_name(self) -> None:
        """Output includes the tree type name for context."""
        actions = ["Release", "Hold"]
        formatted = format_action_list("payment_tree", actions)

        # Should mention the tree type
        assert "payment" in formatted.lower()


# =============================================================================
# Test Group 5: Field List Formatting
# =============================================================================


class TestFieldListFormatting:
    """Tests for formatting field lists."""

    def test_format_field_list_basic(self) -> None:
        """Basic field list formatted correctly."""
        fields = ["balance", "effective_liquidity", "ticks_to_deadline"]
        formatted = format_field_list(fields)

        assert "balance" in formatted
        assert "effective_liquidity" in formatted
        assert "ticks_to_deadline" in formatted

    def test_format_field_list_many_fields(self) -> None:
        """Many fields handled correctly."""
        fields = [
            "balance",
            "effective_liquidity",
            "ticks_to_deadline",
            "remaining_amount",
            "priority",
            "system_tick_in_day",
            "queue1_total_value",
        ]
        formatted = format_field_list(fields)

        # All fields should be present
        for field in fields:
            assert field in formatted

    def test_format_empty_field_list(self) -> None:
        """Empty field list handled gracefully."""
        formatted = format_field_list([])

        # Should either be empty or indicate no fields
        assert formatted == "" or "no fields" in formatted.lower()

    def test_format_single_field(self) -> None:
        """Single field formatted correctly."""
        fields = ["balance"]
        formatted = format_field_list(fields)

        assert "balance" in formatted


# =============================================================================
# Test Group 6: Integration with Rust Schema
# =============================================================================


class TestRustSchemaIntegration:
    """Tests that verify integration with Rust FFI schema."""

    def test_get_policy_schema_returns_json(self) -> None:
        """Rust FFI returns valid policy schema JSON."""
        from payment_simulator.backends import get_policy_schema

        schema_json = get_policy_schema()
        schema = json.loads(schema_json)

        assert "actions" in schema
        assert "expressions" in schema
        assert "values" in schema

    def test_get_cost_schema_returns_json(self) -> None:
        """Rust FFI returns valid cost schema JSON."""
        from payment_simulator.backends import get_cost_schema

        schema_json = get_cost_schema()
        schema = json.loads(schema_json)

        assert "cost_types" in schema

    def test_filter_uses_rust_schema_for_actions(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Filtering correctly includes Release from Rust schema."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Release action should have documentation from Rust
        assert "Release" in schema

        # Should have some description content (from Rust schema)
        assert "RTGS" in schema or "settlement" in schema.lower()

    def test_filter_excludes_disallowed_from_rust(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Filtering correctly excludes Split even though Rust has it."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Split is in Rust schema but NOT in our constraints
        assert "Split" not in schema


# =============================================================================
# Test Group 7: Schema Structure and Completeness
# =============================================================================


class TestSchemaCompleteness:
    """Tests for schema structure and completeness."""

    def test_policy_schema_has_node_id_reminder(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Schema includes reminder about node_id requirement."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Should emphasize node_id requirement
        assert "node_id" in schema.lower()

    def test_policy_schema_has_examples(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Schema includes JSON examples."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Should have JSON examples
        assert '"type"' in schema or '{"type"' in schema or "type:" in schema.lower()

    def test_policy_schema_has_compute_wrapper(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Schema explains compute wrapper requirement."""
        schema = get_filtered_policy_schema(minimal_constraints)

        # Should explain that arithmetic needs compute wrapper
        assert "compute" in schema.lower()

    def test_cost_schema_is_deterministic(self) -> None:
        """Cost schema output is deterministic."""
        schema1 = get_filtered_cost_schema()
        schema2 = get_filtered_cost_schema()

        assert schema1 == schema2

    def test_policy_schema_is_deterministic(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Policy schema output is deterministic."""
        schema1 = get_filtered_policy_schema(minimal_constraints)
        schema2 = get_filtered_policy_schema(minimal_constraints)

        assert schema1 == schema2
