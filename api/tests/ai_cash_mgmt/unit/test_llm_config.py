"""Unit tests for LLMConfig and AgentOptimizationConfig.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestLLMConfig:
    """Test LLM configuration model."""

    def test_llm_config_default_values(self) -> None:
        """LLMConfig should have sensible defaults."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        config = LLMConfig()

        assert config.provider == "openai"
        assert config.model == "gpt-4.1"
        assert config.temperature == 0.0  # Deterministic by default
        assert config.max_retries >= 1
        assert config.timeout_seconds >= 10

    def test_llm_config_custom_values(self) -> None:
        """LLMConfig should accept custom values."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            max_retries=5,
            timeout_seconds=300,
        )

        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.temperature == 0.7
        assert config.max_retries == 5
        assert config.timeout_seconds == 300

    def test_llm_config_openai_reasoning_effort(self) -> None:
        """LLMConfig should support OpenAI reasoning_effort."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-5.1",
            reasoning_effort="high",
        )

        assert config.reasoning_effort == "high"

    def test_llm_config_anthropic_thinking_budget(self) -> None:
        """LLMConfig should support Anthropic thinking_budget."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-5-20250929",
            thinking_budget=10000,
        )

        assert config.thinking_budget == 10000

    def test_llm_config_validates_temperature_range(self) -> None:
        """Temperature must be between 0.0 and 2.0."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig
        from pydantic import ValidationError

        # Valid temperatures
        LLMConfig(temperature=0.0)
        LLMConfig(temperature=1.0)
        LLMConfig(temperature=2.0)

        # Invalid temperatures
        with pytest.raises(ValidationError):
            LLMConfig(temperature=-0.1)

        with pytest.raises(ValidationError):
            LLMConfig(temperature=2.1)

    def test_llm_config_validates_max_retries(self) -> None:
        """Max retries must be between 1 and 10."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig
        from pydantic import ValidationError

        # Valid
        LLMConfig(max_retries=1)
        LLMConfig(max_retries=10)

        # Invalid
        with pytest.raises(ValidationError):
            LLMConfig(max_retries=0)

        with pytest.raises(ValidationError):
            LLMConfig(max_retries=11)

    def test_llm_config_validates_timeout(self) -> None:
        """Timeout must be between 10 and 600 seconds."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig
        from pydantic import ValidationError

        # Valid
        LLMConfig(timeout_seconds=10)
        LLMConfig(timeout_seconds=600)

        # Invalid
        with pytest.raises(ValidationError):
            LLMConfig(timeout_seconds=9)

        with pytest.raises(ValidationError):
            LLMConfig(timeout_seconds=601)

    def test_llm_config_validates_reasoning_effort(self) -> None:
        """Reasoning effort must be valid value."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig
        from pydantic import ValidationError

        # Valid values
        LLMConfig(reasoning_effort="low")
        LLMConfig(reasoning_effort="medium")
        LLMConfig(reasoning_effort="high")
        LLMConfig(reasoning_effort=None)

        # Invalid
        with pytest.raises(ValidationError):
            LLMConfig(reasoning_effort="invalid")

    def test_llm_config_serialization(self) -> None:
        """LLMConfig should serialize to dict correctly."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-5.1",
            reasoning_effort="high",
        )

        data = config.model_dump()

        assert data["provider"] == "openai"
        assert data["model"] == "gpt-5.1"
        assert data["reasoning_effort"] == "high"

    def test_llm_config_from_dict(self) -> None:
        """LLMConfig should be creatable from dict."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMConfig

        data = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250929",
            "thinking_budget": 5000,
        }

        config = LLMConfig.model_validate(data)

        assert config.provider == "anthropic"
        assert config.thinking_budget == 5000


class TestAgentOptimizationConfig:
    """Test per-agent optimization configuration."""

    def test_agent_config_default_no_llm(self) -> None:
        """AgentOptimizationConfig should default to no LLM config."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )

        config = AgentOptimizationConfig()

        assert config.llm_config is None

    def test_agent_config_with_llm(self) -> None:
        """AgentOptimizationConfig should accept LLM config."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
            LLMConfig,
        )

        llm = LLMConfig(provider="anthropic", model="claude-sonnet-4-5-20250929")
        config = AgentOptimizationConfig(llm_config=llm)

        assert config.llm_config is not None
        assert config.llm_config.provider == "anthropic"

    def test_agent_config_from_dict_with_nested_llm(self) -> None:
        """AgentOptimizationConfig should parse nested LLM config from dict."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )

        data = {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-5.1",
                "reasoning_effort": "high",
            }
        }

        config = AgentOptimizationConfig.model_validate(data)

        assert config.llm_config is not None
        assert config.llm_config.provider == "openai"
        assert config.llm_config.reasoning_effort == "high"

    def test_agent_config_serialization(self) -> None:
        """AgentOptimizationConfig should serialize correctly."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
            LLMConfig,
        )

        config = AgentOptimizationConfig(
            llm_config=LLMConfig(provider="google", model="gemini-2.5-pro")
        )

        data = config.model_dump()

        assert data["llm_config"]["provider"] == "google"
        assert data["llm_config"]["model"] == "gemini-2.5-pro"


class TestLLMProviderType:
    """Test LLM provider type enum."""

    def test_provider_type_values(self) -> None:
        """LLMProviderType should have expected values."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import LLMProviderType

        assert LLMProviderType.OPENAI == "openai"
        assert LLMProviderType.ANTHROPIC == "anthropic"
        assert LLMProviderType.GOOGLE == "google"

    def test_llm_config_accepts_enum_provider(self) -> None:
        """LLMConfig should accept enum values for provider."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            LLMConfig,
            LLMProviderType,
        )

        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)

        assert config.provider == "anthropic"


class TestReasoningEffortType:
    """Test reasoning effort type enum."""

    def test_reasoning_effort_values(self) -> None:
        """ReasoningEffortType should have expected values."""
        from payment_simulator.ai_cash_mgmt.config.llm_config import ReasoningEffortType

        assert ReasoningEffortType.LOW == "low"
        assert ReasoningEffortType.MEDIUM == "medium"
        assert ReasoningEffortType.HIGH == "high"
