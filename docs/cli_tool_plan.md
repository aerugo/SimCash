# CLI Tool Implementation Plan

> **Terminal-first simulation interface optimized for AI-driven iteration**

**Status**: Planning Phase
**Priority**: Medium (enhances developer experience)
**Timeline**: 2-3 days implementation
**Dependencies**: Phase 7 complete (Python API + FFI)

---

## Executive Summary

A command-line interface for running payment simulations directly from the terminal, with **first-class support for piping output to AI coding models**. The CLI enables rapid iteration, automated testing, and AI-assisted policy development.

**Key Design Principle**: Output to `stdout` is **always valid JSON** (machine-readable), while human-readable logs go to `stderr` (filterable).

---

## Use Cases

### 1. **AI-Driven Iteration** (Primary Use Case)

AI models can run simulations, analyze results, and iteratively refine configurations:

```bash
# AI model runs simulation and gets structured JSON output
payment-sim run --config config.yaml --output json | ai-model analyze

# AI iterates on policy parameters
for threshold in 5 10 15 20; do
    payment-sim run \
        --config base.yaml \
        --override "agents[0].policy.urgency_threshold=$threshold" \
        --quiet \
        | jq '.metrics.settlement_rate'
done
```

### 2. **Quick Manual Testing**

Developers can test changes without starting the API server:

```bash
# Run a quick simulation
payment-sim run --config test_scenario.yaml

# Compare two policies side-by-side
payment-sim compare \
    --config scenario.yaml \
    --policies fifo,deadline,liquidity \
    --output table
```

### 3. **Batch Processing & CI/CD**

Automated testing in continuous integration:

```bash
# Regression test suite
for config in tests/scenarios/*.yaml; do
    payment-sim run --config "$config" --validate-only || exit 1
done

# Performance benchmarking
payment-sim benchmark --agents 50 --ticks 1000 --output json > bench_results.json
```

### 4. **Data Pipeline Integration**

Generate simulation data for analysis tools:

```bash
# Export to CSV for analysis
payment-sim run --config scenario.yaml --export-csv results/

# Pipe to data processing pipeline
payment-sim run --config config.yaml --output jsonl | \
    jq -c '.events[]' | \
    kafka-console-producer --topic simulation-events
```

---

## CLI Architecture

### Command Structure

```
payment-sim <command> [options]

Commands:
  run          Run a simulation from config file
  compare      Compare multiple policies on same scenario
  benchmark    Performance testing and profiling
  validate     Validate configuration without running
  replay       Replay simulation from seed
  generate     Generate sample configurations
  serve        Start API server (wrapper around uvicorn)

Options (global):
  --quiet, -q        Suppress stderr logs (stdout only)
  --verbose, -v      Detailed logging to stderr
  --output FORMAT    Output format: json (default), jsonl, yaml, table
  --no-color         Disable colored output
  --help, -h         Show help message
  --version          Show version information
```

### Output Philosophy

**Golden Rule**: `stdout` = machine-readable data, `stderr` = human-readable logs

```bash
# Good: AI gets clean JSON
payment-sim run --config cfg.yaml --quiet > results.json

# Logs go to stderr (can be filtered)
payment-sim run --config cfg.yaml 2>/dev/null  # Suppress logs

# Human-friendly progress indicators on stderr
payment-sim run --config cfg.yaml --verbose 2>&1 | grep "Progress"
```

---

## Command Specifications

### 1. `payment-sim run`

**Purpose**: Run a single simulation from configuration file.

**Usage**:
```bash
payment-sim run [OPTIONS] --config FILE

Options:
  --config FILE           Configuration file (YAML or JSON) [required]
  --ticks N               Override tick count
  --seed N                Override RNG seed
  --override PATH=VALUE   Override config value (JSONPath syntax)
  --export-csv DIR        Export results to CSV files
  --export-json FILE      Export full results to JSON file
  --output FORMAT         Output format: json|jsonl|yaml|table
  --quiet, -q             Suppress logs (stdout only)
  --stream                Stream tick results as JSONL
  --watch FILE            Re-run when config file changes
```

