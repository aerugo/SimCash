"""Tests for PydanticAI LLM client.

Tests cover:
- Client initialization with different providers
- Prompt building
- JSON parsing and validation
- Policy field normalization
- Error handling
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from castro.pydantic_llm_client import SYSTEM_PROMPT
from payment_simulator.llm import LLMConfig


@pytest.fixture
def mock_agent():
    """Fixture that mocks the PydanticAI Agent class."""
    with patch("castro.pydantic_llm_client.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        MockAgent.return_value = mock_agent_instance
        yield MockAgent


@pytest.fixture
def client(mock_agent):
    """Create a PydanticAILLMClient with mocked Agent."""
    from castro.pydantic_llm_client import PydanticAILLMClient

    config = LLMConfig(model="anthropic:claude-sonnet-4-5")
    return PydanticAILLMClient(config)


class TestClientInitialization:
    """Tests for client initialization."""

    def test_init_with_anthropic_model(self, mock_agent) -> None:
        """Client should initialize with Anthropic model."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)
        assert client.model == "anthropic:claude-sonnet-4-5"

        # Verify Agent was called with correct model string
        mock_agent.assert_called_once()
        call_args = mock_agent.call_args
        assert call_args[0][0] == "anthropic:claude-sonnet-4-5"

    def test_init_with_openai_model(self, mock_agent) -> None:
        """Client should initialize with OpenAI model."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model="openai:gpt-5.1", reasoning_effort="high")
        client = PydanticAILLMClient(config)
        assert client.model == "openai:gpt-5.1"

    def test_init_with_google_model(self, mock_agent) -> None:
        """Client should initialize with Google model (mapped to google-gla)."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model="google:gemini-2.5-flash")
        client = PydanticAILLMClient(config)
        assert client.model == "google:gemini-2.5-flash"

        # Verify Agent was called with google-gla prefix
        call_args = mock_agent.call_args
        assert call_args[0][0] == "google-gla:gemini-2.5-flash"

    def test_create_llm_client_convenience_function(self, mock_agent) -> None:
        """create_llm_client should create configured client."""
        from castro.pydantic_llm_client import create_llm_client

        client = create_llm_client(
            "anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        assert client.model == "anthropic:claude-sonnet-4-5"


class TestPromptBuilding:
    """Tests for prompt building."""

    def test_build_user_prompt_basic(self, client) -> None:
        """User prompt should include policy and prompt."""
        prompt = client._build_user_prompt(
            prompt="Optimize this policy",
            current_policy={"version": "2.0", "policy_id": "test"},
            context={},
        )

        assert "Optimize this policy" in prompt
        assert '"version": "2.0"' in prompt
        assert '"policy_id": "test"' in prompt

    def test_build_user_prompt_with_history(self, client) -> None:
        """User prompt should include history when provided."""
        prompt = client._build_user_prompt(
            prompt="Optimize this policy",
            current_policy={"version": "2.0"},
            context={
                "history": [
                    {"iteration": 1, "cost": 10000},
                    {"iteration": 2, "cost": 8000},
                ]
            },
        )

        assert "Iteration 1" in prompt
        assert "Iteration 2" in prompt
        assert "$100.00" in prompt  # 10000 cents = $100.00
        assert "$80.00" in prompt  # 8000 cents = $80.00


class TestJSONParsing:
    """Tests for JSON parsing and validation."""

    def test_parse_valid_json(self, client) -> None:
        """Valid JSON should be parsed correctly."""
        response = '{"version": "2.0", "policy_id": "test", "payment_tree": {"type": "action", "node_id": "a", "action": "Release"}}'
        policy = client._parse_policy(response)

        assert policy["version"] == "2.0"
        assert policy["policy_id"] == "test"

    def test_parse_json_with_markdown_code_block(self, client) -> None:
        """JSON in markdown code block should be extracted."""
        response = """```json
{"version": "2.0", "policy_id": "test"}
```"""
        policy = client._parse_policy(response)
        assert policy["version"] == "2.0"

    def test_parse_json_with_markdown_no_lang(self, client) -> None:
        """JSON in markdown code block without lang should be extracted."""
        response = """```
{"version": "2.0", "policy_id": "test"}
```"""
        policy = client._parse_policy(response)
        assert policy["version"] == "2.0"

    def test_parse_invalid_json_raises(self, client) -> None:
        """Invalid JSON should raise ValueError."""
        with pytest.raises(ValueError, match="Failed to parse"):
            client._parse_policy("not valid json {")

    def test_ensure_required_fields_adds_version(self, client) -> None:
        """Missing version should be added."""
        policy: dict[str, Any] = {"policy_id": "test"}
        client._ensure_required_fields(policy)
        assert policy["version"] == "2.0"

    def test_ensure_required_fields_adds_policy_id(self, client) -> None:
        """Missing policy_id should be added."""
        policy: dict[str, Any] = {"version": "2.0"}
        client._ensure_required_fields(policy)
        assert "policy_id" in policy
        assert policy["policy_id"].startswith("llm_policy_")


class TestNodeIdGeneration:
    """Tests for automatic node_id generation."""

    def test_add_node_id_to_action(self, client) -> None:
        """Missing node_id should be added to action nodes."""
        policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "test",
            "payment_tree": {
                "type": "action",
                "action": "Release",
            },
        }
        client._ensure_node_ids(policy)
        assert "node_id" in policy["payment_tree"]

    def test_add_node_id_to_condition(self, client) -> None:
        """Missing node_id should be added to condition nodes."""
        policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "test",
            "payment_tree": {
                "type": "condition",
                "condition": {"op": "<", "left": {"value": 1}, "right": {"value": 2}},
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        }
        client._ensure_node_ids(policy)
        assert "node_id" in policy["payment_tree"]
        assert "node_id" in policy["payment_tree"]["on_true"]
        assert "node_id" in policy["payment_tree"]["on_false"]

    def test_preserve_existing_node_ids(self, client) -> None:
        """Existing node_ids should not be overwritten."""
        policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "test",
            "payment_tree": {
                "type": "action",
                "node_id": "my_custom_id",
                "action": "Release",
            },
        }
        client._ensure_node_ids(policy)
        assert policy["payment_tree"]["node_id"] == "my_custom_id"

    def test_add_node_ids_to_both_trees(self, client) -> None:
        """Both payment_tree and strategic_collateral_tree should get node_ids."""
        policy: dict[str, Any] = {
            "version": "2.0",
            "policy_id": "test",
            "payment_tree": {"type": "action", "action": "Release"},
            "strategic_collateral_tree": {"type": "action", "action": "HoldCollateral"},
        }
        client._ensure_node_ids(policy)
        assert "node_id" in policy["payment_tree"]
        assert "node_id" in policy["strategic_collateral_tree"]


