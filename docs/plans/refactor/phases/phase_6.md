# Phase 6: Castro Migration

**Status:** In Progress
**Created:** 2025-12-11
**Dependencies:** Phase 2 (LLM Module), Phase 4.6 (Terminology Cleanup)

---

## Objectives

Migrate Castro to use the new `payment_simulator.llm` module and remove deprecated local files.

### Goals

1. Update castro to import LLM components from `payment_simulator.llm`
2. Rename `MonteCarloContextBuilder` → `BootstrapContextBuilder`
3. Delete deprecated castro files
4. Maintain full backward compatibility
5. All existing tests continue to pass

### Non-Goals

- Rewriting castro's policy-specific LLM client logic
- Changing castro's public API
- Moving all of castro into payment_simulator

---

## Analysis

### Current State

Castro imports from local modules that duplicate `payment_simulator.llm`:

```python
# castro/runner.py
from castro.pydantic_llm_client import (
    AuditCaptureLLMClient,
    PydanticAILLMClient,
)
from castro.context_builder import MonteCarloContextBuilder

# castro/experiments.py
from castro.model_config import ModelConfig
```

### Migration Challenges

1. **LLMConfig gaps**: `payment_simulator.llm.LLMConfig` is missing:
   - `max_tokens` field
   - `thinking_config` field (Google)
   - `full_model_string` property (maps `google` → `google-gla`)
   - `to_model_settings()` method

2. **Specialized client**: Castro's `PydanticAILLMClient` has policy-specific logic:
   - `SYSTEM_PROMPT` for policy generation
   - `generate_policy()` and `generate_policy_with_audit()`
   - Policy parsing (`_parse_policy`, `_ensure_node_ids`)

3. **Terminology**: `MonteCarloContextBuilder` still uses old naming

### Migration Strategy

**Phase 6.2**: Extend `LLMConfig` with missing features
**Phase 6.3**: Update castro imports to use `payment_simulator.llm`
**Phase 6.4**: Rename `MonteCarloContextBuilder` → `BootstrapContextBuilder`
**Phase 6.5**: Delete deprecated files (`model_config.py`)
**Phase 6.6**: Verification testing

---

## Phase 6.2: Extend LLMConfig

### TDD Tests First

```python
# api/tests/llm/test_config.py - Add new tests

class TestLLMConfigExtended:
    """Tests for extended LLMConfig features."""

    def test_max_tokens_has_default(self) -> None:
        """LLMConfig has default max_tokens."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.max_tokens == 30000

    def test_thinking_config_for_google(self) -> None:
        """LLMConfig supports thinking_config for Google."""
        config = LLMConfig(
            model="google:gemini-2.5-flash",
            thinking_config={"thinking_budget": 8000},
        )
        assert config.thinking_config == {"thinking_budget": 8000}

    def test_full_model_string_maps_google_to_google_gla(self) -> None:
        """full_model_string maps google provider to google-gla."""
        config = LLMConfig(model="google:gemini-2.5-flash")
        assert config.full_model_string == "google-gla:gemini-2.5-flash"

    def test_full_model_string_preserves_other_providers(self) -> None:
        """full_model_string preserves non-google providers."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.full_model_string == "anthropic:claude-sonnet-4-5"

    def test_to_model_settings_basic(self) -> None:
        """to_model_settings returns basic settings dict."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        settings = config.to_model_settings()
        assert settings["temperature"] == 0.0
        assert settings["max_tokens"] == 30000
        assert settings["timeout"] == 120

    def test_to_model_settings_with_anthropic_thinking(self) -> None:
        """to_model_settings includes Anthropic thinking config."""
        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        settings = config.to_model_settings()
        assert "anthropic_thinking" in settings
        assert settings["anthropic_thinking"]["budget_tokens"] == 8000

    def test_to_model_settings_with_openai_reasoning(self) -> None:
        """to_model_settings includes OpenAI reasoning effort."""
        config = LLMConfig(
            model="openai:gpt-5.1",
            reasoning_effort="high",
        )
        settings = config.to_model_settings()
        assert settings["openai_reasoning_effort"] == "high"

    def test_to_model_settings_with_google_thinking(self) -> None:
        """to_model_settings includes Google thinking config."""
        config = LLMConfig(
            model="google:gemini-2.5-flash",
            thinking_config={"thinking_budget": 8000},
        )
        settings = config.to_model_settings()
        assert "google_thinking_config" in settings
```

### Implementation

Update `api/payment_simulator/llm/config.py`:

