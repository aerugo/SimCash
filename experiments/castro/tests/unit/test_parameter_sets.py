"""Unit tests for pre-defined parameter sets.

TDD: These tests define the expected parameter sets.
Run with: pytest experiments/castro/tests/unit/test_parameter_sets.py -v
"""

from __future__ import annotations

import pytest


class TestMinimalConstraints:
    """Tests for MINIMAL_CONSTRAINTS - bare minimum for simple policies."""

    def test_minimal_constraints_is_valid(self) -> None:
        """MINIMAL_CONSTRAINTS is a valid ScenarioConstraints."""
        from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        assert isinstance(MINIMAL_CONSTRAINTS, ScenarioConstraints)

    def test_minimal_has_at_least_one_parameter(self) -> None:
        """MINIMAL_CONSTRAINTS has at least one parameter."""
        from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS

        assert len(MINIMAL_CONSTRAINTS.allowed_parameters) >= 1

    def test_minimal_has_urgency_parameter(self) -> None:
        """MINIMAL_CONSTRAINTS includes urgency threshold."""
        from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS

        param_names = MINIMAL_CONSTRAINTS.get_parameter_names()
        assert "urgency_threshold" in param_names

    def test_minimal_has_basic_fields(self) -> None:
        """MINIMAL_CONSTRAINTS includes basic context fields."""
        from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS

        assert "balance" in MINIMAL_CONSTRAINTS.allowed_fields
        assert "ticks_to_deadline" in MINIMAL_CONSTRAINTS.allowed_fields

    def test_minimal_has_release_and_hold(self) -> None:
        """MINIMAL_CONSTRAINTS includes Release and Hold actions."""
        from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS

        assert "Release" in MINIMAL_CONSTRAINTS.allowed_actions
        assert "Hold" in MINIMAL_CONSTRAINTS.allowed_actions


class TestStandardConstraints:
    """Tests for STANDARD_CONSTRAINTS - common policy parameters."""

    def test_standard_constraints_is_valid(self) -> None:
        """STANDARD_CONSTRAINTS is a valid ScenarioConstraints."""
        from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        assert isinstance(STANDARD_CONSTRAINTS, ScenarioConstraints)

    def test_standard_has_multiple_parameters(self) -> None:
        """STANDARD_CONSTRAINTS has multiple parameters."""
        from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS

        assert len(STANDARD_CONSTRAINTS.allowed_parameters) >= 3

    def test_standard_includes_minimal(self) -> None:
        """STANDARD_CONSTRAINTS includes all MINIMAL parameters."""
        from experiments.castro.parameter_sets import (
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
        )

        minimal_names = set(MINIMAL_CONSTRAINTS.get_parameter_names())
        standard_names = set(STANDARD_CONSTRAINTS.get_parameter_names())

        assert minimal_names.issubset(standard_names)

    def test_standard_has_liquidity_buffer(self) -> None:
        """STANDARD_CONSTRAINTS includes liquidity buffer parameter."""
        from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS

        param_names = STANDARD_CONSTRAINTS.get_parameter_names()
        assert "liquidity_buffer" in param_names

    def test_standard_has_more_fields(self) -> None:
        """STANDARD_CONSTRAINTS has more fields than MINIMAL."""
        from experiments.castro.parameter_sets import (
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
        )

        assert len(STANDARD_CONSTRAINTS.allowed_fields) > len(
            MINIMAL_CONSTRAINTS.allowed_fields
        )


class TestFullConstraints:
    """Tests for FULL_CONSTRAINTS - all SimCash capabilities."""

    def test_full_constraints_is_valid(self) -> None:
        """FULL_CONSTRAINTS is a valid ScenarioConstraints."""
        from experiments.castro.parameter_sets import FULL_CONSTRAINTS
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        assert isinstance(FULL_CONSTRAINTS, ScenarioConstraints)

    def test_full_includes_standard(self) -> None:
        """FULL_CONSTRAINTS includes all STANDARD parameters."""
        from experiments.castro.parameter_sets import (
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )

        standard_names = set(STANDARD_CONSTRAINTS.get_parameter_names())
        full_names = set(FULL_CONSTRAINTS.get_parameter_names())

        assert standard_names.issubset(full_names)

    def test_full_has_most_parameters(self) -> None:
        """FULL_CONSTRAINTS has more parameters than STANDARD."""
        from experiments.castro.parameter_sets import (
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )

        assert len(FULL_CONSTRAINTS.allowed_parameters) > len(
            STANDARD_CONSTRAINTS.allowed_parameters
        )

    def test_full_has_all_payment_fields(self) -> None:
        """FULL_CONSTRAINTS includes all payment tree fields."""
        from experiments.castro.parameter_sets import FULL_CONSTRAINTS
        from experiments.castro.schemas.registry import PAYMENT_TREE_FIELDS

        # Full should have all or most payment tree fields
        assert len(FULL_CONSTRAINTS.allowed_fields) >= len(PAYMENT_TREE_FIELDS) * 0.9

    def test_full_has_all_payment_actions(self) -> None:
        """FULL_CONSTRAINTS includes all payment actions."""
        from experiments.castro.parameter_sets import FULL_CONSTRAINTS
        from experiments.castro.schemas.registry import PAYMENT_ACTIONS

        for action in PAYMENT_ACTIONS:
            assert action in FULL_CONSTRAINTS.allowed_actions


