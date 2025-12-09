# PydanticAI Migration Plan for Castro Experiments

## Overview

Migrate the LLM management in `experiments/castro/` to use PydanticAI, achieving:
- Support for all common providers with minimal configuration
- Streamlined model selection using `provider:model` pattern
- Provider-specific reasoning/thinking settings (temperature, thinking tokens, reasoning effort)
- Compatibility with `ai_cash_mgmt` module's `LLMClientProtocol`
- Foundation for future PydanticAI agent features

## Current Architecture

### Components
1. **CastroLLMClient** (`castro/llm_client.py`):
   - Manual handling of Anthropic/OpenAI clients
   - Provider-specific API calls with custom logic for GPT-5 reasoning
   - Implements `LLMClientProtocol` for ai_cash_mgmt compatibility

2. **LLMConfig** (`ai_cash_mgmt/config/llm_config.py`):
   - `LLMProviderType` enum (openai, anthropic, google)
   - Fields: `reasoning_effort`, `thinking_budget`, `temperature`
   - Provider detection via enum

3. **CastroExperiment** (`castro/experiments.py`):
   - Stores `llm_provider`, `llm_model`, `llm_temperature` separately
   - Auto-detects provider from model name

### Issues with Current Approach
- Separate code paths for each provider
- Manual SDK management for each provider
- Hard to add new providers (Gemini, etc.)
- Provider-specific logic scattered across files

## PydanticAI Benefits

1. **Unified Model String**: `anthropic:claude-sonnet-4-5` or `openai:gpt-5.1`
2. **Provider-Agnostic Agent**: Single API for all providers
3. **ModelSettings**: Provider-specific settings via typed dictionaries
4. **Future Features**: Tools, structured output, result validation

## Migration Design

### New Model Configuration

```python
# castro/model_config.py

from dataclasses import dataclass
from typing import Any

@dataclass
class ModelConfig:
    """Configuration for PydanticAI model.

    Uses provider:model string format for unified model selection.

    Examples:
        >>> config = ModelConfig("anthropic:claude-sonnet-4-5")
        >>> config = ModelConfig("openai:gpt-5.1", reasoning_effort="high")
        >>> config = ModelConfig("google:gemini-2.5-flash", thinking_budget=8000)
    """
    model: str  # "provider:model" format
    temperature: float = 0.0
    max_tokens: int = 30000

    # Provider-specific settings
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: "low", "medium", "high"
    thinking_config: dict[str, Any] | None = None  # Google Gemini thinking

    @property
    def provider(self) -> str:
        """Extract provider from model string."""
        return self.model.split(":")[0] if ":" in self.model else "anthropic"

    @property
    def model_name(self) -> str:
        """Extract model name from model string."""
        return self.model.split(":", 1)[1] if ":" in self.model else self.model

    def to_model_settings(self) -> dict[str, Any]:
        """Convert to PydanticAI ModelSettings dict."""
        settings: dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if self.provider == "anthropic" and self.thinking_budget:
            settings["anthropic_thinking"] = {"budget_tokens": self.thinking_budget}
        elif self.provider == "openai" and self.reasoning_effort:
            settings["openai_reasoning_effort"] = self.reasoning_effort
        elif self.provider == "google" and self.thinking_config:
            settings["google_thinking_config"] = self.thinking_config

        return settings
```

### PydanticAI LLM Client

```python
# castro/pydantic_llm_client.py

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

class PydanticAILLMClient:
    """LLM client using PydanticAI.

    Implements LLMClientProtocol for compatibility with ai_cash_mgmt.
    """

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._agent = Agent(
            config.model,
            system_prompt=SYSTEM_PROMPT,
        )

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate policy via PydanticAI agent."""
        user_prompt = self._build_user_prompt(prompt, current_policy, context)

        result = await self._agent.run(
            user_prompt,
            model_settings=self._config.to_model_settings(),
        )

        return self._parse_policy(result.output)
```

### Simplified Experiment Definition

