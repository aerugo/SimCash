# Phase 9: Castro Module Slimming

**Status:** Planned
**Created:** 2025-12-11
**Dependencies:** Phase 8 (LLMConfig Migration)

## Purpose

Reduce Castro module complexity by removing redundant code and leveraging core SimCash modules. After this phase, Castro becomes a thin experiment-specific layer composed primarily of:

1. Constraints (`CASTRO_CONSTRAINTS`)
2. YAML experiment configurations
3. CLI entry point

## Analysis Summary

### Files Reviewed (Complete Castro Module)

| File | Lines | Assessment |
|------|-------|------------|
| `__init__.py` | ~50 | Keep - public API |
| `audit_display.py` | ~150 | Keep - Castro-specific audit UI |
| `bootstrap_context.py` | ~200 | Keep - enriched context builder (NEW pattern) |
| `constraints.py` | ~100 | Keep - Castro-specific constraints |
| `context_builder.py` | ~100 | **DELETE** - obsolete, replaced by bootstrap_context.py |
| `display.py` | ~200 | Modify - remove duplicate VerboseConfig |
| `events.py` | ~150 | Modify - fix monte_carlo terminology |
| `experiments.py` | ~350 | **DELETE** - redundant with YAML configs |
| `pydantic_llm_client.py` | ~200 | Keep - policy-specific prompts |
| `run_id.py` | ~30 | Keep - simple, Castro-specific |
| `runner.py` | ~936 | Modify - simplify, use YAML loading |
| `simulation.py` | ~150 | Keep - simulation wrapper |
| `state_provider.py` | ~250 | Keep - replay infrastructure |
| `verbose_capture.py` | ~100 | Keep - event capture |
| `verbose_logging.py` | ~200 | Keep - single VerboseConfig source |
| `persistence/models.py` | ~100 | Keep - event models |
| `persistence/repository.py` | ~200 | Keep - event storage |

### Issues Identified

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| 9.1 | `EVENT_MONTE_CARLO_EVALUATION` should be `EVENT_BOOTSTRAP_EVALUATION` | High | `events.py` |
| 9.2 | `create_monte_carlo_event()` should be `create_bootstrap_evaluation_event()` | High | `events.py` |
| 9.3 | Duplicate VerboseConfig in `display.py` and `verbose_logging.py` | High | Both files |
| 9.4 | `experiments.py` duplicates YAML experiment configs | High | `experiments.py` |
| 9.5 | `context_builder.py` obsolete (replaced by `bootstrap_context.py`) | Medium | `context_builder.py` |
| 9.6 | `runner.py` overly complex (936 lines) | Medium | `runner.py` |
| 9.7 | CLI imports from `experiments.py` EXPERIMENTS dict | Medium | `cli.py` |

---

## Task 9.1: Fix Terminology in events.py

### Changes

```python
# OLD
EVENT_MONTE_CARLO_EVALUATION = "monte_carlo_evaluation"

def create_monte_carlo_event(
    run_id: str,
    iteration: int,
    ...
) -> ExperimentEvent:
    """Create monte carlo evaluation event."""
    ...

# NEW
EVENT_BOOTSTRAP_EVALUATION = "bootstrap_evaluation"

def create_bootstrap_evaluation_event(
    run_id: str,
    iteration: int,
    ...
) -> ExperimentEvent:
    """Create bootstrap evaluation event."""
    ...
```

### Files to Modify

| File | Change |
|------|--------|
| `castro/events.py` | Rename constant and function |
| `castro/runner.py` | Update function call |
| `castro/display.py` | Update event type string |
| `castro/state_provider.py` | Update event type string |
| `tests/test_events.py` | Update test assertions |

### Verification

```bash
# Check for remaining monte_carlo references
grep -r "monte_carlo" experiments/castro/castro/ --include="*.py"
grep -r "MONTE_CARLO" experiments/castro/castro/ --include="*.py"
```

---

## Task 9.2: Consolidate VerboseConfig

### Problem

Two different VerboseConfig classes exist:

**verbose_logging.py VerboseConfig:**
```python
@dataclass
class VerboseConfig:
    policy: bool = False
    bootstrap: bool = False
    llm: bool = False
    rejections: bool = False
    debug: bool = False
```

**display.py VerboseConfig:**
```python
@dataclass
class VerboseConfig:
    show_iterations: bool = False
    show_bootstrap: bool = False
    show_llm_calls: bool = False
    show_policy_changes: bool = False
    show_rejections: bool = False
```

### Solution

1. Keep `verbose_logging.py` VerboseConfig as single source of truth
2. Unify field names to match CLI semantics
3. Update `display.py` to import from `verbose_logging.py`
4. Remove duplicate class from `display.py`

### Unified VerboseConfig

