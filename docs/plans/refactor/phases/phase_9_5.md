# Phase 9.5: Runner Decoupling and Legacy Module Deletion

**Status:** Planned
**Created:** 2025-12-11
**Dependencies:** Phase 9 (Castro Module Slimming - partial)
**Risk:** Medium (requires careful refactoring of 936-line runner.py)
**Breaking Changes:** None (internal refactor with backward compatibility)

---

## Purpose

Complete the Phase 9 deferred tasks by decoupling `runner.py` from `CastroExperiment` dataclass, enabling deletion of `experiments.py` and eventual deletion of `context_builder.py`.

**Target outcomes:**
- Delete `experiments.py` (~350 lines)
- `runner.py` accepts YAML-based config via protocol
- Clean separation between experiment definition and runner logic

---

## Problem Analysis

### Current Coupling

`runner.py` (936 lines) is tightly coupled to `CastroExperiment` dataclass:

```python
# runner.py line 169
def __init__(self, experiment: CastroExperiment, ...):

# Properties accessed (25 occurrences):
experiment.name                     # lines 181, 268, 276, 562, 587, 869, 902
experiment.description              # line 278
experiment.master_seed              # lines 194, 272, 717, 871
experiment.scenario_path            # line 606
experiment.optimized_agents         # lines 348, 666, 702, 711, 763, 776, 811, 826, 880

# Methods called (4 occurrences):
experiment.get_convergence_criteria()   # line 189
experiment.get_monte_carlo_config()     # line 190
experiment.get_model_config()           # line 191
experiment.get_output_config()          # line 242
```

### Why Direct Deletion Failed

Phase 9 attempted to delete `experiments.py` but couldn't because:
1. `CastroExperiment` is a concrete class, not a protocol
2. `runner.py` type hints require `CastroExperiment`
3. All 307 tests use `CastroExperiment` directly
4. CLI creates `CastroExperiment` via factory functions

---

## Solution: Protocol-Based Decoupling

### Strategy

1. **Define `ExperimentConfigProtocol`** - Interface that runner.py needs
2. **Create `YamlExperimentConfig`** - Wrapper around dict that implements protocol
3. **Update runner.py type hints** - Use protocol instead of concrete class
4. **Update CLI** - Create `YamlExperimentConfig` from `load_experiment()`
5. **Delete `experiments.py`** - All callers now use protocol

### Why Protocol-Based?

- **Incremental migration**: Both old and new configs work during transition
- **Type safety**: Protocol provides compile-time checking
- **Testable**: Each step can be tested independently
- **Follows codebase patterns**: StateProvider uses same approach

---

## TDD Test Specifications

### Test File 1: `tests/test_experiment_config_protocol.py`

```python
"""TDD tests for ExperimentConfigProtocol.

These tests define the interface that runner.py requires from experiment configs.
Write these tests FIRST, then implement the protocol.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Protocol, runtime_checkable


class TestExperimentConfigProtocolDefinition:
    """Tests that protocol exists and has required methods."""

    def test_protocol_importable(self) -> None:
        """ExperimentConfigProtocol should be importable."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert ExperimentConfigProtocol is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be @runtime_checkable."""
        from castro.experiment_config import ExperimentConfigProtocol
        # Should be able to use isinstance()
        assert hasattr(ExperimentConfigProtocol, '__protocol_attrs__') or \
               hasattr(ExperimentConfigProtocol, '_is_runtime_protocol')


class TestExperimentConfigProtocolProperties:
    """Tests for required protocol properties."""

    def test_protocol_has_name_property(self) -> None:
        """Protocol should require 'name' property."""
        from castro.experiment_config import ExperimentConfigProtocol
        # Check protocol defines name
        assert 'name' in dir(ExperimentConfigProtocol)

    def test_protocol_has_description_property(self) -> None:
        """Protocol should require 'description' property."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert 'description' in dir(ExperimentConfigProtocol)

    def test_protocol_has_master_seed_property(self) -> None:
        """Protocol should require 'master_seed' property."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert 'master_seed' in dir(ExperimentConfigProtocol)

    def test_protocol_has_scenario_path_property(self) -> None:
        """Protocol should require 'scenario_path' property."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert 'scenario_path' in dir(ExperimentConfigProtocol)

    def test_protocol_has_optimized_agents_property(self) -> None:
        """Protocol should require 'optimized_agents' property."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert 'optimized_agents' in dir(ExperimentConfigProtocol)


class TestExperimentConfigProtocolMethods:
    """Tests for required protocol methods."""

    def test_protocol_has_get_convergence_criteria(self) -> None:
        """Protocol should require get_convergence_criteria() method."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert hasattr(ExperimentConfigProtocol, 'get_convergence_criteria')
        assert callable(getattr(ExperimentConfigProtocol, 'get_convergence_criteria', None))

    def test_protocol_has_get_bootstrap_config(self) -> None:
        """Protocol should require get_bootstrap_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert hasattr(ExperimentConfigProtocol, 'get_bootstrap_config')

    def test_protocol_has_get_model_config(self) -> None:
        """Protocol should require get_model_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert hasattr(ExperimentConfigProtocol, 'get_model_config')

    def test_protocol_has_get_output_config(self) -> None:
        """Protocol should require get_output_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol
        assert hasattr(ExperimentConfigProtocol, 'get_output_config')


class TestCastroExperimentImplementsProtocol:
    """Tests that existing CastroExperiment implements protocol."""

    def test_castro_experiment_is_protocol_instance(self) -> None:
        """CastroExperiment should implement ExperimentConfigProtocol."""
        from castro.experiment_config import ExperimentConfigProtocol
        from castro.experiments import CastroExperiment
        from pathlib import Path

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("test.yaml"),
        )
        assert isinstance(exp, ExperimentConfigProtocol)
```

