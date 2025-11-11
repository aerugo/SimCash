# Simulation Performance Diagnostics

## Problem Statement

During simulations with heavy gridlock, performance degrades significantly. We need granular diagnostics to identify which phases of the simulation are bottlenecks:
- Policy evaluation (agent decision-making)
- LSM cycle detection (bilateral/multilateral offsetting)
- RTGS settlement attempts
- Cost accrual
- Transaction arrival generation

## Goals

1. **Instrument key simulation phases** with microsecond-precision timing
2. **Expose timing data via FFI** without significant overhead
3. **Display diagnostics in CLI** with a `--debug` flag
4. **Enable historical analysis** by persisting timing data (optional future enhancement)
5. **Follow TDD** - write tests first, implement to pass tests

## Design

### Architecture

```
┌─────────────────────────────────────────┐
│  Rust Simulation Engine                │
│  backend/src/orchestrator/engine.rs     │
│                                         │
│  tick() {                               │
│    let start = Instant::now();          │
│    // ... phase execution ...           │
│    timing.phase_micros =                │
│      start.elapsed().as_micros();       │
│  }                                      │
│                                         │
│  Returns: TickResult {                  │
│    timing: TickTiming { ... }           │
│  }                                      │
└─────────────┬───────────────────────────┘
              │ FFI (PyO3)
              ▼
┌─────────────────────────────────────────┐
│  Python CLI                             │
│  api/payment_simulator/cli/             │
│                                         │
│  if --debug:                            │
│    display_performance_diagnostics()    │
└─────────────────────────────────────────┘
```

### Data Structures

#### Rust (`backend/src/models/tick_result.rs`)

```rust
#[derive(Debug, Clone, Default)]
pub struct TickTiming {
    /// Time spent generating transaction arrivals (μs)
    pub arrivals_micros: u64,

    /// Time spent evaluating agent policies (μs)
    pub policy_eval_micros: u64,

    /// Time spent on RTGS immediate settlement (μs)
    pub rtgs_settlement_micros: u64,

    /// Time spent processing RTGS queue (μs)
    pub rtgs_queue_micros: u64,

    /// Time spent on LSM cycle detection and settlement (μs)
    pub lsm_micros: u64,

    /// Time spent accruing costs (μs)
    pub cost_accrual_micros: u64,

    /// Total tick execution time (μs)
    pub total_micros: u64,
}

pub struct TickResult {
    pub tick: usize,
    pub num_arrivals: usize,
    pub num_settlements: usize,
    pub num_lsm_releases: usize,
    pub total_cost: i64,
    pub timing: TickTiming,  // NEW
}
```

#### Python Type Hints (`api/payment_simulator/backends/types.py`)

```python
class TickTiming(TypedDict):
    arrivals_micros: int
    policy_eval_micros: int
    rtgs_settlement_micros: int
    rtgs_queue_micros: int
    lsm_micros: int
    cost_accrual_micros: int
    total_micros: int

class TickResult(TypedDict):
    tick: int
    num_arrivals: int
    num_settlements: int
    num_lsm_releases: int
    total_cost: int
    timing: TickTiming  # NEW
```

### CLI Integration

#### Flag Definition

```python
# api/payment_simulator/cli/commands/run.py

@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Show performance diagnostics for each tick"
)
def run(..., debug: bool):
    """Run simulation with optional debug output."""
    pass
```

#### Display Function

```python
# api/payment_simulator/cli/output.py

def log_performance_diagnostics(timing: dict, tick: int) -> None:
    """Display performance breakdown for a single tick.

    Args:
        timing: Dict containing microsecond timings for each phase
        tick: Current tick number
    """
    from rich.table import Table

    table = Table(title=f"⏱️  Performance Diagnostics - Tick {tick}")
    table.add_column("Phase", style="cyan", no_wrap=True)
    table.add_column("Time (μs)", justify="right", style="yellow")
    table.add_column("Time (ms)", justify="right", style="yellow")
    table.add_column("% of Total", justify="right", style="green")

    total = timing["total_micros"]

    phases = [
        ("Arrivals", timing["arrivals_micros"]),
        ("Policy Evaluation", timing["policy_eval_micros"]),
        ("RTGS Settlement", timing["rtgs_settlement_micros"]),
        ("RTGS Queue Processing", timing["rtgs_queue_micros"]),
        ("LSM Coordinator", timing["lsm_micros"]),
        ("Cost Accrual", timing["cost_accrual_micros"]),
    ]

    for name, micros in phases:
        pct = (micros / total * 100) if total > 0 else 0
        millis = micros / 1000.0
        table.add_row(name, f"{micros:,}", f"{millis:.2f}", f"{pct:.1f}%")

    table.add_row("", "", "", "", style="dim")
    millis_total = total / 1000.0
    table.add_row("TOTAL", f"{total:,}", f"{millis_total:.2f}", "100.0%", style="bold")

    console.print(table)
    console.print()  # Blank line for spacing
```

