"""TDD tests for inline policy_constraints in experiment config.

Phase 15.2: Tests for policy_constraints field in ExperimentConfig.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest


class TestInlineConstraintsBasic:
    """Basic tests for inline policy_constraints parsing."""

    def test_experiment_config_parses_inline_constraints(self, tmp_path: Path) -> None:
        """ExperimentConfig.from_yaml() parses policy_constraints dict."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test experiment"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: threshold
                  param_type: int
                  min_value: 0
                  max_value: 100
              allowed_fields:
                - balance
                - amount
              allowed_actions:
                payment_tree:
                  - Release
                  - Hold
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.policy_constraints is not None

    def test_inline_constraints_creates_scenario_constraints(
        self, tmp_path: Path
    ) -> None:
        """Inline constraints create valid ScenarioConstraints object."""
        from payment_simulator.ai_cash_mgmt import ScenarioConstraints
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test experiment"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: threshold
                  param_type: int
                  min_value: 0
                  max_value: 100
              allowed_fields:
                - balance
              allowed_actions:
                payment_tree:
                  - Release
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert isinstance(constraints, ScenarioConstraints)


class TestInlineConstraintsParameters:
    """Tests for allowed_parameters in inline constraints."""

    def test_inline_constraints_with_float_parameter(self, tmp_path: Path) -> None:
        """Inline constraints parse float parameter with min/max."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: liquidity_fraction
                  param_type: float
                  min_value: 0.0
                  max_value: 1.0
                  description: "Fraction of collateral to post"
              allowed_fields: []
              allowed_actions: {}
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert len(constraints.allowed_parameters) == 1
        param = constraints.allowed_parameters[0]
        assert param.name == "liquidity_fraction"
        assert param.param_type == "float"
        assert param.min_value == 0.0
        assert param.max_value == 1.0
        assert param.description == "Fraction of collateral to post"

    def test_inline_constraints_with_multiple_parameters(self, tmp_path: Path) -> None:
        """Inline constraints parse multiple parameters."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: threshold
                  param_type: int
                  min_value: 0
                  max_value: 20
                - name: fraction
                  param_type: float
                  min_value: 0.0
                  max_value: 1.0
                - name: buffer
                  param_type: float
                  min_value: 0.5
                  max_value: 3.0
              allowed_fields: []
              allowed_actions: {}
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert len(constraints.allowed_parameters) == 3
        names = [p.name for p in constraints.allowed_parameters]
        assert "threshold" in names
        assert "fraction" in names
        assert "buffer" in names


class TestInlineConstraintsFields:
    """Tests for allowed_fields in inline constraints."""

    def test_inline_constraints_with_fields(self, tmp_path: Path) -> None:
        """Inline constraints parse allowed_fields correctly."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters: []
              allowed_fields:
                - balance
                - effective_liquidity
                - ticks_to_deadline
                - remaining_amount
                - priority
              allowed_actions: {}
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert len(constraints.allowed_fields) == 5
        assert "balance" in constraints.allowed_fields
        assert "ticks_to_deadline" in constraints.allowed_fields
        assert constraints.is_field_allowed("balance")
        assert not constraints.is_field_allowed("unknown_field")


class TestInlineConstraintsActions:
    """Tests for allowed_actions in inline constraints."""

    def test_inline_constraints_with_actions(self, tmp_path: Path) -> None:
        """Inline constraints parse allowed_actions correctly."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters: []
              allowed_fields: []
              allowed_actions:
                payment_tree:
                  - Release
                  - Hold
                collateral_tree:
                  - PostCollateral
                  - HoldCollateral
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert "payment_tree" in constraints.allowed_actions
        assert "collateral_tree" in constraints.allowed_actions
        assert constraints.is_action_allowed("payment_tree", "Release")
        assert constraints.is_action_allowed("payment_tree", "Hold")
        assert not constraints.is_action_allowed("payment_tree", "InvalidAction")
        assert constraints.is_action_allowed("collateral_tree", "PostCollateral")


class TestBackwardCompatibility:
    """Tests for backward compatibility with constraints_module."""

    def test_constraints_module_still_works(self, tmp_path: Path) -> None:
        """constraints_module (legacy) still loads Python module."""
        from payment_simulator.experiments.config import ExperimentConfig

        # Note: This test uses a real constraints module
        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            constraints: payment_simulator.ai_cash_mgmt.constraints.test_fixtures.MINIMAL_TEST_CONSTRAINTS
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)

        # Should use constraints_module when policy_constraints not present
        assert config.policy_constraints is None
        assert config.constraints_module != ""

    def test_inline_constraints_takes_precedence(self, tmp_path: Path) -> None:
        """Inline policy_constraints overrides constraints_module."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            constraints: some.module.CONSTRAINTS
            policy_constraints:
              allowed_parameters:
                - name: inline_param
                  param_type: int
                  min_value: 0
                  max_value: 10
              allowed_fields:
                - inline_field
              allowed_actions:
                payment_tree:
                  - InlineAction
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        # Should use inline constraints, not module
        assert constraints is not None
        assert len(constraints.allowed_parameters) == 1
        assert constraints.allowed_parameters[0].name == "inline_param"

    def test_no_constraints_returns_none(self, tmp_path: Path) -> None:
        """No constraints (neither inline nor module) returns None."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert constraints is None


class TestGetConstraintsMethod:
    """Tests for the get_constraints() method."""

    def test_get_constraints_returns_inline_when_present(self, tmp_path: Path) -> None:
        """get_constraints() returns inline policy_constraints."""
        from payment_simulator.ai_cash_mgmt import ScenarioConstraints
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: test_param
                  param_type: float
                  min_value: 0.0
                  max_value: 1.0
              allowed_fields:
                - test_field
              allowed_actions:
                payment_tree:
                  - TestAction
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()

        assert isinstance(constraints, ScenarioConstraints)
        assert len(constraints.allowed_parameters) == 1
        assert constraints.allowed_parameters[0].name == "test_param"


class TestConstraintValidation:
    """Tests for constraint validation via YAML."""

    def test_parameter_validates_value(self, tmp_path: Path) -> None:
        """Parameter from YAML constraints can validate values."""
        from payment_simulator.experiments.config import ExperimentConfig

        yaml_content = dedent("""
            name: test_exp
            description: "Test"
            scenario: configs/test.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 10
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
            policy_constraints:
              allowed_parameters:
                - name: threshold
                  param_type: int
                  min_value: 0
                  max_value: 100
              allowed_fields: []
              allowed_actions: {}
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        constraints = config.get_constraints()
        param = constraints.get_parameter_spec("threshold")

        # Valid value
        is_valid, error = param.validate_value(50)
        assert is_valid
        assert error is None

        # Invalid: below min
        is_valid, error = param.validate_value(-1)
        assert not is_valid
        assert "below min" in error

        # Invalid: above max
        is_valid, error = param.validate_value(101)
        assert not is_valid
        assert "above max" in error