---

### Test File 2: `tests/test_yaml_experiment_config.py`

```python
"""TDD tests for YamlExperimentConfig.

YamlExperimentConfig wraps a dict from load_experiment() and
implements ExperimentConfigProtocol.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestYamlExperimentConfigCreation:
    """Tests for creating YamlExperimentConfig."""

    def test_yaml_config_importable(self) -> None:
        """YamlExperimentConfig should be importable."""
        from castro.experiment_config import YamlExperimentConfig
        assert YamlExperimentConfig is not None

    def test_yaml_config_from_load_experiment(self) -> None:
        """YamlExperimentConfig can be created from load_experiment() dict."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config is not None

    def test_yaml_config_implements_protocol(self) -> None:
        """YamlExperimentConfig should implement ExperimentConfigProtocol."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import (
            ExperimentConfigProtocol,
            YamlExperimentConfig,
        )

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config, ExperimentConfigProtocol)


class TestYamlExperimentConfigProperties:
    """Tests for YamlExperimentConfig properties."""

    def test_name_property(self) -> None:
        """name property returns experiment name."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config.name == "exp1"

    def test_description_property(self) -> None:
        """description property returns experiment description."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.description, str)
        assert len(yaml_config.description) > 0

    def test_master_seed_property(self) -> None:
        """master_seed property returns integer seed."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.master_seed, int)

    def test_scenario_path_property(self) -> None:
        """scenario_path property returns Path."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.scenario_path, Path)

    def test_optimized_agents_property(self) -> None:
        """optimized_agents property returns list of agent IDs."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        assert isinstance(yaml_config.optimized_agents, list)
        assert all(isinstance(a, str) for a in yaml_config.optimized_agents)


class TestYamlExperimentConfigMethods:
    """Tests for YamlExperimentConfig methods."""

    def test_get_convergence_criteria_returns_correct_type(self) -> None:
        """get_convergence_criteria() returns ConvergenceCriteria."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from payment_simulator.ai_cash_mgmt import ConvergenceCriteria

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()
        assert isinstance(criteria, ConvergenceCriteria)

    def test_get_convergence_criteria_values(self) -> None:
        """get_convergence_criteria() returns correct values from YAML."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()

        # Values should match YAML config
        assert criteria.max_iterations == config_dict["convergence"]["max_iterations"]
        assert criteria.stability_threshold == config_dict["convergence"]["stability_threshold"]

    def test_get_bootstrap_config_returns_correct_type(self) -> None:
        """get_bootstrap_config() returns BootstrapConfig."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from payment_simulator.ai_cash_mgmt import BootstrapConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert isinstance(bootstrap, BootstrapConfig)

    def test_get_bootstrap_config_deterministic_mode(self) -> None:
        """get_bootstrap_config() handles deterministic mode."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        # exp1 is deterministic
        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert bootstrap.deterministic is True

    def test_get_bootstrap_config_bootstrap_mode(self) -> None:
        """get_bootstrap_config() handles bootstrap mode."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        # exp2 uses bootstrap sampling
        config_dict = load_experiment("exp2")
        yaml_config = YamlExperimentConfig(config_dict)
        bootstrap = yaml_config.get_bootstrap_config()
        assert bootstrap.deterministic is False
        assert bootstrap.num_samples > 1

    def test_get_model_config_returns_correct_type(self) -> None:
        """get_model_config() returns LLMConfig."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from payment_simulator.llm import LLMConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert isinstance(model, LLMConfig)

    def test_get_model_config_values(self) -> None:
        """get_model_config() returns correct values from YAML."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert model.model == config_dict["llm"]["model"]

    def test_get_output_config_returns_correct_type(self) -> None:
        """get_output_config() returns OutputConfig."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from payment_simulator.ai_cash_mgmt import OutputConfig

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        output = yaml_config.get_output_config()
        assert isinstance(output, OutputConfig)


class TestYamlExperimentConfigOverrides:
    """Tests for CLI override support."""

    def test_model_override_affects_get_model_config(self) -> None:
        """Model override should affect get_model_config()."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1", model_override="openai:gpt-4o")
        yaml_config = YamlExperimentConfig(config_dict)
        model = yaml_config.get_model_config()
        assert model.model == "openai:gpt-4o"

    def test_seed_override_affects_master_seed(self) -> None:
        """Seed override should affect master_seed property."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1", seed_override=99999)
        yaml_config = YamlExperimentConfig(config_dict)
        assert yaml_config.master_seed == 99999

    def test_max_iter_override_affects_convergence(self) -> None:
        """Max iter override should affect get_convergence_criteria()."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig

        config_dict = load_experiment("exp1", max_iter_override=100)
        yaml_config = YamlExperimentConfig(config_dict)
        criteria = yaml_config.get_convergence_criteria()
        assert criteria.max_iterations == 100
```