class TestCastroConstraints:
    """Tests for CASTRO_CONSTRAINTS - Castro paper alignment."""

    def test_castro_constraints_is_valid(self) -> None:
        """CASTRO_CONSTRAINTS is a valid ScenarioConstraints."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS
        from experiments.castro.schemas.parameter_config import ScenarioConstraints

        assert isinstance(CASTRO_CONSTRAINTS, ScenarioConstraints)

    def test_castro_only_release_hold_actions(self) -> None:
        """CASTRO_CONSTRAINTS only allows Release and Hold."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert set(CASTRO_CONSTRAINTS.allowed_actions) == {"Release", "Hold"}

    def test_castro_no_split(self) -> None:
        """CASTRO_CONSTRAINTS excludes Split (continuous payments in Castro)."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert "Split" not in CASTRO_CONSTRAINTS.allowed_actions

    def test_castro_no_release_with_credit(self) -> None:
        """CASTRO_CONSTRAINTS excludes ReleaseWithCredit (no interbank credit)."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert "ReleaseWithCredit" not in CASTRO_CONSTRAINTS.allowed_actions

    def test_castro_collateral_restricted(self) -> None:
        """CASTRO_CONSTRAINTS only allows PostCollateral and HoldCollateral."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert CASTRO_CONSTRAINTS.allowed_collateral_actions is not None
        assert set(CASTRO_CONSTRAINTS.allowed_collateral_actions) == {
            "PostCollateral",
            "HoldCollateral",
        }

    def test_castro_no_withdraw_collateral(self) -> None:
        """CASTRO_CONSTRAINTS excludes WithdrawCollateral (no mid-day reduction)."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert CASTRO_CONSTRAINTS.allowed_collateral_actions is not None
        assert "WithdrawCollateral" not in CASTRO_CONSTRAINTS.allowed_collateral_actions

    def test_castro_bank_actions_minimal(self) -> None:
        """CASTRO_CONSTRAINTS bank actions restricted to NoAction."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert CASTRO_CONSTRAINTS.allowed_bank_actions == ["NoAction"]

    def test_castro_has_initial_liquidity_fraction(self) -> None:
        """CASTRO_CONSTRAINTS has initial_liquidity_fraction parameter."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        param_names = CASTRO_CONSTRAINTS.get_parameter_names()
        assert "initial_liquidity_fraction" in param_names

    def test_castro_initial_liquidity_fraction_range(self) -> None:
        """initial_liquidity_fraction is in [0, 1] range."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        param = CASTRO_CONSTRAINTS.get_parameter_by_name("initial_liquidity_fraction")
        assert param is not None
        assert param.min_value == 0.0
        assert param.max_value == 1.0

    def test_castro_has_tick_field(self) -> None:
        """CASTRO_CONSTRAINTS has system_tick_in_day field."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS

        assert "system_tick_in_day" in CASTRO_CONSTRAINTS.allowed_fields

    def test_castro_can_create_agent(self) -> None:
        """CASTRO_CONSTRAINTS can be used to create RobustPolicyAgent."""
        from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        agent = RobustPolicyAgent(constraints=CASTRO_CONSTRAINTS, castro_mode=True)
        assert agent.policy_model is not None

    def test_castro_in_all_constraint_sets(self) -> None:
        """CASTRO_CONSTRAINTS is available via get_constraints."""
        from experiments.castro.parameter_sets import get_constraints

        castro = get_constraints("castro")
        assert castro is not None


class TestParameterSetHierarchy:
    """Tests for parameter set hierarchy and relationships."""

    def test_minimal_is_smallest(self) -> None:
        """MINIMAL_CONSTRAINTS has fewest parameters."""
        from experiments.castro.parameter_sets import (
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )

        assert len(MINIMAL_CONSTRAINTS.allowed_parameters) <= len(
            STANDARD_CONSTRAINTS.allowed_parameters
        )
        assert len(MINIMAL_CONSTRAINTS.allowed_parameters) <= len(
            FULL_CONSTRAINTS.allowed_parameters
        )

    def test_standard_is_middle(self) -> None:
        """STANDARD_CONSTRAINTS is between MINIMAL and FULL."""
        from experiments.castro.parameter_sets import (
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )

        assert len(MINIMAL_CONSTRAINTS.allowed_parameters) <= len(
            STANDARD_CONSTRAINTS.allowed_parameters
        )
        assert len(STANDARD_CONSTRAINTS.allowed_parameters) <= len(
            FULL_CONSTRAINTS.allowed_parameters
        )

    def test_all_sets_can_create_agent(self) -> None:
        """All parameter sets can be used to create RobustPolicyAgent."""
        from experiments.castro.parameter_sets import (
            CASTRO_CONSTRAINTS,
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        for name, constraints, castro_mode in [
            ("castro", CASTRO_CONSTRAINTS, True),
            ("minimal", MINIMAL_CONSTRAINTS, False),
            ("standard", STANDARD_CONSTRAINTS, False),
            ("full", FULL_CONSTRAINTS, False),
        ]:
            agent = RobustPolicyAgent(constraints=constraints, castro_mode=castro_mode)
            assert agent.policy_model is not None, f"Failed to create agent for {name}"
