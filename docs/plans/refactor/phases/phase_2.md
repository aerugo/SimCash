# Phase 2: LLM Module Extraction

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Medium
**Breaking Changes:** None (parallel implementation)

---

## Objectives

1. Create unified LLM configuration (`LLMConfig`)
2. Move `PydanticAILLMClient` to new module
3. Create `AuditCaptureLLMClient` wrapper
4. Ensure all exports from `payment_simulator.llm`

---

## TDD Test Specifications

### Test File: `api/tests/llm/test_config.py`

```python
"""Tests for LLMConfig dataclass."""

import pytest

from payment_simulator.llm.config import LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_creates_with_model_string(self) -> None:
        """LLMConfig creates from provider:model string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model == "anthropic:claude-sonnet-4-5"

    def test_provider_property_extracts_provider(self) -> None:
        """provider property extracts provider from model string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.provider == "anthropic"

    def test_model_name_property_extracts_model(self) -> None:
        """model_name property extracts model from string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model_name == "claude-sonnet-4-5"

    def test_defaults_temperature_to_zero(self) -> None:
        """Default temperature is 0.0 for determinism."""
        config = LLMConfig(model="openai:gpt-4o")
        assert config.temperature == 0.0

    def test_anthropic_thinking_budget(self) -> None:
        """Anthropic models support thinking_budget."""
        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        assert config.thinking_budget == 8000

    def test_openai_reasoning_effort(self) -> None:
        """OpenAI models support reasoning_effort."""
        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="high",
        )
        assert config.reasoning_effort == "high"

    def test_defaults_max_retries_to_three(self) -> None:
        """Default max_retries is 3."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.max_retries == 3

    def test_defaults_timeout_to_120_seconds(self) -> None:
        """Default timeout is 120 seconds."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.timeout_seconds == 120

    def test_is_immutable(self) -> None:
        """LLMConfig is immutable (frozen dataclass)."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        with pytest.raises(AttributeError):
            config.model = "different"  # type: ignore
```

### Test File: `api/tests/llm/test_audit_wrapper.py`

```python
"""Tests for audit capture wrapper."""

import pytest

from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)


class MockLLMClient:
    """Mock LLM client for testing."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        return f"Response to: {prompt}"

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> object:
        return response_model()


class TestLLMInteraction:
    """Tests for LLMInteraction dataclass."""

    def test_is_frozen(self) -> None:
        """LLMInteraction is immutable."""
        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )
        with pytest.raises(AttributeError):
            interaction.user_prompt = "modified"  # type: ignore

    def test_stores_all_fields(self) -> None:
        """LLMInteraction stores all provided fields."""
        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
            parsed_policy={"key": "value"},
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )
        assert interaction.system_prompt == "sys"
        assert interaction.user_prompt == "user"
        assert interaction.raw_response == "response"
        assert interaction.parsed_policy == {"key": "value"}
        assert interaction.prompt_tokens == 100


class TestAuditCaptureLLMClient:
    """Tests for AuditCaptureLLMClient."""

    def test_wraps_delegate_client(self) -> None:
        """Wrapper wraps a delegate client."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper._delegate is mock

    def test_get_last_interaction_returns_none_initially(self) -> None:
        """get_last_interaction returns None before any calls."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper.get_last_interaction() is None

    @pytest.mark.asyncio
    async def test_captures_text_interaction(self) -> None:
        """Captures interaction from generate_text call."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt", "system prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.user_prompt == "test prompt"
        assert interaction.system_prompt == "system prompt"

    @pytest.mark.asyncio
    async def test_captures_response_in_interaction(self) -> None:
        """Captures response text in interaction."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        result = await wrapper.generate_text("test prompt")

        assert result == "Response to: test prompt"
        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.raw_response == "Response to: test prompt"

    @pytest.mark.asyncio
    async def test_captures_latency(self) -> None:
        """Captures latency in interaction."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.latency_seconds >= 0

    def test_get_all_interactions_returns_empty_list_initially(self) -> None:
        """get_all_interactions returns empty list before any calls."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper.get_all_interactions() == []

    @pytest.mark.asyncio
    async def test_get_all_interactions_returns_all_interactions(self) -> None:
        """get_all_interactions returns all captured interactions."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("prompt1")
        await wrapper.generate_text("prompt2")

        interactions = wrapper.get_all_interactions()
        assert len(interactions) == 2
        assert interactions[0].user_prompt == "prompt1"
        assert interactions[1].user_prompt == "prompt2"
```

---

## Implementation Plan

### Step 2.1: Create LLMConfig

```python
# api/payment_simulator/llm/config.py
"""Unified LLM configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Unified LLM configuration.

    Supports multiple LLM providers with provider-specific options.
    All fields are immutable (frozen dataclass).

    Example:
        >>> config = LLMConfig(
        ...     model="anthropic:claude-sonnet-4-5",
        ...     thinking_budget=8000,
        ... )
        >>> config.provider
        'anthropic'
        >>> config.model_name
        'claude-sonnet-4-5'
    """

    # Model specification in provider:model format
    model: str

    # Common settings
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 120

    # Provider-specific (mutually exclusive)
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: low, medium, high

    @property
    def provider(self) -> str:
        """Extract provider from model string."""
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        """Extract model name from model string."""
        return self.model.split(":", 1)[1]
```

### Step 2.2: Create PydanticAILLMClient

