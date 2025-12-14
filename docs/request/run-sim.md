# Feature Request: Consolidate Simulation Execution Methods

**File:** `api/payment_simulator/experiments/runner/optimization.py`

## Summary

Consolidate `_run_initial_simulation()` and `_run_simulation_with_events()` into a single `_run_simulation()` method. These methods do the same thing (run a simulation) but evolved separately, creating unnecessary code duplication and maintenance burden.

## Current State

Two methods exist that both run simulations:

| Method | Lines | Purpose |
|--------|-------|---------|
| `_run_initial_simulation()` | 876-984 | Bootstrap mode initial data collection |
| `_run_simulation_with_events()` | 1057-1160 | Policy evaluation with enriched metrics |

### The Core Execution is Identical

Both methods:
1. Build config with `_build_simulation_config()`
2. Set RNG seed
3. Create `Orchestrator.new(ffi_config)`
4. Loop `for tick in range(total_ticks): orch.tick()`
5. Capture events with `orch.get_tick_events(tick)`
6. Extract costs with `orch.get_agent_accumulated_costs(agent_id)`

### The Only Differences are Post-Processing Choices

| Aspect | `_run_initial_simulation` | `_run_simulation_with_events` |
|--------|---------------------------|-------------------------------|
| Event format | Raw `dict` | Wrapped in `BootstrapEvent` |
| Cost extraction | Just `total_cost` | Full breakdown |
| Metrics | None | `settlement_rate`, `avg_delay` |
| History | Builds `TransactionHistoryCollector` | None |
| Simulation ID | Generated and logged | None |
| Persistence | Conditional on flag | None |

**These differences are arbitrary, not fundamental.** The simulation doesn't care what consumers will do with the results.

## Proposed Design

### Single Simulation Method

```python
@dataclass(frozen=True)
class SimulationResult:
    """Complete simulation output. Callers use what they need."""
    seed: int
    simulation_id: str
    total_cost: int
    per_agent_costs: dict[str, int]
    events: tuple[dict[str, Any], ...]
    cost_breakdown: CostBreakdown
    settlement_rate: float
    avg_delay: float


def _run_simulation(
    self,
    seed: int,
    purpose: str = "eval",
) -> SimulationResult:
    """Run a single simulation.

    ONE method for ALL simulation execution. Returns complete results.
    Callers transform/filter as needed.

    Args:
        seed: RNG seed for deterministic execution.
        purpose: Short label for simulation ID (e.g., "init", "eval", "pair").

    Returns:
        SimulationResult with all captured data.
    """
    # Generate simulation ID
    sim_id = self._generate_simulation_id(purpose)

    # Log to terminal if verbose
    if self._verbose_logger:
        self._verbose_logger.log_simulation_start(
            simulation_id=sim_id,
            purpose=purpose,
            seed=seed,
        )

    # Build and run simulation
    ffi_config = self._build_simulation_config()
    ffi_config["rng_seed"] = seed

    if not self._cost_rates and "cost_rates" in ffi_config:
        self._cost_rates = ffi_config["cost_rates"]

    orch = Orchestrator.new(ffi_config)
    total_ticks = self._config.evaluation.ticks
    all_events: list[dict[str, Any]] = []

    for tick in range(total_ticks):
        orch.tick()
        try:
            tick_events = orch.get_tick_events(tick)
            all_events.extend(tick_events)
        except Exception:
            pass

    # Extract ALL costs (always)
    total_cost = 0
    per_agent_costs: dict[str, int] = {}
    delay_cost = 0
    liquidity_cost = 0
    deadline_penalty = 0
    collateral_cost = 0

    for agent_id in self.optimized_agents:
        try:
            agent_costs = orch.get_agent_accumulated_costs(agent_id)
            agent_total = int(agent_costs.get("total_cost", 0))
            per_agent_costs[agent_id] = agent_total
            total_cost += agent_total
            delay_cost += int(agent_costs.get("delay_cost", 0))
            liquidity_cost += int(agent_costs.get("liquidity_cost", 0))
            deadline_penalty += int(agent_costs.get("deadline_penalty", 0))
            collateral_cost += int(agent_costs.get("collateral_cost", 0))
        except Exception:
            per_agent_costs[agent_id] = 0

    # Extract ALL metrics (always)
    settlement_rate = 1.0
    avg_delay = 0.0
    try:
        metrics = orch.get_system_metrics()
        settled = metrics.get("total_settlements", 0)
        total = metrics.get("total_arrivals", 1)
        settlement_rate = settled / total if total > 0 else 1.0
        avg_delay = float(metrics.get("avg_delay_ticks", 0.0))
    except Exception:
        pass

    result = SimulationResult(
        seed=seed,
        simulation_id=sim_id,
        total_cost=total_cost,
        per_agent_costs=per_agent_costs,
        events=tuple(all_events),
        cost_breakdown=CostBreakdown(
            delay_cost=delay_cost,
            overdraft_cost=liquidity_cost,
            deadline_penalty=deadline_penalty,
            eod_penalty=0,
        ),
        settlement_rate=settlement_rate,
        avg_delay=avg_delay,
    )

    # Persist if flag is set
    if self._repository and self._persist_bootstrap:
        self._persist_simulation(result)

    return result
```