```python
# castro/experiments.py (updated)

@dataclass
class CastroExperiment:
    name: str
    description: str
    scenario_path: Path

    # Model configuration - unified string format
    model: str = "anthropic:claude-sonnet-4-5"
    temperature: float = 0.0
    thinking_budget: int | None = None  # For Claude extended thinking
    reasoning_effort: str | None = None  # For GPT reasoning

    def get_model_config(self) -> ModelConfig:
        return ModelConfig(
            model=self.model,
            temperature=self.temperature,
            thinking_budget=self.thinking_budget,
            reasoning_effort=self.reasoning_effort,
        )

# Factory functions updated
def create_exp1(model: str = "anthropic:claude-sonnet-4-5") -> CastroExperiment:
    return CastroExperiment(
        name="exp1",
        description="2-Period Deterministic Nash Equilibrium",
        scenario_path=Path("configs/exp1_2period.yaml"),
        model=model,
        # ... other config
    )
```

## Compatibility with ai_cash_mgmt

The `LLMClientProtocol` interface from `ai_cash_mgmt/optimization/policy_optimizer.py`:

```python
class LLMClientProtocol(Protocol):
    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]: ...
```

**PydanticAI client maintains this interface** - no changes needed to PolicyOptimizer.

### Future Enhancement: Using PydanticAI for Result Evaluation

PydanticAI's structured output can validate policy responses:

```python
from pydantic import BaseModel

class PolicyResponse(BaseModel):
    version: str
    policy_id: str
    parameters: dict[str, float]
    payment_tree: dict
    strategic_collateral_tree: dict | None = None

# Agent with structured output
agent = Agent(
    model,
    output_type=PolicyResponse,
    system_prompt=SYSTEM_PROMPT,
)
```

This can replace manual JSON parsing and validation in future iterations.

## Implementation Steps

**Status: ✅ COMPLETED (2025-12-09)**

### Phase 1: Add Dependency
- [x] Add `pydantic-ai` to `experiments/castro/pyproject.toml`
- [x] Verify mypy/pyright compatibility

### Phase 2: Create Model Configuration
- [x] Create `castro/model_config.py` with `ModelConfig` dataclass
- [x] Add provider detection and settings conversion
- [x] Write unit tests for ModelConfig (22 tests in `test_model_config.py`)

### Phase 3: Implement PydanticAI Client
- [x] Create `castro/pydantic_llm_client.py`
- [x] Implement `generate_policy()` using PydanticAI Agent
- [x] Preserve JSON parsing logic from current client
- [x] Write unit tests (mock PydanticAI - 22 tests in `test_pydantic_llm_client.py`)

### Phase 4: Update CastroExperiment
- [x] Update dataclass to use `model: str` with provider:model format
- [x] Replace `get_llm_config()` with `get_model_config()`
- [x] Update factory functions
- [x] Update tests

### Phase 5: Update Runner
- [x] Update `ExperimentRunner` to use new ModelConfig
- [x] Replace `CastroLLMClient` instantiation with `PydanticAILLMClient`
- [x] Verify LLMClientProtocol compatibility

### Phase 6: Update CLI
- [x] Update `--model` option to accept provider:model format
- [x] Add optional `--thinking-budget` and `--reasoning-effort` flags
- [x] Update help text and examples

### Phase 7: Cleanup
- [x] Remove `castro/llm_client.py` (old implementation)
- [x] Remove `LLMConfig` usage from castro (keep in ai_cash_mgmt)
- [x] Update documentation (README.md, CLAUDE.md, architecture.md)

## Testing Strategy

### Unit Tests
1. `test_model_config.py`:
   - Provider extraction from model string
   - Settings conversion for each provider
   - Default value handling

2. `test_pydantic_llm_client.py`:
   - Mock PydanticAI agent
   - Prompt building
   - JSON parsing
   - Error handling

### Integration Tests
1. Full experiment run with different providers (requires API keys):
   - `anthropic:claude-sonnet-4-5`
   - `openai:gpt-5.1`
   - `google:gemini-2.5-flash`

2. Verify determinism with same seed

### Regression Tests
- All existing tests in `tests/test_experiments.py` must pass
- CLI commands must work with new format

## Rollback Plan

If issues arise:
1. Keep both implementations during migration
2. Add `--legacy` flag to CLI for old client
3. Revert to old client if PydanticAI issues occur

## Success Criteria

1. All existing tests pass
2. New model string format works: `anthropic:claude-sonnet-4-5`
3. Thinking budget configurable for Claude
4. Reasoning effort configurable for GPT
5. Easy to add new providers (just change model string)
6. ai_cash_mgmt PolicyOptimizer works with new client
7. No performance regression

## Timeline

This migration follows TDD principles:
1. Write tests first for each component
2. Implement to pass tests
3. Refactor as needed
4. Verify full test suite passes after each phase