**Output Format (JSON)**:

```json
{
  "simulation": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "config_file": "scenario.yaml",
    "seed": 42,
    "ticks_executed": 1000,
    "duration_seconds": 0.85,
    "ticks_per_second": 1176.47
  },
  "metrics": {
    "total_transactions": 2543,
    "settled_transactions": 2398,
    "pending_transactions": 145,
    "settlement_rate": 0.9430,
    "total_value": 125430000,
    "settled_value": 119870000,
    "value_settlement_rate": 0.9556,
    "avg_settlement_time_ticks": 3.2,
    "max_settlement_time_ticks": 47,
    "gridlock_events": 3,
    "lsm_releases": 234
  },
  "agents": [
    {
      "id": "BANK_A",
      "final_balance": 950000,
      "peak_overdraft": -150000,
      "transactions_sent": 637,
      "transactions_received": 615,
      "total_costs": 12450
    }
  ],
  "costs": {
    "total_overdraft_cost": 45600,
    "total_delay_cost": 23400,
    "total_deadline_penalties": 145000,
    "total_split_costs": 3200,
    "total_eod_penalties": 0
  },
  "performance": {
    "ticks_per_second": 1176.47,
    "memory_peak_mb": 45.2
  }
}
```

**Output Format (JSONL - Streaming)**:

When using `--stream`, output one JSON object per tick:

```jsonl
{"tick":0,"arrivals":5,"settlements":5,"lsm_releases":0,"costs":0}
{"tick":1,"arrivals":7,"settlements":6,"lsm_releases":2,"costs":120}
{"tick":2,"arrivals":4,"settlements":9,"lsm_releases":1,"costs":80}
...
```

**Examples**:

```bash
# Basic run
payment-sim run --config scenario.yaml

# Override parameters for quick testing
payment-sim run \
    --config base.yaml \
    --seed 12345 \
    --ticks 500 \
    --override "agents[0].policy.urgency_threshold=15"

# AI-friendly: quiet mode with JSON output
payment-sim run --config cfg.yaml --quiet --output json

# Stream results for long-running simulations
payment-sim run --config large.yaml --stream | jq -c '.tick,.settlements'

# Export to CSV for spreadsheet analysis
payment-sim run --config cfg.yaml --export-csv ./results/

# Re-run on file changes (development mode)
payment-sim run --config cfg.yaml --watch cfg.yaml
```

---

### 2. `payment-sim compare`

**Purpose**: Compare multiple policies on the same scenario.

**Usage**:
```bash
payment-sim compare [OPTIONS] --config FILE

Options:
  --config FILE               Base configuration [required]
  --policies LIST             Comma-separated policy names [required]
  --policy-configs FILE       Policy parameters (YAML/JSON)
  --replications N            Number of Monte Carlo runs per policy
  --output FORMAT             Output: json|table|markdown
  --metric METRIC             Primary metric to optimize (default: settlement_rate)
  --export-report FILE        Save comparison report
```

**Output Format (JSON)**:

```json
{
  "scenario": {
    "config_file": "stress_test.yaml",
    "replications": 10,
    "ticks_per_run": 1000
  },
  "policies": [
    {
      "name": "fifo",
      "config": {"type": "Fifo"},
      "results": {
        "settlement_rate": {"mean": 0.9234, "std": 0.0123, "min": 0.9012, "max": 0.9456},
        "avg_settlement_time": {"mean": 5.6, "std": 0.8},
        "total_costs": {"mean": 456700, "std": 23400}
      }
    },
    {
      "name": "deadline",
      "config": {"type": "Deadline", "urgency_threshold": 10},
      "results": {
        "settlement_rate": {"mean": 0.9567, "std": 0.0098, "min": 0.9401, "max": 0.9678},
        "avg_settlement_time": {"mean": 4.2, "std": 0.6},
        "total_costs": {"mean": 389200, "std": 19800}
      }
    }
  ],
  "ranking": [
    {"policy": "deadline", "score": 0.9567, "rank": 1},
    {"policy": "fifo", "score": 0.9234, "rank": 2}
  ],
  "winner": "deadline"
}
```

