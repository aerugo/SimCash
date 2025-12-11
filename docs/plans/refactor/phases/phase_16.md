# Phase 16: Create Generic Experiment Runner in Core

**Status:** COMPLETED (2025-12-11)
**Created:** 2025-12-11
**Purpose:** Move ALL runner logic from Castro to core, enabling YAML-only experiments

---

## Objective

Create a generic experiment runner in core that:
1. Reads system_prompt from experiment config (Phase 15)
2. Reads policy_constraints from experiment config (Phase 15)
3. Executes the optimization loop without experiment-specific code
4. Can be used by ANY experiment directory with just YAML files

After this phase, Castro's ~960 line `runner.py` can be replaced with a thin wrapper.

---

## Current State

### Castro Runner (`experiments/castro/castro/runner.py`)
- ~960 lines of Python code
- Hardcoded imports: `CASTRO_CONSTRAINTS`, `PydanticAILLMClient`
- Tightly coupled to Castro-specific classes
- Contains generic optimization logic that should be reusable

### Core Runner Module (`api/payment_simulator/experiments/runner/`)
- Has protocols, result types, state providers (Phases 4, 11, 13, 14)
- Missing: actual experiment execution logic
- Missing: generic optimization loop

---

## Target State

```
api/payment_simulator/experiments/runner/
├── __init__.py           # Updated exports
├── protocol.py           # ExperimentRunnerProtocol (existing)
├── result.py             # ExperimentResult, ExperimentState (existing)
├── output.py             # OutputHandlerProtocol (existing)
├── state_provider.py     # StateProvider (existing)
├── verbose.py            # VerboseConfig, VerboseLogger (existing)
├── display.py            # display_experiment_output (existing)
├── audit.py              # display_audit_output (existing)
├── optimization.py       # NEW: Generic optimization loop
├── llm_client.py         # NEW: Generic LLM client wrapper
└── experiment_runner.py  # NEW: GenericExperimentRunner class
```

---

## TDD Test Plan

### Task 16.1: Generic LLM Client Wrapper

**Test File:** `api/tests/experiments/runner/test_llm_client_core.py`

```python
class TestGenericLLMClient:
    def test_creates_with_system_prompt_from_config() -> None:
        """LLM client uses system_prompt from LLMConfig."""

    def test_creates_without_system_prompt() -> None:
        """LLM client works when system_prompt is None."""

    def test_generate_policy_calls_underlying_client() -> None:
        """generate_policy() delegates to underlying client."""

    def test_captures_interactions_for_audit() -> None:
        """All LLM interactions are captured for audit replay."""

    def test_respects_max_retries_from_config() -> None:
        """Uses max_retries from LLMConfig."""
```

### Task 16.2: Generic Optimization Loop

**Test File:** `api/tests/experiments/runner/test_optimization_core.py`

```python
class TestOptimizationLoop:
    def test_runs_until_max_iterations() -> None:
        """Loop runs up to max_iterations."""

    def test_stops_on_convergence() -> None:
        """Loop stops when convergence detected."""

    def test_evaluates_policies_each_iteration() -> None:
        """Policies evaluated at start of each iteration."""

    def test_optimizes_each_agent() -> None:
        """Each optimized_agent gets LLM optimization."""

    def test_accepts_improved_policies() -> None:
        """Policies accepted when mean_delta > 0."""

    def test_rejects_worse_policies() -> None:
        """Policies rejected when mean_delta <= 0."""

    def test_uses_paired_comparison() -> None:
        """Uses compute_paired_deltas for comparison."""

    def test_records_events_to_state_provider() -> None:
        """LLM interactions recorded via state provider."""

    def test_costs_are_integer_cents() -> None:
        """All costs use integer cents (INV-1)."""
```

### Task 16.3: GenericExperimentRunner Class

**Test File:** `api/tests/experiments/runner/test_experiment_runner_core.py`

```python
class TestGenericExperimentRunner:
    def test_implements_runner_protocol() -> None:
        """GenericExperimentRunner implements ExperimentRunnerProtocol."""

    def test_creates_from_experiment_config() -> None:
        """Runner created from ExperimentConfig."""

    def test_uses_constraints_from_config() -> None:
        """Uses config.get_constraints() for validation."""

    def test_uses_system_prompt_from_config() -> None:
        """Uses config.llm.system_prompt for LLM."""

    def test_returns_experiment_result() -> None:
        """run() returns ExperimentResult."""

    def test_get_current_state_returns_state() -> None:
        """get_current_state() returns ExperimentState."""

    def test_loads_scenario_from_config_path() -> None:
        """Loads scenario YAML from config.scenario_path."""

    def test_generates_run_id() -> None:
        """Generates unique run_id for each run."""
```

---

## Implementation Plan

### 16.1: Create llm_client.py