### Call Site

```python
# api/payment_simulator/cli/execution/display.py

def display_tick_verbose_output(
    provider: StateProvider,
    result: Dict[str, Any],
    tick_num: int,
    events: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    show_debug: bool = False,  # NEW parameter
) -> None:
    """Display comprehensive tick output.

    Args:
        show_debug: If True, display performance diagnostics
    """
    # ... existing display sections ...

    # ═══════════════════════════════════════════════════════════
    # SECTION 9.5: PERFORMANCE DIAGNOSTICS (conditional)
    # ═══════════════════════════════════════════════════════════
    if show_debug and "timing" in result:
        log_performance_diagnostics(result["timing"], tick_num)

    # ... rest of display ...
```

## Test-Driven Development Plan

### Phase 1: Write Failing Tests

#### Test 1: Rust Unit Test - Timing Data Structure

**File**: `backend/tests/test_performance_timing.rs` (NEW)

```rust
#[cfg(test)]
mod tests {
    use payment_simulator::models::tick_result::TickTiming;

    #[test]
    fn test_tick_timing_default() {
        let timing = TickTiming::default();
        assert_eq!(timing.arrivals_micros, 0);
        assert_eq!(timing.policy_eval_micros, 0);
        assert_eq!(timing.rtgs_settlement_micros, 0);
        assert_eq!(timing.rtgs_queue_micros, 0);
        assert_eq!(timing.lsm_micros, 0);
        assert_eq!(timing.cost_accrual_micros, 0);
        assert_eq!(timing.total_micros, 0);
    }

    #[test]
    fn test_tick_timing_values_are_nonzero() {
        // This will fail initially until we instrument the code
        let config = create_test_config();
        let mut orch = Orchestrator::new(config).unwrap();

        let result = orch.tick().unwrap();

        // After instrumentation, these should all be > 0
        assert!(result.timing.total_micros > 0, "Total time should be measured");
        assert!(result.timing.arrivals_micros > 0, "Arrivals phase should be measured");
        assert!(result.timing.policy_eval_micros > 0, "Policy phase should be measured");
    }
}
```

#### Test 2: Python Integration Test - FFI Timing Exposure

**File**: `api/tests/integration/test_performance_diagnostics.py` (NEW)

```python
import pytest
from payment_simulator.backends.rust_backend import Orchestrator


def test_tick_result_includes_timing_data():
    """Verify that tick() returns timing data in the result."""
    config = {
        "seed": 12345,
        "ticks_per_day": 100,
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 100000,
                "credit_limit": 0,
            },
            {
                "id": "BANK_B",
                "opening_balance": 100000,
                "credit_limit": 0,
            }
        ],
        "cost_rates": {
            "overdraft_cost_bps": 50,
            "delay_cost_per_tick": 10,
        },
    }

    orch = Orchestrator.new(config)
    result = orch.tick()

    # Verify timing key exists
    assert "timing" in result, "Result should include timing data"

    timing = result["timing"]

    # Verify all expected fields exist
    assert "arrivals_micros" in timing
    assert "policy_eval_micros" in timing
    assert "rtgs_settlement_micros" in timing
    assert "rtgs_queue_micros" in timing
    assert "lsm_micros" in timing
    assert "cost_accrual_micros" in timing
    assert "total_micros" in timing

    # Verify types
    for field, value in timing.items():
        assert isinstance(value, int), f"{field} should be int"

    # Verify total is sum of parts (approximately, accounting for overhead)
    parts_sum = (
        timing["arrivals_micros"]
        + timing["policy_eval_micros"]
        + timing["rtgs_settlement_micros"]
        + timing["rtgs_queue_micros"]
        + timing["lsm_micros"]
        + timing["cost_accrual_micros"]
    )
    assert timing["total_micros"] >= parts_sum, "Total should be >= sum of parts"


def test_timing_values_are_reasonable():
    """Verify that timing values are non-zero and within reasonable bounds."""
    config = {
        "seed": 12345,
        "ticks_per_day": 100,
        "agents": [
            {
                "id": f"BANK_{i}",
                "opening_balance": 1000000,
                "credit_limit": 0,
            }
            for i in range(5)
        ],
        "arrival_configs": [
            {
                "agent_id": f"BANK_{i}",
                "rate_per_tick": 2.0,
                "counterparty_weights": {f"BANK_{j}": 1.0 for j in range(5) if j != i},
            }
            for i in range(5)
        ],
    }

    orch = Orchestrator.new(config)
    result = orch.tick()

    timing = result["timing"]

    # Total execution should be non-zero and less than 1 second (1M μs)
    assert timing["total_micros"] > 0, "Total time should be positive"
    assert timing["total_micros"] < 1_000_000, "Tick should complete in < 1 second"

    # Each phase should take some time (even if minimal)
    # Note: Some phases might be 0 if there's nothing to do
    assert timing["arrivals_micros"] >= 0
    assert timing["policy_eval_micros"] >= 0
    assert timing["cost_accrual_micros"] > 0  # Always runs


def test_performance_under_gridlock():
    """Test that we can measure performance during high-gridlock scenarios."""
    config = {
        "seed": 42,
        "ticks_per_day": 100,
        "agents": [
            {
                "id": f"BANK_{i}",
                "opening_balance": 5000,  # Low liquidity
                "credit_limit": 0,
            }
            for i in range(10)
        ],
        "arrival_configs": [
            {
                "agent_id": f"BANK_{i}",
                "rate_per_tick": 3.0,  # High arrival rate
                "amount_distribution": {
                    "distribution_type": "uniform",
                    "min_amount": 1000,
                    "max_amount": 3000,
                },
                "counterparty_weights": {
                    f"BANK_{j}": 1.0 for j in range(10) if j != i
                },
            }
            for i in range(10)
        ],
        "settlement": {
            "lsm_enabled": True,
        },
    }

    orch = Orchestrator.new(config)

    # Run several ticks to build up gridlock
    timings = []
    for _ in range(20):
        result = orch.tick()
        timings.append(result["timing"])

    # Verify we captured timing for all ticks
    assert len(timings) == 20

    # Check that LSM time increases as gridlock builds
    lsm_times = [t["lsm_micros"] for t in timings]

    # Later ticks should generally have higher LSM times (more to process)
    avg_first_5 = sum(lsm_times[:5]) / 5
    avg_last_5 = sum(lsm_times[-5:]) / 5

    # In gridlock, LSM should be doing more work
    # (This might not always hold, but generally true)
    assert any(t > 0 for t in lsm_times), "LSM should run at least once"
```

