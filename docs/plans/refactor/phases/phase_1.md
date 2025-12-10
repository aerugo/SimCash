# Phase 1: Preparation (Pre-Refactor)

**Status:** COMPLETED (2025-12-10)
**Created:** 2025-12-10
**Risk:** Low
**Breaking Changes:** None

---

## Objectives

1. Create directory structure for new modules (llm, experiments)
2. Define protocol interfaces (no implementation yet)
3. Add test fixtures
4. Ensure all existing tests continue to pass

---

## TDD Test Specifications

### Test File: `api/tests/llm/test_protocol.py`

```python
"""Tests for LLM protocol definitions."""

import pytest
from typing import Protocol, runtime_checkable


class TestLLMClientProtocol:
    """Tests for LLMClientProtocol interface."""

    def test_protocol_can_be_imported(self) -> None:
        """LLMClientProtocol can be imported from llm module."""
        from payment_simulator.llm.protocol import LLMClientProtocol
        assert LLMClientProtocol is not None

    def test_protocol_has_generate_structured_output(self) -> None:
        """LLMClientProtocol defines generate_structured_output method."""
        from payment_simulator.llm.protocol import LLMClientProtocol
        assert hasattr(LLMClientProtocol, "generate_structured_output")

    def test_protocol_has_generate_text(self) -> None:
        """LLMClientProtocol defines generate_text method."""
        from payment_simulator.llm.protocol import LLMClientProtocol
        assert hasattr(LLMClientProtocol, "generate_text")

    def test_protocol_is_runtime_checkable(self) -> None:
        """LLMClientProtocol is decorated with @runtime_checkable."""
        from payment_simulator.llm.protocol import LLMClientProtocol
        # Protocol should be runtime checkable for isinstance checks
        assert getattr(LLMClientProtocol, "_is_runtime_checkable", False)
```

### Test File: `api/tests/experiments/test_module_structure.py`

```python
"""Tests for experiments module structure."""


class TestExperimentsModuleStructure:
    """Tests that experiments module has expected structure."""

    def test_experiments_module_can_be_imported(self) -> None:
        """Experiments module can be imported."""
        import payment_simulator.experiments
        assert payment_simulator.experiments is not None

    def test_experiments_has_config_submodule(self) -> None:
        """Experiments has config submodule."""
        import payment_simulator.experiments.config
        assert payment_simulator.experiments.config is not None

    def test_experiments_has_runner_submodule(self) -> None:
        """Experiments has runner submodule."""
        import payment_simulator.experiments.runner
        assert payment_simulator.experiments.runner is not None
```

---

## Implementation Plan

### Step 1.1: Create LLM Module Directory Structure

```bash
mkdir -p api/payment_simulator/llm
touch api/payment_simulator/llm/__init__.py
touch api/payment_simulator/llm/protocol.py
```

### Step 1.2: Create Experiments Module Directory Structure

```bash
mkdir -p api/payment_simulator/experiments/config
mkdir -p api/payment_simulator/experiments/runner
mkdir -p api/payment_simulator/experiments/persistence
touch api/payment_simulator/experiments/__init__.py
touch api/payment_simulator/experiments/config/__init__.py
touch api/payment_simulator/experiments/runner/__init__.py
touch api/payment_simulator/experiments/persistence/__init__.py
```

### Step 1.3: Create Test Directories

```bash
mkdir -p api/tests/llm
mkdir -p api/tests/experiments/config
mkdir -p api/tests/experiments/runner
touch api/tests/llm/__init__.py
touch api/tests/experiments/config/__init__.py
touch api/tests/experiments/runner/__init__.py
```

### Step 1.4: Implement LLMClientProtocol