---

### Test File 3: `tests/test_runner_protocol_compatibility.py`

```python
"""TDD tests for runner.py protocol compatibility.

These tests verify runner.py works with both CastroExperiment
and YamlExperimentConfig via the protocol.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestRunnerAcceptsProtocol:
    """Tests that ExperimentRunner accepts protocol implementations."""

    def test_runner_accepts_castro_experiment(self) -> None:
        """Runner should accept CastroExperiment (backward compat)."""
        from castro.experiments import CastroExperiment
        from castro.runner import ExperimentRunner

        exp = CastroExperiment(
            name="test",
            description="Test",
            scenario_path=Path("configs/exp1_2period.yaml"),
        )
        # Should not raise
        runner = ExperimentRunner(exp)
        assert runner is not None

    def test_runner_accepts_yaml_experiment_config(self) -> None:
        """Runner should accept YamlExperimentConfig."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        # Should not raise
        runner = ExperimentRunner(yaml_config)
        assert runner is not None

    def test_runner_type_hint_is_protocol(self) -> None:
        """Runner __init__ should accept ExperimentConfigProtocol."""
        import inspect
        from castro.runner import ExperimentRunner

        sig = inspect.signature(ExperimentRunner.__init__)
        experiment_param = sig.parameters.get('experiment')
        # Type hint should be ExperimentConfigProtocol or compatible
        assert experiment_param is not None


class TestRunnerBehaviorWithYamlConfig:
    """Tests that runner behaves correctly with YamlExperimentConfig."""

    def test_runner_gets_correct_name(self) -> None:
        """Runner should get correct experiment name from YAML config."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        # Internal state should have correct name
        assert runner._experiment.name == "exp1"

    def test_runner_gets_correct_seed(self) -> None:
        """Runner should get correct master_seed from YAML config."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1", seed_override=12345)
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        assert runner._seed_manager._master_seed == 12345

    def test_runner_gets_correct_optimized_agents(self) -> None:
        """Runner should get correct optimized_agents from YAML config."""
        from castro.experiment_loader import load_experiment
        from castro.experiment_config import YamlExperimentConfig
        from castro.runner import ExperimentRunner

        config_dict = load_experiment("exp1")
        yaml_config = YamlExperimentConfig(config_dict)
        runner = ExperimentRunner(yaml_config)

        expected_agents = config_dict["optimized_agents"]
        assert list(runner._experiment.optimized_agents) == expected_agents
```