**Output Format (Table)**:

```
Policy Comparison Results
=========================
Scenario: stress_test.yaml (10 replications, 1000 ticks each)

Policy          Settlement Rate  Avg Time  Total Costs  Rank
──────────────────────────────────────────────────────────────
deadline        95.67% ± 0.98%   4.2 ± 0.6  $3,892 ± 198  1 ★
liquidity       94.23% ± 1.12%   5.1 ± 0.9  $4,123 ± 234  2
fifo            92.34% ± 1.23%   5.6 ± 0.8  $4,567 ± 234  3

Winner: deadline (4.33 pp improvement over FIFO)
```

**Examples**:

```bash
# Compare three built-in policies
payment-sim compare \
    --config scenario.yaml \
    --policies fifo,deadline,liquidity

# Compare with custom parameters
payment-sim compare \
    --config scenario.yaml \
    --policies deadline \
    --policy-configs deadline_variants.yaml \
    --replications 50

# AI optimization: test parameter sweep
payment-sim compare \
    --config base.yaml \
    --policies deadline \
    --policy-configs <(echo "
policies:
  - name: deadline_5
    config: {type: Deadline, urgency_threshold: 5}
  - name: deadline_10
    config: {type: Deadline, urgency_threshold: 10}
  - name: deadline_15
    config: {type: Deadline, urgency_threshold: 15}
") \
    --output json \
    --quiet
```

---

### 3. `payment-sim benchmark`

**Purpose**: Performance testing and profiling.

**Usage**:
```bash
payment-sim benchmark [OPTIONS]

Options:
  --agents N              Number of agents (default: 10)
  --ticks N               Number of ticks (default: 1000)
  --arrival-rate FLOAT    Transactions per tick per agent (default: 2.0)
  --warmup N              Warmup ticks (default: 100)
  --runs N                Number of benchmark runs (default: 5)
  --profile               Enable detailed profiling
  --output FORMAT         Output: json|table
```

**Output Format (JSON)**:

```json
{
  "benchmark": {
    "date": "2025-10-28T15:30:00Z",
    "platform": "darwin-arm64",
    "cpu": "Apple M1 Max",
    "rust_version": "1.70.0",
    "python_version": "3.13.0"
  },
  "configuration": {
    "agents": 50,
    "ticks": 1000,
    "arrival_rate": 5.0,
    "total_transactions": 250000
  },
  "results": {
    "ticks_per_second": {"mean": 1234.5, "std": 45.6, "min": 1189.2, "max": 1298.7},
    "transactions_per_second": {"mean": 308625, "std": 11400},
    "memory_mb": {"mean": 87.3, "std": 2.1, "peak": 92.4},
    "latency_ms": {"p50": 0.81, "p95": 1.23, "p99": 2.45}
  },
  "breakdown": {
    "arrival_generation": 0.08,
    "policy_evaluation": 0.15,
    "rtgs_settlement": 0.45,
    "lsm_optimization": 0.22,
    "cost_accrual": 0.05,
    "other": 0.05
  }
}
```

**Examples**:

```bash
# Quick performance check
payment-sim benchmark

# Stress test
payment-sim benchmark --agents 100 --ticks 5000 --arrival-rate 10.0

# Detailed profiling
payment-sim benchmark --agents 50 --profile --output json > profile.json
```

---

### 4. `payment-sim validate`

**Purpose**: Validate configuration files without running simulation.

**Usage**:
```bash
payment-sim validate [OPTIONS] FILE...

Options:
  --schema                Show JSON schema for configuration
  --fix                   Attempt to fix common issues
  --output FORMAT         Output: text|json
```

**Output Format (JSON)**:

```json
{
  "file": "config.yaml",
  "valid": false,
  "errors": [
    {
      "path": "agents[0].opening_balance",
      "message": "Must be positive integer",
      "value": -1000000
    },
    {
      "path": "agents[1].policy.type",
      "message": "Unknown policy type: 'Fiffo' (did you mean 'Fifo'?)",
      "suggestions": ["Fifo", "Deadline", "LiquidityAware"]
    }
  ],
  "warnings": [
    {
      "path": "simulation.rng_seed",
      "message": "Using default seed (42). Results will be deterministic but not randomized."
    }
  ]
}
```

