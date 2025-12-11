# Phase 17: Complete Generic CLI in Core

**Status:** IN PROGRESS (2025-12-11)
**Created:** 2025-12-11
**Purpose:** Complete the generic CLI with all experiment commands

---

## Objective

Create a complete generic CLI in core that can manage ANY experiment with YAML configs:
1. `run` - Run experiment from YAML config
2. `list` - List available experiments in a directory
3. `info` - Show detailed experiment information
4. `validate` - Validate experiment YAML config

After this phase, any experiment can be managed entirely via the core CLI with no experiment-specific code.

---

## Current State

### Core CLI (`api/payment_simulator/experiments/cli/`)
- `commands.py` has `replay` and `results` commands (Phase 14.4) ✅
- `common.py` has `build_verbose_config()` helper ✅
- Missing: `run`, `list`, `info`, `validate` commands

### Existing CLI (`api/payment_simulator/cli/commands/experiment.py`)
- Phase 5 created `run`, `validate`, `list`, `info`, `template` commands
- These work but are NOT in the experiments module
- Need to unify with core experiments CLI

---

## Target State

```
api/payment_simulator/experiments/cli/
├── __init__.py           # Updated exports
├── commands.py           # All commands: run, list, info, validate, replay, results
└── common.py             # build_verbose_config (existing)
```

---

## TDD Test Plan

### Task 17.2: Add `run` Command

**Test File:** `api/tests/experiments/cli/test_run_command.py`

```python
class TestRunCommand:
    def test_run_command_exists() -> None:
        """run command exists in experiment_app."""

    def test_run_requires_config_path() -> None:
        """run requires experiment config path argument."""

    def test_run_validates_config_first() -> None:
        """run validates config before execution."""

    def test_run_accepts_dry_run_flag() -> None:
        """run --dry-run validates without executing."""

    def test_run_accepts_seed_override() -> None:
        """run --seed overrides master_seed from config."""

    def test_run_accepts_verbose_flags() -> None:
        """run accepts --verbose and individual verbose flags."""

    def test_run_creates_experiment_runner() -> None:
        """run creates GenericExperimentRunner from config."""

    def test_run_displays_output() -> None:
        """run displays experiment output via display functions."""
```

### Task 17.3: Add `list` Command

**Test File:** `api/tests/experiments/cli/test_list_command.py`

```python
class TestListCommand:
    def test_list_command_exists() -> None:
        """list command exists in experiment_app."""

    def test_list_scans_directory() -> None:
        """list scans directory for YAML files."""

    def test_list_shows_experiment_names() -> None:
        """list shows experiment names from YAML."""

    def test_list_shows_descriptions() -> None:
        """list shows experiment descriptions."""

    def test_list_handles_empty_directory() -> None:
        """list handles empty directory gracefully."""

    def test_list_handles_invalid_yaml() -> None:
        """list skips invalid YAML files with warning."""

    def test_list_uses_default_directory() -> None:
        """list uses current directory if not specified."""
```

### Task 17.4: Add `info` Command

**Test File:** `api/tests/experiments/cli/test_info_command.py`

```python
class TestInfoCommand:
    def test_info_command_exists() -> None:
        """info command exists in experiment_app."""

    def test_info_requires_config_path() -> None:
        """info requires experiment config path argument."""

    def test_info_shows_experiment_name() -> None:
        """info shows experiment name."""

    def test_info_shows_description() -> None:
        """info shows experiment description."""

    def test_info_shows_evaluation_mode() -> None:
        """info shows evaluation mode (bootstrap/deterministic)."""

    def test_info_shows_convergence_settings() -> None:
        """info shows convergence criteria."""

    def test_info_shows_llm_config() -> None:
        """info shows LLM model configuration."""

    def test_info_shows_optimized_agents() -> None:
        """info shows list of optimized agents."""

    def test_info_handles_missing_file() -> None:
        """info shows error for missing file."""

    def test_info_handles_invalid_yaml() -> None:
        """info shows error for invalid YAML."""
```

### Task 17.5: Add `validate` Command

**Test File:** `api/tests/experiments/cli/test_validate_command.py`

```python
class TestValidateCommand:
    def test_validate_command_exists() -> None:
        """validate command exists in experiment_app."""

    def test_validate_requires_config_path() -> None:
        """validate requires experiment config path argument."""

    def test_validate_shows_success() -> None:
        """validate shows success message for valid config."""

    def test_validate_shows_errors() -> None:
        """validate shows errors for invalid config."""

    def test_validate_handles_missing_file() -> None:
        """validate shows error for missing file."""

    def test_validate_handles_yaml_syntax_error() -> None:
        """validate shows error for YAML syntax errors."""

    def test_validate_handles_missing_required_fields() -> None:
        """validate shows error for missing required fields."""
```

---

## Implementation Plan

### 17.2: Add `run` Command

