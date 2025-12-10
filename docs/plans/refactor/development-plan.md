# AI Cash Management Architecture Refactor - Development Plan

**Status:** Draft
**Created:** 2025-12-10
**Last Updated:** 2025-12-10
**Author:** Claude
**Related:**
- [Conceptual Plan](./conceptual-plan.md) - Architecture overview
- [Work Notes](./work_notes.md) - Progress tracking

---

## Overview

This document provides the phase-by-phase implementation plan for the AI Cash Management architecture refactor. Each phase includes:

- **Objectives**: What we're trying to achieve
- **TDD Tests**: Tests to write FIRST (TDD principle)
- **Implementation**: Code to write
- **Verification**: How to confirm success
- **Files**: Specific files to create/modify/delete

---

## Phase 0: Preparation (Pre-Refactor)

**Duration**: 1-2 days
**Risk**: Low
**Breaking Changes**: None

### Objectives

1. Create directory structure for new modules
2. Define protocol interfaces (no implementation)
3. Add comprehensive test fixtures
4. Ensure all existing tests pass

### TDD Tests

```python
# tests/llm/test_protocol.py
"""Tests for LLM protocol - write FIRST, will fail until implemented."""

from payment_simulator.llm.protocol import LLMClientProtocol

def test_llm_client_protocol_has_generate_structured_output():
    """LLMClientProtocol defines generate_structured_output method."""
    assert hasattr(LLMClientProtocol, "generate_structured_output")

def test_llm_client_protocol_has_generate_text():
    """LLMClientProtocol defines generate_text method."""
    assert hasattr(LLMClientProtocol, "generate_text")


# tests/experiments/config/test_experiment_config.py
"""Tests for experiment config loading."""

def test_experiment_config_from_yaml_loads_required_fields():
    """ExperimentConfig.from_yaml loads all required fields."""
    # This test will fail until ExperimentConfig is implemented
    pass  # Placeholder - implement in Phase 2


# tests/fixtures/experiments/test_experiment.yaml
# Create test fixture YAML files for testing
```

### Implementation

1. **Create directory structure**:
```bash
mkdir -p api/payment_simulator/llm
mkdir -p api/payment_simulator/experiments/{config,runner,persistence,orchestrator}
mkdir -p api/tests/llm
mkdir -p api/tests/experiments/{config,runner,persistence}
mkdir -p experiments/castro/experiments
mkdir -p api/tests/fixtures/experiments
```

2. **Create empty `__init__.py` files**

3. **Create protocol stubs**:
```python
# api/payment_simulator/llm/__init__.py
"""LLM integration layer."""

# api/payment_simulator/llm/protocol.py
"""LLM client protocol definitions."""

from typing import Protocol, TypeVar

T = TypeVar("T")

class LLMClientProtocol(Protocol):
    """Protocol for LLM clients."""

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM."""
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM."""
        ...
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/__init__.py` | LLM module init |
| `api/payment_simulator/llm/protocol.py` | Protocol definitions |
| `api/payment_simulator/experiments/__init__.py` | Experiments module init |
| `api/payment_simulator/experiments/config/__init__.py` | Config submodule |
| `api/payment_simulator/experiments/runner/__init__.py` | Runner submodule |
| `api/payment_simulator/experiments/persistence/__init__.py` | Persistence submodule |
| `api/payment_simulator/experiments/orchestrator/__init__.py` | Orchestrator submodule |
| `api/tests/llm/__init__.py` | LLM tests init |
| `api/tests/llm/test_protocol.py` | Protocol tests |
| `api/tests/experiments/__init__.py` | Experiments tests init |
| `api/tests/fixtures/experiments/test_experiment.yaml` | Test fixture |

### Verification

```bash
# All existing tests pass
cd api && .venv/bin/python -m pytest

# New test file exists (tests will fail - expected)
.venv/bin/python -m pytest tests/llm/test_protocol.py -v

# Imports work
.venv/bin/python -c "from payment_simulator.llm.protocol import LLMClientProtocol"
```