```python
# castro/verbose_logging.py
@dataclass
class VerboseConfig:
    """Configuration for verbose output.

    Single source of truth for all Castro verbose settings.
    """
    iterations: bool = False    # Show iteration start/end
    bootstrap: bool = False     # Show per-sample results
    llm: bool = False           # Show LLM call metadata
    policy: bool = False        # Show policy changes
    rejections: bool = False    # Show rejection details
    debug: bool = False         # Show debug info

    @classmethod
    def all_enabled(cls) -> VerboseConfig:
        """Create config with all verbose output enabled."""
        return cls(
            iterations=True,
            bootstrap=True,
            llm=True,
            policy=True,
            rejections=True,
            debug=False,  # Debug stays off even with -v
        )

    @classmethod
    def from_cli_flags(
        cls,
        verbose: bool = False,
        verbose_iterations: bool = False,
        verbose_bootstrap: bool = False,
        verbose_llm: bool = False,
        verbose_policy: bool = False,
        verbose_rejections: bool = False,
        debug: bool = False,
    ) -> VerboseConfig:
        """Create config from CLI flags."""
        if verbose:
            config = cls.all_enabled()
            config.debug = debug
            return config
        return cls(
            iterations=verbose_iterations,
            bootstrap=verbose_bootstrap,
            llm=verbose_llm,
            policy=verbose_policy,
            rejections=verbose_rejections,
            debug=debug,
        )
```

### Files to Modify

| File | Change |
|------|--------|
| `castro/verbose_logging.py` | Unify VerboseConfig |
| `castro/display.py` | Remove duplicate, import from verbose_logging |
| `castro/runner.py` | Update to use unified VerboseConfig |
| `castro/cli.py` | Update flag creation |
| `tests/test_verbose_logging.py` | Update tests |
| `tests/test_display.py` | Update tests |

---

## Task 9.3: Delete experiments.py

### Current Content (~350 lines)

```python
# experiments.py (TO BE DELETED)
@dataclass
class CastroExperiment:
    name: str
    description: str
    scenario_config: SimConfig
    # ... many fields ...

def create_exp1(...) -> CastroExperiment:
    """Create 2-period deterministic experiment."""
    # ~100 lines

def create_exp2(...) -> CastroExperiment:
    """Create 12-period stochastic experiment."""
    # ~100 lines

def create_exp3(...) -> CastroExperiment:
    """Create joint optimization experiment."""
    # ~100 lines

EXPERIMENTS = {
    "exp1": create_exp1,
    "exp2": create_exp2,
    "exp3": create_exp3,
}
```

### Replacement: experiment_loader.py (~50 lines)

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
    """Load experiment configuration from YAML.

    Args:
        name: Experiment name (e.g., "exp1")
        model_override: Override LLM model
        thinking_budget: Anthropic thinking budget
        reasoning_effort: OpenAI reasoning effort
        max_iter_override: Override max iterations
        seed_override: Override master seed

    Returns:
        Experiment configuration dict.

    Raises:
        FileNotFoundError: If experiment YAML not found.
    """
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

### Migration in cli.py

```python
# OLD
from castro.experiments import EXPERIMENTS

@app.command()
def run(experiment: str = typer.Argument(...)):
    if experiment not in EXPERIMENTS:
        raise typer.BadParameter(f"Unknown experiment: {experiment}")
    factory = EXPERIMENTS[experiment]
    exp = factory(model=model, ...)

# NEW
from castro.experiment_loader import load_experiment, list_experiments

@app.command()
def run(experiment: str = typer.Argument(...)):
    try:
        config = load_experiment(
            experiment,
            model_override=model,
            thinking_budget=thinking_budget,
            reasoning_effort=reasoning_effort,
        )
    except FileNotFoundError as e:
        raise typer.BadParameter(str(e)) from e
```

### Files to Modify

| File | Change |
|------|--------|
| `castro/experiments.py` | DELETE |
| `castro/experiment_loader.py` | CREATE |
| `castro/cli.py` | Update imports, use experiment_loader |
| `castro/runner.py` | Update to accept config dict |
| `castro/__init__.py` | Update exports |
| `tests/test_experiments.py` | Rewrite for experiment_loader |

---

## Task 9.4: Delete context_builder.py

### Verification Before Deletion

```bash
# Check if context_builder is still used
grep -r "from castro.context_builder" experiments/castro/
grep -r "from castro import.*BootstrapContextBuilder" experiments/castro/
grep -rn "context_builder" experiments/castro/castro/*.py
```

### Current Usage Analysis

The file contains `BootstrapContextBuilder` that works with `SimulationResult`. This has been superseded by `EnrichedBootstrapContextBuilder` in `bootstrap_context.py` which works with `EnrichedEvaluationResult` (the new pattern from Phase 0.5).

### Files to Modify

| File | Change |
|------|--------|
| `castro/context_builder.py` | DELETE |
| `castro/__init__.py` | Remove from exports |
| `castro/runner.py` | Ensure uses bootstrap_context.py |

---

## Task 9.5: Simplify runner.py

### Current Issues