```python
# api/payment_simulator/llm/pydantic_client.py
"""PydanticAI-based LLM client implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from pydantic_ai import Agent

from payment_simulator.llm.config import LLMConfig

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


class PydanticAILLMClient:
    """LLM client using PydanticAI for structured output.

    Implements LLMClientProtocol.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize with configuration."""
        self._config = config

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM."""
        agent: Agent[None, T] = Agent(
            model=self._config.model,
            result_type=response_model,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM."""
        agent: Agent[None, str] = Agent(
            model=self._config.model,
            result_type=str,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data
```

### Step 2.3: Create AuditCaptureLLMClient

```python
# api/payment_simulator/llm/audit_wrapper.py
"""Audit capture wrapper for LLM clients."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from payment_simulator.llm.protocol import LLMClientProtocol

T = TypeVar("T", bound="BaseModel")


@dataclass(frozen=True)
class LLMInteraction:
    """Captured LLM interaction for audit trail.

    Immutable record of a single LLM interaction.
    """

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float


class AuditCaptureLLMClient:
    """Wrapper that captures interactions for audit replay.

    Wraps any LLMClientProtocol implementation and captures
    all interactions for later replay.

    Example:
        >>> base_client = PydanticAILLMClient(config)
        >>> audit_client = AuditCaptureLLMClient(base_client)
        >>> result = await audit_client.generate_text("prompt")
        >>> interaction = audit_client.get_last_interaction()
        >>> interaction.user_prompt
        'prompt'
    """

    def __init__(self, delegate: LLMClientProtocol) -> None:
        """Initialize with delegate client."""
        self._delegate = delegate
        self._interactions: list[LLMInteraction] = []

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction."""
        return self._interactions[-1] if self._interactions else None

    def get_all_interactions(self) -> list[LLMInteraction]:
        """Get all captured interactions."""
        return list(self._interactions)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text and capture interaction."""
        start = time.perf_counter()
        result = await self._delegate.generate_text(prompt, system_prompt)
        latency = time.perf_counter() - start

        self._interactions.append(LLMInteraction(
            system_prompt=system_prompt or "",
            user_prompt=prompt,
            raw_response=result,
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=0,  # Not available from base client
            completion_tokens=0,
            latency_seconds=latency,
        ))

        return result

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output and capture interaction."""
        start = time.perf_counter()
        try:
            result = await self._delegate.generate_structured_output(
                prompt, response_model, system_prompt
            )
            latency = time.perf_counter() - start

            # Try to extract dict representation
            parsed: dict[str, Any] | None = None
            if hasattr(result, "model_dump"):
                parsed = result.model_dump()
            elif hasattr(result, "__dict__"):
                parsed = result.__dict__

            self._interactions.append(LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response=str(result),
                parsed_policy=parsed,
                parsing_error=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            ))

            return result

        except Exception as e:
            latency = time.perf_counter() - start
            self._interactions.append(LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response="",
                parsed_policy=None,
                parsing_error=str(e),
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            ))
            raise
```

### Step 2.4: Update Module Exports

```python
# api/payment_simulator/llm/__init__.py
"""LLM integration layer.

This module provides unified LLM abstraction for all modules
needing LLM capabilities.

Example:
    >>> from payment_simulator.llm import LLMConfig, PydanticAILLMClient
    >>> config = LLMConfig(model="anthropic:claude-sonnet-4-5")
    >>> client = PydanticAILLMClient(config)
"""

from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.protocol import LLMClientProtocol
from payment_simulator.llm.pydantic_client import PydanticAILLMClient

__all__ = [
    "LLMClientProtocol",
    "LLMConfig",
    "PydanticAILLMClient",
    "AuditCaptureLLMClient",
    "LLMInteraction",
]
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/config.py` | LLMConfig dataclass |
| `api/payment_simulator/llm/pydantic_client.py` | PydanticAI implementation |
| `api/payment_simulator/llm/audit_wrapper.py` | Audit capture wrapper |
| `api/tests/llm/test_config.py` | Config tests |
| `api/tests/llm/test_audit_wrapper.py` | Wrapper tests |

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/llm/__init__.py` | Add exports for new modules |

---

## Verification Checklist

### TDD Tests
- [ ] `test_creates_with_model_string` passes
- [ ] `test_provider_property_extracts_provider` passes
- [ ] `test_model_name_property_extracts_model` passes
- [ ] `test_defaults_temperature_to_zero` passes
- [ ] `test_anthropic_thinking_budget` passes
- [ ] `test_openai_reasoning_effort` passes
- [ ] `test_is_immutable` passes (LLMConfig)
- [ ] `test_is_frozen` passes (LLMInteraction)
- [ ] `test_wraps_delegate_client` passes
- [ ] `test_get_last_interaction_returns_none_initially` passes
- [ ] `test_captures_text_interaction` passes
- [ ] `test_captures_response_in_interaction` passes
- [ ] `test_captures_latency` passes
- [ ] `test_get_all_interactions_returns_empty_list_initially` passes
- [ ] `test_get_all_interactions_returns_all_interactions` passes

### Type Checking
```bash
cd api && .venv/bin/python -m mypy payment_simulator/llm/
```

### Import Verification
```bash
cd api && .venv/bin/python -c "from payment_simulator.llm import LLMConfig, PydanticAILLMClient, AuditCaptureLLMClient, LLMInteraction"
```

---

## Notes

Phase 2 creates the foundation for LLM integration that can be used by:
- Castro experiments (via adapter)
- Future experiments via experiment framework
- Any module needing LLM capabilities

Key design decisions:
- `LLMConfig` is frozen (immutable) for safety
- `AuditCaptureLLMClient` captures all interactions for replay
- `LLMInteraction` is frozen for audit integrity
- `PydanticAILLMClient` uses pydantic-ai for structured output

---

*Phase 2 Plan v1.0 - 2025-12-10*