**Examples**:

```bash
# Validate single file
payment-sim validate config.yaml

# Validate all configs in directory
payment-sim validate configs/*.yaml

# Get JSON schema for editor integration
payment-sim validate --schema > config.schema.json

# Auto-fix common issues
payment-sim validate --fix broken.yaml > fixed.yaml
```

---

### 5. `payment-sim replay`

**Purpose**: Replay simulation with exact determinism.

**Usage**:
```bash
payment-sim replay [OPTIONS] --seed N --config FILE

Options:
  --seed N                RNG seed to replay [required]
  --config FILE           Original configuration [required]
  --compare FILE          Compare output to previous run
  --output FORMAT         Output: json|diff
```

**Use Case**: Debugging non-determinism, verifying fixes.

**Examples**:

```bash
# Replay exact simulation
payment-sim replay --seed 42 --config original.yaml

# Verify determinism
payment-sim run --config cfg.yaml --seed 12345 --output json > run1.json
payment-sim replay --seed 12345 --config cfg.yaml --output json > run2.json
diff run1.json run2.json  # Should be identical

# Compare to expected output
payment-sim replay \
    --seed 42 \
    --config cfg.yaml \
    --compare expected_output.json
```

---

### 6. `payment-sim generate`

**Purpose**: Generate sample configurations and scenarios.

**Usage**:
```bash
payment-sim generate [OPTIONS] TEMPLATE

Templates:
  minimal         Minimal 2-agent setup
  stress          High-volume stress test
  gridlock        Circular dependency scenario
  comparison      Multi-policy comparison template
  research        Full research study template

Options:
  --agents N              Number of agents (default: varies by template)
  --output FILE           Write to file (default: stdout)
  --format FORMAT         Format: yaml|json
```

**Examples**:

```bash
# Generate minimal config
payment-sim generate minimal > my_config.yaml

# Generate 50-agent stress test
payment-sim generate stress --agents 50 > stress_test.yaml

# Generate research study template
payment-sim generate research --output study/config.yaml
```

---

### 7. `payment-sim serve`

**Purpose**: Start FastAPI server (convenience wrapper).

**Usage**:
```bash
payment-sim serve [OPTIONS]

Options:
  --host HOST             Bind to host (default: localhost)
  --port PORT             Port number (default: 8000)
  --reload                Enable auto-reload (development)
  --workers N             Number of worker processes
```

**Examples**:

```bash
# Start development server
payment-sim serve --reload

# Production mode
payment-sim serve --host 0.0.0.0 --port 8080 --workers 4
```

---

## AI Integration Patterns

### Pattern 1: Iterative Parameter Tuning

AI model explores parameter space:

```python
import subprocess
import json

def run_simulation(threshold: int) -> dict:
    """Run simulation with AI model."""
    result = subprocess.run(
        [
            "payment-sim", "run",
            "--config", "base.yaml",
            "--override", f"agents[0].policy.urgency_threshold={threshold}",
            "--quiet",
            "--output", "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)

# AI iterates
best_threshold = None
best_score = -float('inf')

for threshold in range(5, 21):
    result = run_simulation(threshold)
    score = result["metrics"]["settlement_rate"]

    if score > best_score:
        best_score = score
        best_threshold = threshold

print(f"Optimal threshold: {best_threshold} (score: {best_score:.4f})")
```

### Pattern 2: Multi-Objective Optimization

AI balances multiple metrics:

```bash
#!/bin/bash
# AI script to find Pareto frontier

for threshold in {5..20}; do
    payment-sim run \
        --config base.yaml \
        --override "agents[0].policy.urgency_threshold=$threshold" \
        --quiet \
        | jq -c '{
            threshold: '$threshold',
            settlement_rate: .metrics.settlement_rate,
            avg_time: .metrics.avg_settlement_time_ticks,
            costs: .costs.total_overdraft_cost
        }'
done | jq -s 'sort_by(-.settlement_rate)'
```

