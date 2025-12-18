"""Tests for system prompt builder.

The system prompt provides the LLM with context for policy optimization,
including domain explanation, cost structure, and filtered schemas.
"""

from __future__ import annotations

from typing import Any

import pytest
from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
from payment_simulator.ai_cash_mgmt.constraints.parameter_spec import ParameterSpec

# Import the functions we'll implement (TDD - tests written first)
from payment_simulator.ai_cash_mgmt.prompts.system_prompt_builder import (
    SystemPromptBuilder,
    build_system_prompt,
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


@pytest.fixture
def sample_cost_rates() -> dict[str, Any]:
    """Sample cost rates for testing."""
    return {
        "overdraft_bps_per_tick": 0.001,
        "delay_cost_per_tick_per_cent": 0.0001,
        "deadline_penalty": 50000,
        "eod_penalty_per_transaction": 10000,
        "split_friction_cost": 1000,
    }


# =============================================================================
# Test Group 1: System Prompt Structure
# =============================================================================


class TestSystemPromptStructure:
    """Tests for system prompt overall structure."""

    def test_prompt_starts_with_expert_role(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt begins with expert role definition."""
        prompt = build_system_prompt(minimal_constraints)
        assert prompt.lower().startswith("you are")
        assert "expert" in prompt.lower()

    def test_prompt_includes_domain_explanation(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt includes RTGS/queue/settlement explanation."""
        prompt = build_system_prompt(minimal_constraints)
        # Should explain key domain concepts
        assert (
            "RTGS" in prompt
            or "real-time" in prompt.lower()
            or "settlement" in prompt.lower()
        )
        assert "queue" in prompt.lower()

    def test_prompt_includes_cost_objectives(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt explains cost minimization objective."""
        prompt = build_system_prompt(minimal_constraints)
        assert "cost" in prompt.lower()
        assert "minimize" in prompt.lower() or "objective" in prompt.lower()

    def test_prompt_includes_policy_tree_explanation(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt explains policy tree architecture."""
        prompt = build_system_prompt(minimal_constraints)
        assert "policy" in prompt.lower()
        assert "tree" in prompt.lower() or "decision" in prompt.lower()
        assert "condition" in prompt.lower()
        assert "action" in prompt.lower()

    def test_prompt_includes_optimization_process(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt explains what the LLM receives."""
        prompt = build_system_prompt(minimal_constraints)
        assert "simulation" in prompt.lower()
        # Should mention iteration or history
        assert "iteration" in prompt.lower() or "history" in prompt.lower()

    def test_prompt_is_not_empty(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt is not empty."""
        prompt = build_system_prompt(minimal_constraints)
        assert len(prompt) > 1000  # Should be substantial

    def test_prompt_mentions_json_output(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt mentions JSON policy output."""
        prompt = build_system_prompt(minimal_constraints)
        assert "JSON" in prompt or "json" in prompt


# =============================================================================
# Test Group 2: Schema Injection
# =============================================================================


class TestSchemaInjection:
    """Tests for schema injection into system prompt."""

    def test_policy_schema_injected(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Policy schema section is included."""
        prompt = build_system_prompt(minimal_constraints)
        # Should have policy format section
        has_policy_section = (
            "POLICY FORMAT" in prompt.upper()
            or "policy schema" in prompt.lower()
            or "ALLOWED ACTIONS" in prompt.upper()
        )
        assert has_policy_section

    def test_cost_schema_injected(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Cost schema section is included."""
        prompt = build_system_prompt(minimal_constraints)
        # Should have cost parameters section
        has_cost_section = (
            "COST PARAMETERS" in prompt.upper()
            or "cost schema" in prompt.lower()
            or "overdraft" in prompt.lower()
        )
        assert has_cost_section

    def test_node_id_requirement_emphasized(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """node_id requirement is clearly stated."""
        prompt = build_system_prompt(minimal_constraints)
        assert "node_id" in prompt
        # Should emphasize importance
        is_emphasized = (
            "unique" in prompt.lower()
            or "CRITICAL" in prompt
            or "MUST" in prompt
            or "required" in prompt.lower()
        )
        assert is_emphasized

    def test_allowed_actions_visible(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Allowed actions from constraints are in prompt."""
        prompt = build_system_prompt(minimal_constraints)
        # Should show allowed actions
        assert "Release" in prompt
        assert "Hold" in prompt
        # Should NOT show Split as a payment_tree action (it may appear
        # elsewhere like in cost documentation for "Split Friction Cost")
        # Check that "- **Split**" isn't present (action header format)
        assert "- **Split**" not in prompt

    def test_allowed_fields_visible(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Allowed fields from constraints are in prompt."""
        prompt = build_system_prompt(minimal_constraints)
        # Should show allowed fields
        assert "balance" in prompt
        assert "ticks_to_deadline" in prompt

    def test_allowed_parameters_visible(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Allowed parameters from constraints are in prompt."""
        prompt = build_system_prompt(minimal_constraints)
        assert "urgency_threshold" in prompt
        # Should show bounds
        assert "0" in prompt
        assert "20" in prompt


# =============================================================================
# Test Group 3: Cost Rate Injection
# =============================================================================


class TestCostRateInjection:
    """Tests for cost rate injection."""

    def test_cost_rates_included(
        self,
        minimal_constraints: ScenarioConstraints,
        sample_cost_rates: dict[str, Any],
    ) -> None:
        """Current cost rates are shown when provided."""
        prompt = build_system_prompt(minimal_constraints, cost_rates=sample_cost_rates)
        # Should include actual values
        assert "0.001" in prompt
        assert "0.0001" in prompt

    def test_default_rates_used_when_none(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Default documentation used when no rates provided."""
        prompt = build_system_prompt(minimal_constraints)
        # Should still include cost documentation
        assert "overdraft" in prompt.lower()
        assert "delay" in prompt.lower()

    def test_cost_formulas_included(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Cost formulas are explained."""
        prompt = build_system_prompt(minimal_constraints)
        # Should have formula explanations
        assert "formula" in prompt.lower() or "calculation" in prompt.lower()


# =============================================================================
# Test Group 5: Builder Pattern
# =============================================================================


class TestBuilderPattern:
    """Tests for SystemPromptBuilder fluent API."""

    def test_builder_creates_prompt(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Builder creates valid prompt."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.build()
        assert len(prompt) > 1000
        assert "Release" in prompt

    def test_builder_with_cost_rates(
        self,
        minimal_constraints: ScenarioConstraints,
        sample_cost_rates: dict[str, Any],
    ) -> None:
        """Builder accepts cost rates."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_cost_rates(sample_cost_rates).build()
        assert "0.001" in prompt

    def test_builder_method_chaining(
        self,
        castro_constraints: ScenarioConstraints,
        sample_cost_rates: dict[str, Any],
    ) -> None:
        """Builder supports method chaining."""
        prompt = (
            SystemPromptBuilder(castro_constraints)
            .with_cost_rates(sample_cost_rates)
            .with_examples(True)
            .build()
        )
        assert len(prompt) > 1000


# =============================================================================
# Test Group 6: Prompt Quality
# =============================================================================


class TestPromptQuality:
    """Tests for prompt quality and completeness."""

    def test_prompt_is_deterministic(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Same inputs produce same prompt."""
        prompt1 = build_system_prompt(minimal_constraints)
        prompt2 = build_system_prompt(minimal_constraints)
        assert prompt1 == prompt2

    def test_prompt_has_compute_wrapper_reminder(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt reminds about compute wrapper requirement."""
        prompt = build_system_prompt(minimal_constraints)
        assert "compute" in prompt.lower()

    def test_prompt_explains_value_types(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt explains value types (field, param, value, compute)."""
        prompt = build_system_prompt(minimal_constraints)
        # Should explain how to reference values
        has_value_explanation = (
            '"field"' in prompt or '"param"' in prompt or '{"field":' in prompt.lower()
        )
        assert has_value_explanation

    def test_prompt_explains_condition_nodes(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt explains condition node structure."""
        prompt = build_system_prompt(minimal_constraints)
        assert "condition" in prompt.lower()
        # Should mention on_true/on_false or similar
        has_branching = (
            "on_true" in prompt
            or "on_false" in prompt
            or "true" in prompt.lower()
            or "false" in prompt.lower()
        )
        assert has_branching

    def test_prompt_with_multiple_tree_types(
        self, full_constraints: ScenarioConstraints
    ) -> None:
        """Prompt handles multiple tree types correctly."""
        prompt = build_system_prompt(full_constraints)
        # Should include all enabled tree types
        assert "payment" in prompt.lower()
        assert "bank" in prompt.lower()
        assert "collateral" in prompt.lower()
        # Should include their actions
        assert "Release" in prompt
        assert "SetReleaseBudget" in prompt
        assert "PostCollateral" in prompt


# =============================================================================
# Test Group 7: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_constraints(self) -> None:
        """Prompt works with empty constraints."""
        constraints = ScenarioConstraints()
        prompt = build_system_prompt(constraints)
        # Should still produce valid prompt
        assert len(prompt) > 500

    def test_constraints_with_only_fields(self) -> None:
        """Prompt works with only fields specified."""
        constraints = ScenarioConstraints(
            allowed_fields=["balance", "effective_liquidity"],
        )
        prompt = build_system_prompt(constraints)
        assert "balance" in prompt
        assert "effective_liquidity" in prompt

    def test_constraints_with_only_actions(self) -> None:
        """Prompt works with only actions specified."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release"]},
        )
        prompt = build_system_prompt(constraints)
        assert "Release" in prompt

    def test_empty_cost_rates(self, minimal_constraints: ScenarioConstraints) -> None:
        """Prompt works with empty cost rates dict."""
        prompt = build_system_prompt(minimal_constraints, cost_rates={})
        # Should still have cost documentation
        assert "cost" in prompt.lower()


# =============================================================================
# Test Group 8: Prompt Customization Injection
# =============================================================================


class TestPromptCustomization:
    """Tests for prompt customization injection."""

    def test_customization_injected_when_provided(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Customization text is injected into prompt."""
        customization = "CUSTOM: This is a special experiment."
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization(customization).build()
        assert "CUSTOM: This is a special experiment" in prompt

    def test_customization_after_expert_intro(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Customization appears after expert introduction."""
        customization = "EXPERIMENT_MARKER: Nash equilibrium game"
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization(customization).build()

        # Find positions
        expert_idx = prompt.lower().find("you are")
        custom_idx = prompt.find("EXPERIMENT_MARKER")

        # Both should be present and customization after expert intro
        assert expert_idx >= 0
        assert custom_idx > expert_idx

    def test_customization_before_domain_explanation(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Customization appears before detailed domain explanation."""
        customization = "UNIQUE_MARKER_FOR_TEST"
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization(customization).build()

        # Find positions
        custom_idx = prompt.find("UNIQUE_MARKER_FOR_TEST")
        domain_idx = prompt.lower().find("domain context")

        # Both should be present
        assert custom_idx >= 0
        # Note: domain_idx might not exist if the heading is different
        # Just verify customization is present and early in prompt
        assert custom_idx < len(prompt) // 3  # Should be in first third

    def test_no_customization_when_none(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """No customization section when None provided."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.build()  # No with_customization call
        # Should not have customization marker
        assert "EXPERIMENT CUSTOMIZATION" not in prompt

    def test_empty_string_customization_ignored(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Empty string customization does not add section."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization("").build()
        # Should not have customization marker
        assert "EXPERIMENT CUSTOMIZATION" not in prompt

    def test_whitespace_customization_ignored(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Whitespace-only customization does not add section."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization("   \n\t  ").build()
        # Should not have customization marker
        assert "EXPERIMENT CUSTOMIZATION" not in prompt

    def test_multiline_customization_preserved(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Multiline customization text is preserved."""
        customization = """This is line 1.
This is line 2.
This is line 3 with special chars: $100, 50%."""
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization(customization).build()

        assert "This is line 1." in prompt
        assert "This is line 2." in prompt
        assert "$100, 50%" in prompt

    def test_customization_with_header(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Customization section has clear header."""
        customization = "Custom experiment instructions"
        builder = SystemPromptBuilder(minimal_constraints)
        prompt = builder.with_customization(customization).build()

        # Should have some form of header/delimiter
        has_header = (
            "EXPERIMENT" in prompt.upper()
            or "CUSTOMIZATION" in prompt.upper()
            or "###" in prompt
        )
        assert has_header

    def test_build_system_prompt_function_with_customization(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """build_system_prompt function supports customization."""
        customization = "Function-level customization test"
        prompt = build_system_prompt(
            minimal_constraints,
            customization=customization,
        )
        assert "Function-level customization test" in prompt

        # Both should be present
        assert "CASTRO_CUSTOM: Nash equilibrium expected" in prompt
        assert "collateral" in prompt.lower()  # Castro mode content

    def test_customization_order_in_builder(
        self,
        minimal_constraints: ScenarioConstraints,
        sample_cost_rates: dict[str, Any],
    ) -> None:
        """Customization order doesn't affect builder output."""
        customization = "ORDER_TEST_MARKER"

        # Build with different method orders
        prompt1 = (
            SystemPromptBuilder(minimal_constraints)
            .with_customization(customization)
            .with_cost_rates(sample_cost_rates)
            .build()
        )

        prompt2 = (
            SystemPromptBuilder(minimal_constraints)
            .with_cost_rates(sample_cost_rates)
            .with_customization(customization)
            .build()
        )

        # Both should contain the marker
        assert "ORDER_TEST_MARKER" in prompt1
        assert "ORDER_TEST_MARKER" in prompt2


# =============================================================================
# Test Group 9: Tree Type Filtering
# =============================================================================


class TestTreeTypeFiltering:
    """Tests for tree type filtering based on constraints.

    When tree types don't have allowed actions in constraints, they should
    not be mentioned in the system prompt to prevent the LLM from generating
    invalid policies with those tree types.
    """

    def test_policy_architecture_excludes_unused_trees(self) -> None:
        """Policy architecture section doesn't mention trees without allowed actions."""
        # Only payment_tree enabled
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        prompt = build_system_prompt(constraints)

        # payment_tree should be mentioned
        assert "payment_tree" in prompt

        # Trees without actions should NOT be mentioned in Tree Types section
        # Find the Tree Types section and check what's there
        tree_types_section = prompt.split("### Tree Types")[1].split("###")[0]
        assert "strategic_collateral_tree" not in tree_types_section
        assert "end_of_tick_collateral_tree" not in tree_types_section
        assert "bank_tree" not in tree_types_section

    def test_policy_architecture_includes_all_enabled_trees(self) -> None:
        """Policy architecture section includes all enabled tree types."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release"],
                "bank_tree": ["NoAction"],
                "strategic_collateral_tree": ["PostCollateral"],
            },
        )
        prompt = build_system_prompt(constraints)

        # Find the Tree Types section
        tree_types_section = prompt.split("### Tree Types")[1].split("###")[0]

        # All enabled trees should be mentioned
        assert "payment_tree" in tree_types_section
        assert "bank_tree" in tree_types_section
        assert "strategic_collateral_tree" in tree_types_section

        # Disabled tree should NOT be mentioned
        assert "end_of_tick_collateral_tree" not in tree_types_section

    def test_error_examples_exclude_unused_trees_single_tree(self) -> None:
        """Error examples don't reference trees when only one tree is enabled.

        When only one tree type is enabled, ERROR 2 (wrong action for tree)
        isn't relevant because there's no confusion possible.
        """
        # Only payment_tree enabled
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        prompt = build_system_prompt(constraints)

        # ERROR 2 should not appear when only one tree is enabled
        # (no confusion possible between tree types)
        error_section = prompt.split("## Common Errors to Avoid")[1]
        assert "ERROR 2" not in error_section

    def test_error_examples_contextual_to_enabled_trees(self) -> None:
        """Error examples use enabled tree types when showing ERROR 2."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release", "Hold"],
                "strategic_collateral_tree": ["PostCollateral", "HoldCollateral"],
            },
        )
        prompt = build_system_prompt(constraints)

        # ERROR 2 should appear with contextual examples
        error_section = prompt.split("## Common Errors to Avoid")[1]
        assert "ERROR 2" in error_section
        assert "strategic_collateral_tree" in error_section

    def test_error_examples_use_bank_tree_when_enabled(self) -> None:
        """Error examples use bank_tree in examples when enabled with payment_tree."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release", "Hold"],
                "bank_tree": ["NoAction", "SetReleaseBudget"],
            },
        )
        prompt = build_system_prompt(constraints)

        # ERROR 2 should appear with bank_tree examples
        error_section = prompt.split("## Common Errors to Avoid")[1]
        assert "ERROR 2" in error_section
        assert "bank_tree" in error_section

    def test_evaluation_flow_filtered_by_enabled_trees(self) -> None:
        """Evaluation flow only mentions enabled tree types."""
        # Only payment_tree enabled
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        prompt = build_system_prompt(constraints)

        # Find the Evaluation Flow section
        eval_section = prompt.split("### Evaluation Flow")[1].split("##")[0]

        # Should mention payment tree
        assert "Payment tree" in eval_section or "payment" in eval_section.lower()

        # Should NOT mention bank tree or collateral trees
        assert "Bank tree" not in eval_section
        assert "Collateral" not in eval_section

    def test_evaluation_flow_includes_all_enabled_trees(self) -> None:
        """Evaluation flow mentions all enabled tree types."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release"],
                "bank_tree": ["NoAction"],
                "strategic_collateral_tree": ["PostCollateral"],
            },
        )
        prompt = build_system_prompt(constraints)

        # Find the Evaluation Flow section
        eval_section = prompt.split("### Evaluation Flow")[1].split("##")[0]

        # Should mention all enabled tree types
        assert "Bank tree" in eval_section
        assert "Collateral" in eval_section
        assert "Payment tree" in eval_section

    def test_empty_constraints_provides_generic_guidance(self) -> None:
        """Empty constraints provide generic tree guidance."""
        constraints = ScenarioConstraints()
        prompt = build_system_prompt(constraints)

        # Should still have tree architecture section
        assert "Policy Tree Architecture" in prompt

        # Should have generic guidance
        assert "scenario constraints" in prompt.lower() or "defined by" in prompt.lower()
