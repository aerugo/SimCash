"""TDD tests for prompt_customization in experiment config.

Tests for the new prompt_customization field that replaces system_prompt
in the llm section. The new structure allows:
- `all`: customization for all agents
- `<agent_id>`: customization for specific agent

These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest


class TestPromptCustomizationConfig:
    """Tests for PromptCustomization dataclass."""

    def test_prompt_customization_dataclass_exists(self) -> None:
        """PromptCustomization dataclass can be imported."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        assert PromptCustomization is not None

    def test_prompt_customization_with_all_field(self) -> None:
        """PromptCustomization accepts 'all' field."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(all="Global customization for all agents")
        assert config.all == "Global customization for all agents"

    def test_prompt_customization_with_agent_specific_field(self) -> None:
        """PromptCustomization accepts agent-specific fields."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            agent_customizations={"BANK_A": "Customization for Bank A"}
        )
        assert config.agent_customizations["BANK_A"] == "Customization for Bank A"

    def test_prompt_customization_all_defaults_to_none(self) -> None:
        """PromptCustomization 'all' defaults to None."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization()
        assert config.all is None

    def test_prompt_customization_agent_customizations_defaults_to_empty(self) -> None:
        """PromptCustomization agent_customizations defaults to empty dict."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization()
        assert config.agent_customizations == {}

    def test_prompt_customization_get_for_agent_returns_all_only(self) -> None:
        """get_for_agent() returns 'all' when only 'all' is set."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(all="Global prompt")
        result = config.get_for_agent("BANK_A")
        assert result == "Global prompt"

    def test_prompt_customization_get_for_agent_returns_agent_only(self) -> None:
        """get_for_agent() returns agent-specific when only that is set."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            agent_customizations={"BANK_A": "Agent A prompt"}
        )
        result = config.get_for_agent("BANK_A")
        assert result == "Agent A prompt"

    def test_prompt_customization_get_for_agent_combines_all_and_specific(self) -> None:
        """get_for_agent() combines 'all' and agent-specific, 'all' first."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            all="Global instructions",
            agent_customizations={"BANK_A": "Agent A specific"}
        )
        result = config.get_for_agent("BANK_A")
        assert "Global instructions" in result
        assert "Agent A specific" in result
        # 'all' should come before agent-specific
        assert result.index("Global") < result.index("Agent A")

    def test_prompt_customization_get_for_agent_unknown_agent_returns_all(self) -> None:
        """get_for_agent() returns 'all' for unknown agent."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            all="Global prompt",
            agent_customizations={"BANK_A": "Agent A prompt"}
        )
        result = config.get_for_agent("UNKNOWN_AGENT")
        assert result == "Global prompt"

    def test_prompt_customization_get_for_agent_none_when_empty(self) -> None:
        """get_for_agent() returns None when no customization."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization()
        result = config.get_for_agent("BANK_A")
        assert result is None

    def test_prompt_customization_blank_string_is_ignored(self) -> None:
        """Blank string customizations are treated as no customization."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            all="",  # Blank string
            agent_customizations={"BANK_A": ""}  # Blank string
        )
        result = config.get_for_agent("BANK_A")
        assert result is None

    def test_prompt_customization_whitespace_only_is_ignored(self) -> None:
        """Whitespace-only customizations are treated as no customization."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(
            all="   \n\t  ",  # Whitespace only
        )
        result = config.get_for_agent("BANK_A")
        assert result is None

    def test_prompt_customization_is_frozen(self) -> None:
        """PromptCustomization is immutable (frozen)."""
        from payment_simulator.experiments.config.experiment_config import (
            PromptCustomization,
        )

        config = PromptCustomization(all="Test")
        with pytest.raises(AttributeError):
            config.all = "Modified"  # type: ignore[misc]


class TestExperimentConfigPromptCustomization:
    """Tests for prompt_customization in ExperimentConfig YAML parsing."""

    def test_experiment_config_parses_prompt_customization_all(
        self, tmp_path: Path
    ) -> None:
        """ExperimentConfig.from_yaml() parses prompt_customization.all."""
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
            prompt_customization:
              all: |
                You are optimizing a Castro game.
                Generate valid JSON policies.
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.prompt_customization is not None
        assert "Castro game" in config.prompt_customization.all

    def test_experiment_config_parses_agent_specific_customization(
        self, tmp_path: Path
    ) -> None:
        """ExperimentConfig.from_yaml() parses agent-specific customizations."""
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
            prompt_customization:
              BANK_A: "Bank A should post 0 collateral"
              BANK_B: "Bank B should post 20% collateral"
            optimized_agents:
              - BANK_A
              - BANK_B
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.prompt_customization is not None
        assert "Bank A should post 0" in config.prompt_customization.get_for_agent("BANK_A")
        assert "Bank B should post 20%" in config.prompt_customization.get_for_agent("BANK_B")

    def test_experiment_config_parses_all_and_agent_customizations(
        self, tmp_path: Path
    ) -> None:
        """ExperimentConfig.from_yaml() parses both 'all' and agent customizations."""
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
            prompt_customization:
              all: "General: This is a 2-period game."
              BANK_A: "Specific: Bank A optimal is 0.0"
            optimized_agents:
              - BANK_A
              - BANK_B
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)

        # BANK_A should get both
        bank_a_prompt = config.prompt_customization.get_for_agent("BANK_A")
        assert "General: This is a 2-period game" in bank_a_prompt
        assert "Specific: Bank A optimal is 0.0" in bank_a_prompt

        # BANK_B should only get 'all'
        bank_b_prompt = config.prompt_customization.get_for_agent("BANK_B")
        assert "General: This is a 2-period game" in bank_b_prompt
        assert "Specific: Bank A" not in bank_b_prompt

    def test_experiment_config_prompt_customization_optional(
        self, tmp_path: Path
    ) -> None:
        """prompt_customization is optional in ExperimentConfig."""
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
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.prompt_customization is None

    def test_experiment_config_ignores_unknown_agent_in_customization(
        self, tmp_path: Path
    ) -> None:
        """Unknown agent keys in prompt_customization are ignored at parse time."""
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
            prompt_customization:
              all: "Global prompt"
              UNKNOWN_BANK: "This should be ignored"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        # Should not raise - unknown agents are just stored, ignored at use time
        config = ExperimentConfig.from_yaml(config_path)
        assert config.prompt_customization is not None
        # BANK_A only gets 'all' since UNKNOWN_BANK doesn't apply
        assert config.prompt_customization.get_for_agent("BANK_A") == "Global prompt"

    def test_experiment_config_empty_prompt_customization_becomes_none(
        self, tmp_path: Path
    ) -> None:
        """Empty prompt_customization block is treated as None."""
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
            prompt_customization: {}
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        # Empty dict should result in None or empty PromptCustomization
        if config.prompt_customization is not None:
            assert config.prompt_customization.get_for_agent("BANK_A") is None


class TestPromptCustomizationMultipleAgents:
    """Tests for prompt_customization with multiple agents."""

    def test_three_agents_each_get_correct_customization(self, tmp_path: Path) -> None:
        """Each of 3 agents gets correct combined customization."""
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
            prompt_customization:
              all: "Global: Minimize total cost."
              BANK_A: "A: Should be aggressive."
              BANK_B: "B: Should be conservative."
              BANK_C: "C: Should balance."
            optimized_agents:
              - BANK_A
              - BANK_B
              - BANK_C
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)

        # Each agent should get global + their specific
        assert "Global: Minimize" in config.prompt_customization.get_for_agent("BANK_A")
        assert "A: Should be aggressive" in config.prompt_customization.get_for_agent("BANK_A")

        assert "Global: Minimize" in config.prompt_customization.get_for_agent("BANK_B")
        assert "B: Should be conservative" in config.prompt_customization.get_for_agent("BANK_B")

        assert "Global: Minimize" in config.prompt_customization.get_for_agent("BANK_C")
        assert "C: Should balance" in config.prompt_customization.get_for_agent("BANK_C")

    def test_agent_without_specific_only_gets_all(self, tmp_path: Path) -> None:
        """Agent without specific customization only gets 'all'."""
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
            prompt_customization:
              all: "Global only"
              BANK_A: "A specific"
            optimized_agents:
              - BANK_A
              - BANK_B
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)

        # BANK_B has no specific, so only gets 'all'
        bank_b_prompt = config.prompt_customization.get_for_agent("BANK_B")
        assert bank_b_prompt == "Global only"
        assert "A specific" not in bank_b_prompt


class TestBackwardCompatibility:
    """Tests for backward compatibility with old system_prompt field."""

    def test_old_system_prompt_still_works_but_deprecated(
        self, tmp_path: Path
    ) -> None:
        """Old system_prompt in llm section still works but is deprecated."""
        from payment_simulator.experiments.config import ExperimentConfig

        # This is the OLD format that should still work
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
              system_prompt: |
                Old style system prompt.
                Still supported for backward compatibility.
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        # Old system_prompt should be converted to prompt_customization.all
        assert config.prompt_customization is not None
        assert "Old style system prompt" in config.prompt_customization.all

    def test_new_format_takes_precedence_over_old(
        self, tmp_path: Path
    ) -> None:
        """New prompt_customization takes precedence over old system_prompt."""
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
              system_prompt: "Old format - should be ignored"
            prompt_customization:
              all: "New format - should be used"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert "New format - should be used" in config.prompt_customization.all
        assert "Old format" not in config.prompt_customization.all
