# LLM Integration Module

> Unified LLM abstraction for policy optimization experiments

The `payment_simulator.llm` module provides a unified interface for integrating Large Language Models into the payment simulation system. It supports multiple providers (Anthropic, OpenAI, Google) with a consistent API.

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration](configuration.md) | LLMConfig reference and provider settings |
| [Protocols](protocols.md) | Protocol definitions for LLM clients |

## Quick Start

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

# Create configuration
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
)

# Create client
client = PydanticAILLMClient(config)

# Generate structured output
from pydantic import BaseModel

class PolicyUpdate(BaseModel):
    policy_id: str
    parameters: dict[str, float]

result = await client.generate_structured_output(
    prompt="Suggest policy parameters...",
    response_model=PolicyUpdate,
    system_prompt="You are a policy optimization assistant.",
)
```

## Key Components

### LLMConfig

Unified configuration for all LLM providers:

```python
from payment_simulator.llm import LLMConfig

# Anthropic with extended thinking
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
    thinking_budget=8000,
)

# OpenAI with reasoning effort
config = LLMConfig(
    model="openai:o1",
    reasoning_effort="high",
)

# Google Gemini
config = LLMConfig(
    model="google:gemini-2.5-flash",
)
```

### LLMClientProtocol

Protocol defining the LLM client interface:

```python
from payment_simulator.llm import LLMClientProtocol

class LLMClientProtocol(Protocol):
    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T: ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str: ...
```

### PydanticAILLMClient

Implementation using PydanticAI for structured output:

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

config = LLMConfig(model="anthropic:claude-sonnet-4-5")
client = PydanticAILLMClient(config)

# Structured output with automatic parsing
result = await client.generate_structured_output(
    prompt="...",
    response_model=MyModel,
)

# Plain text generation
text = await client.generate_text(prompt="...")
```

### AuditCaptureLLMClient

Wrapper that captures interactions for audit trails:

```python
from payment_simulator.llm import (
    LLMConfig,
    PydanticAILLMClient,
    AuditCaptureLLMClient,
)

# Create base client
base = PydanticAILLMClient(LLMConfig(model="anthropic:claude-sonnet-4-5"))

# Wrap with audit capture
client = AuditCaptureLLMClient(base)

# Use client normally
result = await client.generate_text("Hello")

# Retrieve interaction for audit
interaction = client.get_last_interaction()
print(f"Prompt: {interaction.user_prompt}")
print(f"Response: {interaction.raw_response}")
print(f"Latency: {interaction.latency_seconds}s")
```

## Supported Providers

| Provider | Model Examples | Special Features |
|----------|---------------|------------------|
| `anthropic` | claude-sonnet-4-5, claude-opus-4 | Extended thinking (`thinking_budget`) |
| `openai` | gpt-4o, o1, o3 | Reasoning effort (`reasoning_effort`) |
| `google` | gemini-2.5-flash | Thinking config |

## Model String Format

Models are specified in `provider:model` format:

```
provider:model-name
```

Examples:
- `anthropic:claude-sonnet-4-5`
- `openai:gpt-4o`
- `openai:o1`
- `google:gemini-2.5-flash`

## Module Exports

```python
from payment_simulator.llm import (
    # Configuration
    LLMConfig,

    # Protocols
    LLMClientProtocol,

    # Implementations
    PydanticAILLMClient,
    AuditCaptureLLMClient,

    # Data classes
    LLMInteraction,
)
```

## Related Documentation

- [Experiment CLI](../cli/commands/experiment.md) - Using LLM in experiments
- [AI Cash Management](../ai_cash_mgmt/index.md) - Bootstrap evaluation

## Implementation Details

**Location**: `api/payment_simulator/llm/`

| File | Purpose |
|------|---------|
| `config.py` | LLMConfig dataclass |
| `protocol.py` | LLMClientProtocol definition |
| `pydantic_client.py` | PydanticAI implementation |
| `audit_wrapper.py` | Audit capture wrapper |

---

*Last updated: 2025-12-10*
