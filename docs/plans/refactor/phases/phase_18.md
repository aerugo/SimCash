# Phase 18: Delete Castro Python Code (YAML-Only Experiments)

**Status:** IN PROGRESS
**Created:** 2025-12-11
**Estimated Duration:** 1-2 hours
**Risk:** Medium (deleting code, but backed up in git)
**Breaking Changes:** Yes - Castro CLI will no longer work, use core CLI instead

---

## Overview

Phase 18 completes the YAML-only experiments vision. After this phase:

- Castro will contain ONLY YAML files, papers, and documentation
- ALL Python code will be in core `payment_simulator.experiments` module
- New experiments can be created by writing YAML only (no code needed)

## Pre-Requisites

Phases 15-17 must be complete:
- [x] Phase 15: Extended ExperimentConfig with `system_prompt` and `policy_constraints` support
- [x] Phase 16: Created GenericExperimentRunner in core
- [x] Phase 17: Created generic CLI in core

## Current State

### Files to Delete (~4200 lines)

```
experiments/castro/
├── castro/                    # DELETE ALL (~14 Python files)
│   ├── __init__.py
│   ├── audit_display.py       (~272 lines)
│   ├── bootstrap_context.py   (~25 lines - re-export)
│   ├── constraints.py         (~86 lines) → INLINE to YAML
│   ├── context_builder.py     (~377 lines)
│   ├── display.py             (~359 lines)
│   ├── experiment_config.py   (~279 lines)
│   ├── experiment_loader.py   (~123 lines)
│   ├── pydantic_llm_client.py (~469 lines) → INLINE system_prompt to YAML
│   ├── run_id.py              (~20 lines - re-export)
│   ├── runner.py              (~958 lines)
│   ├── simulation.py          (~241 lines)
│   ├── verbose_capture.py     (small)
│   └── verbose_logging.py     (~713 lines)
├── cli.py                     # DELETE (~600 lines)
└── tests/                     # DELETE (~24 test files)
```

### Files to Keep

```
experiments/castro/
├── experiments/               # KEEP - YAML experiment configs
│   ├── exp1.yaml             # UPDATE with inline system_prompt
│   ├── exp2.yaml             # UPDATE with inline system_prompt
│   └── exp3.yaml             # UPDATE with inline system_prompt
├── configs/                   # KEEP - YAML scenario configs
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/                    # KEEP - Research papers
│   └── castro_et_al_2025.pdf
├── README.md                  # UPDATE with new usage
└── pyproject.toml             # UPDATE (minimal - metadata only)
```

---

## Implementation Steps

### Task 18.1: Update Castro Experiment YAMLs

Add inline `system_prompt` and `policy_constraints` to each experiment YAML.

#### SYSTEM_PROMPT (from pydantic_llm_client.py lines 139-192)

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  timeout_seconds: 120
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

    Policy structure:
    {
      "version": "2.0",
      "policy_id": "<unique_policy_name>",
      "parameters": {
        "initial_liquidity_fraction": <float 0.0-1.0>,
        "urgency_threshold": <float 0-20>,
        "liquidity_buffer_factor": <float 0.5-3.0>
      },
      "payment_tree": { decision tree for payment actions },
      "strategic_collateral_tree": { decision tree for collateral at t=0 }
    }

    CRITICAL: Every node MUST have a unique "node_id" string field!

    Decision tree node types:
    1. Action node: {"type": "action", "node_id": "<unique_id>", "action": "Release" or "Hold"}
    2. Condition node: {
         "type": "condition",
         "node_id": "<unique_id>",
         "condition": {"op": "<operator>", "left": {...}, "right": {...}},
         "on_true": <node>,
         "on_false": <node>
       }
    3. Collateral action node: {
         "type": "action",
         "node_id": "<unique_id>",
         "action": "PostCollateral" or "HoldCollateral",
         "parameters": {
           "amount": {"compute": {...} or "value": <number>},
           "reason": {"value": "InitialAllocation" or "LiquidityTopup"}
         }
       }

    Condition operands:
    - {"field": "<field_name>"} - context fields: ticks_to_deadline, system_tick_in_day,
      remaining_collateral_capacity
    - {"param": "<param_name>"} - policy parameter reference
    - {"value": <literal>} - literal number value

    Operators: "<", "<=", ">", ">=", "==", "!="

    Compute expressions: {"compute": {"op": "*", "left": {...}, "right": {...}}}

    Rules:
    - EVERY node must have a unique node_id field (REQUIRED by parser)
    - payment_tree actions: "Release" or "Hold" only
    - strategic_collateral_tree: Post collateral at tick 0, hold otherwise
    - Use remaining_collateral_capacity field for collateral amount calculations
    - All numeric values must respect parameter bounds
    - Output ONLY valid JSON, no markdown or explanation