```python
@experiment_app.command()
def run(
    config_path: Annotated[Path, typer.Argument(help="Path to experiment YAML config")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate without executing")] = False,
    seed: Annotated[int | None, typer.Option("--seed", help="Override master seed")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    # ... other verbose flags
) -> None:
    """Run experiment from YAML configuration."""
    # 1. Load and validate config
    config = ExperimentConfig.from_yaml(config_path)

    # 2. Override seed if provided
    if seed is not None:
        config = config.with_seed(seed)

    # 3. Dry run just validates
    if dry_run:
        console.print("[green]Configuration valid![/green]")
        return

    # 4. Create runner and execute
    runner = GenericExperimentRunner(config, verbose_config=verbose_config)
    result = asyncio.run(runner.run())

    # 5. Display results
    display_experiment_output(runner, console, verbose_config)
```

### 17.3: Add `list` Command

```python
@experiment_app.command("list")
def list_experiments(
    directory: Annotated[Path, typer.Argument(help="Directory containing experiments")] = Path("."),
) -> None:
    """List available experiments in directory."""
    # Scan for YAML files
    yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

    # Parse each and show table
    table = Table(title="Available Experiments")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Mode")
    table.add_column("Agents")

    for yaml_file in yaml_files:
        try:
            config = ExperimentConfig.from_yaml(yaml_file)
            table.add_row(
                config.name,
                config.description[:50] + "..." if len(config.description) > 50 else config.description,
                config.evaluation.mode,
                ", ".join(config.optimized_agents),
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Skipping {yaml_file.name}: {e}[/yellow]")

    console.print(table)
```

### 17.4: Add `info` Command

```python
@experiment_app.command()
def info(
    config_path: Annotated[Path, typer.Argument(help="Path to experiment YAML config")],
) -> None:
    """Show detailed experiment information."""
    config = ExperimentConfig.from_yaml(config_path)

    # Name and description
    console.print(f"[bold cyan]Experiment: {config.name}[/bold cyan]")
    console.print(f"Description: {config.description}")
    console.print()

    # Evaluation settings
    console.print("[bold]Evaluation:[/bold]")
    console.print(f"  Mode: {config.evaluation.mode}")
    console.print(f"  Ticks: {config.evaluation.ticks}")
    if config.evaluation.mode == "bootstrap":
        console.print(f"  Samples: {config.evaluation.num_samples}")
    console.print()

    # Convergence settings
    console.print("[bold]Convergence:[/bold]")
    console.print(f"  Max iterations: {config.convergence.max_iterations}")
    console.print(f"  Stability threshold: {config.convergence.stability_threshold}")
    console.print(f"  Stability window: {config.convergence.stability_window}")
    console.print()

    # LLM settings
    console.print("[bold]LLM:[/bold]")
    console.print(f"  Model: {config.llm.model}")
    console.print(f"  Temperature: {config.llm.temperature}")
    if config.llm.system_prompt:
        console.print(f"  System prompt: (defined, {len(config.llm.system_prompt)} chars)")
    console.print()

    # Agents
    console.print("[bold]Optimized Agents:[/bold]")
    for agent in config.optimized_agents:
        console.print(f"  - {agent}")
```

### 17.5: Add `validate` Command

```python
@experiment_app.command()
def validate(
    config_path: Annotated[Path, typer.Argument(help="Path to experiment YAML config")],
) -> None:
    """Validate experiment YAML configuration."""
    if not config_path.exists():
        console.print(f"[red]Error: File not found: {config_path}[/red]")
        raise typer.Exit(1)

    try:
        config = ExperimentConfig.from_yaml(config_path)
        console.print(f"[green]✓ Configuration valid: {config.name}[/green]")

        # Show summary
        console.print(f"  Evaluation mode: {config.evaluation.mode}")
        console.print(f"  Max iterations: {config.convergence.max_iterations}")
        console.print(f"  Optimized agents: {', '.join(config.optimized_agents)}")

    except yaml.YAMLError as e:
        console.print(f"[red]YAML syntax error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `cli/commands.py` | MODIFY | Add run, list, info, validate commands |
| `tests/cli/test_run_command.py` | CREATE | TDD tests for run command |
| `tests/cli/test_list_command.py` | CREATE | TDD tests for list command |
| `tests/cli/test_info_command.py` | CREATE | TDD tests for info command |
| `tests/cli/test_validate_command.py` | CREATE | TDD tests for validate command |

---

## Verification

```bash
# Run new tests
cd api && .venv/bin/python -m pytest tests/experiments/cli/ -v

# Run all experiment tests
cd api && .venv/bin/python -m pytest tests/experiments/ -v

# Verify no regression
cd api && .venv/bin/python -m pytest tests/ --tb=short

# Manual verification
payment-sim experiments validate experiments/castro/experiments/exp1.yaml
payment-sim experiments list experiments/castro/experiments/
payment-sim experiments info experiments/castro/experiments/exp1.yaml
payment-sim experiments run experiments/castro/experiments/exp1.yaml --dry-run
```

---

## Success Criteria

1. ✅ All new tests pass
2. ✅ Commands work with any experiment YAML
3. ✅ No hardcoded experiment-specific logic
4. ✅ mypy passes on new code
5. ✅ Help text is clear and complete

---

*Created: 2025-12-11*
