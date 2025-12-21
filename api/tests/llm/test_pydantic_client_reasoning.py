"""Tests for PydanticAILLMClient reasoning extraction.

These tests verify that the PydanticAI client correctly passes
model settings and extracts reasoning from ThinkingPart objects.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.pydantic_client import PydanticAILLMClient
from payment_simulator.llm.result import LLMResult


class MockPolicy(BaseModel):
    """Mock policy for testing."""

    name: str


class TestPydanticAIClientModelSettings:
    """Tests for model settings being passed to PydanticAI Agent."""

    @pytest.fixture
    def client_with_reasoning(self) -> PydanticAILLMClient:
        """Create client configured for reasoning."""
        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="medium",
            reasoning_summary="detailed",
        )
        return PydanticAILLMClient(config)

    @pytest.fixture
    def client_without_reasoning(self) -> PydanticAILLMClient:
        """Create client without reasoning config."""
        config = LLMConfig(model="openai:gpt-4o")
        return PydanticAILLMClient(config)

    @pytest.mark.asyncio
    async def test_model_settings_passed_to_agent(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify model settings are passed to PydanticAI Agent."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="test")
            mock_result.all_messages.return_value = []
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            # Verify model_settings was passed
            call_kwargs = mock_agent_cls.call_args.kwargs
            assert "model_settings" in call_kwargs
            settings = call_kwargs["model_settings"]
            assert settings.get("openai_reasoning_effort") == "medium"
            assert settings.get("openai_reasoning_summary") == "detailed"


class TestPydanticAIClientReasoningExtraction:
    """Tests for reasoning extraction in PydanticAILLMClient."""

    @pytest.fixture
    def client_with_reasoning(self) -> PydanticAILLMClient:
        """Create client configured for reasoning."""
        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="medium",
            reasoning_summary="detailed",
        )
        return PydanticAILLMClient(config)

    @pytest.fixture
    def client_without_reasoning(self) -> PydanticAILLMClient:
        """Create client without reasoning config."""
        config = LLMConfig(model="openai:gpt-4o")
        return PydanticAILLMClient(config)

    @pytest.mark.asyncio
    async def test_reasoning_extracted_from_thinking_parts(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify reasoning is extracted from ThinkingPart in messages."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            # Create mock ThinkingPart
            mock_thinking_part = MagicMock()
            mock_thinking_part.__class__.__name__ = "ThinkingPart"
            mock_thinking_part.content = "I analyzed the options and decided..."

            # Create mock message containing the thinking part
            mock_message = MagicMock()
            mock_message.parts = [mock_thinking_part]

            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="test")
            mock_result.all_messages.return_value = [mock_message]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            assert isinstance(result, LLMResult)
            assert result.reasoning_summary == "I analyzed the options and decided..."

    @pytest.mark.asyncio
    async def test_reasoning_none_when_no_thinking_parts(
        self, client_without_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify reasoning is None when no ThinkingPart present."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            # Create mock message without thinking parts
            mock_text_part = MagicMock()
            mock_text_part.__class__.__name__ = "TextPart"
            mock_text_part.content = "Here is the policy..."

            mock_message = MagicMock()
            mock_message.parts = [mock_text_part]

            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="test")
            mock_result.all_messages.return_value = [mock_message]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_without_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            assert isinstance(result, LLMResult)
            assert result.reasoning_summary is None

    @pytest.mark.asyncio
    async def test_multiple_thinking_parts_concatenated(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify multiple ThinkingParts are concatenated."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            # Create multiple thinking parts
            mock_thinking_1 = MagicMock()
            mock_thinking_1.__class__.__name__ = "ThinkingPart"
            mock_thinking_1.content = "First, I consider..."

            mock_thinking_2 = MagicMock()
            mock_thinking_2.__class__.__name__ = "ThinkingPart"
            mock_thinking_2.content = "Then, I evaluate..."

            mock_message = MagicMock()
            mock_message.parts = [mock_thinking_1, mock_thinking_2]

            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="test")
            mock_result.all_messages.return_value = [mock_message]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            assert result.reasoning_summary is not None
            assert "First, I consider..." in result.reasoning_summary
            assert "Then, I evaluate..." in result.reasoning_summary

    @pytest.mark.asyncio
    async def test_generate_structured_output_returns_llm_result(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify return type is LLMResult with correct data type."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="fifo_policy")
            mock_result.all_messages.return_value = []
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            assert isinstance(result, LLMResult)
            assert isinstance(result.data, MockPolicy)
            assert result.data.name == "fifo_policy"

    @pytest.mark.asyncio
    async def test_generate_text_returns_llm_result(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify generate_text returns LLMResult."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = "plain text response"
            mock_result.all_messages.return_value = []
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_text(prompt="test")

            assert isinstance(result, LLMResult)
            assert result.data == "plain text response"

    @pytest.mark.asyncio
    async def test_reasoning_from_multiple_messages(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify reasoning extracted from multiple messages."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            # Create thinking parts across multiple messages
            mock_thinking_1 = MagicMock()
            mock_thinking_1.__class__.__name__ = "ThinkingPart"
            mock_thinking_1.content = "Initial analysis..."

            mock_thinking_2 = MagicMock()
            mock_thinking_2.__class__.__name__ = "ThinkingPart"
            mock_thinking_2.content = "Further consideration..."

            mock_message_1 = MagicMock()
            mock_message_1.parts = [mock_thinking_1]

            mock_message_2 = MagicMock()
            mock_message_2.parts = [mock_thinking_2]

            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.output = MockPolicy(name="test")
            mock_result.all_messages.return_value = [mock_message_1, mock_message_2]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

            assert result.reasoning_summary is not None
            assert "Initial analysis..." in result.reasoning_summary
            assert "Further consideration..." in result.reasoning_summary