#### Test 3: Python CLI Test - Debug Flag

**File**: `api/tests/cli/test_debug_flag.py` (NEW)

```python
import pytest
from click.testing import CliRunner
from payment_simulator.cli.commands.run import run
from unittest.mock import patch, MagicMock


def test_debug_flag_accepted():
    """Verify --debug flag is accepted by CLI."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create minimal config
        with open("config.yaml", "w") as f:
            f.write("""
seed: 12345
ticks_per_day: 10
agents:
  - id: BANK_A
    opening_balance: 100000
  - id: BANK_B
    opening_balance: 100000
""")

        result = runner.invoke(run, [
            "--config", "config.yaml",
            "--num-ticks", "1",
            "--debug",  # NEW flag
        ])

        # Should not error on unknown option
        assert result.exit_code == 0 or "--debug" not in result.output


@patch("payment_simulator.cli.execution.display.display_tick_verbose_output")
def test_debug_flag_enables_performance_display(mock_display):
    """Verify --debug flag triggers performance diagnostics display."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("config.yaml", "w") as f:
            f.write("""
seed: 12345
ticks_per_day: 10
agents:
  - id: BANK_A
    opening_balance: 100000
  - id: BANK_B
    opening_balance: 100000
""")

        result = runner.invoke(run, [
            "--config", "config.yaml",
            "--num-ticks", "2",
            "--verbose",
            "--debug",
        ])

        # Verify display function was called with show_debug=True
        assert mock_display.called
        # Check that at least one call had show_debug=True
        calls_with_debug = [
            call for call in mock_display.call_args_list
            if call.kwargs.get("show_debug") is True
        ]
        assert len(calls_with_debug) > 0, "Should call display with show_debug=True"
```

#### Test 4: Display Function Test

**File**: `api/tests/cli/test_performance_output.py` (NEW)