---

## Phase 1: LLM Module Extraction

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: None (parallel implementation)

### Objectives

1. Create unified LLM configuration (`LLMConfig`)
2. Move `PydanticAILLMClient` to new module
3. Create `AuditCaptureLLMClient` wrapper
4. Add Castro adapter to use new module

### TDD Tests

```python
# tests/llm/test_config.py
"""Tests for LLMConfig."""

import pytest
from payment_simulator.llm.config import LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

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


# tests/llm/test_pydantic_client.py
"""Tests for PydanticAI LLM client."""

import pytest
from pydantic import BaseModel
from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.pydantic_client import PydanticAILLMClient


class PolicyOutput(BaseModel):
    """Test response model."""
    policy_id: str
    parameters: dict[str, float]


class TestPydanticAILLMClient:
    """Tests for PydanticAILLMClient."""

    def test_creates_with_config(self) -> None:
        """Client creates with LLMConfig."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)
        assert client._config == config

    @pytest.mark.asyncio
    async def test_generate_structured_output_returns_model(self) -> None:
        """generate_structured_output returns parsed model."""
        # This test requires mocking - skip in unit tests, cover in integration
        pytest.skip("Requires LLM mock or integration test")


# tests/llm/test_audit_wrapper.py
"""Tests for audit capture wrapper."""

import pytest
from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.protocol import LLMClientProtocol


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


class TestLLMInteraction:
    """Tests for LLMInteraction dataclass."""

    def test_is_frozen(self) -> None:
        """LLMInteraction is immutable (frozen)."""
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
```

### Implementation

1. **Create LLMConfig**:

```python
# api/payment_simulator/llm/config.py
"""Unified LLM configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Unified LLM configuration.

    Supports multiple LLM providers with provider-specific options.

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

2. **Move PydanticAILLMClient** (copy from castro, adapt):

```python
# api/payment_simulator/llm/pydantic_client.py
"""PydanticAI-based LLM client implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

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
        agent = Agent(
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
        agent = Agent(
            model=self._config.model,
            result_type=str,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data
```

3. **Create AuditCaptureLLMClient**:

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
        self._last_interaction: LLMInteraction | None = None

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction."""
        return self._last_interaction

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text and capture interaction."""
        start = time.perf_counter()
        result = await self._delegate.generate_text(prompt, system_prompt)
        latency = time.perf_counter() - start

        self._last_interaction = LLMInteraction(
            system_prompt=system_prompt or "",
            user_prompt=prompt,
            raw_response=result,
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=0,  # Not available from base client
            completion_tokens=0,
            latency_seconds=latency,
        )

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

            self._last_interaction = LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response=str(result),
                parsed_policy=parsed,
                parsing_error=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            )

            return result

        except Exception as e:
            latency = time.perf_counter() - start
            self._last_interaction = LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response="",
                parsed_policy=None,
                parsing_error=str(e),
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            )
            raise
```

4. **Update module `__init__.py`**:

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

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/config.py` | LLMConfig dataclass |
| `api/payment_simulator/llm/pydantic_client.py` | PydanticAI implementation |
| `api/payment_simulator/llm/audit_wrapper.py` | Audit capture wrapper |
| `api/tests/llm/test_config.py` | Config tests |
| `api/tests/llm/test_pydantic_client.py` | Client tests |
| `api/tests/llm/test_audit_wrapper.py` | Wrapper tests |

### Files to Modify (Later)

| File | Change |
|------|--------|
| `experiments/castro/castro/runner.py` | Import from `payment_simulator.llm` |

### Verification

```bash
# All LLM module tests pass
cd api && .venv/bin/python -m pytest tests/llm/ -v

# Type checking passes
.venv/bin/python -m mypy payment_simulator/llm/

# Imports work
.venv/bin/python -c "from payment_simulator.llm import LLMConfig, PydanticAILLMClient"
```

---

## Phase 2: Experiment Configuration Framework

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: None (new code)

### Objectives

1. Create `ExperimentConfig` YAML loader
2. Create `EvaluationConfig` for bootstrap/deterministic settings
3. Create experiment YAML schema
4. Add validation for experiment configs

### TDD Tests

```python
# tests/experiments/config/test_experiment_config.py
"""Tests for ExperimentConfig YAML loading."""

from pathlib import Path

import pytest

from payment_simulator.experiments.config.experiment_config import (
    ExperimentConfig,
    EvaluationConfig,
    OutputConfig,
)


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    @pytest.fixture
    def valid_yaml_path(self, tmp_path: Path) -> Path:
        """Create valid experiment YAML."""
        content = """