class TestGeneratePolicy:
    """Tests for generate_policy method with mocked Agent."""

    @pytest.mark.asyncio
    async def test_generate_policy_success(self, mock_agent) -> None:
        """generate_policy should return parsed policy from agent."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")

        # Configure mock return value
        mock_result = MagicMock()
        mock_result.output = '{"version": "2.0", "policy_id": "test", "payment_tree": {"type": "action", "node_id": "a", "action": "Release"}}'

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result
        mock_agent.return_value = mock_agent_instance

        client = PydanticAILLMClient(config)

        policy = await client.generate_policy(
            prompt="Optimize",
            current_policy={"version": "1.0"},
            context={},
        )

        assert policy["version"] == "2.0"
        assert policy["policy_id"] == "test"
        mock_agent_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_policy_passes_model_settings(self, mock_agent) -> None:
        """generate_policy should pass model settings to agent."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model=
            "anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
            temperature=0.5,
        )

        mock_result = MagicMock()
        mock_result.output = '{"version": "2.0", "policy_id": "test"}'

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result
        mock_agent.return_value = mock_agent_instance

        client = PydanticAILLMClient(config)

        await client.generate_policy(
            prompt="Optimize",
            current_policy={},
            context={},
        )

        # Verify model_settings was passed
        call_args = mock_agent_instance.run.call_args
        model_settings = call_args.kwargs["model_settings"]
        assert model_settings["temperature"] == 0.5
        assert "anthropic_thinking" in model_settings

    @pytest.mark.asyncio
    async def test_generate_policy_invalid_json_raises(self, mock_agent) -> None:
        """generate_policy should raise on invalid JSON response."""
        from castro.pydantic_llm_client import PydanticAILLMClient

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")

        mock_result = MagicMock()
        mock_result.output = "not valid json"

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result
        mock_agent.return_value = mock_agent_instance

        client = PydanticAILLMClient(config)

        with pytest.raises(ValueError, match="Failed to parse"):
            await client.generate_policy(
                prompt="Optimize",
                current_policy={},
                context={},
            )


class TestSystemPrompt:
    """Tests for system prompt content."""

    def test_system_prompt_includes_policy_structure(self) -> None:
        """System prompt should describe policy structure."""
        assert "version" in SYSTEM_PROMPT
        assert "policy_id" in SYSTEM_PROMPT
        assert "payment_tree" in SYSTEM_PROMPT

    def test_system_prompt_mentions_node_id(self) -> None:
        """System prompt should emphasize node_id requirement."""
        assert "node_id" in SYSTEM_PROMPT
        assert "CRITICAL" in SYSTEM_PROMPT or "MUST" in SYSTEM_PROMPT

    def test_system_prompt_mentions_actions(self) -> None:
        """System prompt should mention valid actions."""
        assert "Release" in SYSTEM_PROMPT
        assert "Hold" in SYSTEM_PROMPT