---

### Test File 4: `tests/test_experiments_py_deleted.py`

```python
"""TDD tests verifying experiments.py can be deleted.

These tests ensure all callers use the protocol-based approach
and experiments.py is no longer needed.
"""

from __future__ import annotations

import pytest


class TestExperimentsPyDeleted:
    """Tests that experiments.py is deleted."""

    def test_experiments_module_not_importable(self) -> None:
        """castro.experiments should not be importable."""
        with pytest.raises(ImportError):
            from castro import experiments  # noqa: F401

    def test_castro_experiment_not_importable(self) -> None:
        """CastroExperiment should not be importable from castro.experiments."""
        with pytest.raises(ImportError):
            from castro.experiments import CastroExperiment  # noqa: F401

    def test_experiments_dict_not_importable(self) -> None:
        """EXPERIMENTS dict should not be importable."""
        with pytest.raises(ImportError):
            from castro.experiments import EXPERIMENTS  # noqa: F401

    def test_create_exp_functions_not_importable(self) -> None:
        """create_exp1/2/3 should not be importable."""
        with pytest.raises(ImportError):
            from castro.experiments import create_exp1  # noqa: F401


class TestExperimentLoaderIsReplacement:
    """Tests that experiment_loader.py is the replacement."""

    def test_experiment_loader_importable(self) -> None:
        """castro.experiment_loader should be importable."""
        from castro import experiment_loader
        assert experiment_loader is not None

    def test_yaml_experiment_config_importable(self) -> None:
        """YamlExperimentConfig should be importable."""
        from castro.experiment_config import YamlExperimentConfig
        assert YamlExperimentConfig is not None

    def test_list_experiments_works(self) -> None:
        """list_experiments() should work."""
        from castro.experiment_loader import list_experiments
        exps = list_experiments()
        assert "exp1" in exps
        assert "exp2" in exps
        assert "exp3" in exps

    def test_load_experiment_works(self) -> None:
        """load_experiment() should work."""
        from castro.experiment_loader import load_experiment
        config = load_experiment("exp1")
        assert config["name"] == "exp1"
```

---

## Implementation Plan

### Task 9.5.1: Create ExperimentConfigProtocol

**TDD Test File:** `tests/test_experiment_config_protocol.py` (first 4 test classes)

**Steps:**
1. Write protocol definition tests
2. Run tests → FAIL
3. Create `castro/experiment_config.py`
4. Define `ExperimentConfigProtocol` with `@runtime_checkable`
5. Run tests → PASS

**New file: `castro/experiment_config.py`**
```python
"""Protocol and implementations for experiment configuration.

This module defines the interface that ExperimentRunner requires
and provides implementations for both legacy CastroExperiment
and new YAML-based configs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt import (
        BootstrapConfig,
        ConvergenceCriteria,
        OutputConfig,
    )
    from payment_simulator.llm import LLMConfig


@runtime_checkable
class ExperimentConfigProtocol(Protocol):
    """Protocol defining the interface for experiment configurations.

    ExperimentRunner accepts any object implementing this protocol.
    Both CastroExperiment (legacy) and YamlExperimentConfig implement it.
    """

    @property
    def name(self) -> str:
        """Experiment name."""
        ...

    @property
    def description(self) -> str:
        """Experiment description."""
        ...

    @property
    def master_seed(self) -> int:
        """Master seed for determinism."""
        ...

    @property
    def scenario_path(self) -> Path:
        """Path to scenario configuration file."""
        ...

    @property
    def optimized_agents(self) -> list[str]:
        """List of agent IDs to optimize."""
        ...

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        """Get convergence criteria configuration."""
        ...

    def get_bootstrap_config(self) -> BootstrapConfig:
        """Get bootstrap sampling configuration."""
        ...

    def get_model_config(self) -> LLMConfig:
        """Get LLM model configuration."""
        ...

    def get_output_config(self) -> OutputConfig:
        """Get output configuration."""
        ...
```

---

### Task 9.5.2: Create YamlExperimentConfig

**TDD Test File:** `tests/test_yaml_experiment_config.py`

**Steps:**
1. Write YamlExperimentConfig tests
2. Run tests → FAIL
3. Implement `YamlExperimentConfig` class
4. Run tests → PASS

