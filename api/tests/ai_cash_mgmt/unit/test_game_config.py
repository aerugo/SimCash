"""Unit tests for GameConfig and related configuration models.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


class TestOptimizationScheduleType:
    """Test optimization schedule type enum."""

    def test_schedule_type_values(self) -> None:
        """OptimizationScheduleType should have expected values."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            OptimizationScheduleType,
        )

        assert OptimizationScheduleType.EVERY_X_TICKS == "every_x_ticks"
        assert OptimizationScheduleType.AFTER_EOD == "after_eod"
        assert OptimizationScheduleType.ON_SIMULATION_END == "on_simulation_end"


class TestSampleMethod:
    """Test sample method enum."""

    def test_sample_method_values(self) -> None:
        """SampleMethod should have expected values."""
        from payment_simulator.ai_cash_mgmt.config.game_config import SampleMethod

        assert SampleMethod.BOOTSTRAP == "bootstrap"
        assert SampleMethod.PERMUTATION == "permutation"
        assert SampleMethod.STRATIFIED == "stratified"


class TestOptimizationSchedule:
    """Test optimization schedule configuration."""

    def test_every_x_ticks_requires_interval(self) -> None:
        """every_x_ticks schedule requires interval_ticks."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from pydantic import ValidationError

        # Valid
        schedule = OptimizationSchedule(
            type=OptimizationScheduleType.EVERY_X_TICKS,
            interval_ticks=100,
        )
        assert schedule.interval_ticks == 100

        # Invalid - missing interval
        with pytest.raises(ValidationError):
            OptimizationSchedule(type=OptimizationScheduleType.EVERY_X_TICKS)

    def test_after_eod_defaults_min_remaining_days(self) -> None:
        """after_eod schedule should default min_remaining_days."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            OptimizationSchedule,
            OptimizationScheduleType,
        )

        schedule = OptimizationSchedule(type=OptimizationScheduleType.AFTER_EOD)

        assert schedule.min_remaining_days == 1

    def test_on_simulation_end_defaults_min_remaining_repetitions(self) -> None:
        """on_simulation_end schedule should default min_remaining_repetitions."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            OptimizationSchedule,
            OptimizationScheduleType,
        )

        schedule = OptimizationSchedule(
            type=OptimizationScheduleType.ON_SIMULATION_END
        )

        assert schedule.min_remaining_repetitions == 1


class TestBootstrapConfig:
    """Test Bootstrap configuration."""

    def test_bootstrap_defaults(self) -> None:
        """BootstrapConfig should have sensible defaults."""
        from payment_simulator.ai_cash_mgmt.config.game_config import BootstrapConfig

        config = BootstrapConfig()

        assert config.num_samples == 20
        assert config.sample_method == "bootstrap"
        assert config.evaluation_ticks == 100
        assert config.parallel_workers == 8

    def test_bootstrap_validates_num_samples(self) -> None:
        """num_samples must be between 5 and 1000."""
        from payment_simulator.ai_cash_mgmt.config.game_config import BootstrapConfig
        from pydantic import ValidationError

        # Valid
        BootstrapConfig(num_samples=5)
        BootstrapConfig(num_samples=1000)

        # Invalid
        with pytest.raises(ValidationError):
            BootstrapConfig(num_samples=4)

        with pytest.raises(ValidationError):
            BootstrapConfig(num_samples=1001)


class TestConvergenceCriteria:
    """Test convergence criteria configuration."""

    def test_convergence_defaults(self) -> None:
        """ConvergenceCriteria should have sensible defaults."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
        )

        config = ConvergenceCriteria()

        assert config.metric == "total_cost"
        assert config.stability_threshold == 0.05
        assert config.stability_window == 5
        assert config.max_iterations == 50
        assert config.improvement_threshold == 0.01

    def test_convergence_validates_thresholds(self) -> None:
        """Convergence thresholds must be in valid ranges."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
        )
        from pydantic import ValidationError

        # Invalid stability_threshold
        with pytest.raises(ValidationError):
            ConvergenceCriteria(stability_threshold=0.0001)  # Too low

        with pytest.raises(ValidationError):
            ConvergenceCriteria(stability_threshold=0.6)  # Too high


class TestOutputConfig:
    """Test output configuration."""

    def test_output_defaults(self) -> None:
        """OutputConfig should have sensible defaults."""
        from payment_simulator.ai_cash_mgmt.config.game_config import OutputConfig

        config = OutputConfig()

        assert "results" in config.database_path
        assert config.save_policy_diffs is True
        assert config.save_iteration_metrics is True
        assert config.verbose is True


class TestGameConfig:
    """Test complete game configuration."""

    def test_game_config_minimal(self) -> None:
        """GameConfig with minimal required fields."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            GameConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )

        config = GameConfig(
            game_id="test-game-001",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.AFTER_EOD,
            ),
        )

        assert config.game_id == "test-game-001"
        assert config.master_seed == 42
        assert "BANK_A" in config.optimized_agents

    def test_game_config_validates_optimized_agents(self) -> None:
        """optimized_agents must have at least one agent."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            GameConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GameConfig(
                game_id="test",
                scenario_config="test.yaml",
                master_seed=42,
                optimized_agents={},  # Empty!
                optimization_schedule=OptimizationSchedule(
                    type=OptimizationScheduleType.AFTER_EOD,
                ),
            )

    def test_get_llm_config_for_agent_returns_specific_config(self) -> None:
        """get_llm_config_for_agent returns agent-specific config when set."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            GameConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
            LLMConfig,
        )

        config = GameConfig(
            game_id="test",
            scenario_config="test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(
                    llm_config=LLMConfig(
                        provider="anthropic",
                        model="claude-sonnet-4-5-20250929",
                    )
                ),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.AFTER_EOD,
            ),
        )

        llm_config = config.get_llm_config_for_agent("BANK_A")

        assert llm_config.provider == "anthropic"
        assert llm_config.model == "claude-sonnet-4-5-20250929"

    def test_get_llm_config_for_agent_returns_default_when_not_specified(
        self,
    ) -> None:
        """get_llm_config_for_agent returns default config when agent has none."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            GameConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
            LLMConfig,
        )

        config = GameConfig(
            game_id="test",
            scenario_config="test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),  # No llm_config
            },
            default_llm_config=LLMConfig(
                provider="openai",
                model="gpt-5.1",
                reasoning_effort="high",
            ),
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.AFTER_EOD,
            ),
        )

        llm_config = config.get_llm_config_for_agent("BANK_A")

        assert llm_config.provider == "openai"
        assert llm_config.model == "gpt-5.1"
        assert llm_config.reasoning_effort == "high"

    def test_get_optimized_agent_ids(self) -> None:
        """get_optimized_agent_ids returns list of agent IDs."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            GameConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )

        config = GameConfig(
            game_id="test",
            scenario_config="test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
                "BANK_C": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.AFTER_EOD,
            ),
        )

        agent_ids = config.get_optimized_agent_ids()

        assert set(agent_ids) == {"BANK_A", "BANK_B", "BANK_C"}

    def test_game_config_from_yaml(self) -> None:
        """GameConfig should load from YAML file."""
        from payment_simulator.ai_cash_mgmt.config.game_config import GameConfig

        yaml_content = """
game_id: yaml-test-001
scenario_config: scenarios/test.yaml
master_seed: 12345
optimized_agents:
  BANK_A:
    llm_config:
      provider: openai
      model: gpt-5.1
      reasoning_effort: high
  BANK_B:
    llm_config:
      provider: anthropic
      model: claude-sonnet-4-5-20250929
      thinking_budget: 10000
default_llm_config:
  provider: openai
  model: gpt-4.1
optimization_schedule:
  type: after_eod
  min_remaining_days: 2
bootstrap:
  num_samples: 30
  sample_method: bootstrap
convergence:
  stability_threshold: 0.03
  max_iterations: 100
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            config = GameConfig.from_yaml(f.name)

        assert config.game_id == "yaml-test-001"
        assert config.master_seed == 12345
        assert "BANK_A" in config.optimized_agents
        assert "BANK_B" in config.optimized_agents
        assert config.bootstrap.num_samples == 30
        assert config.convergence.max_iterations == 100

        # Verify per-agent LLM configs
        llm_a = config.get_llm_config_for_agent("BANK_A")
        assert llm_a.provider == "openai"
        assert llm_a.reasoning_effort == "high"

        llm_b = config.get_llm_config_for_agent("BANK_B")
        assert llm_b.provider == "anthropic"
        assert llm_b.thinking_budget == 10000


class TestPolicyConstraints:
    """Test policy constraints configuration."""

    def test_policy_constraints_defaults_to_none(self) -> None:
        """PolicyConstraints fields should default to None."""
        from payment_simulator.ai_cash_mgmt.config.game_config import PolicyConstraints

        config = PolicyConstraints()

        assert config.allowed_parameters is None
        assert config.allowed_fields is None
        assert config.allowed_actions is None

    def test_policy_constraints_accepts_lists(self) -> None:
        """PolicyConstraints should accept constraint lists."""
        from payment_simulator.ai_cash_mgmt.config.game_config import PolicyConstraints

        config = PolicyConstraints(
            allowed_parameters=[
                {"name": "amount_threshold", "type": "int", "min": 0, "max": 1000000}
            ],
            allowed_fields=["amount", "priority", "sender_id"],
            allowed_actions=["submit", "queue", "hold"],
        )

        assert len(config.allowed_parameters) == 1
        assert "amount" in config.allowed_fields
        assert "submit" in config.allowed_actions