```

#### POLICY_CONSTRAINTS (from constraints.py)

```yaml
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
    - name: liquidity_buffer
      param_type: float
      min_value: 0.5
      max_value: 3.0
      description: "Multiplier for required liquidity"

  allowed_fields:
    # Time context
    - system_tick_in_day
    - ticks_remaining_in_day
    - current_tick
    # Agent liquidity state
    - balance
    - effective_liquidity
    # Transaction context
    - ticks_to_deadline
    - remaining_amount
    - amount
    - priority
    # Queue state
    - queue1_total_value
    - outgoing_queue_size
    # Collateral
    - max_collateral_capacity
    - posted_collateral

  allowed_actions:
    payment_tree:
      - Release
      - Hold
    bank_tree:
      - NoAction
    collateral_tree:
      - PostCollateral
      - HoldCollateral
```

### Task 18.2: Verify Experiments Work via Core CLI

Before deleting, verify the updated YAMLs work with the core CLI:

```bash
# Validate all experiment configs
payment-sim experiments validate experiments/castro/experiments/exp1.yaml
payment-sim experiments validate experiments/castro/experiments/exp2.yaml
payment-sim experiments validate experiments/castro/experiments/exp3.yaml

# List experiments
payment-sim experiments list experiments/castro/experiments/

# Show info
payment-sim experiments info experiments/castro/experiments/exp1.yaml

# Dry-run (validates without executing)
payment-sim experiments run experiments/castro/experiments/exp1.yaml --dry-run
```

### Task 18.3: Delete Castro Python Code

Delete the entire `experiments/castro/castro/` directory:

```bash
rm -rf experiments/castro/castro/
```

### Task 18.4: Delete Castro CLI

Delete `experiments/castro/cli.py`:

```bash
rm experiments/castro/cli.py
```

### Task 18.5: Delete Castro Tests

Delete the entire `experiments/castro/tests/` directory:

```bash
rm -rf experiments/castro/tests/
```

### Task 18.6: Update pyproject.toml

Change from a Python package to minimal metadata:

```toml
[project]
name = "castro-experiments"
version = "1.0.0"
description = "Castro et al. (2025) experiment configurations for SimCash"
readme = "README.md"
requires-python = ">=3.11"

# No dependencies - this is YAML-only!
dependencies = []

[project.optional-dependencies]
# None needed

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build]
exclude = ["tests/"]
```

### Task 18.7: Update README.md

Update with new usage instructions:

```markdown
# Castro Experiments

This directory contains experiment configurations for replicating the work from Castro et al. (2025).

## Requirements

All experiments run via the core SimCash CLI. Make sure you have the `api` package installed:

```bash
cd /path/to/SimCash/api
uv sync --extra dev
```

## Running Experiments

Use the core `payment-sim experiments` CLI:

```bash
# List available experiments
payment-sim experiments list experiments/castro/experiments/

# Show experiment details
payment-sim experiments info experiments/castro/experiments/exp1.yaml

# Validate configuration
payment-sim experiments validate experiments/castro/experiments/exp1.yaml

# Run an experiment
payment-sim experiments run experiments/castro/experiments/exp1.yaml

# Run with verbose output
payment-sim experiments run experiments/castro/experiments/exp1.yaml --verbose

# Run with custom seed
payment-sim experiments run experiments/castro/experiments/exp1.yaml --seed 12345
```

## Experiments

| Experiment | Description | Mode |
|------------|-------------|------|
| exp1 | 2-Period Deterministic Nash Equilibrium | deterministic |
| exp2 | 12-Period Stochastic LVTS-Style | bootstrap |
| exp3 | Joint Liquidity & Timing Optimization | bootstrap |

## Configuration Files

- `experiments/` - Experiment YAML configurations
- `configs/` - Scenario YAML configurations
- `papers/` - Reference papers

## Reference

Castro et al. (2025) "AI Cash Management: Optimizing Payment Timing with Large Language Models"
```

---

## TDD Approach

Since we're deleting code, our TDD approach is:

1. **Before deletion**: Verify core CLI works with updated YAMLs
2. **After deletion**: Verify core CLI still works
3. **Write test**: `api/tests/experiments/cli/test_castro_yaml_experiments.py`

```python
"""Tests verifying Castro experiments work via core CLI."""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from payment_simulator.cli.main import app
from payment_simulator.experiments.config import ExperimentConfig


CASTRO_EXPERIMENTS_DIR = Path("experiments/castro/experiments")


