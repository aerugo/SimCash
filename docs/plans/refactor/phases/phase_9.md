# Phase 9: Castro Module Slimming

**Status:** Planned
**Created:** 2025-12-11
**Last Updated:** 2025-12-11
**Dependencies:** Phase 8 (Bootstrap Terminology Migration)
**Risk:** Low (internal cleanup)
**Breaking Changes:** None

---

## Purpose

Reduce Castro module complexity by removing redundant code and leveraging core SimCash modules. After this phase, Castro becomes a thin experiment-specific layer.

**Target outcome**: ~400 lines of code removed, cleaner architecture.

---

## Issues to Fix

| ID | Issue | Severity | File(s) | Lines Affected |
|----|-------|----------|---------|----------------|
| 9.1 | `EVENT_MONTE_CARLO_EVALUATION` → `EVENT_BOOTSTRAP_EVALUATION` | High | `events.py` | ~30 |
| 9.2 | `create_monte_carlo_event()` → `create_bootstrap_evaluation_event()` | High | `events.py`, `runner.py` | ~50 |
| 9.3 | Duplicate VerboseConfig classes | High | `verbose_logging.py`, `display.py` | ~100 |
| 9.4 | Redundant `experiments.py` | High | `experiments.py` | ~350 |
| 9.5 | Obsolete `context_builder.py` | Medium | `context_builder.py` | ~100 |
| 9.6 | CLI imports from EXPERIMENTS dict | Medium | `cli.py` | ~20 |
| 9.7 | Update `__init__.py` exports | Low | `__init__.py` | ~10 |

---

## TDD Test Specifications

### Test File 1: `tests/test_events_bootstrap_terminology.py`

```python
"""TDD tests for bootstrap terminology in events.py.

These tests verify the terminology migration from Monte Carlo to Bootstrap.
Write these tests FIRST, then implement changes to make them pass.
"""

import pytest
from datetime import datetime


class TestEventTypeConstants:
    """Tests for event type constant naming."""

    def test_bootstrap_evaluation_constant_exists(self) -> None:
        """EVENT_BOOTSTRAP_EVALUATION constant should exist."""
        from castro.events import EVENT_BOOTSTRAP_EVALUATION
        assert EVENT_BOOTSTRAP_EVALUATION == "bootstrap_evaluation"

    def test_monte_carlo_constant_removed(self) -> None:
        """EVENT_MONTE_CARLO_EVALUATION constant should NOT exist."""
        from castro import events
        assert not hasattr(events, "EVENT_MONTE_CARLO_EVALUATION")

    def test_all_event_types_contains_bootstrap(self) -> None:
        """ALL_EVENT_TYPES should contain bootstrap_evaluation."""
        from castro.events import ALL_EVENT_TYPES
        assert "bootstrap_evaluation" in ALL_EVENT_TYPES
        assert "monte_carlo_evaluation" not in ALL_EVENT_TYPES


class TestBootstrapEventCreation:
    """Tests for create_bootstrap_evaluation_event function."""

    def test_create_bootstrap_evaluation_event_exists(self) -> None:
        """create_bootstrap_evaluation_event function should exist."""
        from castro.events import create_bootstrap_evaluation_event
        assert callable(create_bootstrap_evaluation_event)

    def test_create_monte_carlo_event_removed(self) -> None:
        """create_monte_carlo_event function should NOT exist."""
        from castro import events
        assert not hasattr(events, "create_monte_carlo_event")

    def test_create_bootstrap_evaluation_event_returns_correct_type(self) -> None:
        """Event should have event_type='bootstrap_evaluation'."""
        from castro.events import (
            create_bootstrap_evaluation_event,
            EVENT_BOOTSTRAP_EVALUATION,
        )
        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[{"seed": 42, "cost": 1000}],
            mean_cost=1000,
            std_cost=100,
        )
        assert event.event_type == EVENT_BOOTSTRAP_EVALUATION
        assert event.event_type == "bootstrap_evaluation"

    def test_create_bootstrap_evaluation_event_has_required_details(self) -> None:
        """Event details should contain seed_results, mean_cost, std_cost."""
        from castro.events import create_bootstrap_evaluation_event
        seed_results = [
            {"seed": 42, "cost": 1000, "settled": 5, "total": 6},
            {"seed": 43, "cost": 1200, "settled": 4, "total": 6},
        ]
        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=2,
            seed_results=seed_results,
            mean_cost=1100,
            std_cost=141,
        )
        assert event.details["seed_results"] == seed_results
        assert event.details["mean_cost"] == 1100
        assert event.details["std_cost"] == 141
        assert event.iteration == 2

    def test_bootstrap_event_costs_are_integers(self) -> None:
        """Costs should be integers (INV-1 compliance)."""
        from castro.events import create_bootstrap_evaluation_event
        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[{"seed": 42, "cost": 1000}],
            mean_cost=1000,
            std_cost=100,
        )
        assert isinstance(event.details["mean_cost"], int)
        assert isinstance(event.details["std_cost"], int)


class TestEventSerialization:
    """Tests for event serialization with new naming."""

    def test_bootstrap_event_to_dict_has_correct_type(self) -> None:
        """Serialized event should have event_type='bootstrap_evaluation'."""
        from castro.events import create_bootstrap_evaluation_event
        event = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=1,
            seed_results=[],
            mean_cost=0,
            std_cost=0,
        )
        event_dict = event.to_dict()
        assert event_dict["event_type"] == "bootstrap_evaluation"

    def test_bootstrap_event_round_trip(self) -> None:
        """Event should survive serialization round-trip."""
        from castro.events import (
            create_bootstrap_evaluation_event,
            ExperimentEvent,
        )
        original = create_bootstrap_evaluation_event(
            run_id="test-run",
            iteration=5,
            seed_results=[{"seed": 99, "cost": 500}],
            mean_cost=500,
            std_cost=0,
        )
        event_dict = original.to_dict()
        restored = ExperimentEvent.from_dict(event_dict)
        assert restored.event_type == original.event_type
        assert restored.details == original.details
```

