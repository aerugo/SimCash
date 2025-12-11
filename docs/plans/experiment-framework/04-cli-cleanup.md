# Plan: CLI Cleanup and Consolidation

## Problem Statement

There are two experiment CLI files in the codebase:

1. **`cli/commands/experiment.py`** - Simpler duplicate with basic commands
   - Creates `experiment_app` Typer app
   - Has: `run`, `validate`, `template`, `list`, `info`
   - Missing: `replay`, `results` (database commands)
   - Uses `typer.echo()` for output
   - Does NOT use StateProvider pattern

2. **`experiments/cli/commands.py`** - Full-featured implementation
   - Creates `experiment_app` Typer app
   - Has: `run`, `validate`, `list`, `info`, `replay`, `results`
   - Uses Rich Console for output
   - Uses StateProvider pattern for replay identity
   - Uses `build_verbose_config()` helper

This duplication causes confusion and risks divergent behavior.

## Goal

Consolidate to a single CLI implementation that:
1. Lives in `experiments/cli/commands.py` (canonical location)
2. Has all commands (run, replay, results, validate, list, info, template)
3. Uses StateProvider pattern for replay identity
4. Removes the duplicate file

## TDD Approach

### Test File: `api/tests/experiments/cli/test_cli_commands.py`

Write tests that verify the consolidated CLI works correctly.

---

## Task 1: Verify existing commands work

### Test 1.1: Run command exists and works

```python
from typer.testing import CliRunner
from payment_simulator.experiments.cli.commands import experiment_app

runner = CliRunner()

def test_run_command_exists():
    """Run command is available in CLI."""
    result = runner.invoke(experiment_app, ["run", "--help"])
    assert result.exit_code == 0
    assert "Run experiment" in result.output
```

### Test 1.2: Replay command exists

```python
def test_replay_command_exists():
    """Replay command is available in CLI."""
    result = runner.invoke(experiment_app, ["replay", "--help"])
    assert result.exit_code == 0
    assert "Replay experiment" in result.output
```

### Test 1.3: Results command exists

```python
def test_results_command_exists():
    """Results command is available in CLI."""
    result = runner.invoke(experiment_app, ["results", "--help"])
    assert result.exit_code == 0
    assert "List experiment runs" in result.output
```

### Test 1.4: Validate command exists

```python
def test_validate_command_exists():
    """Validate command is available in CLI."""
    result = runner.invoke(experiment_app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "Validate experiment" in result.output
```

### Test 1.5: List command exists

```python
def test_list_command_exists():
    """List command is available in CLI."""
    result = runner.invoke(experiment_app, ["list", "--help"])
    assert result.exit_code == 0
    assert "List available experiments" in result.output
```

### Test 1.6: Info command exists

```python
def test_info_command_exists():
    """Info command is available in CLI."""
    result = runner.invoke(experiment_app, ["info", "--help"])
    assert result.exit_code == 0
    assert "Show detailed experiment" in result.output
```

---

## Task 2: Add missing template command

The `experiments/cli/commands.py` is missing the `template` command from the duplicate file.

### Test 2.1: Template command exists

```python
def test_template_command_exists():
    """Template command is available in CLI."""
    result = runner.invoke(experiment_app, ["template", "--help"])
    assert result.exit_code == 0
    assert "Generate" in result.output
```

### Test 2.2: Template generates valid YAML

```python
def test_template_generates_valid_yaml():
    """Template command generates valid experiment YAML."""
    result = runner.invoke(experiment_app, ["template"])
    assert result.exit_code == 0

    # Parse the output as YAML
    import yaml
    config = yaml.safe_load(result.output)

    # Verify required fields
    assert "name" in config
    assert "evaluation" in config
    assert "convergence" in config
    assert "optimized_agents" in config
```

### Test 2.3: Template can write to file

```python
def test_template_writes_to_file(tmp_path):
    """Template command can write to output file."""
    output_file = tmp_path / "template.yaml"
    result = runner.invoke(experiment_app, ["template", "-o", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()

    # Verify file contents
    import yaml
    with open(output_file) as f:
        config = yaml.safe_load(f)
    assert "name" in config
```

### Implementation 2

Add template command to `experiments/cli/commands.py`:

```python
@experiment_app.command()
def template(
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (stdout if not specified)",
        ),
    ] = None,
) -> None:
    """Generate an experiment configuration template.

    Creates a YAML template with sensible defaults and all
    required fields. You can modify this template to create
    your own experiments.

    Examples:
        # Print template to stdout
        experiments template

        # Save template to file
        experiments template -o my_experiment.yaml
    """
    template_config = {
        "name": "my_experiment",
        "description": "Description of your experiment",
        "scenario": "configs/scenario.yaml",
        "evaluation": {
            "mode": "bootstrap",
            "num_samples": 10,
            "ticks": 12,
        },
        "convergence": {
            "max_iterations": 50,
            "stability_threshold": 0.05,
            "stability_window": 5,
            "improvement_threshold": 0.01,
        },
        "llm": {
            "model": "anthropic:claude-sonnet-4-5",
            "temperature": 0.0,
            "max_retries": 3,
            "timeout_seconds": 120,
        },
        "optimized_agents": ["BANK_A"],
        "constraints": "your_module.constraints.YOUR_CONSTRAINTS",
        "output": {
            "directory": "results",
            "database": "experiments.db",
            "verbose": True,
        },
        "master_seed": 42,
    }

    yaml_content = yaml.dump(template_config, default_flow_style=False, sort_keys=False)

    if output:
        output.write_text(yaml_content)
        console.print(f"[green]Template written to {output}[/green]")
    else:
        console.print(yaml_content)
```