name: test_experiment
description: "Test experiment for unit tests"
scenario: configs/test_scenario.yaml
evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
optimized_agents:
  - BANK_A
  - BANK_B
constraints: castro.constraints.CASTRO_CONSTRAINTS
output:
  directory: results
  database: test.db
"""
        yaml_path = tmp_path / "experiment.yaml"
        yaml_path.write_text(content)
        return yaml_path

    def test_loads_from_yaml(self, valid_yaml_path: Path) -> None:
        """ExperimentConfig loads from YAML file."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.name == "test_experiment"
        assert config.description == "Test experiment for unit tests"

    def test_loads_scenario_path(self, valid_yaml_path: Path) -> None:
        """Loads scenario path as Path object."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.scenario_path == Path("configs/test_scenario.yaml")

    def test_loads_evaluation_config(self, valid_yaml_path: Path) -> None:
        """Loads nested evaluation config."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.evaluation.mode == "bootstrap"
        assert config.evaluation.num_samples == 10
        assert config.evaluation.ticks == 12

    def test_loads_convergence_config(self, valid_yaml_path: Path) -> None:
        """Loads convergence criteria."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.convergence.max_iterations == 25
        assert config.convergence.stability_threshold == 0.05

    def test_loads_llm_config(self, valid_yaml_path: Path) -> None:
        """Loads LLM configuration."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.llm.model == "anthropic:claude-sonnet-4-5"
        assert config.llm.temperature == 0.0

    def test_loads_optimized_agents(self, valid_yaml_path: Path) -> None:
        """Loads list of optimized agents."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.optimized_agents == ["BANK_A", "BANK_B"]

    def test_loads_constraints_module(self, valid_yaml_path: Path) -> None:
        """Loads constraints module path."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.constraints_module == "castro.constraints.CASTRO_CONSTRAINTS"

    def test_loads_output_config(self, valid_yaml_path: Path) -> None:
        """Loads output configuration."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.output.directory == Path("results")
        assert config.output.database == "test.db"

    def test_raises_on_missing_file(self) -> None:
        """Raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml(Path("nonexistent.yaml"))

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        """Raises error on invalid YAML."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{ invalid yaml :::")
        with pytest.raises(Exception):  # yaml.YAMLError
            ExperimentConfig.from_yaml(bad_yaml)

    def test_raises_on_missing_required_field(self, tmp_path: Path) -> None:
        """Raises ValidationError on missing required field."""
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("name: test\n")  # Missing other fields
        with pytest.raises(Exception):  # pydantic.ValidationError
            ExperimentConfig.from_yaml(incomplete)


class TestEvaluationConfig:
    """Tests for EvaluationConfig."""

    def test_bootstrap_mode_requires_num_samples(self) -> None:
        """Bootstrap mode requires num_samples."""
        config = EvaluationConfig(mode="bootstrap", num_samples=10, ticks=12)
        assert config.num_samples == 10

    def test_deterministic_mode_ignores_samples(self) -> None:
        """Deterministic mode ignores num_samples."""
        config = EvaluationConfig(mode="deterministic", num_samples=None, ticks=12)
        assert config.num_samples is None

    def test_defaults_to_bootstrap(self) -> None:
        """Default mode is bootstrap."""
        config = EvaluationConfig(ticks=12)
        assert config.mode == "bootstrap"
```

### Implementation

```python
# api/payment_simulator/experiments/config/experiment_config.py
"""Experiment configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from payment_simulator.ai_cash_mgmt.config.game_config import ConvergenceCriteria
from payment_simulator.llm.config import LLMConfig


