"""Tests for Castro paper alignment constraints.

These tests verify that:
1. CASTRO_CONSTRAINTS parameter set has the correct restrictions
2. Castro validation functions correctly identify violations
3. Policies conforming to Castro rules pass validation
4. Policies violating Castro rules fail validation
"""

from __future__ import annotations

import pytest

from experiments.castro.generator.validation import (
    CASTRO_ALLOWED_COLLATERAL_ACTIONS,
    CASTRO_ALLOWED_PAYMENT_ACTIONS,
    CASTRO_FORBIDDEN_COLLATERAL_ACTIONS,
    ValidationResult,
    _find_actions_in_tree,
    _is_tick_zero_condition,
    _is_tick_zero_guarded_collateral_tree,
    validate_castro_collateral_tree,
    validate_castro_policy,
)
from experiments.castro.parameter_sets import CASTRO_CONSTRAINTS


# ============================================================================
# Tests for CASTRO_CONSTRAINTS parameter set
# ============================================================================


class TestCastroConstraints:
    """Test CASTRO_CONSTRAINTS parameter set configuration."""

    def test_only_release_and_hold_allowed(self) -> None:
        """Castro model only allows Release (x_t=1) and Hold (x_t=0)."""
        assert set(CASTRO_CONSTRAINTS.allowed_actions) == {"Release", "Hold"}

    def test_no_split_action(self) -> None:
        """Split is not allowed in Castro model (continuous payments assumed)."""
        assert "Split" not in CASTRO_CONSTRAINTS.allowed_actions

    def test_no_release_with_credit(self) -> None:
        """ReleaseWithCredit not allowed (no interbank credit in Castro)."""
        assert "ReleaseWithCredit" not in CASTRO_CONSTRAINTS.allowed_actions

    def test_collateral_actions_restricted(self) -> None:
        """Only PostCollateral and HoldCollateral allowed (no withdrawal)."""
        assert CASTRO_CONSTRAINTS.allowed_collateral_actions is not None
        assert set(CASTRO_CONSTRAINTS.allowed_collateral_actions) == {
            "PostCollateral",
            "HoldCollateral",
        }

    def test_no_withdraw_collateral(self) -> None:
        """WithdrawCollateral not allowed (no mid-day collateral reduction)."""
        assert CASTRO_CONSTRAINTS.allowed_collateral_actions is not None
        assert "WithdrawCollateral" not in CASTRO_CONSTRAINTS.allowed_collateral_actions

    def test_bank_actions_minimal(self) -> None:
        """Bank actions restricted to NoAction only."""
        assert CASTRO_CONSTRAINTS.allowed_bank_actions == ["NoAction"]

    def test_has_initial_liquidity_fraction_parameter(self) -> None:
        """Must have initial_liquidity_fraction parameter (x_0 in Castro)."""
        param_names = [p.name for p in CASTRO_CONSTRAINTS.allowed_parameters]
        assert "initial_liquidity_fraction" in param_names

    def test_initial_liquidity_fraction_range(self) -> None:
        """initial_liquidity_fraction must be in [0, 1]."""
        param = CASTRO_CONSTRAINTS.get_parameter_by_name("initial_liquidity_fraction")
        assert param is not None
        assert param.min_value == 0.0
        assert param.max_value == 1.0

    def test_has_tick_field(self) -> None:
        """Must have system_tick_in_day field for tick-0 guard."""
        assert "system_tick_in_day" in CASTRO_CONSTRAINTS.allowed_fields

    def test_no_lsm_fields(self) -> None:
        """LSM fields should not be in Castro constraints."""
        lsm_fields = [f for f in CASTRO_CONSTRAINTS.allowed_fields if "lsm" in f.lower()]
        assert len(lsm_fields) == 0, f"Found LSM fields: {lsm_fields}"

    def test_no_credit_fields(self) -> None:
        """Credit fields should not be in Castro constraints."""
        credit_fields = [
            f for f in CASTRO_CONSTRAINTS.allowed_fields if "credit" in f.lower()
        ]
        assert len(credit_fields) == 0, f"Found credit fields: {credit_fields}"


# ============================================================================
# Tests for tick-zero condition detection
# ============================================================================