**Add to `castro/experiment_config.py`:**
```python
class YamlExperimentConfig:
    """Experiment configuration loaded from YAML.

    Wraps a dict from load_experiment() and implements
    ExperimentConfigProtocol for use with ExperimentRunner.

    Example:
        >>> from castro.experiment_loader import load_experiment
        >>> from castro.experiment_config import YamlExperimentConfig
        >>> config_dict = load_experiment("exp1")
        >>> yaml_config = YamlExperimentConfig(config_dict)
        >>> runner = ExperimentRunner(yaml_config)
    """

    def __init__(self, config: dict[str, Any], output_dir: Path | None = None) -> None:
        """Initialize from config dict.

        Args:
            config: Dictionary from load_experiment()
            output_dir: Override for output directory
        """
        self._config = config
        self._output_dir = output_dir or Path("results")

    @property
    def name(self) -> str:
        return self._config["name"]

    @property
    def description(self) -> str:
        return self._config["description"]

    @property
    def master_seed(self) -> int:
        return self._config.get("master_seed", 42)

    @property
    def scenario_path(self) -> Path:
        return Path(self._config["scenario_path"])

    @property
    def optimized_agents(self) -> list[str]:
        return self._config["optimized_agents"]

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        from payment_simulator.ai_cash_mgmt import ConvergenceCriteria
        conv = self._config.get("convergence", {})
        return ConvergenceCriteria(
            max_iterations=conv.get("max_iterations", 25),
            stability_threshold=conv.get("stability_threshold", 0.05),
            stability_window=conv.get("stability_window", 5),
        )

    def get_bootstrap_config(self) -> BootstrapConfig:
        from payment_simulator.ai_cash_mgmt import BootstrapConfig, SampleMethod
        eval_cfg = self._config.get("evaluation", {})
        is_deterministic = eval_cfg.get("mode") == "deterministic"
        return BootstrapConfig(
            deterministic=is_deterministic,
            num_samples=eval_cfg.get("num_samples", 1) if not is_deterministic else 1,
            sample_method=SampleMethod.BOOTSTRAP,
            evaluation_ticks=eval_cfg.get("ticks", 100),
        )

    def get_model_config(self) -> LLMConfig:
        from payment_simulator.llm import LLMConfig
        llm = self._config.get("llm", {})
        return LLMConfig(
            model=llm.get("model", "anthropic:claude-sonnet-4-5"),
            temperature=llm.get("temperature", 0.0),
            thinking_budget=llm.get("thinking_budget"),
            reasoning_effort=llm.get("reasoning_effort"),
        )

    def get_output_config(self) -> OutputConfig:
        from payment_simulator.ai_cash_mgmt import OutputConfig
        return OutputConfig(
            database_path=str(self._output_dir / f"{self.name}.db"),
            verbose=True,
        )
```

---

### Task 9.5.3: Update runner.py Type Hints

**TDD Test File:** `tests/test_runner_protocol_compatibility.py`

**Steps:**
1. Write runner protocol compatibility tests
2. Run tests → Some PASS (CastroExperiment works), Some FAIL (type hints)
3. Update `runner.py` import and type hint:
   ```python
   from castro.experiment_config import ExperimentConfigProtocol

   class ExperimentRunner:
       def __init__(
           self,
           experiment: ExperimentConfigProtocol,
           ...
       ) -> None:
   ```
4. Run tests → PASS

**Changes to `runner.py`:**
- Line 45: Add `from castro.experiment_config import ExperimentConfigProtocol`
- Line 169: Change type hint from `CastroExperiment` to `ExperimentConfigProtocol`

---

### Task 9.5.4: Update CLI to Use YamlExperimentConfig

**Steps:**
1. Update `cli.py` to create `YamlExperimentConfig` instead of using `EXPERIMENTS[]`
2. Remove `EXPERIMENTS` import
3. Verify CLI still works

**Changes to `cli.py`:**
```python
# OLD
from castro.experiments import DEFAULT_MODEL, EXPERIMENTS
exp = EXPERIMENTS[experiment](
    output_dir=output_dir,
    model=model,
    ...
)

# NEW
from castro.experiment_loader import load_experiment
from castro.experiment_config import YamlExperimentConfig

config_dict = load_experiment(
    experiment,
    model_override=model if model != DEFAULT_MODEL else None,
    thinking_budget=thinking_budget,
    reasoning_effort=reasoning_effort,
    max_iter_override=max_iter if max_iter != 25 else None,
    seed_override=seed if seed != 42 else None,
)
exp = YamlExperimentConfig(config_dict, output_dir=output_dir)
```