**Expected TDD Cycle:**
1. Run tests → All FAIL (functions don't exist yet)
2. Rename `EVENT_MONTE_CARLO_EVALUATION` → `EVENT_BOOTSTRAP_EVALUATION`
3. Run tests → Some pass
4. Rename `create_monte_carlo_event` → `create_bootstrap_evaluation_event`
5. Run tests → All pass

---

### Test File 2: `tests/test_verbose_config_unified.py`

```python
"""TDD tests for unified VerboseConfig.

These tests verify that there is exactly ONE VerboseConfig class
and it serves all display needs.
"""

import pytest


class TestVerboseConfigSingleSource:
    """Tests ensuring VerboseConfig has single source of truth."""

    def test_verbose_logging_exports_verbose_config(self) -> None:
        """verbose_logging.py should export VerboseConfig."""
        from castro.verbose_logging import VerboseConfig
        assert VerboseConfig is not None

    def test_display_imports_from_verbose_logging(self) -> None:
        """display.py should import VerboseConfig from verbose_logging."""
        from castro.display import VerboseConfig as DisplayConfig
        from castro.verbose_logging import VerboseConfig as LoggingConfig
        # Both should be the exact same class
        assert DisplayConfig is LoggingConfig

    def test_no_duplicate_verbose_config(self) -> None:
        """There should be only ONE VerboseConfig class definition."""
        import inspect
        import castro.display as display_module
        import castro.verbose_logging as logging_module

        # VerboseConfig should be defined in verbose_logging
        # and only imported (not redefined) in display
        logging_source = inspect.getfile(logging_module.VerboseConfig)
        display_source = inspect.getfile(display_module.VerboseConfig)

        # Both should point to verbose_logging.py
        assert "verbose_logging" in logging_source
        assert logging_source == display_source or "verbose_logging" in display_source


class TestVerboseConfigFields:
    """Tests for VerboseConfig field names (unified)."""

    def test_has_iterations_field(self) -> None:
        """VerboseConfig should have 'iterations' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "iterations")

    def test_has_bootstrap_field(self) -> None:
        """VerboseConfig should have 'bootstrap' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "bootstrap")

    def test_has_llm_field(self) -> None:
        """VerboseConfig should have 'llm' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "llm")

    def test_has_policy_field(self) -> None:
        """VerboseConfig should have 'policy' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "policy")

    def test_has_rejections_field(self) -> None:
        """VerboseConfig should have 'rejections' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "rejections")

    def test_has_debug_field(self) -> None:
        """VerboseConfig should have 'debug' field."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert hasattr(config, "debug")

    def test_no_show_prefix_fields(self) -> None:
        """VerboseConfig should NOT have 'show_*' prefixed fields."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        field_names = [f.name for f in config.__dataclass_fields__.values()]
        show_fields = [f for f in field_names if f.startswith("show_")]
        assert show_fields == [], f"Found deprecated 'show_*' fields: {show_fields}"


class TestVerboseConfigConstructors:
    """Tests for VerboseConfig factory methods."""

    def test_all_enabled_sets_main_flags_true(self) -> None:
        """all_enabled() should set all main flags except debug."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig.all_enabled()
        assert config.iterations is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is True
        assert config.rejections is True
        assert config.debug is False  # Debug stays off

    def test_from_cli_flags_verbose_enables_all(self) -> None:
        """from_cli_flags with verbose=True enables all."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig.from_cli_flags(verbose=True)
        assert config.iterations is True
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is True
        assert config.rejections is True

    def test_from_cli_flags_individual_override(self) -> None:
        """Individual flags should work independently."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig.from_cli_flags(
            verbose=False,
            verbose_bootstrap=True,
            verbose_llm=True,
        )
        assert config.iterations is False
        assert config.bootstrap is True
        assert config.llm is True
        assert config.policy is False
        assert config.rejections is False

    def test_from_cli_flags_debug_independent(self) -> None:
        """Debug flag should work independently of verbose."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig.from_cli_flags(verbose=False, debug=True)
        assert config.debug is True
        assert config.bootstrap is False

    def test_any_property_true_when_any_flag_set(self) -> None:
        """'any' property returns True if any flag is set."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig(bootstrap=True)
        assert config.any is True

    def test_any_property_false_when_all_off(self) -> None:
        """'any' property returns False when all flags are False."""
        from castro.verbose_logging import VerboseConfig
        config = VerboseConfig()
        assert config.any is False
```

**Expected TDD Cycle:**
1. Run tests → Many FAIL (display.py has its own VerboseConfig)
2. Unify VerboseConfig field names in verbose_logging.py
3. Update display.py to import from verbose_logging
4. Remove duplicate class from display.py
5. Update all callers
6. Run tests → All pass

---

### Test File 3: `tests/test_experiment_loader.py`

```python
"""TDD tests for YAML-based experiment loading.

These tests define the interface for experiment_loader.py
which replaces experiments.py.
"""

import pytest
from pathlib import Path


class TestListExperiments:
    """Tests for listing available experiments."""

    def test_list_experiments_returns_list(self) -> None:
        """list_experiments() should return a list of strings."""
        from castro.experiment_loader import list_experiments
        result = list_experiments()
        assert isinstance(result, list)

    def test_list_experiments_contains_exp1(self) -> None:
        """list_experiments() should include 'exp1'."""
        from castro.experiment_loader import list_experiments
        result = list_experiments()
        assert "exp1" in result

    def test_list_experiments_contains_exp2(self) -> None:
        """list_experiments() should include 'exp2'."""
        from castro.experiment_loader import list_experiments
        result = list_experiments()
        assert "exp2" in result

    def test_list_experiments_contains_exp3(self) -> None:
        """list_experiments() should include 'exp3'."""
        from castro.experiment_loader import list_experiments
        result = list_experiments()
        assert "exp3" in result


class TestLoadExperiment:
    """Tests for loading individual experiments."""

    def test_load_experiment_returns_dict(self) -> None:
        """load_experiment() should return a dictionary."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert isinstance(result, dict)

    def test_load_experiment_has_name(self) -> None:
        """Loaded experiment should have 'name' field."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert "name" in result
        assert result["name"] == "exp1"

    def test_load_experiment_has_description(self) -> None:
        """Loaded experiment should have 'description' field."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert "description" in result
        assert isinstance(result["description"], str)

    def test_load_experiment_has_evaluation_config(self) -> None:
        """Loaded experiment should have 'evaluation' config."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert "evaluation" in result
        assert "mode" in result["evaluation"]
        assert "ticks" in result["evaluation"]

    def test_load_experiment_has_llm_config(self) -> None:
        """Loaded experiment should have 'llm' config."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert "llm" in result
        assert "model" in result["llm"]

    def test_load_experiment_has_optimized_agents(self) -> None:
        """Loaded experiment should have 'optimized_agents' list."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1")
        assert "optimized_agents" in result
        assert isinstance(result["optimized_agents"], list)


class TestLoadExperimentOverrides:
    """Tests for CLI override parameters."""

    def test_model_override_changes_llm_model(self) -> None:
        """model_override should change the LLM model."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1", model_override="openai:gpt-4o")
        assert result["llm"]["model"] == "openai:gpt-4o"

    def test_thinking_budget_override(self) -> None:
        """thinking_budget should be added to LLM config."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1", thinking_budget=16000)
        assert result["llm"]["thinking_budget"] == 16000

    def test_reasoning_effort_override(self) -> None:
        """reasoning_effort should be added to LLM config."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1", reasoning_effort="high")
        assert result["llm"]["reasoning_effort"] == "high"

    def test_max_iter_override(self) -> None:
        """max_iter_override should change max_iterations."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1", max_iter_override=100)
        assert result["convergence"]["max_iterations"] == 100

    def test_seed_override(self) -> None:
        """seed_override should change master_seed."""
        from castro.experiment_loader import load_experiment
        result = load_experiment("exp1", seed_override=99999)
        assert result["master_seed"] == 99999


class TestLoadExperimentErrors:
    """Tests for error handling."""

    def test_load_nonexistent_raises_file_not_found(self) -> None:
        """Loading nonexistent experiment should raise FileNotFoundError."""
        from castro.experiment_loader import load_experiment
        with pytest.raises(FileNotFoundError):
            load_experiment("nonexistent_experiment")

    def test_error_message_includes_name(self) -> None:
        """Error message should include the experiment name."""
        from castro.experiment_loader import load_experiment
        with pytest.raises(FileNotFoundError) as exc_info:
            load_experiment("fake_experiment")
        assert "fake_experiment" in str(exc_info.value)


class TestGetLLMConfig:
    """Tests for extracting LLMConfig from experiment config."""

    def test_get_llm_config_returns_llm_config(self) -> None:
        """get_llm_config() should return LLMConfig instance."""
        from castro.experiment_loader import load_experiment, get_llm_config
        from payment_simulator.llm import LLMConfig

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        assert isinstance(llm_config, LLMConfig)

    def test_get_llm_config_preserves_model(self) -> None:
        """LLMConfig should have correct model."""
        from castro.experiment_loader import load_experiment, get_llm_config

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        assert llm_config.model == exp_config["llm"]["model"]

    def test_get_llm_config_preserves_temperature(self) -> None:
        """LLMConfig should have correct temperature."""
        from castro.experiment_loader import load_experiment, get_llm_config

        exp_config = load_experiment("exp1")
        llm_config = get_llm_config(exp_config)

        expected_temp = exp_config["llm"].get("temperature", 0.0)
        assert llm_config.temperature == expected_temp
```

**Expected TDD Cycle:**
1. Run tests → All FAIL (experiment_loader.py doesn't exist)
2. Create experiment_loader.py with list_experiments()
3. Run tests → Some pass
4. Add load_experiment() with basic loading
5. Run tests → More pass
6. Add override parameters
7. Add error handling
8. Add get_llm_config()
9. Run tests → All pass

---

### Test File 4: `tests/test_experiments_py_removed.py`

```python
"""TDD tests verifying experiments.py is removed.

These tests ensure experiments.py is deleted and
its functionality is replaced by experiment_loader.py.
"""

import pytest


class TestExperimentsPyRemoved:
    """Tests that experiments.py no longer exists."""

    def test_experiments_module_removed(self) -> None:
        """Importing castro.experiments should fail."""
        with pytest.raises(ImportError):
            from castro import experiments  # noqa: F401

    def test_experiments_dict_not_importable(self) -> None:
        """EXPERIMENTS dict should not be importable."""
        with pytest.raises(ImportError):
            from castro.experiments import EXPERIMENTS  # noqa: F401

    def test_create_exp_functions_not_importable(self) -> None:
        """create_exp1/2/3 functions should not be importable."""
        with pytest.raises(ImportError):
            from castro.experiments import create_exp1  # noqa: F401

    def test_castro_experiment_class_not_importable(self) -> None:
        """CastroExperiment class should not be importable."""
        with pytest.raises(ImportError):
            from castro.experiments import CastroExperiment  # noqa: F401


class TestExperimentLoaderReplacement:
    """Tests that experiment_loader.py replaces experiments.py."""

    def test_experiment_loader_importable(self) -> None:
        """castro.experiment_loader should be importable."""
        from castro import experiment_loader  # noqa: F401

    def test_list_experiments_replaces_experiments_dict_keys(self) -> None:
        """list_experiments() should return same experiments as old EXPERIMENTS dict."""
        from castro.experiment_loader import list_experiments
        exps = list_experiments()
        # These were the keys in the old EXPERIMENTS dict
        assert set(exps) >= {"exp1", "exp2", "exp3"}

    def test_load_experiment_replaces_factory_functions(self) -> None:
        """load_experiment() should replace create_exp1/2/3 factory functions."""
        from castro.experiment_loader import load_experiment

        # Should be able to load all three experiments
        exp1 = load_experiment("exp1")
        exp2 = load_experiment("exp2")
        exp3 = load_experiment("exp3")

        assert exp1["name"] == "exp1"
        assert exp2["name"] == "exp2"
        assert exp3["name"] == "exp3"
```

---

### Test File 5: `tests/test_context_builder_removed.py`

```python
"""TDD tests verifying context_builder.py is removed.

context_builder.py was replaced by bootstrap_context.py.
"""

import pytest


class TestContextBuilderRemoved:
    """Tests that context_builder.py is removed."""

    def test_context_builder_module_removed(self) -> None:
        """Importing castro.context_builder should fail."""
        with pytest.raises(ImportError):
            from castro import context_builder  # noqa: F401

    def test_bootstrap_context_builder_not_in_context_builder(self) -> None:
        """BootstrapContextBuilder should not come from context_builder.py."""
        # The class exists in bootstrap_context.py, not context_builder.py
        with pytest.raises(ImportError):
            from castro.context_builder import BootstrapContextBuilder  # noqa: F401


class TestBootstrapContextReplacement:
    """Tests that bootstrap_context.py is the replacement."""

    def test_enriched_bootstrap_context_builder_importable(self) -> None:
        """EnrichedBootstrapContextBuilder should be importable."""
        from castro.bootstrap_context import EnrichedBootstrapContextBuilder
        assert EnrichedBootstrapContextBuilder is not None

    def test_bootstrap_context_module_exists(self) -> None:
        """castro.bootstrap_context module should exist."""
        from castro import bootstrap_context  # noqa: F401
```

---

## Implementation Plan

### Task 9.1: Fix Terminology in events.py

**TDD Test File:** `tests/test_events_bootstrap_terminology.py`

**Steps:**
1. Write tests for EVENT_BOOTSTRAP_EVALUATION constant
2. Write tests for create_bootstrap_evaluation_event function
3. Run tests → FAIL
4. Rename EVENT_MONTE_CARLO_EVALUATION → EVENT_BOOTSTRAP_EVALUATION
5. Rename create_monte_carlo_event → create_bootstrap_evaluation_event
6. Update ALL_EVENT_TYPES list
7. Run tests → PASS

**Files to modify:**
- `castro/events.py`: Rename constant and function
- `castro/runner.py`: Update call site
- `castro/display.py`: Update event type string
- `castro/state_provider.py`: Update event type string
- `tests/test_events.py`: Update assertions

---

### Task 9.2: Consolidate VerboseConfig

**TDD Test File:** `tests/test_verbose_config_unified.py`

**Steps:**
1. Write tests for unified VerboseConfig
2. Run tests → FAIL
3. Update `verbose_logging.py` VerboseConfig with unified fields:
   - `iterations` (was missing)
   - `bootstrap`
   - `llm`
   - `policy`
   - `rejections`
   - `debug`
4. Add `all_enabled()` classmethod
5. Update `from_cli_flags()` with new parameter names
6. Remove VerboseConfig from `display.py`, import instead
7. Update `display.py` to use new field names
8. Update `runner.py` to use unified VerboseConfig
9. Update `cli.py` flag names
10. Run tests → PASS

**Files to modify:**
- `castro/verbose_logging.py`: Unify VerboseConfig
- `castro/display.py`: Remove duplicate, import from verbose_logging
- `castro/runner.py`: Update usage
- `castro/cli.py`: Update flag names

---

### Task 9.3: Create experiment_loader.py

**TDD Test File:** `tests/test_experiment_loader.py`

**Steps:**
1. Write tests for list_experiments()
2. Write tests for load_experiment()
3. Write tests for override parameters
4. Write tests for error handling
5. Write tests for get_llm_config()
6. Run tests → FAIL
7. Create `castro/experiment_loader.py` with ~50 lines
8. Implement list_experiments()
9. Implement load_experiment() with basic loading
10. Add override parameters
11. Add error handling
12. Add get_llm_config()
13. Run tests → PASS

**New file:**
```python
# castro/experiment_loader.py
"""YAML-based experiment loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from payment_simulator.llm import LLMConfig


EXPERIMENTS_DIR = Path(__file__).parent.parent / "experiments"


def list_experiments() -> list[str]:
    """List available experiment names."""
    return [p.stem for p in EXPERIMENTS_DIR.glob("*.yaml")]


def load_experiment(
    name: str,
    *,
    model_override: str | None = None,
    thinking_budget: int | None = None,
    reasoning_effort: str | None = None,
    max_iter_override: int | None = None,
    seed_override: int | None = None,
) -> dict[str, Any]:
    """Load experiment configuration from YAML."""
    yaml_path = EXPERIMENTS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        msg = f"Experiment not found: {name} (looked for {yaml_path})"
        raise FileNotFoundError(msg)

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    # Apply overrides
    if model_override:
        config["llm"]["model"] = model_override
    if thinking_budget:
        config["llm"]["thinking_budget"] = thinking_budget
    if reasoning_effort:
        config["llm"]["reasoning_effort"] = reasoning_effort
    if max_iter_override:
        config["convergence"]["max_iterations"] = max_iter_override
    if seed_override:
        config["master_seed"] = seed_override

    return config


def get_llm_config(experiment_config: dict[str, Any]) -> LLMConfig:
    """Extract LLMConfig from experiment config."""
    llm = experiment_config["llm"]
    return LLMConfig(
        model=llm["model"],
        temperature=llm.get("temperature", 0.0),
        max_retries=llm.get("max_retries", 3),
        timeout_seconds=llm.get("timeout_seconds", 120),
        thinking_budget=llm.get("thinking_budget"),
        reasoning_effort=llm.get("reasoning_effort"),
    )
```

---

### Task 9.4: Delete experiments.py

**TDD Test File:** `tests/test_experiments_py_removed.py`

**Steps:**
1. Write tests verifying experiments.py is not importable
2. Run tests → FAIL (experiments.py still exists)
3. Update cli.py to use experiment_loader instead of EXPERIMENTS
4. Update any other imports
5. Delete experiments.py
6. Run tests → PASS

**Files to modify:**
- `castro/cli.py`: Update imports
- `castro/__init__.py`: Remove experiments.py exports
- Delete: `castro/experiments.py`

---

### Task 9.5: Delete context_builder.py

**TDD Test File:** `tests/test_context_builder_removed.py`

**Steps:**
1. Write tests verifying context_builder.py is not importable
2. Verify bootstrap_context.py is the replacement
3. Run tests → FAIL
4. Verify runner.py uses EnrichedBootstrapContextBuilder
5. Update any remaining imports
6. Delete context_builder.py
7. Run tests → PASS

**Files to modify:**
- `castro/__init__.py`: Remove context_builder exports
- Delete: `castro/context_builder.py`

---

### Task 9.6: Update __init__.py exports

**Steps:**
1. Remove exports for deleted modules
2. Add exports for experiment_loader
3. Update VerboseConfig export location
4. Verify all public API still works

**File to modify:**
- `castro/__init__.py`

---

## Verification Checklist

### Before Starting (Capture Baseline)
- [ ] Record total test count: `cd experiments/castro && uv run pytest tests/ -v --tb=no | tail -5`
- [ ] Record all tests pass
- [ ] Record line count of castro module

### TDD Verification (Per Task)
- [ ] Task 9.1: `test_events_bootstrap_terminology.py` all pass
- [ ] Task 9.2: `test_verbose_config_unified.py` all pass
- [ ] Task 9.3: `test_experiment_loader.py` all pass
- [ ] Task 9.4: `test_experiments_py_removed.py` all pass
- [ ] Task 9.5: `test_context_builder_removed.py` all pass

### Integration Verification
- [ ] All existing tests pass: `uv run pytest tests/ -v`
- [ ] No remaining monte_carlo terminology: `grep -r "monte_carlo" castro/ --include="*.py"`
- [ ] No remaining MONTE_CARLO constants: `grep -r "MONTE_CARLO" castro/ --include="*.py"`
- [ ] CLI list command works: `uv run castro list`
- [ ] CLI run command works: `uv run castro run exp1 --max-iter 1 --dry-run`
- [ ] Replay still works (if database exists)

### Final Metrics
- [ ] Record new line count (expect ~400 less)
- [ ] Files deleted: experiments.py, context_builder.py
- [ ] New file created: experiment_loader.py (~50 lines)

---

## Rollback Plan

If issues arise during implementation:

1. **Git reset**: All changes are in a single branch, can be reverted
2. **Restore deleted files**: `git checkout HEAD~1 -- castro/experiments.py castro/context_builder.py`
3. **Revert cli.py**: `git checkout HEAD~1 -- castro/cli.py`

All changes are isolated to the Castro module - no core SimCash changes.

---

## Expected Outcomes

### Lines of Code

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| experiments.py | ~350 | 0 | -350 |
| context_builder.py | ~100 | 0 | -100 |
| experiment_loader.py | 0 | ~50 | +50 |
| display.py VerboseConfig | ~50 | 0 | -50 |
| Tests | existing | +100 | +100 |
| **Net Production Code** | | | **-450** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_events_bootstrap_terminology.py | 10 |
| test_verbose_config_unified.py | 15 |
| test_experiment_loader.py | 18 |
| test_experiments_py_removed.py | 5 |
| test_context_builder_removed.py | 4 |
| **Total** | **52** |

---

*Phase 9 Plan v2.0 - Enhanced with Rigorous TDD - 2025-12-11*
