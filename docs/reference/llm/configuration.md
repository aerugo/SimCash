# LLM Configuration

> Unified configuration for all LLM providers

## LLMConfig

The `LLMConfig` dataclass provides unified configuration for all supported LLM providers.

### Import

```python
from payment_simulator.llm import LLMConfig
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | *required* | Model in `provider:model` format |
| `temperature` | `float` | `0.0` | Sampling temperature (0.0 = deterministic) |
| `max_retries` | `int` | `3` | Maximum retry attempts on failure |
| `timeout_seconds` | `int` | `120` | Request timeout in seconds |
| `system_prompt` | `str \| None` | `None` | Default system prompt for requests |
| `thinking_budget` | `int \| None` | `None` | Anthropic extended thinking budget (tokens) |
| `reasoning_effort` | `str \| None` | `None` | OpenAI reasoning effort: `low`, `medium`, `high` |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `provider` | `str` | Extracts provider from model string |
| `model_name` | `str` | Extracts model name from model string |

### Basic Usage

```python
from payment_simulator.llm import LLMConfig

# Basic configuration
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
)

# Access properties
print(config.provider)     # "anthropic"
print(config.model_name)   # "claude-sonnet-4-5"
```

## Model String Format

Models are specified using the `provider:model` format:

```
provider:model-name
```

### Supported Providers

| Provider | Prefix | Example Models |
|----------|--------|---------------|
| Anthropic | `anthropic:` | claude-sonnet-4-5, claude-opus-4 |
| OpenAI | `openai:` | gpt-4o, gpt-4-turbo, o1, o3 |
| Google | `google:` | gemini-2.5-flash, gemini-2.5-pro |

### Examples

```python
# Anthropic Claude
config = LLMConfig(model="anthropic:claude-sonnet-4-5")

# OpenAI GPT-4
config = LLMConfig(model="openai:gpt-4o")

# OpenAI O1 (reasoning model)
config = LLMConfig(model="openai:o1")

# Google Gemini
config = LLMConfig(model="google:gemini-2.5-flash")
```

## Provider-Specific Settings

### Anthropic Extended Thinking

Claude models support extended thinking, which provides more detailed reasoning:

```python
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    thinking_budget=8000,  # Token budget for thinking
)
```

The `thinking_budget` specifies the maximum tokens Claude can use for internal reasoning before generating a response.

### OpenAI Reasoning Effort

OpenAI's reasoning models (O1, O3) support adjustable reasoning effort:

```python
config = LLMConfig(
    model="openai:o1",
    reasoning_effort="high",  # "low", "medium", or "high"
)
```

| Level | Description |
|-------|-------------|
| `low` | Minimal reasoning, faster response |
| `medium` | Balanced reasoning |
| `high` | Maximum reasoning, slower but more thorough |

### Temperature Settings

Temperature controls randomness in model outputs:

```python
# Deterministic output (recommended for policy optimization)
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
)

# More creative output
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.7,
)
```

**Recommendation**: Use `temperature=0.0` for policy optimization to ensure reproducible results.

## Retry and Timeout Settings

```python
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    max_retries=5,        # Retry up to 5 times on failure
    timeout_seconds=180,  # 3 minute timeout
)
```

## YAML Configuration

When using experiment YAML files, LLM configuration is specified in the `llm` section:

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.
  # Optional provider-specific:
  # thinking_budget: 8000      # Anthropic only
  # reasoning_effort: high     # OpenAI only
```

The `system_prompt` field allows defining the prompt inline in the YAML. For experiments, this is the **preferred approach** as it makes the experiment self-contained.

## Complete Examples

### Anthropic with Extended Thinking

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
    thinking_budget=8000,
    max_retries=3,
    timeout_seconds=120,
)

client = PydanticAILLMClient(config)
```

### OpenAI with High Reasoning

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

config = LLMConfig(
    model="openai:o1",
    temperature=0.0,  # Note: O1 may ignore temperature
    reasoning_effort="high",
    timeout_seconds=300,  # Longer timeout for reasoning
)

client = PydanticAILLMClient(config)
```

### Google Gemini

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

config = LLMConfig(
    model="google:gemini-2.5-flash",
    temperature=0.0,
)

client = PydanticAILLMClient(config)
```

## Environment Variables

API keys are typically configured via environment variables:

| Provider | Environment Variable |
|----------|---------------------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google | `GOOGLE_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` |

## Related Documentation

- [LLM Protocols](protocols.md) - Protocol definitions
- [Experiment CLI](../cli/commands/experiment.md) - Using in experiments

---

*Last updated: 2025-12-11*
