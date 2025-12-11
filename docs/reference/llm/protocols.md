# LLM Protocols

> Protocol definitions for LLM client implementations

## LLMClientProtocol

The `LLMClientProtocol` defines the interface that all LLM client implementations must follow.

### Import

```python
from payment_simulator.llm import LLMClientProtocol
```

### Definition

```python
from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMClientProtocol(Protocol):
    """Protocol for LLM clients."""

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM.

        Args:
            prompt: User prompt to send to the model.
            response_model: Pydantic model class for response parsing.
            system_prompt: Optional system prompt for context.

        Returns:
            Parsed response as instance of response_model.

        Raises:
            ValidationError: If response cannot be parsed.
            TimeoutError: If request times out.
        """
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM.

        Args:
            prompt: User prompt to send to the model.
            system_prompt: Optional system prompt for context.

        Returns:
            Raw text response from the model.
        """
        ...
```

### Methods

#### generate_structured_output

Generates a structured response that is automatically parsed into a Pydantic model.

```python
from pydantic import BaseModel
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

class PolicySuggestion(BaseModel):
    policy_id: str
    threshold: float
    rationale: str

config = LLMConfig(model="anthropic:claude-sonnet-4-5")
client = PydanticAILLMClient(config)

suggestion = await client.generate_structured_output(
    prompt="Suggest optimal threshold for payment timing...",
    response_model=PolicySuggestion,
    system_prompt="You are a payment policy optimization assistant.",
)

print(f"Threshold: {suggestion.threshold}")
print(f"Rationale: {suggestion.rationale}")
```

#### generate_text

Generates plain text output without structured parsing.

```python
config = LLMConfig(model="anthropic:claude-sonnet-4-5")
client = PydanticAILLMClient(config)

explanation = await client.generate_text(
    prompt="Explain the trade-off between delay costs and overdraft costs.",
    system_prompt="You are a payment systems expert.",
)

print(explanation)
```

## Implementations

### PydanticAILLMClient

The primary implementation using the PydanticAI library:

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

config = LLMConfig(model="anthropic:claude-sonnet-4-5")
client = PydanticAILLMClient(config)
```

### AuditCaptureLLMClient

A wrapper that captures all interactions for audit trails:

```python
from payment_simulator.llm import (
    LLMConfig,
    PydanticAILLMClient,
    AuditCaptureLLMClient,
    LLMInteraction,
)

# Create base client
base = PydanticAILLMClient(LLMConfig(model="anthropic:claude-sonnet-4-5"))

# Wrap with audit capture
client = AuditCaptureLLMClient(base)

# Use client
result = await client.generate_text("Hello")

# Get captured interaction
interaction: LLMInteraction = client.get_last_interaction()
```

## LLMInteraction

Data class for captured LLM interactions:

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class LLMInteraction:
    """Captured LLM interaction for audit trail."""

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `system_prompt` | `str` | System prompt sent to model |
| `user_prompt` | `str` | User prompt sent to model |
| `raw_response` | `str` | Raw response text |
| `parsed_policy` | `dict \| None` | Parsed structured output (if applicable) |
| `parsing_error` | `str \| None` | Error message if parsing failed |
| `prompt_tokens` | `int` | Tokens in the prompt |
| `completion_tokens` | `int` | Tokens in the completion |
| `latency_seconds` | `float` | Request latency in seconds |

### Usage

```python
interaction = client.get_last_interaction()

if interaction:
    print(f"Prompt: {interaction.user_prompt[:100]}...")
    print(f"Response: {interaction.raw_response[:100]}...")
    print(f"Latency: {interaction.latency_seconds:.2f}s")

    if interaction.parsing_error:
        print(f"Error: {interaction.parsing_error}")
```

## Custom Implementations

You can create custom LLM clients by implementing the protocol:

```python
from payment_simulator.llm import LLMClientProtocol

class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        return self._responses.get(prompt, "Default response")

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> object:
        # Return a mock instance
        return response_model(policy_id="mock", threshold=0.5)

# Use in tests
mock_client = MockLLMClient({"test": "mocked response"})
result = await mock_client.generate_text("test")
```

## Type Checking

The protocol supports runtime type checking with `@runtime_checkable`:

```python
from typing import runtime_checkable
from payment_simulator.llm import LLMClientProtocol

# Check if an object implements the protocol
client = PydanticAILLMClient(config)
assert isinstance(client, LLMClientProtocol)  # True
```

## Related Documentation

- [LLM Configuration](configuration.md) - Configuration options
- [LLM Module Index](index.md) - Module overview

---

*Last updated: 2025-12-10*