class TestCastroYamlExperimentsValidate:
    """Test Castro YAML experiments validate successfully."""

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp1_yaml_validates(self) -> None:
        """exp1.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp1.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp1"
        assert config.llm.system_prompt is not None
        assert len(config.llm.system_prompt) > 500  # Has full system prompt

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp2_yaml_validates(self) -> None:
        """exp2.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp2.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp2"
        assert config.evaluation.mode == "bootstrap"
        assert config.llm.system_prompt is not None

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_exp3_yaml_validates(self) -> None:
        """exp3.yaml should validate successfully."""
        config_path = CASTRO_EXPERIMENTS_DIR / "exp3.yaml"
        config = ExperimentConfig.from_yaml(config_path)
        assert config.name == "exp3"
        assert config.llm.system_prompt is not None


class TestCastroYamlNoPythonCode:
    """Verify Castro has no Python code after Phase 18."""

    @pytest.mark.skipif(
        not Path("experiments/castro").exists(),
        reason="Castro directory not found",
    )
    def test_no_castro_python_module(self) -> None:
        """experiments/castro/castro/ should not exist."""
        castro_module = Path("experiments/castro/castro")
        assert not castro_module.exists(), "Castro Python module should be deleted"

    @pytest.mark.skipif(
        not Path("experiments/castro").exists(),
        reason="Castro directory not found",
    )
    def test_no_castro_cli(self) -> None:
        """experiments/castro/cli.py should not exist."""
        cli_file = Path("experiments/castro/cli.py")
        assert not cli_file.exists(), "Castro CLI should be deleted"

    @pytest.mark.skipif(
        not Path("experiments/castro").exists(),
        reason="Castro directory not found",
    )
    def test_no_castro_tests(self) -> None:
        """experiments/castro/tests/ should not exist."""
        tests_dir = Path("experiments/castro/tests")
        assert not tests_dir.exists(), "Castro tests should be deleted"


class TestCoreCLIWithCastroYaml:
    """Test core CLI commands work with Castro YAML files."""

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_validate_command_works(self) -> None:
        """Validate command should work with Castro YAMLs."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiments", "validate", str(CASTRO_EXPERIMENTS_DIR / "exp1.yaml")],
        )
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_info_command_works(self) -> None:
        """Info command should work with Castro YAMLs."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiments", "info", str(CASTRO_EXPERIMENTS_DIR / "exp1.yaml")],
        )
        assert result.exit_code == 0
        assert "exp1" in result.stdout

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_list_command_works(self) -> None:
        """List command should show Castro experiments."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiments", "list", str(CASTRO_EXPERIMENTS_DIR)],
        )
        assert result.exit_code == 0
        assert "exp1" in result.stdout

    @pytest.mark.skipif(
        not CASTRO_EXPERIMENTS_DIR.exists(),
        reason="Castro experiments directory not found",
    )
    def test_dry_run_command_works(self) -> None:
        """Dry-run should validate without executing."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["experiments", "run", str(CASTRO_EXPERIMENTS_DIR / "exp1.yaml"), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower() or "valid" in result.stdout.lower()
```

---

## Verification

After Phase 18 completion:

1. **Core CLI works**:
   ```bash
   payment-sim experiments list experiments/castro/experiments/
   payment-sim experiments validate experiments/castro/experiments/exp1.yaml
   payment-sim experiments info experiments/castro/experiments/exp1.yaml
   payment-sim experiments run experiments/castro/experiments/exp1.yaml --dry-run
   ```

2. **No Castro Python code**:
   ```bash
   ls experiments/castro/castro/  # Should fail - directory doesn't exist
   ls experiments/castro/cli.py   # Should fail - file doesn't exist
   ls experiments/castro/tests/   # Should fail - directory doesn't exist
   ```

3. **Tests pass**:
   ```bash
   cd api
   .venv/bin/python -m pytest tests/experiments/cli/test_castro_yaml_experiments.py -v
   ```

4. **Final structure**:
   ```
   experiments/castro/
   ├── experiments/
   │   ├── exp1.yaml
   │   ├── exp2.yaml
   │   └── exp3.yaml
   ├── configs/
   │   ├── exp1_2period.yaml
   │   ├── exp2_12period.yaml
   │   └── exp3_joint.yaml
   ├── papers/
   │   └── castro_et_al_2025.pdf
   ├── README.md
   └── pyproject.toml
   ```

---

## Rollback Plan

If issues are found:

1. Git checkout to restore deleted files
2. All code is preserved in git history
3. Can be restored in < 5 minutes

---

## Expected Outcome

- Castro = YAML configs + papers + docs (no Python code)
- ALL Python code in core `payment_simulator.experiments`
- New experiments can be created by writing YAML only
- ~4200 lines of Castro Python code deleted
- Core is the single source of truth for experiment infrastructure