Generic LLM client that:
- Takes LLMConfig (with system_prompt)
- Wraps PydanticAILLMClient from core llm module
- Captures interactions for audit
- Uses policy constraints for parsing/validation

```python
# api/payment_simulator/experiments/runner/llm_client.py

class ExperimentLLMClient:
    """Generic LLM client for experiment optimization.

    Reads system_prompt from config and wraps core LLM client.
    """

    def __init__(
        self,
        config: LLMConfig,
        constraints: ScenarioConstraints,
    ) -> None:
        self._config = config
        self._constraints = constraints
        self._interactions: list[LLMInteraction] = []

    async def generate_policy(
        self,
        agent_id: str,
        context: dict[str, Any],
    ) -> PolicyGenerationResult:
        """Generate improved policy for agent."""
        ...
```

### 16.2: Create optimization.py

Generic optimization loop that:
- Takes ExperimentConfig
- Uses BootstrapPolicyEvaluator for evaluation
- Uses ExperimentLLMClient for policy generation
- Uses ConvergenceDetector for stopping
- Records events via StateProvider

```python
# api/payment_simulator/experiments/runner/optimization.py

class OptimizationLoop:
    """Generic optimization loop for experiments.

    Executes the standard optimization algorithm:
    1. Evaluate current policies
    2. Check convergence
    3. For each agent, generate new policy
    4. Accept/reject based on paired comparison
    5. Repeat
    """

    def __init__(
        self,
        config: ExperimentConfig,
        state_provider: LiveStateProvider,
        llm_client: ExperimentLLMClient,
        verbose_logger: VerboseLogger | None = None,
    ) -> None:
        ...

    async def run(self) -> OptimizationResult:
        """Run optimization to convergence."""
        ...
```

### 16.3: Create experiment_runner.py

```python
# api/payment_simulator/experiments/runner/experiment_runner.py

class GenericExperimentRunner:
    """Generic experiment runner that works with any YAML config.

    Example:
        >>> config = ExperimentConfig.from_yaml(Path("exp1.yaml"))
        >>> runner = GenericExperimentRunner(config)
        >>> result = await runner.run()
    """

    def __init__(
        self,
        config: ExperimentConfig,
        verbose_config: VerboseConfig | None = None,
        run_id: str | None = None,
    ) -> None:
        ...

    async def run(self) -> ExperimentResult:
        """Run experiment to completion."""
        ...

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state."""
        ...
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `runner/llm_client.py` | CREATE | Generic LLM client wrapper |
| `runner/optimization.py` | CREATE | Generic optimization loop |
| `runner/experiment_runner.py` | CREATE | GenericExperimentRunner class |
| `runner/__init__.py` | MODIFY | Add new exports |
| `tests/.../test_llm_client_core.py` | CREATE | TDD tests |
| `tests/.../test_optimization_core.py` | CREATE | TDD tests |
| `tests/.../test_experiment_runner_core.py` | CREATE | TDD tests |

---

## Key Design Decisions

### 1. Config-Driven Everything
- System prompt from `config.llm.system_prompt`
- Constraints from `config.get_constraints()`
- Evaluation mode from `config.evaluation`
- Convergence from `config.convergence`

### 2. Protocol-Based Abstractions
- Use existing `ExperimentRunnerProtocol`
- Use existing `ExperimentStateProviderProtocol`
- LLM client follows protocol pattern

### 3. No Experiment-Specific Code
- No imports from Castro
- No hardcoded constraints
- No hardcoded prompts

### 4. INV-1 Compliance
- All costs are integer cents
- No floats in cost calculations

---

## Dependencies

- Phase 15: system_prompt and policy_constraints in config ✅ DONE
- Phase 11: ExperimentStateProviderProtocol ✅ DONE
- Phase 14: VerboseConfig, VerboseLogger ✅ DONE
- Core ai_cash_mgmt: BootstrapPolicyEvaluator, ConvergenceDetector ✅ EXISTS

---

## Verification

```bash
# Run new tests
cd api && .venv/bin/python -m pytest tests/experiments/runner/test_llm_client_core.py -v
cd api && .venv/bin/python -m pytest tests/experiments/runner/test_optimization_core.py -v
cd api && .venv/bin/python -m pytest tests/experiments/runner/test_experiment_runner_core.py -v

# Run all runner tests
cd api && .venv/bin/python -m pytest tests/experiments/runner/ -v

# Verify no regression
cd api && .venv/bin/python -m pytest tests/ --tb=short
```

---

## Success Criteria

1. ✅ All new tests pass
2. ✅ GenericExperimentRunner implements ExperimentRunnerProtocol
3. ✅ Runner uses config.llm.system_prompt (no hardcoded prompts)
4. ✅ Runner uses config.get_constraints() (no hardcoded constraints)
5. ✅ All costs are integer cents (INV-1)
6. ✅ mypy passes on new files

---

*Created: 2025-12-11*