```python
@dataclass(frozen=True)
class LLMConfig:
    """Unified LLM configuration."""

    model: str
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 120
    max_tokens: int = 30000  # NEW

    # Provider-specific
    thinking_budget: int | None = None  # Anthropic
    reasoning_effort: str | None = None  # OpenAI
    thinking_config: dict[str, Any] | None = None  # Google (NEW)

    @property
    def provider(self) -> str:
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        return self.model.split(":", 1)[1]

    @property
    def full_model_string(self) -> str:  # NEW
        """Get provider:model string for PydanticAI.

        Maps provider aliases:
        - google → google-gla (Google AI Language API)
        """
        provider = self.provider
        model_name = self.model_name
        if provider == "google":
            return f"google-gla:{model_name}"
        return self.model

    def to_model_settings(self) -> dict[str, Any]:  # NEW
        """Convert to PydanticAI ModelSettings dict."""
        settings: dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_seconds,
        }

        if self.provider == "anthropic" and self.thinking_budget:
            settings["anthropic_thinking"] = {"budget_tokens": self.thinking_budget}
        elif self.provider == "openai" and self.reasoning_effort:
            settings["openai_reasoning_effort"] = self.reasoning_effort
            if self.reasoning_effort == "high":
                settings["max_tokens"] = max(self.max_tokens, 30000)
        elif self.provider == "google" and self.thinking_config:
            settings["google_thinking_config"] = self.thinking_config

        return settings
```

### Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/llm/config.py` | Add `max_tokens`, `thinking_config`, `full_model_string`, `to_model_settings()` |
| `api/tests/llm/test_config.py` | Add tests for new features |

### Verification

```bash
cd api && .venv/bin/python -m pytest tests/llm/test_config.py -v
```

---

## Phase 6.3: Update Castro Imports

### TDD Tests First

```python
# experiments/castro/tests/test_llm_import_migration.py
"""Tests for LLM import migration."""

def test_castro_uses_payment_simulator_llm_config() -> None:
    """castro.experiments imports LLMConfig from payment_simulator."""
    from castro.experiments import CastroExperiment
    from payment_simulator.llm import LLMConfig

    # Create experiment
    exp = CastroExperiment(
        name="test",
        description="Test",
        scenario_path=Path("test.yaml"),
    )

    # model_config should be compatible with LLMConfig
    assert hasattr(exp, 'get_llm_config')
    config = exp.get_llm_config()
    assert isinstance(config, LLMConfig)

def test_model_config_alias_works() -> None:
    """ModelConfig alias still works for backward compatibility."""
    # Should import without error (alias)
    from castro.experiments import ModelConfig

    config = ModelConfig(model="anthropic:claude-sonnet-4-5")
    assert config.model == "anthropic:claude-sonnet-4-5"
```

### Implementation

1. **Update `castro/experiments.py`**:

```python
# Change import from:
from castro.model_config import ModelConfig

# To:
from payment_simulator.llm import LLMConfig

# For backward compatibility:
ModelConfig = LLMConfig  # Alias
```

2. **Update `castro/pydantic_llm_client.py`**:

```python
# Change import from:
from castro.model_config import ModelConfig

# To:
from payment_simulator.llm import LLMConfig

# Update type hints:
def __init__(self, config: LLMConfig) -> None:  # Was ModelConfig
```

3. **Update `CastroExperiment.get_llm_config()`** method to return `LLMConfig`.

### Files to Modify

| File | Change |
|------|--------|
| `experiments/castro/castro/experiments.py` | Import `LLMConfig` from `payment_simulator.llm` |
| `experiments/castro/castro/pydantic_llm_client.py` | Import `LLMConfig` from `payment_simulator.llm` |

### Verification

```bash
cd experiments/castro && python -m pytest tests/test_llm_import_migration.py -v
cd experiments/castro && python -m pytest tests/ -v
```

---

## Phase 6.4: Rename MonteCarloContextBuilder

### TDD Tests First

```python
# experiments/castro/tests/test_context_builder_rename.py
"""Tests for context builder rename."""

def test_bootstrap_context_builder_exists() -> None:
    """BootstrapContextBuilder should exist in context_builder module."""
    from castro.context_builder import BootstrapContextBuilder
    assert BootstrapContextBuilder is not None

def test_monte_carlo_context_builder_alias_works() -> None:
    """MonteCarloContextBuilder alias works for backward compatibility."""
    from castro.context_builder import MonteCarloContextBuilder
    from castro.context_builder import BootstrapContextBuilder
    assert MonteCarloContextBuilder is BootstrapContextBuilder

def test_runner_uses_bootstrap_context_builder() -> None:
    """Runner should import BootstrapContextBuilder."""
    # Check that runner.py can be imported without error
    from castro.runner import ExperimentRunner
    assert ExperimentRunner is not None
```