@dataclass
class EvaluationConfig:
    """Evaluation mode configuration.

    Controls how policies are evaluated (bootstrap vs deterministic).
    """

    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.mode not in ("bootstrap", "deterministic"):
            msg = f"Invalid evaluation mode: {self.mode}"
            raise ValueError(msg)


@dataclass
class OutputConfig:
    """Output configuration."""

    directory: Path = field(default_factory=lambda: Path("results"))
    database: str = "experiments.db"
    verbose: bool = True


@dataclass
class ExperimentConfig:
    """Experiment configuration loaded from YAML.

    Defines all settings needed to run an experiment.

    Example YAML:
        name: exp1
        description: "2-Period Deterministic"
        scenario: configs/exp1_2period.yaml
        evaluation:
          mode: bootstrap
          num_samples: 10
          ticks: 12
        convergence:
          max_iterations: 25
        llm:
          model: "anthropic:claude-sonnet-4-5"
        optimized_agents:
          - BANK_A
        constraints: castro.constraints.CASTRO_CONSTRAINTS
        output:
          directory: results
    """

    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceCriteria
    llm: LLMConfig
    optimized_agents: list[str]
    constraints_module: str
    output: OutputConfig
    master_seed: int = 42

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        """Load experiment config from YAML file.

        Args:
            path: Path to experiment YAML file.

        Returns:
            ExperimentConfig loaded from file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            yaml.YAMLError: If YAML is invalid.
            ValidationError: If required fields missing.
        """
        if not path.exists():
            msg = f"Experiment config not found: {path}"
            raise FileNotFoundError(msg)

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        """Create config from dictionary."""
        # Validate required fields
        required = ["name", "scenario", "evaluation", "convergence", "llm", "optimized_agents"]
        missing = [f for f in required if f not in data]
        if missing:
            msg = f"Missing required fields: {missing}"
            raise ValueError(msg)

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            scenario_path=Path(data["scenario"]),
            evaluation=EvaluationConfig(
                mode=data["evaluation"].get("mode", "bootstrap"),
                num_samples=data["evaluation"].get("num_samples", 10),
                ticks=data["evaluation"]["ticks"],
            ),
            convergence=ConvergenceCriteria(
                max_iterations=data["convergence"].get("max_iterations", 50),
                stability_threshold=data["convergence"].get("stability_threshold", 0.05),
                stability_window=data["convergence"].get("stability_window", 5),
                improvement_threshold=data["convergence"].get("improvement_threshold", 0.01),
            ),
            llm=LLMConfig(
                model=data["llm"]["model"],
                temperature=data["llm"].get("temperature", 0.0),
                max_retries=data["llm"].get("max_retries", 3),
                thinking_budget=data["llm"].get("thinking_budget"),
                reasoning_effort=data["llm"].get("reasoning_effort"),
            ),
            optimized_agents=data["optimized_agents"],
            constraints_module=data.get("constraints", ""),
            output=OutputConfig(
                directory=Path(data.get("output", {}).get("directory", "results")),
                database=data.get("output", {}).get("database", "experiments.db"),
                verbose=data.get("output", {}).get("verbose", True),
            ),
            master_seed=data.get("master_seed", 42),
        )

    def load_constraints(self) -> Any:
        """Dynamically load constraints from module path.

        Returns:
            ScenarioConstraints loaded from constraints_module.
        """
        import importlib

        if not self.constraints_module:
            return None

        # Parse "module.path.VARIABLE"
        parts = self.constraints_module.rsplit(".", 1)
        if len(parts) != 2:
            msg = f"Invalid constraints module format: {self.constraints_module}"
            raise ValueError(msg)

        module_path, variable_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, variable_name)
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/experiments/config/experiment_config.py` | Main config class |
| `api/payment_simulator/experiments/config/evaluation_config.py` | Evaluation settings |
| `api/tests/experiments/config/test_experiment_config.py` | Config tests |

### Verification

```bash
# Config tests pass
cd api && .venv/bin/python -m pytest tests/experiments/config/ -v