class TestTickZeroCondition:
    """Test _is_tick_zero_condition helper function."""

    def test_detects_system_tick_equals_zero(self) -> None:
        """Detect system_tick_in_day == 0 pattern."""
        condition = {
            "op": "==",
            "left": {"field": "system_tick_in_day"},
            "right": {"value": 0},
        }
        assert _is_tick_zero_condition(condition) is True

    def test_detects_current_tick_equals_zero(self) -> None:
        """Detect current_tick == 0 pattern."""
        condition = {
            "op": "==",
            "left": {"field": "current_tick"},
            "right": 0,  # Direct int value
        }
        assert _is_tick_zero_condition(condition) is True

    def test_detects_zero_on_left(self) -> None:
        """Detect 0 == system_tick_in_day pattern."""
        condition = {
            "op": "==",
            "left": {"value": 0},
            "right": {"field": "system_tick_in_day"},
        }
        assert _is_tick_zero_condition(condition) is True

    def test_rejects_other_tick_values(self) -> None:
        """Reject system_tick_in_day == 1."""
        condition = {
            "op": "==",
            "left": {"field": "system_tick_in_day"},
            "right": {"value": 1},
        }
        assert _is_tick_zero_condition(condition) is False

    def test_rejects_other_operators(self) -> None:
        """Reject != or < operators."""
        condition = {
            "op": ">=",
            "left": {"field": "system_tick_in_day"},
            "right": {"value": 0},
        }
        assert _is_tick_zero_condition(condition) is False

    def test_rejects_other_fields(self) -> None:
        """Reject balance == 0."""
        condition = {
            "op": "==",
            "left": {"field": "balance"},
            "right": {"value": 0},
        }
        assert _is_tick_zero_condition(condition) is False


# ============================================================================
# Tests for Castro collateral tree validation
# ============================================================================


class TestCastroCollateralTreeValidation:
    """Test Castro-specific collateral tree validation."""

    def test_valid_tick_zero_guarded_tree(self) -> None:
        """Valid tree: PostCollateral only at tick 0."""
        tree = {
            "type": "condition",
            "node_id": "SC1",
            "condition": {
                "op": "==",
                "left": {"field": "system_tick_in_day"},
                "right": {"value": 0},
            },
            "on_true": {
                "type": "action",
                "node_id": "SC2",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 10000}},
            },
            "on_false": {
                "type": "action",
                "node_id": "SC3",
                "action": "HoldCollateral",
            },
        }
        is_valid, error = _is_tick_zero_guarded_collateral_tree(tree)
        assert is_valid is True
        assert error == ""

    def test_invalid_unguarded_post_collateral(self) -> None:
        """Invalid: PostCollateral at root without tick guard."""
        tree = {
            "type": "action",
            "node_id": "SC1",
            "action": "PostCollateral",
            "parameters": {"amount": {"value": 10000}},
        }
        is_valid, error = _is_tick_zero_guarded_collateral_tree(tree)
        assert is_valid is False
        assert "tick==0 guard" in error

    def test_valid_hold_only_tree(self) -> None:
        """Valid: HoldCollateral at root (never posts)."""
        tree = {
            "type": "action",
            "node_id": "SC1",
            "action": "HoldCollateral",
        }
        is_valid, error = _is_tick_zero_guarded_collateral_tree(tree)
        assert is_valid is True

    def test_invalid_post_in_false_branch(self) -> None:
        """Invalid: PostCollateral in non-tick-0 branch."""
        tree = {
            "type": "condition",
            "node_id": "SC1",
            "condition": {
                "op": "==",
                "left": {"field": "system_tick_in_day"},
                "right": {"value": 0},
            },
            "on_true": {
                "type": "action",
                "node_id": "SC2",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 10000}},
            },
            "on_false": {
                # This should be HoldCollateral, not PostCollateral!
                "type": "action",
                "node_id": "SC3",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 5000}},
            },
        }
        is_valid, error = _is_tick_zero_guarded_collateral_tree(tree)
        assert is_valid is False
        assert "non-tick-0 branch" in error

    def test_validation_result_for_valid_tree(self) -> None:
        """validate_castro_collateral_tree returns success for valid tree."""
        tree = {
            "type": "condition",
            "node_id": "SC1",
            "condition": {
                "op": "==",
                "left": {"field": "system_tick_in_day"},
                "right": 0,
            },
            "on_true": {
                "type": "action",
                "node_id": "SC2",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 10000}},
            },
            "on_false": {
                "type": "action",
                "node_id": "SC3",
                "action": "HoldCollateral",
            },
        }
        result = validate_castro_collateral_tree(tree)
        assert result.is_valid is True


# ============================================================================
# Tests for full Castro policy validation
# ============================================================================


