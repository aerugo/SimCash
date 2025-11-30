"""Tests for policy-scenario validation (TDD - tests written first).

These tests validate the core function that checks if a policy
is valid for a given scenario's feature toggles.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml


class TestValidatePolicyForScenario:
    """Test the validate_policy_for_scenario function."""

    def test_policy_valid_without_toggles(self) -> None:
        """Policy validates when no toggles specified in scenario."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            # No policy_feature_toggles
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.forbidden_categories) == 0

    def test_policy_valid_with_allowed_categories(self) -> None:
        """Policy using only allowed categories passes."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={"include": ["PaymentAction"]},
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_policy_invalid_with_forbidden_category_include(self) -> None:
        """Policy using category NOT in include list fails."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        # Policy uses CollateralAction, but scenario only allows PaymentAction
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 1000}}
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={"include": ["PaymentAction"]},
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is False
        assert "CollateralAction" in result.forbidden_categories

    def test_policy_invalid_with_excluded_category(self) -> None:
        """Policy using category IN exclude list fails."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        # Policy uses CollateralAction which is excluded
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 1000}}
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={"exclude": ["CollateralAction"]},
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is False
        assert "CollateralAction" in result.forbidden_categories

    def test_policy_with_forbidden_field_category(self) -> None:
        """Policy using forbidden field category fails."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        # Policy uses CollateralField which is excluded
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": ">",
                    "left": {"field": "posted_collateral"},
                    "right": {"value": 0}
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={"exclude": ["CollateralField"]},
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is False
        assert "CollateralField" in result.forbidden_categories

    def test_validation_result_includes_all_forbidden_categories(self) -> None:
        """Error result includes all forbidden categories used."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        # Policy uses multiple forbidden categories
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "condition",
                "node_id": "C1",
                "condition": {
                    "op": ">",
                    "left": {"field": "balance"},  # AgentField
                    "right": {"field": "posted_collateral"}  # CollateralField
                },
                "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
                "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={
                "exclude": ["AgentField", "CollateralField"]
            },
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is False
        assert "AgentField" in result.forbidden_categories
        assert "CollateralField" in result.forbidden_categories

    def test_rust_validation_errors_returned(self) -> None:
        """Rust-level validation errors are returned properly."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        # Invalid policy (invalid action name)
        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "InvalidActionName"  # Does not exist
            }
        })

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        # Should fail at Rust validation level
        assert result.valid is False
        assert len(result.errors) > 0

    def test_invalid_json_returns_error(self) -> None:
        """Invalid JSON returns appropriate error."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        policy_json = "not valid json {"

        scenario = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
        )

        result = validate_policy_for_scenario(policy_json, scenario_config=scenario)

        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_with_scenario_path(self) -> None:
        """Can validate with scenario file path instead of config object."""
        from payment_simulator.policy.validation import validate_policy_for_scenario

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            }
        })

        scenario_dict = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            "policy_feature_toggles": {
                "include": ["PaymentAction"],
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(scenario_dict, f)
            scenario_path = Path(f.name)

        try:
            result = validate_policy_for_scenario(
                policy_json, scenario_path=scenario_path
            )
            assert result.valid is True
        finally:
            scenario_path.unlink()

    def test_scenario_config_takes_precedence(self) -> None:
        """scenario_config takes precedence over scenario_path."""
        from payment_simulator.policy.validation import validate_policy_for_scenario
        from payment_simulator.config.schemas import SimulationConfig

        policy_json = json.dumps({
            "version": "1.0",
            "policy_id": "test_policy",
            "end_of_tick_collateral_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "PostCollateral",
                "parameters": {"amount": {"value": 1000}}
            }
        })

        # Scenario path would ALLOW CollateralAction
        scenario_dict = {
            "simulation": {"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            "agents": [{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            "policy_feature_toggles": {"include": ["CollateralAction"]},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(scenario_dict, f)
            scenario_path = Path(f.name)

        # But scenario_config FORBIDS CollateralAction
        scenario_config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[{
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "policy": {"type": "Fifo"},
            }],
            policy_feature_toggles={"exclude": ["CollateralAction"]},
        )

        try:
            result = validate_policy_for_scenario(
                policy_json,
                scenario_path=scenario_path,
                scenario_config=scenario_config,  # Takes precedence
            )
            # Should fail because scenario_config forbids CollateralAction
            assert result.valid is False
            assert "CollateralAction" in result.forbidden_categories
        finally:
            scenario_path.unlink()


class TestPolicyValidationResult:
    """Test the PolicyValidationResult dataclass."""

    def test_result_dataclass_fields(self) -> None:
        """PolicyValidationResult has expected fields."""
        from payment_simulator.policy.validation import PolicyValidationResult

        result = PolicyValidationResult(
            valid=True,
            policy_id="test_policy",
            version="1.0",
            description="Test description",
        )

        assert result.valid is True
        assert result.policy_id == "test_policy"
        assert result.version == "1.0"
        assert result.description == "Test description"
        assert result.errors == []
        assert result.forbidden_categories == []
        assert result.forbidden_elements == []

    def test_result_with_errors(self) -> None:
        """PolicyValidationResult can hold error details."""
        from payment_simulator.policy.validation import PolicyValidationResult

        result = PolicyValidationResult(
            valid=False,
            errors=[
                {"type": "ForbiddenCategory", "message": "Category not allowed"},
            ],
            forbidden_categories=["CollateralAction"],
            forbidden_elements=["PostCollateral"],
        )

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "ForbiddenCategory"
        assert "CollateralAction" in result.forbidden_categories
        assert "PostCollateral" in result.forbidden_elements
