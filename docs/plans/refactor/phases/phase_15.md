# Phase 15: Extend Experiment Config Schema for YAML-Only

**Status:** IN PROGRESS
**Created:** 2025-12-11
**Purpose:** Extend experiment YAML schema to support system_prompt and policy_constraints inline

---

## Objective

Enable experiments to define ALL configuration in YAML with NO Python code required.
After this phase:
- `system_prompt` can be defined inline in experiment YAML
- `policy_constraints` can be defined inline in experiment YAML (no module reference needed)
- Core can create `ScenarioConstraints` directly from YAML data

---

## Current State

### ExperimentConfig (api/payment_simulator/experiments/config/experiment_config.py)
- Has `constraints_module: str` referencing Python code (e.g., "castro.constraints.CASTRO_CONSTRAINTS")
- Has `load_constraints()` method that dynamically imports Python module

### LLMConfig (api/payment_simulator/llm/config.py)
- No `system_prompt` field
- System prompt is hardcoded in Castro's `pydantic_llm_client.py`

### ScenarioConstraints (api/payment_simulator/ai_cash_mgmt/constraints/)
- Already a Pydantic model - can serialize to/from dict
- Can be created directly from YAML data without Python code

---

## Target State

### New YAML Structure
```yaml
name: exp1
description: "2-Period Deterministic"

scenario: configs/exp1_2period.yaml

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0

  # NEW: System prompt inline or from file
  system_prompt: |
    You are an expert in payment system optimization...

  # OR reference external file
  system_prompt_file: prompts/policy_optimization.md

# NEW: Inline policy constraints (replaces constraints_module)
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
      description: "Fraction of collateral to post at t=0"
    - name: urgency_threshold
      param_type: int
      min_value: 0
      max_value: 20
      description: "Ticks before deadline to release payment"

  allowed_fields:
    - balance
    - effective_liquidity
    - ticks_to_deadline
    - remaining_amount

  allowed_actions:
    payment_tree: ["Release", "Hold"]
    collateral_tree: ["PostCollateral", "HoldCollateral"]

# DEPRECATED: constraints_module still supported for backward compat
# constraints: castro.constraints.CASTRO_CONSTRAINTS

evaluation:
  mode: deterministic
  ticks: 2

optimized_agents:
  - BANK_A
  - BANK_B
```

---

## TDD Test Plan

### Task 15.1: Add system_prompt to LLMConfig

**Test File:** `api/tests/experiments/config/test_system_prompt.py`

```python
class TestSystemPromptInConfig:
    def test_llm_config_accepts_system_prompt() -> None:
        """LLMConfig can have system_prompt field."""

    def test_experiment_config_parses_inline_system_prompt() -> None:
        """ExperimentConfig.from_yaml() parses inline system_prompt."""

    def test_experiment_config_loads_system_prompt_from_file() -> None:
        """ExperimentConfig.from_yaml() loads system_prompt_file."""

    def test_system_prompt_file_not_found_raises_error() -> None:
        """Missing system_prompt_file raises FileNotFoundError."""

    def test_system_prompt_and_file_both_present_uses_inline() -> None:
        """Inline system_prompt takes precedence over file."""
```

### Task 15.2: Add policy_constraints to ExperimentConfig

**Test File:** `api/tests/experiments/config/test_inline_constraints.py`

```python
class TestInlineConstraints:
    def test_experiment_config_parses_inline_constraints() -> None:
        """ExperimentConfig.from_yaml() parses policy_constraints."""

    def test_inline_constraints_creates_scenario_constraints() -> None:
        """Inline constraints create valid ScenarioConstraints object."""

    def test_inline_constraints_with_parameters() -> None:
        """Inline constraints parse allowed_parameters correctly."""

    def test_inline_constraints_with_fields() -> None:
        """Inline constraints parse allowed_fields correctly."""

    def test_inline_constraints_with_actions() -> None:
        """Inline constraints parse allowed_actions correctly."""

    def test_constraints_module_still_works_for_backward_compat() -> None:
        """constraints_module (legacy) still loads Python module."""

    def test_inline_constraints_takes_precedence() -> None:
        """Inline policy_constraints overrides constraints_module."""
```

### Task 15.3: Constraint Validation

**Test File:** `api/tests/experiments/config/test_yaml_constraint_validator.py`

```python
class TestYamlConstraintValidator:
    def test_parameter_spec_from_yaml() -> None:
        """ParameterSpec created from YAML dict."""

    def test_scenario_constraints_from_yaml() -> None:
        """ScenarioConstraints created from YAML dict."""

    def test_invalid_param_type_raises_error() -> None:
        """Invalid param_type in YAML raises ValueError."""

    def test_missing_param_name_raises_error() -> None:
        """Missing parameter name raises ValueError."""
```

---

## Implementation Plan

### 15.1: Add system_prompt to LLMConfig

1. Update `api/payment_simulator/llm/config.py`:
   - Add `system_prompt: str | None = None` field
   - Add `system_prompt_file: str | None = None` field
   - Update `from_dict()` if present

2. Update `api/payment_simulator/experiments/config/experiment_config.py`:
   - Parse `system_prompt` and `system_prompt_file` from llm section
   - Load file content if `system_prompt_file` is specified
   - Pass to LLMConfig

### 15.2: Add policy_constraints to ExperimentConfig

1. Update `api/payment_simulator/experiments/config/experiment_config.py`:
   - Add `policy_constraints: ScenarioConstraints | None = None` field
   - Parse `policy_constraints` dict from YAML in `_from_dict()`
   - Create `ScenarioConstraints.model_validate()` from dict
   - Keep `constraints_module` for backward compatibility

2. Update `get_constraints()` method:
   - Return inline `policy_constraints` if present
   - Fall back to `load_constraints()` from module if not

### 15.3: Integration

1. Ensure `ScenarioConstraints` can be created from YAML dict
2. Verify existing Castro experiments still work (backward compat)
3. Create example experiment YAML with inline constraints

---

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/llm/config.py` | Add system_prompt, system_prompt_file fields |
| `api/payment_simulator/experiments/config/experiment_config.py` | Add policy_constraints parsing, get_constraints() |
| `api/tests/experiments/config/test_system_prompt.py` | NEW - TDD tests |
| `api/tests/experiments/config/test_inline_constraints.py` | NEW - TDD tests |

---

## Verification

```bash
# Run new tests
cd api && .venv/bin/python -m pytest tests/experiments/config/test_system_prompt.py -v
cd api && .venv/bin/python -m pytest tests/experiments/config/test_inline_constraints.py -v

# Run all experiment config tests
cd api && .venv/bin/python -m pytest tests/experiments/config/ -v

# Verify no regression
cd api && .venv/bin/python -m pytest tests/ -v --tb=short
```

---

## Success Criteria

1. ✅ All new tests pass
2. ✅ Existing Castro experiments still work (backward compat)
3. ✅ Can create experiment with inline system_prompt
4. ✅ Can create experiment with inline policy_constraints
5. ✅ mypy passes on modified files

---

*Created: 2025-12-11*