class TestCastroPolicyValidation:
    """Test validate_castro_policy for complete policies."""

    def test_valid_minimal_castro_policy(self) -> None:
        """Valid minimal policy conforming to Castro rules."""
        policy = {
            "version": "2.0",
            "policy_id": "castro_valid",
            "parameters": {
                "initial_liquidity_fraction": 0.5,
                "urgency_threshold": 3.0,
            },
            "strategic_collateral_tree": {
                "type": "condition",
                "node_id": "SC1",
                "condition": {
                    "op": "==",
                    "left": {"field": "system_tick_in_day"},
                    "right": 0,
                },
                "on_true": {
                    "type": "action",
                    "node_id": "SC2",
                    "action": "PostCollateral",
                    "parameters": {"amount": {"value": 10000}},
                },
                "on_false": {
                    "type": "action",
                    "node_id": "SC3",
                    "action": "HoldCollateral",
                },
            },
            "payment_tree": {
                "type": "condition",
                "node_id": "P1",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency_threshold"},
                },
                "on_true": {"type": "action", "node_id": "P2", "action": "Release"},
                "on_false": {"type": "action", "node_id": "P3", "action": "Hold"},
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is True

    def test_invalid_policy_with_split(self) -> None:
        """Invalid: policy uses Split action."""
        policy = {
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "Split",  # Not allowed in Castro
                "parameters": {"num_parts": {"value": 2}},
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("Split" in e for e in result.errors)

    def test_invalid_policy_with_release_with_credit(self) -> None:
        """Invalid: policy uses ReleaseWithCredit action."""
        policy = {
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "ReleaseWithCredit",  # Not allowed in Castro
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("ReleaseWithCredit" in e for e in result.errors)

    def test_invalid_policy_with_withdraw_collateral(self) -> None:
        """Invalid: policy uses WithdrawCollateral."""
        policy = {
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "SC1",
                "action": "WithdrawCollateral",  # Not allowed in Castro
                "parameters": {"amount": {"value": 5000}},
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("WithdrawCollateral" in e for e in result.errors)

    def test_invalid_unguarded_collateral_tree(self) -> None:
        """Invalid: collateral tree posts without tick-0 guard."""
        policy = {
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "SC1",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 10000}},
            },
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "Release",
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("tick" in e.lower() and "guard" in e.lower() for e in result.errors)

    def test_invalid_end_of_tick_collateral_tree(self) -> None:
        """Invalid: end_of_tick_collateral_tree modifies collateral."""
        policy = {
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "E1",
                "action": "PostCollateral",  # Not allowed - should be HoldCollateral
                "parameters": {"amount": {"value": 5000}},
            },
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "Release",
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("end_of_tick" in e.lower() for e in result.errors)

    def test_invalid_bank_tree_with_budget(self) -> None:
        """Invalid: bank_tree uses SetReleaseBudget."""
        policy = {
            "bank_tree": {
                "type": "action",
                "node_id": "B1",
                "action": "SetReleaseBudget",  # Not allowed in Castro
                "parameters": {"max_value_to_release": {"value": 100000}},
            },
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "Release",
            },
        }
        result = validate_castro_policy(policy, strict=True)
        assert result.is_valid is False
        assert any("SetReleaseBudget" in e for e in result.errors)

    def test_non_strict_mode_produces_warnings(self) -> None:
        """Non-strict mode produces warnings instead of errors."""
        policy = {
            "payment_tree": {
                "type": "action",
                "node_id": "P1",
                "action": "Split",  # Would be error in strict mode
            },
        }
        result = validate_castro_policy(policy, strict=False)
        # Non-strict should pass but with warnings
        assert result.is_valid is True
        assert len(result.warnings) > 0


# ============================================================================
# Tests for action discovery
# ============================================================================


class TestFindActionsInTree:
    """Test _find_actions_in_tree helper function."""

    def test_finds_single_action(self) -> None:
        """Find action in single-node tree."""
        tree = {"type": "action", "node_id": "A1", "action": "Release"}
        actions = _find_actions_in_tree(tree)
        assert len(actions) == 1
        assert actions[0][0] == "Release"
        assert actions[0][1] == ["A1"]

    def test_finds_actions_in_condition_tree(self) -> None:
        """Find actions in both branches of condition."""
        tree = {
            "type": "condition",
            "node_id": "N1",
            "condition": {"op": "==", "left": {"value": 1}, "right": {"value": 1}},
            "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
            "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
        }
        actions = _find_actions_in_tree(tree)
        assert len(actions) == 2
        action_names = {a[0] for a in actions}
        assert action_names == {"Release", "Hold"}

    def test_finds_nested_actions(self) -> None:
        """Find actions in deeply nested tree."""
        tree = {
            "type": "condition",
            "node_id": "N1",
            "condition": {"op": "==", "left": {"value": 1}, "right": {"value": 1}},
            "on_true": {
                "type": "condition",
                "node_id": "N2",
                "condition": {"op": "==", "left": {"value": 1}, "right": {"value": 1}},
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
            },
            "on_false": {"type": "action", "node_id": "A3", "action": "Split"},
        }
        actions = _find_actions_in_tree(tree)
        assert len(actions) == 3
        action_names = {a[0] for a in actions}
        assert action_names == {"Release", "Hold", "Split"}