```python
# api/payment_simulator/llm/protocol.py
"""LLM client protocol definitions.

This module defines the interface that all LLM clients must implement.
This allows the system to work with different LLM providers (OpenAI,
Anthropic, etc.) without tight coupling.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM clients.

    Any LLM client implementation must provide these methods to be
    compatible with the experiment system.

    Example:
        >>> class MyLLMClient:
        ...     async def generate_structured_output(
        ...         self,
        ...         prompt: str,
        ...         response_model: type[T],
        ...         system_prompt: str | None = None,
        ...     ) -> T: ...
        ...
        ...     async def generate_text(
        ...         self,
        ...         prompt: str,
        ...         system_prompt: str | None = None,
        ...     ) -> str: ...
        >>>
        >>> isinstance(MyLLMClient(), LLMClientProtocol)
        True
    """

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM.

        Args:
            prompt: The prompt to send to the LLM.
            response_model: Pydantic model to parse response into.
            system_prompt: Optional system prompt.

        Returns:
            Instance of response_model populated by LLM.
        """
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM.

        Args:
            prompt: The prompt to send to the LLM.
            system_prompt: Optional system prompt.

        Returns:
            Text response from LLM.
        """
        ...
```

### Step 1.5: Create Module __init__.py Files

```python
# api/payment_simulator/llm/__init__.py
"""LLM integration layer.

Provides a unified interface for working with different LLM providers.
"""

from payment_simulator.llm.protocol import LLMClientProtocol

__all__ = ["LLMClientProtocol"]
```

```python
# api/payment_simulator/experiments/__init__.py
"""Experiment framework for policy optimization.

This module provides:
- Experiment configuration loading (from YAML)
- Experiment runner framework
- Output handling (console, file, database)
"""

__all__: list[str] = []
```

```python
# api/payment_simulator/experiments/config/__init__.py
"""Experiment configuration module."""

__all__: list[str] = []
```

```python
# api/payment_simulator/experiments/runner/__init__.py
"""Experiment runner module."""

__all__: list[str] = []
```

```python
# api/payment_simulator/experiments/persistence/__init__.py
"""Experiment persistence module."""

__all__: list[str] = []
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/__init__.py` | LLM module init with exports |
| `api/payment_simulator/llm/protocol.py` | LLMClientProtocol definition |
| `api/payment_simulator/experiments/__init__.py` | Experiments module init |
| `api/payment_simulator/experiments/config/__init__.py` | Config submodule |
| `api/payment_simulator/experiments/runner/__init__.py` | Runner submodule |
| `api/payment_simulator/experiments/persistence/__init__.py` | Persistence submodule |
| `api/tests/llm/__init__.py` | Test module init |
| `api/tests/llm/test_protocol.py` | Protocol tests |
| `api/tests/experiments/__init__.py` | Test module init |
| `api/tests/experiments/test_module_structure.py` | Module structure tests |

---

## Verification Checklist

### TDD Tests
- [x] `test_protocol_can_be_imported` passes
- [x] `test_protocol_has_generate_structured_output` passes
- [x] `test_protocol_has_generate_text` passes
- [x] `test_protocol_is_runtime_checkable` passes
- [x] `test_mock_implementation_satisfies_protocol` passes (added)
- [x] `test_module_exports_protocol` passes (added)
- [x] `test_experiments_module_can_be_imported` passes
- [x] `test_experiments_has_config_submodule` passes
- [x] `test_experiments_has_runner_submodule` passes
- [x] `test_experiments_has_persistence_submodule` passes (added)

### Existing Tests
```bash
# Ensure no regressions
cd api && uv run pytest tests/ -v --ignore=tests/e2e/
```

### Type Checking
```bash
cd api && uv run mypy payment_simulator/llm/
cd api && uv run mypy payment_simulator/experiments/
```

---

## Notes

Phase 1 is a low-risk preparatory phase. It creates the scaffolding for
future phases without changing any existing functionality.

Key points:
- No business logic changes
- Only creates empty modules and protocol definitions
- Sets up test infrastructure
- Existing tests must continue to pass

---

*Phase 1 Plan v1.0 - 2025-12-10*
