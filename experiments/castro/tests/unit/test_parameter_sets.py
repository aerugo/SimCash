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
            MINIMAL_CONSTRAINTS,
            STANDARD_CONSTRAINTS,
            FULL_CONSTRAINTS,
        )
        from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent

        for name, constraints in [
            ("minimal", MINIMAL_CONSTRAINTS),
            ("standard", STANDARD_CONSTRAINTS),
            ("full", FULL_CONSTRAINTS),
        ]:
            agent = RobustPolicyAgent(constraints=constraints)
            assert agent.policy_model is not None, f"Failed to create agent for {name}"