# Type checking passes
.venv/bin/python -m mypy payment_simulator/experiments/config/
```

---

## Phase 3: Experiment Runner Framework

**Duration**: 3-4 days
**Risk**: Medium
**Breaking Changes**: None (parallel implementation)

### Objectives

1. Create `ExperimentRunnerProtocol`
2. Create `BaseExperimentRunner` with optimization loop
3. Create `OutputHandlerProtocol` and implementations
4. Create unified experiment persistence

### TDD Tests

```python
# tests/experiments/runner/test_base_runner.py
"""Tests for BaseExperimentRunner."""

import pytest

from payment_simulator.experiments.runner.base_runner import BaseExperimentRunner
from payment_simulator.experiments.runner.output import SilentOutput


class MockEvaluator:
    """Mock policy evaluator for testing."""

    def evaluate(self, policy: dict, agent_id: str) -> int:
        return 1000  # Fixed cost

    def compare(self, old: dict, new: dict, agent_id: str) -> dict:
        return {"delta": -100, "old_cost": 1000, "new_cost": 900}


class MockLLMClient:
    """Mock LLM client for testing."""

    async def generate_structured_output(self, prompt: str, model: type, **kwargs) -> dict:
        return {"policy_id": "test", "parameters": {"threshold": 5.0}}


class TestBaseExperimentRunner:
    """Tests for BaseExperimentRunner."""

    @pytest.fixture
    def runner(self, tmp_path) -> BaseExperimentRunner:
        """Create runner with mock components."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
            EvaluationConfig,
            OutputConfig,
        )
        from payment_simulator.ai_cash_mgmt.config.game_config import ConvergenceCriteria
        from payment_simulator.llm.config import LLMConfig

        config = ExperimentConfig(
            name="test",
            description="Test experiment",
            scenario_path=tmp_path / "scenario.yaml",
            evaluation=EvaluationConfig(mode="deterministic", ticks=10),
            convergence=ConvergenceCriteria(max_iterations=3),
            llm=LLMConfig(model="mock:test"),
            optimized_agents=["BANK_A"],
            constraints_module="",
            output=OutputConfig(),
        )

        return BaseExperimentRunner(
            config=config,
            evaluator=MockEvaluator(),
            llm_client=MockLLMClient(),
            constraints=None,
            output=SilentOutput(),
        )

    def test_creates_with_config(self, runner: BaseExperimentRunner) -> None:
        """Runner creates with config."""
        assert runner._config.name == "test"

    @pytest.mark.asyncio
    async def test_runs_until_convergence_or_max_iterations(
        self, runner: BaseExperimentRunner
    ) -> None:
        """Runner completes after max iterations."""
        result = await runner.run()
        assert result.num_iterations <= 3
```

### Implementation

See full implementation in conceptual-plan.md Phase 4 section.

Key files:
- `api/payment_simulator/experiments/runner/protocol.py`
- `api/payment_simulator/experiments/runner/base_runner.py`
- `api/payment_simulator/experiments/runner/output.py`

### Verification

```bash
cd api && .venv/bin/python -m pytest tests/experiments/runner/ -v
```

---

## Phase 4: CLI Commands

**Duration**: 2 days
**Risk**: Low
**Breaking Changes**: None (new commands)

### Objectives

1. Create `payment-sim experiment` command group
2. Implement `run`, `validate`, `list`, `info` subcommands
3. Create Castro CLI thin wrapper

### New CLI Commands

#### `payment-sim experiment` Command Group

```bash
# Run experiment from YAML
payment-sim experiment run path/to/experiment.yaml [OPTIONS]

Options:
  --model TEXT           Override LLM model (provider:model format)
  --max-iter INT         Override max iterations
  --seed INT             Override master seed
  --output-dir PATH      Override output directory
  --verbose              Enable verbose output
  --quiet                Suppress output
  --dry-run              Validate config without running

# Validate experiment configuration
payment-sim experiment validate path/to/experiment.yaml

# List experiments in directory
payment-sim experiment list --dir experiments/castro/experiments/

# Show experiment info
payment-sim experiment info path/to/experiment.yaml

# Generate experiment template
payment-sim experiment template --output new_experiment.yaml

# Replay experiment from database
payment-sim experiment replay <run_id> --db experiments.db [OPTIONS]

Options:
  --verbose              Enable verbose output
  --audit                Show detailed audit trail
  --start INT            Start iteration (for audit)
  --end INT              End iteration (for audit)

# List experiment results
payment-sim experiment results --db experiments.db [OPTIONS]

Options:
  --experiment TEXT      Filter by experiment name
  --limit INT            Max results to show
```

### Implementation

```python
# api/payment_simulator/cli/commands/experiment.py
"""Experiment CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