### Pattern 3: A/B Testing

AI runs controlled experiments:

```bash
# Control group
payment-sim run --config control.yaml --output json > control_results.json

# Treatment group
payment-sim run \
    --config control.yaml \
    --override "agents[0].policy.type=Deadline" \
    --override "agents[0].policy.urgency_threshold=10" \
    --output json > treatment_results.json

# Statistical comparison
jq -s '
  {
    control_settlement_rate: .[0].metrics.settlement_rate,
    treatment_settlement_rate: .[1].metrics.settlement_rate,
    improvement: (.[1].metrics.settlement_rate - .[0].metrics.settlement_rate)
  }
' control_results.json treatment_results.json
```

### Pattern 4: Batch Experiments

AI runs Monte Carlo simulations:

```bash
#!/bin/bash
# Generate 100 runs with different seeds

for seed in {1..100}; do
    payment-sim run \
        --config experiment.yaml \
        --seed $seed \
        --quiet \
        --output jsonl
done | jq -s '
  {
    mean_settlement_rate: (map(.metrics.settlement_rate) | add / length),
    std_settlement_rate: (map(.metrics.settlement_rate) | [.[]] |
                          (add / length) as $mean |
                          map(pow(. - $mean; 2)) | add / length | sqrt)
  }
'
```

---

## Implementation Plan

### Phase 1: Core CLI Framework (Day 1)

**Goal**: Basic `run` command with JSON output.

**Tasks**:
- [ ] Set up Click/Typer CLI framework
- [ ] Implement `payment-sim run` command
- [ ] JSON output to stdout, logs to stderr
- [ ] Configuration file loading (YAML/JSON)
- [ ] Basic error handling

**Deliverable**: Working `run` command that outputs structured JSON.

**Test**:
```bash
payment-sim run --config test.yaml --output json > result.json
jq '.metrics.settlement_rate' result.json
```

---

### Phase 2: Advanced Run Features (Day 1-2)

**Goal**: Add streaming, overrides, and export options.

**Tasks**:
- [ ] Implement `--stream` mode (JSONL output)
- [ ] Implement `--override` for parameter tweaking
- [ ] Add `--export-csv` and `--export-json`
- [ ] Add `--watch` for auto-reload
- [ ] Add progress indicators (stderr only)

**Deliverable**: Full-featured `run` command.

**Test**:
```bash
# Override test
payment-sim run --config base.yaml --override "simulation.rng_seed=999"

# Streaming test
payment-sim run --config cfg.yaml --stream | head -10
```

---

### Phase 3: Comparison & Benchmarking (Day 2)

**Goal**: Policy comparison and performance testing.

**Tasks**:
- [ ] Implement `payment-sim compare` command
- [ ] Monte Carlo replications
- [ ] Statistical analysis (mean, std, confidence intervals)
- [ ] Table formatting for human readability
- [ ] Implement `payment-sim benchmark` command
- [ ] Performance profiling integration

**Deliverable**: Working `compare` and `benchmark` commands.

**Test**:
```bash
payment-sim compare --config test.yaml --policies fifo,deadline
payment-sim benchmark --agents 50
```

---

### Phase 4: Utilities & Polish (Day 3)

**Goal**: Validation, replay, generation, and documentation.

**Tasks**:
- [ ] Implement `payment-sim validate` command
- [ ] JSON schema generation
- [ ] Implement `payment-sim replay` command
- [ ] Implement `payment-sim generate` templates
- [ ] Implement `payment-sim serve` wrapper
- [ ] Shell completion scripts (bash, zsh, fish)
- [ ] Man page generation
- [ ] Comprehensive CLI documentation

**Deliverable**: Complete CLI tool with all features.

**Test**:
```bash
payment-sim validate broken.yaml
payment-sim generate minimal > test.yaml
payment-sim replay --seed 42 --config test.yaml
```

---

### Phase 5: AI Integration Examples (Day 3)

**Goal**: Document AI integration patterns.

