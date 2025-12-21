# Phase 1: Extend LLMConfig with Reasoning Summary

**Status**: Pending
**Started**:

---

## Objective

Add `reasoning_summary` field to `LLMConfig` and update `to_model_settings()` to include it in the OpenAI model settings. This enables capturing reasoning summaries from OpenAI reasoning models (o1, o3, etc.).

---

## Invariants Enforced in This Phase

- INV-2: Determinism - No effect (configuration change only)
- INV-3: FFI Boundary - No effect (pure Python change)

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `api/tests/llm/test_llm_config.py`:

**Test Cases**:
1. `test_reasoning_summary_field_optional` - Verify default is None
2. `test_reasoning_summary_accepts_valid_values` - 'concise', 'detailed' work
3. `test_to_model_settings_includes_reasoning_summary` - Settings include the field
4. `test_to_model_settings_omits_when_none` - Settings don't include when None
5. `test_reasoning_summary_only_for_openai` - Non-OpenAI providers ignore it

```python
"""Tests for LLMConfig reasoning summary configuration."""

import pytest

from payment_simulator.llm.config import LLMConfig


class TestLLMConfigReasoningSummary:
    """Tests for reasoning_summary field in LLMConfig."""

    def test_reasoning_summary_field_optional(self) -> None:
        """Verify reasoning_summary defaults to None."""
        config = LLMConfig(model="openai:o1")
        assert config.reasoning_summary is None

    def test_reasoning_summary_accepts_concise(self) -> None:
        """Verify 'concise' is a valid value."""
        config = LLMConfig(model="openai:o1", reasoning_summary="concise")
        assert config.reasoning_summary == "concise"

    def test_reasoning_summary_accepts_detailed(self) -> None:
        """Verify 'detailed' is a valid value."""
        config = LLMConfig(model="openai:o1", reasoning_summary="detailed")
        assert config.reasoning_summary == "detailed"

    def test_to_model_settings_includes_reasoning_summary(self) -> None:
        """Verify to_model_settings includes openai_reasoning_summary."""
        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="medium",
            reasoning_summary="detailed",
        )
        settings = config.to_model_settings()
        assert settings.get("openai_reasoning_summary") == "detailed"

    def test_to_model_settings_omits_when_none(self) -> None:
        """Verify reasoning_summary not in settings when None."""
        config = LLMConfig(model="openai:o1", reasoning_effort="medium")
        settings = config.to_model_settings()
        assert "openai_reasoning_summary" not in settings

    def test_reasoning_summary_ignored_for_anthropic(self) -> None:
        """Verify reasoning_summary has no effect for non-OpenAI providers."""
        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            reasoning_summary="detailed",  # Should be ignored
        )
        settings = config.to_model_settings()
        # Should not include OpenAI-specific setting for Anthropic
        assert "openai_reasoning_summary" not in settings
```

### Step 1.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/llm/config.py`:

```python
@dataclass(frozen=True)
class LLMConfig:
    """Unified LLM configuration.

    ...existing docstring...

    Attributes:
        ...existing attributes...
        reasoning_summary: OpenAI reasoning summary detail level ('concise', 'detailed').
    """

    # ... existing fields ...

    # Provider-specific options (mutually exclusive by convention)
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: low, medium, high
    reasoning_summary: str | None = None  # OpenAI: concise, detailed (NEW)
    thinking_config: dict[str, Any] | None = None  # Google Gemini thinking

    # ... existing methods ...

    def to_model_settings(self) -> dict[str, Any]:
        """Convert to PydanticAI ModelSettings dict."""
        settings: dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_seconds,
        }

        provider = self.provider

        if provider == "anthropic" and self.thinking_budget:
            settings["anthropic_thinking"] = {"budget_tokens": self.thinking_budget}
        elif provider == "openai":
            if self.reasoning_effort:
                settings["openai_reasoning_effort"] = self.reasoning_effort
                if self.reasoning_effort == "high":
                    settings["max_tokens"] = max(self.max_tokens, 30000)
            if self.reasoning_summary:
                settings["openai_reasoning_summary"] = self.reasoning_summary
        elif provider == "google" and self.thinking_config:
            settings["google_thinking_config"] = self.thinking_config

        return settings
```

### Step 1.3: Refactor

- Ensure type annotations are complete
- Add docstring example for reasoning_summary
- Verify no bare `Any` types

---

## Implementation Details

### Valid Values for reasoning_summary

According to Pydantic AI docs:
- `'concise'`: Brief reasoning summary
- `'detailed'`: Detailed reasoning summary

### When to Apply reasoning_summary

Only apply for OpenAI provider:
```python
if provider == "openai" and self.reasoning_summary:
    settings["openai_reasoning_summary"] = self.reasoning_summary
```

### Edge Cases to Handle

1. **reasoning_summary without reasoning_effort**: Valid - user may want summaries at default effort
2. **reasoning_summary for non-OpenAI**: Silently ignored (no error)
3. **Invalid values**: No validation in this phase (Pydantic AI will validate)

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/llm/config.py` | MODIFY |
| `api/tests/llm/test_llm_config.py` | CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/llm/test_llm_config.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/llm/config.py

# Lint
.venv/bin/python -m ruff check payment_simulator/llm/config.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes (mypy)
- [ ] Lint passes (ruff)
- [ ] Docstrings updated with reasoning_summary
- [ ] No breaking changes to existing code