experiment_app = typer.Typer(
    name="experiment",
    help="Experiment framework commands",
    no_args_is_help=True,
)

console = Console()


@experiment_app.command()
def run(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Override LLM model"),
    ] = None,
    max_iter: Annotated[
        int | None,
        typer.Option("--max-iter", "-i", help="Override max iterations"),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option("--seed", "-s", help="Override master seed"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Override output directory"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress output"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate config without running"),
    ] = False,
) -> None:
    """Run an experiment from YAML configuration.

    Examples:
        # Run with defaults
        payment-sim experiment run experiments/exp1.yaml

        # Override model and iterations
        payment-sim experiment run exp.yaml --model openai:gpt-4o --max-iter 50

        # Dry run (validate only)
        payment-sim experiment run exp.yaml --dry-run
    """
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig
    from payment_simulator.experiments.runner.base_runner import BaseExperimentRunner
    from payment_simulator.experiments.runner.output import (
        RichConsoleOutput,
        SilentOutput,
    )
    from payment_simulator.llm import PydanticAILLMClient

    # Load config
    try:
        config = ExperimentConfig.from_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Invalid config: {e}[/red]")
        raise typer.Exit(1) from None

    # Apply CLI overrides
    if model:
        config.llm.model = model
    if max_iter:
        config.convergence.max_iterations = max_iter
    if seed:
        config.master_seed = seed
    if output_dir:
        config.output.directory = output_dir

    if dry_run:
        console.print("[green]Configuration valid![/green]")
        console.print(f"  Name: {config.name}")
        console.print(f"  Scenario: {config.scenario_path}")
        console.print(f"  Agents: {config.optimized_agents}")
        return

    # Create components
    llm_client = PydanticAILLMClient(config.llm)
    constraints = config.load_constraints()
    output_handler = SilentOutput() if quiet else RichConsoleOutput(console, verbose)

    # Create and run
    runner = BaseExperimentRunner(
        config=config,
        evaluator=...,  # Create from config
        llm_client=llm_client,
        constraints=constraints,
        output=output_handler,
    )

    try:
        result = asyncio.run(runner.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None

    # Show results
    table = Table(title=f"Results: {config.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Run ID", result.run_id)
    table.add_row("Final Cost", f"${result.final_cost / 100:.2f}")
    table.add_row("Iterations", str(result.num_iterations))
    table.add_row("Converged", "Yes" if result.converged else "No")
    console.print(table)


@experiment_app.command()
def validate(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
) -> None:
    """Validate experiment configuration.

    Checks that the config file is valid YAML, has all required fields,
    and references valid scenario and constraint files.
    """
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1) from None

    console.print("[green]Configuration valid![/green]")
    console.print(f"  Name: {config.name}")
    console.print(f"  Description: {config.description}")
    console.print(f"  Scenario: {config.scenario_path}")
    console.print(f"  Mode: {config.evaluation.mode}")
    console.print(f"  Agents: {', '.join(config.optimized_agents)}")