**Tasks**:
- [ ] Create `docs/cli_ai_integration.md`
- [ ] Python examples (subprocess integration)
- [ ] Shell script examples (jq pipelines)
- [ ] Claude/GPT integration examples
- [ ] Jupyter notebook tutorial

**Deliverable**: Complete documentation for AI usage.

---

## Technical Implementation

### Technology Stack

- **CLI Framework**: [Typer](https://typer.tiangolo.com/) (Click-based, type-safe)
- **Output Formatting**: `rich` (tables, progress), `json` (machine-readable)
- **Configuration**: Reuse existing `payment_simulator.config` (Pydantic)
- **Simulation**: Call existing `payment_simulator.api.main` logic (no duplication)

### Project Structure

```
api/
├── payment_simulator/
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py           # CLI entry point
│   │   ├── commands/
│   │   │   ├── run.py        # payment-sim run
│   │   │   ├── compare.py    # payment-sim compare
│   │   │   ├── benchmark.py  # payment-sim benchmark
│   │   │   ├── validate.py   # payment-sim validate
│   │   │   ├── replay.py     # payment-sim replay
│   │   │   ├── generate.py   # payment-sim generate
│   │   │   └── serve.py      # payment-sim serve
│   │   ├── output.py         # Output formatters (JSON, table, JSONL)
│   │   ├── templates.py      # Config templates
│   │   └── utils.py          # Helpers
│   └── ...
└── pyproject.toml            # Add CLI entry point

[project.scripts]
payment-sim = "payment_simulator.cli.main:app"
```

### Entry Point (`cli/main.py`)

```python
import typer
from payment_simulator.cli.commands import (
    run, compare, benchmark, validate, replay, generate, serve
)

app = typer.Typer(
    name="payment-sim",
    help="Payment Simulator - High-performance RTGS simulation",
    add_completion=True,
)

app.add_typer(run.app, name="run")
app.add_typer(compare.app, name="compare")
app.add_typer(benchmark.app, name="benchmark")
app.add_typer(validate.app, name="validate")
app.add_typer(replay.app, name="replay")
app.add_typer(generate.app, name="generate")
app.add_typer(serve.app, name="serve")

if __name__ == "__main__":
    app()
```

### Output Strategy

```python
import sys
import json
from typing import Any
from rich.console import Console
from rich.progress import Progress

# stderr console for human logs
console = Console(stderr=True)

# stdout for machine-readable output
def output_json(data: Any):
    """Output JSON to stdout (machine-readable)."""
    print(json.dumps(data, indent=2))

def output_jsonl(data: Any):
    """Output JSONL to stdout (streaming)."""
    print(json.dumps(data))

def log_info(message: str):
    """Log info to stderr (human-readable)."""
    console.print(f"[blue]ℹ[/blue] {message}")

def log_error(message: str):
    """Log error to stderr."""
    console.print(f"[red]✗[/red] {message}", style="bold red")

def log_success(message: str):
    """Log success to stderr."""
    console.print(f"[green]✓[/green] {message}")
```

---

## Testing Strategy

### Unit Tests

Test individual commands in isolation:

```python
from typer.testing import CliRunner
from payment_simulator.cli.main import app

runner = CliRunner()

def test_run_command_json_output():
    """Test run command outputs valid JSON."""
    result = runner.invoke(app, [
        "run",
        "--config", "test_data/minimal.yaml",
        "--quiet",
        "--output", "json",
    ])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "metrics" in data
    assert "simulation" in data
```

### Integration Tests

Test full workflows:

```python
def test_ai_iteration_workflow():
    """Test AI parameter tuning workflow."""
    best_threshold = None
    best_score = -float('inf')

    for threshold in range(5, 16):
        result = runner.invoke(app, [
            "run",
            "--config", "base.yaml",
            "--override", f"agents[0].policy.urgency_threshold={threshold}",
            "--quiet",
        ])

        data = json.loads(result.stdout)
        score = data["metrics"]["settlement_rate"]

        if score > best_score:
            best_score = score
            best_threshold = threshold

    assert best_threshold is not None
    assert 5 <= best_threshold <= 15
```

### E2E Tests

Test actual shell invocation:

```bash
#!/bin/bash
# test_cli_e2e.sh

# Test basic run
payment-sim run --config test.yaml --output json > /tmp/result.json
jq -e '.metrics.settlement_rate' /tmp/result.json

# Test parameter override
payment-sim run \
    --config test.yaml \
    --override "simulation.rng_seed=999" \
    --quiet \
    | jq -e '.simulation.seed == 999'

# Test streaming
payment-sim run --config test.yaml --stream --ticks 10 | wc -l | grep 10

echo "✓ All E2E tests passed"
```

---

## Success Criteria

The CLI tool is complete when:

- ✅ `payment-sim run` outputs valid JSON to stdout
- ✅ Logs go to stderr (filterable with `2>/dev/null`)
- ✅ Can override config parameters from command line
- ✅ `--stream` mode outputs JSONL for long runs
- ✅ `payment-sim compare` compares policies
- ✅ `payment-sim benchmark` profiles performance
- ✅ `payment-sim validate` checks configs
- ✅ AI model can iterate on parameters via subprocess
- ✅ Shell completion works (bash, zsh)
- ✅ Comprehensive documentation in `docs/cli_usage.md`
- ✅ 20+ unit tests covering all commands
- ✅ E2E test suite demonstrating AI workflows

---

## Future Enhancements (Post-MVP)

### Interactive Mode

```bash
payment-sim run --config cfg.yaml --interactive

# Interactive prompt appears:
> Current tick: 0
> Type 'tick' to advance, 'state' to view, 'submit' to add transaction, 'quit' to exit
> tick 10
> Advancing 10 ticks...
> ...
```

### Watch Mode with Auto-Reload

```bash
payment-sim run --config cfg.yaml --watch cfg.yaml --stream
# Watches config file, re-runs on changes, streams results
```

### Distributed Execution

```bash
payment-sim compare \
    --config cfg.yaml \
    --policies fifo,deadline,liquidity \
    --replications 1000 \
    --distributed redis://localhost:6379
```

### WebSocket Streaming

```bash
payment-sim run --config cfg.yaml --ws ws://localhost:8080/stream
# Streams tick results to WebSocket for real-time dashboard
```

---

## Documentation

Will create:

1. **`docs/cli_usage.md`**: Complete CLI reference
2. **`docs/cli_ai_integration.md`**: AI integration patterns
3. **`docs/cli_tutorial.md`**: Step-by-step tutorial
4. **Man pages**: `man payment-sim`
5. **Shell completion**: Autocomplete for commands and options

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 0.5 days | Basic `run` command |
| Phase 2 | 0.5 days | Advanced `run` features |
| Phase 3 | 0.5 days | `compare` + `benchmark` |
| Phase 4 | 0.5 days | Utilities + polish |
| Phase 5 | 0.5 days | Documentation |
| **Total** | **2.5 days** | **Complete CLI tool** |

---

## Dependencies

**Python Packages** (add to `pyproject.toml`):
```toml
[project.dependencies]
# ... existing ...
typer = ">=0.9.0"           # CLI framework
rich = ">=13.0.0"           # Terminal formatting
shellingham = ">=1.5.0"     # Shell detection for completion

[project.scripts]
payment-sim = "payment_simulator.cli.main:app"
```

---

## Summary

This CLI tool transforms the Payment Simulator into an **AI-first research platform**:

- **Clean output**: JSON to stdout, logs to stderr (pipeable)
- **Parameter tuning**: Override any config value from command line
- **Batch execution**: Run hundreds of simulations in parallel
- **Streaming**: Monitor long simulations in real-time
- **Comparison**: Evaluate policies systematically
- **Validation**: Catch errors before running
- **Templates**: Quick-start with generated configs

**AI models can now**:
- Iterate on parameters without manual intervention
- Run experiments and parse results automatically
- Optimize policies through parameter sweeps
- Generate insights from batch simulations

**Implementation**: 2.5 days for full-featured CLI tool ready for AI-driven research.

---

*Last updated: 2025-10-28*
*Status: Ready for implementation*