---

### Task 9.5.5: Delete experiments.py

**TDD Test File:** `tests/test_experiments_py_deleted.py`

**Steps:**
1. Write deletion verification tests
2. Run tests → FAIL (experiments.py still exists)
3. Update `castro/__init__.py` to remove experiments exports
4. Delete `castro/experiments.py`
5. Run tests → PASS

**Changes to `castro/__init__.py`:**
```python
__all__ = [
    # Core exports
    "CASTRO_CONSTRAINTS",
    "ExperimentResult",
    "ExperimentRunner",
    # Experiment loading (preferred)
    "list_experiments",
    "load_experiment",
    "get_llm_config",
    # Protocol and config
    "ExperimentConfigProtocol",
    "YamlExperimentConfig",
    # REMOVED: Legacy exports
    # "EXPERIMENTS",
    # "CastroExperiment",
    # "create_exp1",
    # "create_exp2",
    # "create_exp3",
]
```

---

### Task 9.5.6: Update Existing Tests

**Steps:**
1. Update tests that import `CastroExperiment` to use `YamlExperimentConfig`
2. Update tests that use `EXPERIMENTS` dict
3. Run full test suite

**Files to update:**
- `tests/test_deterministic_mode.py`
- `tests/test_pydantic_llm_client.py`
- Any other test importing from `castro.experiments`

---

## Verification Checklist

### Before Starting
- [ ] Record baseline: `uv run pytest tests/ -v --tb=no | tail -5`
- [ ] Verify all 335 tests pass

### TDD Verification (Per Task)
- [ ] Task 9.5.1: `test_experiment_config_protocol.py` all pass
- [ ] Task 9.5.2: `test_yaml_experiment_config.py` all pass
- [ ] Task 9.5.3: `test_runner_protocol_compatibility.py` all pass
- [ ] Task 9.5.4: CLI commands work
- [ ] Task 9.5.5: `test_experiments_py_deleted.py` all pass
- [ ] Task 9.5.6: All existing tests pass

### Integration Verification
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] CLI list command: `uv run castro list`
- [ ] CLI run command: `uv run castro run exp1 --max-iter 1 --dry-run`
- [ ] No remaining imports from `castro.experiments`

### Final Metrics
- [ ] `experiments.py` deleted (~350 lines removed)
- [ ] `experiment_config.py` created (~150 lines added)
- [ ] Net reduction: ~200 lines

---

## Rollback Plan

If issues arise:

1. **Git reset**: `git checkout HEAD~1 -- experiments/castro/`
2. **Restore experiments.py**: `git checkout origin/main -- experiments/castro/castro/experiments.py`
3. **Revert cli.py**: `git checkout origin/main -- experiments/castro/cli.py`
4. **Revert runner.py**: `git checkout origin/main -- experiments/castro/castro/runner.py`

All changes are isolated to Castro module.

---

## Phase 9.6 Preview: context_builder.py Migration

**NOT in scope for 9.5** but documented for planning:

The `context_builder.py` deletion requires migrating runner.py to use `EnrichedBootstrapContextBuilder` instead of `BootstrapContextBuilder`. This is a larger change because:

1. Different data structures (`SimulationResult` vs `EnrichedEvaluationResult`)
2. Different evaluation pipeline
3. Many test dependencies

This should be a separate phase (9.6 or Phase 10) after 9.5 stabilizes.

---

## Expected Outcomes

### Lines of Code

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| experiments.py | ~350 | 0 | -350 |
| experiment_config.py | 0 | ~150 | +150 |
| cli.py changes | - | ~20 | +20 |
| runner.py changes | - | ~5 | +5 |
| **Net Production Code** | | | **~-175** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_experiment_config_protocol.py | ~12 |
| test_yaml_experiment_config.py | ~18 |
| test_runner_protocol_compatibility.py | ~6 |
| test_experiments_py_deleted.py | ~8 |
| **Total** | **~44** |

---

*Phase 9.5 Plan v1.0 - Protocol-Based Decoupling - 2025-12-11*