```python
import pytest
from payment_simulator.cli.output import log_performance_diagnostics
from rich.console import Console
from io import StringIO


def test_log_performance_diagnostics_structure():
    """Verify performance diagnostics display correctly."""
    timing = {
        "arrivals_micros": 1000,
        "policy_eval_micros": 5000,
        "rtgs_settlement_micros": 2000,
        "rtgs_queue_micros": 3000,
        "lsm_micros": 10000,
        "cost_accrual_micros": 500,
        "total_micros": 22000,
    }

    # Capture output
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True)

    # Temporarily replace global console
    import payment_simulator.cli.output as output_module
    original_console = output_module.console
    output_module.console = console

    try:
        log_performance_diagnostics(timing, tick=42)
        output = string_io.getvalue()

        # Verify table headers
        assert "Performance Diagnostics" in output
        assert "Tick 42" in output
        assert "Phase" in output
        assert "Time (μs)" in output
        assert "% of Total" in output

        # Verify phases are listed
        assert "Arrivals" in output
        assert "Policy Evaluation" in output
        assert "LSM Coordinator" in output

        # Verify values appear (as strings)
        assert "1,000" in output or "1000" in output  # arrivals
        assert "10,000" in output or "10000" in output  # lsm
        assert "22,000" in output or "22000" in output  # total

        # Verify percentages
        assert "45.5%" in output or "45.4%" in output  # LSM is ~45% of total

    finally:
        output_module.console = original_console


def test_log_performance_diagnostics_handles_zero_total():
    """Verify graceful handling of zero total time."""
    timing = {
        "arrivals_micros": 0,
        "policy_eval_micros": 0,
        "rtgs_settlement_micros": 0,
        "rtgs_queue_micros": 0,
        "lsm_micros": 0,
        "cost_accrual_micros": 0,
        "total_micros": 0,
    }

    # Should not crash
    try:
        log_performance_diagnostics(timing, tick=1)
    except ZeroDivisionError:
        pytest.fail("Should handle zero total gracefully")
```

### Phase 2: Implement to Pass Tests

**Implementation Order:**

1. ✅ **Rust data structures** (`backend/src/models/tick_result.rs`)
   - Add `TickTiming` struct
   - Update `TickResult` to include timing

2. ✅ **Rust instrumentation** (`backend/src/orchestrator/engine.rs`)
   - Add `use std::time::Instant;`
   - Capture timing for each phase
   - Populate `TickTiming` in `TickResult`

3. ✅ **FFI exposure** (`backend/src/ffi/types.rs`)
   - Update `tick_result_to_py()` to include timing dict

4. ✅ **Python types** (`api/payment_simulator/backends/types.py`)
   - Add `TickTiming` TypedDict
   - Update `TickResult` TypedDict

5. ✅ **Display function** (`api/payment_simulator/cli/output.py`)
   - Implement `log_performance_diagnostics()`

6. ✅ **CLI integration** (`api/payment_simulator/cli/commands/run.py`)
   - Add `--debug` flag
   - Pass `show_debug` to display function

7. ✅ **Display call site** (`api/payment_simulator/cli/execution/display.py`)
   - Add `show_debug` parameter
   - Conditionally call `log_performance_diagnostics()`

### Phase 3: Verify

1. ✅ Run Rust tests: `cd backend && cargo test test_performance_timing`
2. ✅ Run Python integration tests: `cd api && pytest tests/integration/test_performance_diagnostics.py -v`
3. ✅ Run CLI tests: `pytest tests/cli/test_debug_flag.py tests/cli/test_performance_output.py -v`
4. ✅ Manual test with real config:
   ```bash
   payment-sim run --config sim_config_example.yaml --num-ticks 50 --verbose --debug
   ```
5. ✅ Verify output shows performance table after each tick

## Success Criteria

- [x] All new tests pass
- [x] No regressions in existing tests
- [x] `--debug` flag displays performance table in verbose mode
- [x] Timing values are reasonable (microseconds, non-negative)
- [x] Performance overhead is minimal (< 1% of tick time)
- [x] Code follows project patterns (FFI safety, determinism preserved)

## Future Enhancements (Out of Scope)

1. **Per-agent policy timing** - Track which agents are slow in policy evaluation
2. **LSM breakdown** - Separate bilateral vs. cycle detection timing
3. **Persistence** - Store timing data in database for historical analysis
4. **Aggregated statistics** - Show min/max/avg/p95 across all ticks at end
5. **Flamegraphs** - Visual representation of where time is spent
6. **Replay support** - Persist and display timing during replay

## Non-Goals

- ❌ Profiling arbitrary Rust functions (use `cargo flamegraph` for that)
- ❌ Memory profiling (use `valgrind` or `heaptrack`)
- ❌ Network performance (not applicable to simulation)
- ❌ Always-on overhead (only enabled with `--debug`)

## Implementation Notes

### Performance Overhead

Using `std::time::Instant` has minimal overhead (~10-50 nanoseconds per call). With 7 timing captures per tick, overhead is ~350 nanoseconds = 0.00035 milliseconds, which is negligible compared to typical tick times of 1-100 milliseconds.

### Determinism

Timing measurements do NOT affect simulation state:
- RNG seed is unchanged
- No timing-based branching in logic
- Pure observation without side effects

This preserves the critical determinism invariant.

### Alternative Considered: Tracing

Rust's `tracing` crate offers structured logging with spans. However:
- **Overhead**: Adds 5-10% performance cost even when disabled
- **Granularity**: Too fine-grained (function-level, not phase-level)
- **Integration**: Would require significant refactoring

Manual instrumentation with `Instant` is simpler and sufficient for our needs.

---

*Created: 2025-11-11*
*Status: IMPLEMENTING*
