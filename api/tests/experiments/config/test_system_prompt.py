"""TDD tests for system_prompt in experiment config.

Phase 15.1: Tests for system_prompt field in LLMConfig and ExperimentConfig.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest


class TestLLMConfigSystemPrompt:
    """Tests for system_prompt field in LLMConfig."""

    def test_llm_config_accepts_system_prompt(self) -> None:
        """LLMConfig can have system_prompt field."""
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="You are a helpful assistant.",
        )
        assert config.system_prompt == "You are a helpful assistant."

    def test_llm_config_system_prompt_default_none(self) -> None:
        """LLMConfig system_prompt defaults to None."""
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.system_prompt is None

    def test_llm_config_multiline_system_prompt(self) -> None:
        """LLMConfig accepts multiline system_prompt."""
        from payment_simulator.llm import LLMConfig

        prompt = dedent("""
            You are an expert in payment systems.

            Your task is to optimize policies.
            Follow these rules:
            1. Generate valid JSON
            2. Respect parameter bounds
        """).strip()

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt=prompt,
        )
        assert "payment systems" in config.system_prompt
        assert "parameter bounds" in config.system_prompt


class TestExperimentConfigSystemPrompt:
    """Tests for system_prompt in ExperimentConfig YAML parsing."""

    def test_experiment_config_parses_inline_system_prompt(self, tmp_path: Path) -> None:
        """ExperimentConfig.from_yaml() parses inline system_prompt."""
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
              system_prompt: |
                You are an expert in payment optimization.
                Generate valid JSON policies.
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.llm.system_prompt is not None
        assert "payment optimization" in config.llm.system_prompt
        assert "valid JSON" in config.llm.system_prompt

    def test_experiment_config_loads_system_prompt_from_file(
        self, tmp_path: Path
    ) -> None:
        """ExperimentConfig.from_yaml() loads system_prompt_file content."""
        from payment_simulator.experiments.config import ExperimentConfig

        # Create prompt file
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("You are a policy optimization expert.\nFollow the rules.")

        yaml_content = dedent(f"""
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
              system_prompt_file: "{prompt_file}"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.llm.system_prompt is not None
        assert "policy optimization expert" in config.llm.system_prompt

    def test_system_prompt_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """Missing system_prompt_file raises FileNotFoundError."""
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
              system_prompt_file: "nonexistent_prompt.md"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml(config_path)

    def test_system_prompt_and_file_both_present_uses_inline(
        self, tmp_path: Path
    ) -> None:
        """Inline system_prompt takes precedence over system_prompt_file."""
        from payment_simulator.experiments.config import ExperimentConfig

        # Create prompt file
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Content from file.")

        yaml_content = dedent(f"""
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
              system_prompt: "Inline prompt content."
              system_prompt_file: "{prompt_file}"
            optimized_agents:
              - BANK_A
        """)

        config_path = tmp_path / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.llm.system_prompt == "Inline prompt content."
        assert "Content from file" not in config.llm.system_prompt

    def test_relative_system_prompt_file_resolved_from_yaml_dir(
        self, tmp_path: Path
    ) -> None:
        """system_prompt_file relative path resolved from YAML file directory."""
        from payment_simulator.experiments.config import ExperimentConfig

        # Create subdirectory structure
        exp_dir = tmp_path / "experiments"
        exp_dir.mkdir()
        prompts_dir = exp_dir / "prompts"
        prompts_dir.mkdir()

        # Create prompt file in prompts subdir
        prompt_file = prompts_dir / "policy.md"
        prompt_file.write_text("Policy optimization prompt from relative path.")

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
              system_prompt_file: "prompts/policy.md"
            optimized_agents:
              - BANK_A
        """)

        config_path = exp_dir / "exp.yaml"
        config_path.write_text(yaml_content)

        config = ExperimentConfig.from_yaml(config_path)
        assert config.llm.system_prompt is not None
        assert "relative path" in config.llm.system_prompt


class TestSystemPromptInvariant:
    """Tests for system_prompt invariants."""

    def test_system_prompt_is_immutable(self) -> None:
        """LLMConfig with system_prompt is frozen (immutable)."""
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="Test prompt",
        )

        with pytest.raises((AttributeError, TypeError)):
            config.system_prompt = "Modified"  # type: ignore[misc]

    def test_system_prompt_empty_string_is_valid(self) -> None:
        """Empty string system_prompt is valid (but probably not useful)."""
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="",
        )
        assert config.system_prompt == ""
