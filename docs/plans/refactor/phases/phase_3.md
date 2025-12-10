# Phase 3: Experiment Configuration Framework

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Medium
**Breaking Changes:** None (new code)

---

## Objectives

1. Create `ExperimentConfig` YAML loader
2. Create `EvaluationConfig` for bootstrap/deterministic settings
3. Create `OutputConfig` for output settings
4. Create `ConvergenceConfig` for convergence criteria
5. Add validation for experiment configs

---

## TDD Test Specifications

### Test File: `api/tests/experiments/config/test_experiment_config.py`

```python
"""Tests for ExperimentConfig YAML loading."""

import pytest
from pathlib import Path

from payment_simulator.experiments.config.experiment_config import (
    ExperimentConfig,
    EvaluationConfig,
    OutputConfig,
    ConvergenceConfig,
)


class TestEvaluationConfig:
    """Tests for EvaluationConfig dataclass."""

    def test_bootstrap_mode_requires_num_samples(self) -> None:
        """Bootstrap mode requires num_samples."""
        config = EvaluationConfig(mode="bootstrap", num_samples=10, ticks=12)
        assert config.num_samples == 10

    def test_defaults_mode_to_bootstrap(self) -> None:
        """Default mode is bootstrap."""
        config = EvaluationConfig(ticks=12)
        assert config.mode == "bootstrap"

    def test_is_frozen(self) -> None:
        """EvaluationConfig is immutable."""
        config = EvaluationConfig(ticks=12)
        with pytest.raises(AttributeError):
            config.mode = "deterministic"

    def test_raises_on_invalid_mode(self) -> None:
        """Raises ValueError on invalid mode."""
        with pytest.raises(ValueError, match="Invalid evaluation mode"):
            EvaluationConfig(mode="invalid", ticks=12)


class TestOutputConfig:
    """Tests for OutputConfig dataclass."""

    def test_default_directory_is_results(self) -> None:
        """Default directory is 'results'."""
        config = OutputConfig()
        assert config.directory == Path("results")

    def test_default_database_is_experiments_db(self) -> None:
        """Default database is 'experiments.db'."""
        config = OutputConfig()
        assert config.database == "experiments.db"

    def test_is_frozen(self) -> None:
        """OutputConfig is immutable."""
        config = OutputConfig()
        with pytest.raises(AttributeError):
            config.directory = Path("other")


class TestConvergenceConfig:
    """Tests for ConvergenceConfig dataclass."""

    def test_default_max_iterations(self) -> None:
        """Default max_iterations is 50."""
        config = ConvergenceConfig()
        assert config.max_iterations == 50

    def test_default_stability_threshold(self) -> None:
        """Default stability_threshold is 0.05."""
        config = ConvergenceConfig()
        assert config.stability_threshold == 0.05

    def test_is_frozen(self) -> None:
        """ConvergenceConfig is immutable."""
        config = ConvergenceConfig()
        with pytest.raises(AttributeError):
            config.max_iterations = 100


class TestExperimentConfig:
    """Tests for ExperimentConfig YAML loading."""

    @pytest.fixture
    def valid_yaml_path(self, tmp_path: Path) -> Path:
        """Create valid experiment YAML."""
        content = '''
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
'''
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

    def test_raises_on_missing_required_field(self, tmp_path: Path) -> None:
        """Raises ValueError on missing required field."""
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("name: test\n")  # Missing other fields
        with pytest.raises(ValueError, match="Missing required fields"):
            ExperimentConfig.from_yaml(incomplete)

    def test_can_import_from_module(self) -> None:
        """ExperimentConfig can be imported from experiments.config."""
        from payment_simulator.experiments.config import ExperimentConfig
        assert ExperimentConfig is not None
```

---

## Implementation Plan

### Step 3.1: Create EvaluationConfig

```python
@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation mode configuration."""
    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    def __post_init__(self) -> None:
        if self.mode not in ("bootstrap", "deterministic"):
            raise ValueError(f"Invalid evaluation mode: {self.mode}")
```

### Step 3.2: Create OutputConfig

```python
@dataclass(frozen=True)
class OutputConfig:
    """Output configuration."""
    directory: Path = field(default_factory=lambda: Path("results"))
    database: str = "experiments.db"
    verbose: bool = True
```

### Step 3.3: Create ConvergenceConfig

```python
@dataclass(frozen=True)
class ConvergenceConfig:
    """Convergence criteria configuration."""
    max_iterations: int = 50
    stability_threshold: float = 0.05
    stability_window: int = 5
    improvement_threshold: float = 0.01
```

### Step 3.4: Create ExperimentConfig

```python
@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment configuration loaded from YAML."""
    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceConfig
    llm: LLMConfig
    optimized_agents: tuple[str, ...]
    constraints_module: str
    output: OutputConfig
    master_seed: int = 42

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        """Load from YAML file."""
        ...
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/experiments/config/experiment_config.py` | Main config classes |
| `api/tests/experiments/config/test_experiment_config.py` | Config tests |

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/experiments/config/__init__.py` | Add exports |

---

## Verification Checklist

### TDD Tests
- [ ] `test_bootstrap_mode_requires_num_samples` passes
- [ ] `test_defaults_mode_to_bootstrap` passes
- [ ] `test_is_frozen` passes (EvaluationConfig)
- [ ] `test_raises_on_invalid_mode` passes
- [ ] `test_default_directory_is_results` passes
- [ ] `test_default_database_is_experiments_db` passes
- [ ] `test_default_max_iterations` passes
- [ ] `test_loads_from_yaml` passes
- [ ] `test_loads_scenario_path` passes
- [ ] `test_loads_evaluation_config` passes
- [ ] `test_loads_convergence_config` passes
- [ ] `test_loads_llm_config` passes
- [ ] `test_loads_optimized_agents` passes
- [ ] `test_raises_on_missing_file` passes
- [ ] `test_raises_on_missing_required_field` passes
- [ ] `test_can_import_from_module` passes

### Type Checking
```bash
cd api && .venv/bin/python -m mypy payment_simulator/experiments/config/
```

---

## Notes

Phase 3 creates the foundation for YAML-driven experiment configuration.
This enables non-programmers to define experiments and enables version
control of experiment definitions.

Key design decisions:
- All config dataclasses are frozen (immutable)
- ExperimentConfig.from_yaml() is the primary loading interface
- Nested configs (evaluation, convergence, llm, output) are also frozen
- LLMConfig is reused from the llm module (Phase 2)

---

*Phase 3 Plan v1.0 - 2025-12-10*
