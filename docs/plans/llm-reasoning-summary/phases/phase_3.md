# Phase 3: Update PydanticAILLMClient

**Status**: Pending
**Started**:

---

## Objective

Update `PydanticAILLMClient` to:
1. Pass model settings (temperature, reasoning_effort, reasoning_summary) to the PydanticAI Agent
2. Extract reasoning/thinking content from the response
3. Return `LLMResult[T]` with both data and reasoning

This is the core implementation phase where reasoning is actually captured.

---

## Invariants Enforced in This Phase

- INV-9: Policy Evaluation Identity - Reasoning capture is observational only; it does not affect the parsed policy data

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Create `api/tests/llm/test_pydantic_client_reasoning.py`:

**Test Cases**:
1. `test_model_settings_passed_to_agent` - Verify settings are applied
2. `test_reasoning_extracted_from_thinking_parts` - Extract ThinkingPart content
3. `test_reasoning_none_when_no_thinking_parts` - Handle no thinking
4. `test_multiple_thinking_parts_concatenated` - Multiple parts combined
5. `test_generate_structured_output_returns_llm_result` - Return type is LLMResult

```python
"""Tests for PydanticAILLMClient reasoning extraction."""

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
    async def test_model_settings_passed_to_agent(
        self, client_with_reasoning: PydanticAILLMClient
    ) -> None:
        """Verify model settings are passed to PydanticAI Agent."""
        with patch("payment_simulator.llm.pydantic_client.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.data = MockPolicy(name="test")
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
            mock_result.data = MockPolicy(name="test")
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
            mock_result.data = MockPolicy(name="test")
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
            mock_result.data = MockPolicy(name="test")
            mock_result.all_messages.return_value = [mock_message]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            result = await client_with_reasoning.generate_structured_output(
                prompt="test",
                response_model=MockPolicy,
            )

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
            mock_result.data = MockPolicy(name="fifo_policy")
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
```

### Step 3.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/llm/pydantic_client.py`:

```python
"""PydanticAI-based LLM client implementation.

This module provides the PydanticAILLMClient which uses PydanticAI
to interact with LLM providers and generate structured output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.result import LLMResult

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


class PydanticAILLMClient:
    """LLM client using PydanticAI for structured output.

    Implements LLMClientProtocol. Uses PydanticAI's Agent abstraction
    to handle LLM interactions and structured output parsing.

    Now supports reasoning/thinking capture for OpenAI reasoning models.
    Configure via LLMConfig.reasoning_summary to capture reasoning.

    Example:
        >>> config = LLMConfig(
        ...     model="openai:o1",
        ...     reasoning_effort="medium",
        ...     reasoning_summary="detailed",
        ... )
        >>> client = PydanticAILLMClient(config)
        >>> result = await client.generate_structured_output(prompt, PolicyModel)
        >>> result.data  # The parsed policy
        >>> result.reasoning_summary  # The LLM's reasoning (if captured)
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize with configuration."""
        self._config = config

    def _extract_reasoning(self, messages: list[ModelMessage]) -> str | None:
        """Extract reasoning/thinking content from messages.

        Iterates through all messages and parts, extracting content from
        ThinkingPart objects. Multiple thinking parts are concatenated
        with newlines.

        Args:
            messages: List of messages from agent.run() result.

        Returns:
            Concatenated reasoning content, or None if no thinking parts found.
        """
        reasoning_parts: list[str] = []

        for message in messages:
            if not hasattr(message, "parts"):
                continue
            for part in message.parts:
                # Check for ThinkingPart by class name (avoids import issues)
                if part.__class__.__name__ == "ThinkingPart":
                    content = getattr(part, "content", None)
                    if content:
                        reasoning_parts.append(str(content))

        if not reasoning_parts:
            return None
        return "\n\n".join(reasoning_parts)

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> LLMResult[T]:
        """Generate structured output from LLM.

        Uses PydanticAI to parse the LLM response into the specified
        Pydantic model type. If reasoning is configured, extracts
        thinking content from the response.

        Args:
            prompt: The user prompt to send to the LLM.
            response_model: Pydantic model type to parse response into.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing the parsed model and optional reasoning.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        # Get model settings from config
        model_settings = self._config.to_model_settings()

        agent: Agent[None, T] = Agent(
            model=self._config.full_model_string,
            result_type=response_model,
            system_prompt=system_prompt or "",
            model_settings=model_settings,
        )
        result = await agent.run(prompt)

        # Extract reasoning from messages
        reasoning = self._extract_reasoning(result.all_messages())

        return LLMResult(data=result.data, reasoning_summary=reasoning)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResult[str]:
        """Generate plain text from LLM.

        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt for context.

        Returns:
            LLMResult containing the text response and optional reasoning.

        Raises:
            Various PydanticAI exceptions on failure.
        """
        model_settings = self._config.to_model_settings()

        agent: Agent[None, str] = Agent(
            model=self._config.full_model_string,
            result_type=str,
            system_prompt=system_prompt or "",
            model_settings=model_settings,
        )
        result = await agent.run(prompt)

        reasoning = self._extract_reasoning(result.all_messages())

        return LLMResult(data=result.data, reasoning_summary=reasoning)
```

### Step 3.3: Refactor

- Consider importing ThinkingPart type for better type safety (if available)
- Add logging for reasoning extraction (optional)
- Ensure backward compatibility with callers expecting just data

---

## Implementation Details

### Extracting ThinkingPart Content

PydanticAI stores thinking/reasoning content in `ThinkingPart` objects within messages:

```python
# result.all_messages() returns list of ModelMessage
# Each ModelMessage has .parts containing various part types
# ThinkingPart.content contains the reasoning text
```

We check by class name to avoid import coupling:
```python
if part.__class__.__name__ == "ThinkingPart":
    content = getattr(part, "content", None)
```

### Model Settings

Pass all settings from `LLMConfig.to_model_settings()`:
```python
model_settings = self._config.to_model_settings()
agent = Agent(..., model_settings=model_settings)
```

### Backward Compatibility Consideration

**IMPORTANT**: This changes the return type from `T` to `LLMResult[T]`.

Callers must be updated:
```python
# Before
policy = await client.generate_structured_output(prompt, PolicyModel)

# After
result = await client.generate_structured_output(prompt, PolicyModel)
policy = result.data
reasoning = result.reasoning_summary
```

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/llm/pydantic_client.py` | MODIFY |
| `api/tests/llm/test_pydantic_client_reasoning.py` | CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/llm/test_pydantic_client_reasoning.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/llm/pydantic_client.py

# Lint
.venv/bin/python -m ruff check payment_simulator/llm/pydantic_client.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] Model settings correctly passed to Agent
- [ ] ThinkingPart content correctly extracted
- [ ] Multiple thinking parts concatenated
- [ ] Returns LLMResult with data and reasoning
- [ ] Works when no thinking parts present (returns None)
