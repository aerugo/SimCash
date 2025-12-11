# Phase 5: CLI Commands

**Status:** COMPLETED
**Started:** 2025-12-10
**Completed:** 2025-12-10
**Duration:** ~0.5 day

---

## Overview

Phase 5 creates the `payment-sim experiment` CLI command group that provides
a unified interface for running, validating, and managing LLM policy
optimization experiments.

---

## Objectives

1. Create `payment-sim experiment` command group
2. Implement `validate` command for config validation
3. Implement `info` command for framework information
4. Implement `template` command for config generation
5. Implement `list` command for directory scanning
6. Implement `run` command (placeholder for Phase 6 integration)

---

## TDD Tests

### Test File: `api/tests/cli/test_experiment_commands.py`

Tests written first (TDD):

```python
class TestValidateCommand:
    """Tests for 'experiment validate' command."""

    def test_validate_success_shows_config_info(self) -> None:
        """Valid config shows name, description, scenario."""
        pass

    def test_validate_missing_file_shows_error(self) -> None:
        """Missing file shows error and exits with code 1."""
        pass

    def test_validate_invalid_yaml_shows_error(self) -> None:
        """Invalid YAML shows error message."""
        pass

    def test_validate_invalid_schema_shows_error(self) -> None:
        """Config missing required fields shows validation error."""
        pass


class TestInfoCommand:
    """Tests for 'experiment info' command."""

    def test_info_shows_evaluation_modes(self) -> None:
        """Shows bootstrap and deterministic modes."""
        pass

    def test_info_shows_key_features(self) -> None:
        """Shows key features of the framework."""
        pass

    def test_info_shows_available_commands(self) -> None:
        """Shows list of available commands."""
        pass


class TestTemplateCommand:
    """Tests for 'experiment template' command."""

    def test_template_outputs_to_stdout(self) -> None:
        """Without -o, outputs to stdout."""
        pass

    def test_template_writes_to_file(self) -> None:
        """With -o, writes to specified file."""
        pass

    def test_template_has_required_fields(self) -> None:
        """Generated template has all required fields."""
        pass


class TestListCommand:
    """Tests for 'experiment list' command."""

    def test_list_shows_experiments_in_directory(self) -> None:
        """Lists all .yaml/.yml files in directory."""
        pass

    def test_list_missing_directory_shows_error(self) -> None:
        """Missing directory shows error and exits."""
        pass

    def test_list_empty_directory_shows_message(self) -> None:
        """Empty directory shows appropriate message."""
        pass


class TestRunCommand:
    """Tests for 'experiment run' command."""

    def test_run_loads_config(self) -> None:
        """Run command loads and validates config."""
        pass

    def test_run_dry_run_skips_execution(self) -> None:
        """--dry-run validates without executing."""
        pass

    def test_run_seed_override_works(self) -> None:
        """--seed overrides config seed."""
        pass
```

---

## Implementation

### File: `api/payment_simulator/cli/commands/experiment.py`

**Commands Implemented:**

1. **`validate`** - Validates experiment YAML against ExperimentConfig schema
   - Loads YAML file
   - Validates against schema
   - Shows config summary on success
   - Shows error message on failure

2. **`info`** - Shows framework information
   - Evaluation modes (bootstrap, deterministic)
   - Key features
   - Available commands

3. **`template`** - Generates config template
   - Outputs to stdout by default
   - `-o` flag writes to file
   - Includes all required fields with sensible defaults

4. **`list`** - Lists experiments in directory
   - Scans for .yaml/.yml files
   - Shows name, description, mode, agents
   - Handles invalid files gracefully

5. **`run`** - Runs experiment (placeholder)
   - Loads and validates config
   - `--dry-run` for validation only
   - `--seed` to override seed
   - `--verbose` for detailed output
   - **Note:** Actual execution deferred to Phase 6

### Registration in main CLI:

```python
# api/payment_simulator/cli/main.py
from payment_simulator.cli.commands.experiment import experiment_app

app.add_typer(experiment_app, name="experiment")
```

---

## Files Created

| File | Purpose |
|------|---------|
| `api/payment_simulator/cli/commands/experiment.py` | CLI commands implementation |
| `api/tests/cli/test_experiment_commands.py` | Command tests |

---

## Files Modified

| File | Change |
|------|--------|
| `api/payment_simulator/cli/main.py` | Added experiment_app to main CLI |

---

## Usage Examples

```bash
# Show help
payment-sim experiment --help

# Validate a config
payment-sim experiment validate experiments/exp1.yaml

# Show framework info
payment-sim experiment info

# Generate template
payment-sim experiment template
payment-sim experiment template -o new_experiment.yaml

# List experiments
payment-sim experiment list experiments/castro/experiments/

# Run experiment (placeholder - use castro run for now)
payment-sim experiment run experiments/exp1.yaml
payment-sim experiment run experiments/exp1.yaml --dry-run
payment-sim experiment run experiments/exp1.yaml --seed 12345
```

---

## Verification

```bash
# Run CLI tests
cd api && .venv/bin/python -m pytest tests/cli/test_experiment_commands.py -v

# Verify CLI help works
payment-sim experiment --help

# Verify commands work
payment-sim experiment info
payment-sim experiment template
```

---

## Notes

### What's Implemented

- Full CLI command structure
- Config validation
- Template generation
- Directory listing
- Dry-run capability

### What's Deferred to Phase 6

- Actual experiment execution in `run` command
- Integration with BaseExperimentRunner
- Results persistence
- Real-time progress output

### Phase 6 Integration Point

The `_run_experiment_async()` function in `experiment.py` is the integration
point. Phase 6 will:

1. Create experiment runner from config
2. Wire up LLM client
3. Execute optimization loop
4. Persist results to database
5. Display real-time progress

---

## Status Summary

| Objective | Status |
|-----------|--------|
| Create command group | DONE |
| validate command | DONE |
| info command | DONE |
| template command | DONE |
| list command | DONE |
| run command (placeholder) | DONE (awaiting Phase 6) |

**Overall: 100% of Phase 5 scope, 85% of full functionality**

The `run` command is a complete placeholder per plan - actual execution
requires Phase 6 Castro migration to wire up the experiment runner.
