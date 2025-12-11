"""TDD tests for generic experiment LLM client.

Phase 16.1: Tests for ExperimentLLMClient in core.
These tests MUST FAIL before implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestExperimentLLMClientBasic:
    """Basic tests for ExperimentLLMClient creation."""

    def test_import_from_experiments_runner(self) -> None:
        """ExperimentLLMClient can be imported from experiments.runner."""
        from payment_simulator.experiments.runner import ExperimentLLMClient

        assert ExperimentLLMClient is not None

    def test_creates_with_llm_config(self) -> None:
        """ExperimentLLMClient can be created with LLMConfig."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="You are a payment optimization expert.",
        )

        client = ExperimentLLMClient(config)
        assert client is not None

    def test_uses_system_prompt_from_config(self) -> None:
        """Client uses system_prompt from LLMConfig."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        custom_prompt = "You are a custom policy generator."
        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt=custom_prompt,
        )

        client = ExperimentLLMClient(config)
        assert client.system_prompt == custom_prompt

    def test_creates_without_system_prompt(self) -> None:
        """Client works when system_prompt is None."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")

        client = ExperimentLLMClient(config)
        assert client.system_prompt is None

    def test_model_property_returns_model_string(self) -> None:
        """model property returns the model string."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="openai:gpt-4o")
        client = ExperimentLLMClient(config)

        assert client.model == "openai:gpt-4o"


class TestExperimentLLMClientInteraction:
    """Tests for LLM interaction capture."""

    def test_has_generate_policy_method(self) -> None:
        """Client has async generate_policy method."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        assert hasattr(client, "generate_policy")
        # Should be async
        import inspect

        assert inspect.iscoroutinefunction(client.generate_policy)

    def test_captures_interactions_for_audit(self) -> None:
        """All LLM interactions are captured for audit replay."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        # Should have methods for retrieving interactions
        assert hasattr(client, "get_last_interaction")
        assert hasattr(client, "get_all_interactions")
        assert hasattr(client, "clear_interactions")

    def test_get_last_interaction_initially_none(self) -> None:
        """get_last_interaction returns None before any calls."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        assert client.get_last_interaction() is None

    def test_get_all_interactions_initially_empty(self) -> None:
        """get_all_interactions returns empty list before any calls."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        assert client.get_all_interactions() == []


class TestLLMInteractionDataclass:
    """Tests for LLMInteraction dataclass."""

    def test_llm_interaction_importable(self) -> None:
        """LLMInteraction can be imported from experiments.runner."""
        from payment_simulator.experiments.runner import LLMInteraction

        assert LLMInteraction is not None

    def test_llm_interaction_has_required_fields(self) -> None:
        """LLMInteraction has all required fields for audit."""
        from payment_simulator.experiments.runner import LLMInteraction

        interaction = LLMInteraction(
            system_prompt="System prompt here",
            user_prompt="User prompt here",
            raw_response='{"policy_id": "test"}',
            parsed_policy={"policy_id": "test"},
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )

        assert interaction.system_prompt == "System prompt here"
        assert interaction.user_prompt == "User prompt here"
        assert interaction.raw_response == '{"policy_id": "test"}'
        assert interaction.parsed_policy == {"policy_id": "test"}
        assert interaction.parsing_error is None
        assert interaction.prompt_tokens == 100
        assert interaction.completion_tokens == 50
        assert interaction.latency_seconds == 1.5

    def test_llm_interaction_is_frozen(self) -> None:
        """LLMInteraction is immutable (frozen dataclass)."""
        from payment_simulator.experiments.runner import LLMInteraction

        interaction = LLMInteraction(
            system_prompt="System",
            user_prompt="User",
            raw_response="{}",
        )

        with pytest.raises((AttributeError, TypeError)):
            interaction.system_prompt = "Modified"  # type: ignore[misc]


class TestExperimentLLMClientConfig:
    """Tests for configuration handling."""

    def test_respects_max_retries_from_config(self) -> None:
        """Client uses max_retries from LLMConfig."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5", max_retries=5)
        client = ExperimentLLMClient(config)

        assert client.max_retries == 5

    def test_respects_temperature_from_config(self) -> None:
        """Client uses temperature from LLMConfig."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5", temperature=0.7)
        client = ExperimentLLMClient(config)

        assert client.temperature == 0.7

    def test_default_temperature_is_zero(self) -> None:
        """Default temperature is 0.0 for deterministic output."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        assert client.temperature == 0.0


class TestPolicyParsing:
    """Tests for policy parsing logic."""

    def test_has_parse_policy_method(self) -> None:
        """Client has parse_policy method for extracting JSON."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        assert hasattr(client, "parse_policy")

    def test_parse_policy_extracts_json(self) -> None:
        """parse_policy extracts valid JSON from response."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        response = '{"policy_id": "test", "version": "2.0"}'
        policy = client.parse_policy(response)

        assert policy["policy_id"] == "test"
        assert policy["version"] == "2.0"

    def test_parse_policy_handles_markdown_code_block(self) -> None:
        """parse_policy extracts JSON from markdown code blocks."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        response = """Here's the policy:
```json
{"policy_id": "markdown_test", "version": "2.0"}
```
"""
        policy = client.parse_policy(response)

        assert policy["policy_id"] == "markdown_test"

    def test_parse_policy_raises_on_invalid_json(self) -> None:
        """parse_policy raises ValueError on invalid JSON."""
        from payment_simulator.experiments.runner import ExperimentLLMClient
        from payment_simulator.llm import LLMConfig

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = ExperimentLLMClient(config)

        with pytest.raises(ValueError, match="parse"):
            client.parse_policy("This is not JSON at all")


class TestBackwardCompatibility:
    """Tests for Castro backward compatibility (skipped in API env)."""

    @pytest.mark.skip(reason="Castro not available in API test environment")
    def test_castro_can_use_core_llm_client(self) -> None:
        """Castro can import and use ExperimentLLMClient from core."""
        from payment_simulator.experiments.runner import ExperimentLLMClient

        # In Castro environment, this would test actual integration
        pass
