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
        assert "RTGS" in prompt or "real-time" in prompt.lower() or "settlement" in prompt.lower()
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
# Test Group 4: Castro Mode
# =============================================================================


class TestCastroMode:
    """Tests for Castro paper alignment mode."""

    def test_castro_mode_adds_constraints(
        self, castro_constraints: ScenarioConstraints
    ) -> None:
        """Castro mode includes initial decision emphasis."""
        prompt = build_system_prompt(castro_constraints, castro_mode=True)
        # Castro-specific content about t=0 decision
        has_castro_content = (
            "initial" in prompt.lower()
            or "t=0" in prompt
            or "tick 0" in prompt.lower()
        )
        assert has_castro_content

    def test_castro_mode_emphasizes_collateral_timing(
        self, castro_constraints: ScenarioConstraints
    ) -> None:
        """Castro mode emphasizes collateral decision timing."""
        prompt = build_system_prompt(castro_constraints, castro_mode=True)
        # Should mention collateral and timing
        assert "collateral" in prompt.lower()

    def test_non_castro_mode_works(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Non-Castro mode produces valid prompt without Castro content."""
        prompt = build_system_prompt(minimal_constraints, castro_mode=False)
        # Should be a valid prompt
        assert len(prompt) > 1000
        # Should not have excessive Castro-specific content
        # (Some mention of collateral might still exist if in constraints)


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

    def test_builder_with_castro_mode(
        self, castro_constraints: ScenarioConstraints
    ) -> None:
        """Builder accepts Castro mode flag."""
        builder = SystemPromptBuilder(castro_constraints)
        prompt = builder.with_castro_mode(True).build()
        # Should have Castro content
        has_castro = "initial" in prompt.lower() or "t=0" in prompt
        assert has_castro

    def test_builder_method_chaining(
        self,
        castro_constraints: ScenarioConstraints,
        sample_cost_rates: dict[str, Any],
    ) -> None:
        """Builder supports method chaining."""
        prompt = (
            SystemPromptBuilder(castro_constraints)
            .with_cost_rates(sample_cost_rates)
            .with_castro_mode(True)
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
            '"field"' in prompt
            or '"param"' in prompt
            or '{"field":' in prompt.lower()
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

    def test_empty_cost_rates(
        self, minimal_constraints: ScenarioConstraints
    ) -> None:
        """Prompt works with empty cost rates dict."""
        prompt = build_system_prompt(minimal_constraints, cost_rates={})
        # Should still have cost documentation
        assert "cost" in prompt.lower()