---

## Task 3: Remove duplicate CLI file

### Test 3.1: Verify main CLI uses correct app

```python
def test_main_cli_uses_experiments_app():
    """Main CLI uses the experiments/cli/commands.py app."""
    from payment_simulator.cli.main import app

    # Check that experiment subcommand points to the correct app
    # This is implementation-specific; adjust based on how apps are registered

    # The key is that running "payment-sim experiment run" uses
    # the experiments/cli/commands.py implementation
```

### Test 3.2: Replay command accessible from main CLI

```python
def test_replay_accessible_from_main_cli():
    """Replay command is accessible via main CLI."""
    from payment_simulator.cli.main import app

    result = runner.invoke(app, ["experiment", "replay", "--help"])
    assert result.exit_code == 0
    assert "Replay experiment" in result.output
```

### Implementation 3

1. Delete `cli/commands/experiment.py`
2. Update `cli/main.py` to import from correct location:

```python
# In cli/main.py

# Remove this import:
# from payment_simulator.cli.commands.experiment import experiment_app

# Add this import:
from payment_simulator.experiments.cli.commands import experiment_app

# Register the app
app.add_typer(experiment_app, name="experiment")
```

---

## Task 4: Verify no broken imports

### Test 4.1: No references to deleted file

```python
import subprocess

def test_no_references_to_deleted_cli():
    """No code references the deleted cli/commands/experiment.py."""
    result = subprocess.run(
        ["grep", "-r", "cli.commands.experiment", "api/payment_simulator/"],
        capture_output=True,
        text=True,
    )
    # Should find nothing (grep returns 1 if no matches)
    assert result.returncode == 1 or result.stdout.strip() == ""
```

### Test 4.2: All CLI tests pass

```python
def test_all_cli_tests_pass():
    """All existing CLI tests still pass after consolidation."""
    # This is a meta-test - run pytest on CLI tests
    import subprocess
    result = subprocess.run(
        ["pytest", "api/tests/experiments/cli/", "-v"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
```

---

## Task 5: Update any documentation

### Test 5.1: CLAUDE.md doesn't reference deleted file

```python
def test_claudemd_updated():
    """CLAUDE.md doesn't reference deleted cli/commands/experiment.py."""
    with open("api/CLAUDE.md") as f:
        content = f.read()
    assert "cli/commands/experiment.py" not in content
```

---

## Verification Checklist

- [ ] All tests pass before changes (baseline)
- [ ] Template command added to experiments/cli/commands.py
- [ ] cli/commands/experiment.py deleted
- [ ] cli/main.py updated to use experiments/cli/commands.py
- [ ] No broken imports
- [ ] All CLI tests still pass
- [ ] Main CLI has all commands: run, replay, results, validate, list, info, template
- [ ] Documentation updated

## Files to Modify

1. `api/payment_simulator/experiments/cli/commands.py` - Add template command
2. `api/payment_simulator/cli/main.py` - Update import
3. `api/payment_simulator/cli/commands/experiment.py` - DELETE this file
4. `api/tests/experiments/cli/test_cli_commands.py` - New/updated test file

## Migration Steps

1. **Before any changes**: Run all tests to establish baseline
2. **Add template command**: Add to experiments/cli/commands.py, verify with tests
3. **Update main.py**: Change import to use experiments/cli/commands
4. **Delete duplicate**: Remove cli/commands/experiment.py
5. **Run all tests**: Verify nothing broke
6. **Search for stale references**: Grep for any remaining references
7. **Update documentation**: If any docs reference the old file

## Risk Assessment

- **Low risk**: The experiments/cli/commands.py already has more functionality
- **Migration**: Just switching imports, no logic changes
- **Rollback**: Easy to restore deleted file if needed

## Commands Comparison

| Command | cli/commands/experiment.py | experiments/cli/commands.py |
|---------|---------------------------|----------------------------|
| run | Yes | Yes |
| validate | Yes | Yes |
| template | Yes | **No (add)** |
| list | Yes | Yes |
| info | Yes (framework info) | Yes (config info) |
| replay | **No** | Yes |
| results | **No** | Yes |

The `info` commands differ slightly:
- Duplicate: Shows framework overview
- Canonical: Shows config file details

Decision: Keep the config-focused `info` since `--help` provides framework overview.

