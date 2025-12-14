# Phase 3: Refactor `_run_initial_simulation()` to Use `_run_simulation()`

**Goal**: Refactor `_run_initial_simulation()` to use the new unified `_run_simulation()` method.

## Background

The `_run_initial_simulation()` method runs the initial simulation for bootstrap mode. It:
1. Generates simulation ID and logs to terminal
2. Runs simulation and captures all events
3. Builds TransactionHistoryCollector for bootstrap sampling
4. Persists to database if `--persist-bootstrap` flag is set
5. Returns `InitialSimulationResult`

Most of this is now handled by `_run_simulation()`. We just need to:
1. Call `_run_simulation()` to get the base result
2. Transform `SimulationResult` to `InitialSimulationResult`
3. Build TransactionHistoryCollector from events

## Current Implementation (Lines 1013-1121)

```python
def _run_initial_simulation(self) -> InitialSimulationResult:
    # 1. Generate simulation ID
    sim_id = self._generate_simulation_id("init")

    # 2. Log to terminal if verbose
    if self._verbose_logger:
        self._verbose_logger.log_simulation_start(...)

    # 3. Build config and run simulation
    ffi_config = self._build_simulation_config()
    ffi_config["rng_seed"] = self._config.master_seed
    orch = Orchestrator.new(ffi_config)

    # 4. Capture events
    for tick in range(total_ticks):
        orch.tick()
        tick_events = orch.get_tick_events(tick)
        all_events.extend(tick_events)

    # 5. Build TransactionHistoryCollector
    collector = TransactionHistoryCollector()
    collector.process_events(all_events)
    agent_histories = {...}

    # 6. Extract costs
    for agent_id in self.optimized_agents:
        agent_costs = orch.get_agent_accumulated_costs(agent_id)
        ...

    # 7. Persist if flag set
    if self._repository and self._persist_bootstrap:
        ...

    # 8. Return InitialSimulationResult
    return InitialSimulationResult(...)
```

## New Implementation

```python
def _run_initial_simulation(self) -> InitialSimulationResult:
    # Run simulation using unified method
    result = self._run_simulation(
        seed=self._config.master_seed,
        purpose="init",
        iteration=0,
        persist=self._persist_bootstrap,
    )

    # Build transaction history from events
    collector = TransactionHistoryCollector()
    collector.process_events(list(result.events))

    agent_histories = {
        agent_id: collector.get_agent_history(agent_id)
        for agent_id in self.optimized_agents
    }

    # Format events for LLM context
    verbose_output = self._format_events_for_llm(list(result.events))

    return InitialSimulationResult(
        events=result.events,
        agent_histories=agent_histories,
        total_cost=result.total_cost,
        per_agent_costs=result.per_agent_costs,
        verbose_output=verbose_output,
    )
```

## TDD Approach

### Step 1: Verify Existing Tests Pass Before Refactoring

Run all existing tests to establish baseline:
```bash
cd api
uv run python -m pytest tests/ -k "initial_simulation" -v
```

### Step 2: Identify Tests That Cover _run_initial_simulation

Check for tests that use `_run_initial_simulation()` or `InitialSimulationResult`.

### Step 3: Refactor and Verify

1. Replace the method body with the new implementation
2. Run the same tests to verify no regression
3. Run full test suite

## Success Criteria

- [ ] All existing tests pass
- [ ] No behavior change for callers
- [ ] Code duplication removed (~50 lines)
- [ ] mypy/ruff pass
- [ ] `_run_initial_simulation()` uses `_run_simulation()` internally

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/experiments/runner/optimization.py` | Refactor `_run_initial_simulation()` |

## Notes

- The `_run_simulation()` method already handles:
  - Simulation ID generation
  - Verbose logging
  - Event capture
  - Cost extraction
  - Persistence
- We just need to add the TransactionHistoryCollector logic on top