### Implementation

1. **Update `castro/context_builder.py`**:
   - Rename class `MonteCarloContextBuilder` → `BootstrapContextBuilder`
   - Add alias: `MonteCarloContextBuilder = BootstrapContextBuilder`
   - Update all docstrings

2. **Update `castro/runner.py`**:
   - Change import: `from castro.context_builder import BootstrapContextBuilder`

3. **Update tests** that reference `MonteCarloContextBuilder`

### Files to Modify

| File | Change |
|------|--------|
| `experiments/castro/castro/context_builder.py` | Rename class, add alias |
| `experiments/castro/castro/runner.py` | Update import |
| `experiments/castro/tests/test_agent_context.py` | Update imports |
| `experiments/castro/tests/test_verbose_context_integration.py` | Update imports |

### Verification

```bash
cd experiments/castro && python -m pytest tests/test_context_builder_rename.py -v
cd experiments/castro && python -m pytest tests/ -v
```

---

## Phase 6.5: Delete Deprecated Files

### Pre-Deletion Verification

Before deleting any file, verify:
1. No imports reference the file (grep across codebase)
2. All tests pass
3. `castro run exp1 --dry-run` works

### Files to Delete

| File | Reason | Replaced By |
|------|--------|-------------|
| `experiments/castro/castro/model_config.py` | Merged into LLM module | `payment_simulator.llm.LLMConfig` |

### Files to KEEP (for now)

| File | Reason |
|------|--------|
| `experiments/castro/castro/pydantic_llm_client.py` | Contains policy-specific logic not in generic LLM module |
| `experiments/castro/castro/context_builder.py` | Active use, just renamed class |
| `experiments/castro/castro/simulation.py` | Still used for full simulation runs |

### Verification

```bash
# Check no imports reference deleted file
grep -r "from castro.model_config" experiments/castro/

# Should return empty (all imports updated)
```

---

## Phase 6.6: Verification Testing

### Manual Verification Checklist

- [ ] `castro run exp1 --dry-run` - verify config loads
- [ ] `castro run exp2 --dry-run` - verify config loads
- [ ] `castro run exp3 --dry-run` - verify config loads
- [ ] All castro unit tests pass
- [ ] All payment_simulator tests pass

### Automated Tests

```bash
# Run all castro tests
cd experiments/castro && python -m pytest tests/ -v

# Run all api tests
cd api && .venv/bin/python -m pytest -v

# Run specific LLM tests
cd api && .venv/bin/python -m pytest tests/llm/ -v
```

---

## Files Changed Summary

### Created
| File | Purpose |
|------|---------|
| `experiments/castro/tests/test_llm_import_migration.py` | Verify LLM import migration |
| `experiments/castro/tests/test_context_builder_rename.py` | Verify context builder rename |

### Modified
| File | Change |
|------|--------|
| `api/payment_simulator/llm/config.py` | Add `max_tokens`, `thinking_config`, `full_model_string`, `to_model_settings()` |
| `api/tests/llm/test_config.py` | Add tests for new features |
| `experiments/castro/castro/experiments.py` | Import from `payment_simulator.llm` |
| `experiments/castro/castro/pydantic_llm_client.py` | Import from `payment_simulator.llm` |
| `experiments/castro/castro/context_builder.py` | Rename class to `BootstrapContextBuilder` |
| `experiments/castro/castro/runner.py` | Update imports |
| `experiments/castro/tests/*.py` | Update context builder imports |

### Deleted
| File | Reason |
|------|--------|
| `experiments/castro/castro/model_config.py` | Replaced by `payment_simulator.llm.LLMConfig` |
| `experiments/castro/tests/test_model_config.py` | No longer needed |

---

## Success Criteria

- [ ] All existing tests pass
- [ ] castro imports `LLMConfig` from `payment_simulator.llm`
- [ ] `MonteCarloContextBuilder` renamed to `BootstrapContextBuilder`
- [ ] `castro/model_config.py` deleted
- [ ] No import errors when running castro
- [ ] `castro run exp1 --dry-run` works

---

## Rollback Plan

If migration fails:
1. Restore deleted files from git
2. Revert import changes
3. Revert LLMConfig changes

Git commands:
```bash
git checkout HEAD~1 -- experiments/castro/castro/model_config.py
git checkout HEAD~1 -- experiments/castro/tests/test_model_config.py
```

---

*Phase 6 Plan - Version 1.0*