1. **936 lines** - too long for a single module
2. Contains experiment loading logic (should use experiment_loader.py)
3. Contains verbose display logic (should delegate to display.py)
4. Mixed concerns: orchestration, evaluation, persistence, display

### Target Changes

1. Remove experiment loading (use experiment_loader.py)
2. Extract verbose output to display.py helpers
3. Simplify _evaluate_policies to use EnrichedBootstrapContextBuilder
4. Target: < 700 lines

### Files to Modify

| File | Change |
|------|--------|
| `castro/runner.py` | Simplify, delegate to other modules |
| `castro/display.py` | Add helper functions for runner |

---

## Task 9.6: Update __init__.py Exports

### Current Exports (experiments.py based)

```python
from castro.experiments import (
    CastroExperiment,
    create_exp1,
    create_exp2,
    create_exp3,
    EXPERIMENTS,
)
```

### New Exports

```python
from castro.experiment_loader import (
    load_experiment,
    list_experiments,
    get_llm_config,
)
from castro.constraints import CASTRO_CONSTRAINTS
from castro.runner import ExperimentRunner, ExperimentResult
from castro.events import (
    ExperimentEvent,
    EVENT_BOOTSTRAP_EVALUATION,  # Renamed
    create_bootstrap_evaluation_event,  # Renamed
)
```

---

## Implementation Order

1. **9.1**: Fix terminology in events.py (low risk, isolated)
2. **9.2**: Consolidate VerboseConfig (medium risk, touches several files)
3. **9.3**: Create experiment_loader.py and update cli.py
4. **9.4**: Delete experiments.py (after 9.3 verified working)
5. **9.5**: Delete context_builder.py
6. **9.6**: Simplify runner.py
7. **9.7**: Update __init__.py exports

---

## Test Plan

### TDD Tests to Write First

```python
# tests/test_experiment_loader.py
class TestExperimentLoader:
    def test_list_experiments_returns_all_yamls(self) -> None: ...
    def test_load_experiment_returns_config_dict(self) -> None: ...
    def test_load_experiment_applies_model_override(self) -> None: ...
    def test_load_experiment_applies_thinking_budget(self) -> None: ...
    def test_load_nonexistent_raises_file_not_found(self) -> None: ...
    def test_get_llm_config_extracts_config(self) -> None: ...


# tests/test_verbose_config_unified.py
class TestVerboseConfigUnified:
    def test_all_enabled_sets_all_true_except_debug(self) -> None: ...
    def test_from_cli_flags_verbose_enables_all(self) -> None: ...
    def test_from_cli_flags_individual_flags(self) -> None: ...
    def test_debug_flag_independent_of_verbose(self) -> None: ...
```

### Existing Tests to Update

| Test File | Updates Needed |
|-----------|----------------|
| `tests/test_events.py` | Update to use `EVENT_BOOTSTRAP_EVALUATION` |
| `tests/test_experiments.py` | Rewrite for experiment_loader |
| `tests/test_verbose_logging.py` | Update for unified VerboseConfig |
| `tests/test_display.py` | Update imports, remove duplicate tests |
| `tests/test_cli_commands.py` | Update for new experiment loading |

---

## Verification Commands

```bash
# After all changes, run full test suite
cd experiments/castro && uv run pytest tests/ -v

# Verify no remaining monte_carlo terminology
grep -r "monte_carlo" experiments/castro/castro/ --include="*.py"
grep -r "MONTE_CARLO" experiments/castro/castro/ --include="*.py"

# Verify experiments still work
uv run castro list
uv run castro run exp1 --max-iter 1 --verbose
uv run castro run exp2 --max-iter 1 --verbose-bootstrap

# Verify replay still works (with existing database)
uv run castro results
uv run castro replay <run_id> --verbose

# Type checking
cd experiments/castro && uv run mypy castro/

# Linting
uv run ruff check castro/
```

---

## Expected Outcomes

### Lines of Code

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| experiments.py | 350 | 0 | -350 |
| context_builder.py | 100 | 0 | -100 |
| experiment_loader.py | 0 | 50 | +50 |
| display.py (VerboseConfig) | 50 | 0 | -50 |
| Tests | 0 | 50 | +50 |
| **Net** | **500** | **100** | **-400** |

### File Count

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| Python modules | 17 | 16 | -1 |

### Import Graph Simplification

Before: `cli.py` → `experiments.py` → `simulation.py` + `constraints.py` + `verbose_logging.py`

After: `cli.py` → `experiment_loader.py` → `constraints.py`

---

## Rollback Plan

If issues arise:

1. Restore `experiments.py` from git
2. Revert `cli.py` to use EXPERIMENTS dict
3. Restore `context_builder.py` from git
4. Revert terminology changes in events.py

All changes are isolated to Castro module - no core SimCash changes needed.

---

## Related Documents

- [Conceptual Plan](../conceptual-plan.md) - Phase 9 overview
- [Development Plan](../development-plan.md) - Timeline and dependencies
- [Work Notes](../work_notes.md) - Progress tracking