@experiment_app.command("list")
def list_experiments(
    directory: Annotated[
        Path,
        typer.Option("--dir", "-d", help="Directory containing experiment YAMLs"),
    ] = Path("experiments"),
) -> None:
    """List available experiments in a directory."""
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    if not directory.exists():
        console.print(f"[red]Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    yamls = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    if not yamls:
        console.print(f"[yellow]No experiment files found in {directory}[/yellow]")
        return

    table = Table(title="Available Experiments")
    table.add_column("File", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")
    table.add_column("Mode")
    table.add_column("Agents")

    for yaml_path in sorted(yamls):
        try:
            config = ExperimentConfig.from_yaml(yaml_path)
            table.add_row(
                yaml_path.name,
                config.name,
                config.description[:40] + "..." if len(config.description) > 40 else config.description,
                config.evaluation.mode,
                ", ".join(config.optimized_agents),
            )
        except Exception as e:
            table.add_row(yaml_path.name, "[red]Error[/red]", str(e)[:40], "", "")

    console.print(table)


@experiment_app.command()
def info(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
) -> None:
    """Show detailed experiment configuration."""
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1) from None

    console.print(f"[bold cyan]{config.name}[/bold cyan]")
    console.print(f"Description: {config.description}")
    console.print()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Scenario Path", str(config.scenario_path))
    table.add_row("Master Seed", str(config.master_seed))
    table.add_row("", "")
    table.add_row("[bold]Evaluation[/bold]", "")
    table.add_row("  Mode", config.evaluation.mode)
    table.add_row("  Samples", str(config.evaluation.num_samples or "N/A"))
    table.add_row("  Ticks", str(config.evaluation.ticks))
    table.add_row("", "")
    table.add_row("[bold]Convergence[/bold]", "")
    table.add_row("  Max Iterations", str(config.convergence.max_iterations))
    table.add_row("  Stability Threshold", f"{config.convergence.stability_threshold:.1%}")
    table.add_row("", "")
    table.add_row("[bold]LLM[/bold]", "")
    table.add_row("  Model", config.llm.model)
    table.add_row("  Temperature", str(config.llm.temperature))
    table.add_row("", "")
    table.add_row("[bold]Agents[/bold]", ", ".join(config.optimized_agents))

    console.print(table)


@experiment_app.command()
def template(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
) -> None:
    """Generate experiment configuration template."""
    template = """# Experiment Configuration
name: my_experiment
description: "Description of the experiment"

# Scenario configuration file (relative to experiment file)
scenario: configs/scenario.yaml

# Evaluation settings
evaluation:
  mode: bootstrap  # or "deterministic"
  num_samples: 10  # Number of bootstrap samples
  ticks: 12        # Ticks per evaluation

# Convergence criteria
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01

# LLM configuration
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  # thinking_budget: 8000  # For Anthropic extended thinking
  # reasoning_effort: high  # For OpenAI o1/o3 models

# Agents to optimize
optimized_agents:
  - BANK_A
  - BANK_B

# Constraints module (Python import path)
constraints: castro.constraints.CASTRO_CONSTRAINTS

# Output settings
output:
  directory: results
  database: experiments.db
  verbose: true

# Master seed for determinism
master_seed: 42
"""

    if output:
        output.write_text(template)
        console.print(f"[green]Template written to {output}[/green]")
    else:
        console.print(template)
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/cli/commands/experiment.py` | CLI commands |
| `api/tests/cli/test_experiment_commands.py` | CLI tests |

### Verification

```bash
# CLI help works
payment-sim experiment --help
payment-sim experiment run --help

# Template generation works
payment-sim experiment template

# Validation works
payment-sim experiment validate tests/fixtures/experiment.yaml
```

---

## Phase 5: Castro Migration

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: Castro CLI changes (backwards compatible)

### Objectives

1. Create experiment YAML files from Python dataclasses
2. Update Castro CLI to use experiment framework
3. Keep backwards compatibility with existing commands

### Tasks

1. **Create YAML experiment definitions**:
   - `experiments/castro/experiments/exp1.yaml`
   - `experiments/castro/experiments/exp2.yaml`
   - `experiments/castro/experiments/exp3.yaml`

2. **Simplify Castro CLI**:
   - Import from experiment framework
   - Keep existing command signatures
   - Map `castro run exp1` → `payment-sim experiment run experiments/exp1.yaml`

3. **Remove duplicated code**:
   - `castro/pydantic_llm_client.py` (use `payment_simulator.llm`)
   - `castro/model_config.py` (merged into `payment_simulator.llm`)
   - Simplify `castro/runner.py` to use `BaseExperimentRunner`

### Example YAML (exp2.yaml)

```yaml
# experiments/castro/experiments/exp2.yaml
name: exp2
description: "12-Period Stochastic LVTS-Style"

scenario: configs/exp2_12period.yaml

evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3

optimized_agents:
  - BANK_A
  - BANK_B

constraints: castro.constraints.CASTRO_CONSTRAINTS

output:
  directory: results
  database: castro.db
  verbose: true

master_seed: 42
```

---

## Phase 6: Documentation

**Duration**: 2-3 days
**Risk**: Low

### Documentation Structure

```
docs/reference/
├── llm/
│   ├── index.md
│   ├── configuration.md
│   ├── protocols.md
│   ├── providers.md
│   └── audit.md
├── experiments/
│   ├── index.md
│   ├── configuration.md
│   ├── runner.md
│   ├── cli.md
│   ├── persistence.md
│   └── extending.md
├── ai_cash_mgmt/
│   ├── index.md (updated)
│   └── ... (existing, trimmed)
└── castro/
    ├── index.md (simplified)
    ├── constraints.md
    └── experiments.md
```

### Documentation Tasks

1. **Create `docs/reference/llm/`**:
   - Protocol reference
   - Configuration options
   - Provider-specific settings
   - Audit capture guide

2. **Create `docs/reference/experiments/`**:
   - YAML configuration reference
   - Runner API reference
   - CLI command reference
   - How to create new experiments

3. **Update `docs/reference/ai_cash_mgmt/`**:
   - Remove sections moved to experiments/llm
   - Focus on bootstrap, constraints, optimization

4. **Replace `docs/reference/castro/`**:
   - Simplify to Castro-specific content only
   - Reference experiment framework docs

5. **Add architecture doc**:
   - `docs/reference/architecture/XX-experiment-framework.md`

---

## Verification Checklist

Before each phase is complete:

- [ ] All new tests pass
- [ ] All existing tests pass
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)
- [ ] Documentation updated
- [ ] Changes committed with clear messages

Before final merge:

- [ ] Full test suite passes
- [ ] Performance benchmarks acceptable
- [ ] Documentation complete
- [ ] Castro experiments still work
- [ ] Determinism verified (same seed = same result)
- [ ] Replay identity maintained

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 0: Preparation | 1-2 days | None |
| Phase 1: LLM Module | 2-3 days | Phase 0 |
| Phase 2: Experiment Config | 2-3 days | Phase 0 |
| Phase 3: Experiment Runner | 3-4 days | Phases 1, 2 |
| Phase 4: CLI Commands | 2 days | Phase 3 |
| Phase 5: Castro Migration | 2-3 days | Phase 4 |
| Phase 6: Documentation | 2-3 days | Phase 5 |

**Total: ~15-20 days**

---

*Document Version 1.0 - Initial Draft*
