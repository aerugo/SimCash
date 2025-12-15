# Phase 3: CLI Integration

**Status**: Pending
**Started**: -

---

## Objective

Wire the chart command into the experiment CLI with proper options, validation, and error handling.

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Add to `api/tests/experiments/cli/test_experiment_commands.py` (or create if needed):

**Test Cases**:
1. `test_chart_command_basic` - Command runs with valid run_id
2. `test_chart_command_agent_filter` - `--agent` option works
3. `test_chart_command_parameter_requires_agent` - `--parameter` without `--agent` fails

```python
from typer.testing import CliRunner

class TestChartCommand:
    def test_chart_command_basic(self, tmp_db: Path) -> None:
        """Chart command generates output file."""
        # Setup: Create experiment in database
        # Run: payment-sim experiment chart <run-id> --db <tmp_db>
        # Verify: Output file created

    def test_chart_command_agent_filter(self, tmp_db: Path) -> None:
        """--agent option filters to single agent."""
        # Run with --agent BANK_A
        # Verify chart created with agent in title

    def test_chart_command_parameter_requires_agent(self) -> None:
        """--parameter without --agent shows error."""
        runner = CliRunner()
        result = runner.invoke(
            experiment_app,
            ["chart", "run-123", "--parameter", "initial_liquidity_fraction"],
        )
        assert result.exit_code == 1
        assert "--agent" in result.output
```

### Step 3.2: Implement to Pass Tests (GREEN)

Add to `api/payment_simulator/experiments/cli/commands.py`:

```python
@experiment_app.command()
def chart(
    run_id: Annotated[
        str,
        typer.Argument(help="Run ID to visualize (e.g., exp1-20251209-143022-a1b2c3)"),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", "-d", help="Path to database file"),
    ] = DEFAULT_DB_PATH,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Filter to specific agent's costs"),
    ] = None,
    parameter: Annotated[
        str | None,
        typer.Option(
            "--parameter",
            "-p",
            help="Show parameter value at each iteration (requires --agent)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (default: <run_id>.png)",
        ),
    ] = None,
) -> None:
    """Generate convergence chart for an experiment run.

    Creates a line plot showing cost optimization over iterations:
    - Primary line: Cost trajectory following accepted policies
    - Secondary line (subtle): Cost of all tested policies

    Use --agent to filter to a specific agent's costs.
    Use --parameter with --agent to annotate parameter values.

    Examples:
        # Basic chart for all agents
        payment-sim experiment chart exp1-20251215-084901-866d63

        # Chart for specific agent
        payment-sim experiment chart exp1-20251215-084901-866d63 --agent BANK_A

        # Chart with parameter value annotations
        payment-sim experiment chart exp1-20251215-084901-866d63 \\
            --agent BANK_A --parameter initial_liquidity_fraction

        # Custom output path
        payment-sim experiment chart exp1-20251215-084901-866d63 --output results/chart.png

        # From specific database
        payment-sim experiment chart exp1-20251215-084901-866d63 --db results/custom.db
    """
    # Validate: --parameter requires --agent
    if parameter is not None and agent is None:
        console.print(
            "[red]Error: --parameter requires --agent to be specified[/red]"
        )
        console.print("Example: --agent BANK_A --parameter initial_liquidity_fraction")
        raise typer.Exit(1)

    # Check database exists
    if not db.exists():
        console.print(f"[red]Database not found: {db}[/red]")
        raise typer.Exit(1)

    # Default output path
    if output is None:
        output = Path(f"{run_id}.png")

    # Open repository
    try:
        repo = ExperimentRepository(db)
    except Exception as e:
        console.print(f"[red]Failed to open database: {e}[/red]")
        raise typer.Exit(1) from e

    # Import charting service
    from payment_simulator.experiments.analysis.charting import (
        ExperimentChartService,
        render_convergence_chart,
    )

    try:
        # Extract data
        service = ExperimentChartService(repo)
        chart_data = service.extract_chart_data(
            run_id=run_id,
            agent_filter=agent,
            parameter_name=parameter,
        )

        # Check we have data
        if not chart_data.data_points:
            console.print(f"[yellow]No iteration data found for run: {run_id}[/yellow]")
            repo.close()
            raise typer.Exit(1)

        # Render chart
        render_convergence_chart(chart_data, output)

        console.print(f"[green]Chart saved to: {output}[/green]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        repo.close()
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Failed to generate chart: {e}[/red]")
        repo.close()
        raise typer.Exit(1) from e

    repo.close()
```

### Step 3.3: Refactor

- Ensure error messages are helpful
- Add progress indication for large experiments

---

## CLI Interface Specification

### Command Synopsis

```
payment-sim experiment chart <run-id> [OPTIONS]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `run-id` | String | Run ID to visualize (e.g., `exp1-20251215-084901-866d63`) |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db` | `-d` | Path | `results/experiments.db` | Path to database file |
| `--agent` | `-a` | String | `null` | Filter to specific agent's costs |
| `--parameter` | `-p` | String | `null` | Show parameter value at each iteration (requires `--agent`) |
| `--output` | `-o` | Path | `<run-id>.png` | Output file path |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Database not found, run not found, or invalid options |

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/cli/commands.py` | MODIFY (add chart command) |
| `api/tests/experiments/cli/test_experiment_commands.py` | CREATE or MODIFY |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/cli/test_experiment_commands.py -v

# Manual test (requires actual experiment database)
payment-sim experiment chart exp1-20251215-084901-866d63 --db results/experiments.db

# Test with agent filter
payment-sim experiment chart exp1-20251215-084901-866d63 --agent BANK_A

# Test with parameter
payment-sim experiment chart exp1-20251215-084901-866d63 \
    --agent BANK_A --parameter initial_liquidity_fraction

# Test error case
payment-sim experiment chart exp1-20251215-084901-866d63 --parameter foo
# Should error: "--parameter requires --agent"
```

---

## Completion Criteria

- [ ] Command registered in experiment_app
- [ ] Basic usage works
- [ ] `--agent` filtering works
- [ ] `--parameter` with `--agent` works
- [ ] `--parameter` without `--agent` shows helpful error
- [ ] `--output` controls output path
- [ ] Missing database shows error
- [ ] Invalid run_id shows error
- [ ] All tests pass