### Callers Transform as Needed

**For bootstrap initialization:**
```python
def _run_initial_simulation(self) -> InitialSimulationResult:
    result = self._run_simulation(self._config.master_seed, purpose="init")

    # Build transaction history from events
    collector = TransactionHistoryCollector()
    collector.process_events(list(result.events))
    agent_histories = {
        agent_id: collector.get_agent_history(agent_id)
        for agent_id in self.optimized_agents
    }

    return InitialSimulationResult(
        events=result.events,
        agent_histories=agent_histories,
        total_cost=result.total_cost,
        per_agent_costs=result.per_agent_costs,
        verbose_output=self._format_events_for_llm(list(result.events)),
    )
```

**For policy evaluation:**
```python
def _run_simulation_with_events(self, seed: int, sample_idx: int) -> EnrichedEvaluationResult:
    result = self._run_simulation(seed, purpose="eval")

    # Wrap events in typed objects
    event_trace = tuple(
        BootstrapEvent(
            tick=e.get("tick", 0),
            event_type=e.get("event_type", "unknown"),
            details=e,
        )
        for e in result.events
    )

    return EnrichedEvaluationResult(
        sample_idx=sample_idx,
        seed=seed,
        total_cost=result.total_cost,
        settlement_rate=result.settlement_rate,
        avg_delay=result.avg_delay,
        event_trace=event_trace,
        cost_breakdown=result.cost_breakdown,
    )
```

## Requirements

### 1. Simulation IDs in Terminal Output

Every simulation MUST log its ID to terminal when verbose logging is enabled:

```
  Simulation: exp1-20251214-143022-a1b2c3-sim-001-init (Initial Bootstrap)
  Simulation: exp1-20251214-143022-a1b2c3-sim-002-eval (Evaluation, iter 1)
```

This enables users to:
- Track which simulations ran
- Replay specific simulations by ID
- Debug issues in specific simulation runs

### 2. Conditional Persistence with `--persist-bootstrap`

When the `--persist-bootstrap` flag is active, ALL simulations should be persisted:

```python
if self._repository and self._persist_bootstrap:
    self._persist_simulation(result)
```

The persistence should include:
- `simulation_id`
- `purpose` (init, eval, pair, etc.)
- `seed`
- `total_cost` and `per_agent_costs`
- `events` (full event list for replay)
- `cost_breakdown`
- `metrics` (settlement_rate, avg_delay)

### 3. Single Source of Truth

After refactoring:
- ONE method runs simulations
- ONE place to update when FFI changes
- ONE place for logging/persistence logic
- Callers only transform results, never duplicate execution logic

## Benefits

| Benefit | Impact |
|---------|--------|
| ~120 lines of duplicated code removed | Easier maintenance |
| Single FFI interaction point | Fewer bugs when FFI changes |
| Consistent simulation IDs | Better observability |
| Consistent persistence | Reliable replay capability |
| Clearer architecture | Easier onboarding |

## Migration Path

1. Add `SimulationResult` dataclass
2. Implement `_run_simulation()` with full extraction
3. Refactor `_run_initial_simulation()` to call `_run_simulation()`
4. Refactor `_run_simulation_with_events()` to call `_run_simulation()`
5. Verify all tests pass
6. Remove any remaining duplication

## Related Files

- `api/payment_simulator/experiments/runner/optimization.py` - Main refactoring target
- `api/payment_simulator/experiments/runner/verbose.py` - `log_simulation_start()` method
- `api/payment_simulator/experiments/cli/commands.py` - `--persist-bootstrap` flag
- `api/tests/experiments/cli/test_experiment_id_logging.py` - Existing tests to maintain
