# Phase 2: Implement `_run_simulation()` Method

**Goal**: Create a single unified simulation execution method following TDD principles.

## Background

Both `_run_initial_simulation()` and `_run_simulation_with_events()` share the same core logic:
1. Build config with `_build_simulation_config()`
2. Set RNG seed
3. Create `Orchestrator.new(ffi_config)`
4. Loop `for tick in range(total_ticks): orch.tick()`
5. Capture events with `orch.get_tick_events(tick)`
6. Extract costs with `orch.get_agent_accumulated_costs(agent_id)`

The new `_run_simulation()` method will consolidate this into ONE place.

## Method Signature

```python
def _run_simulation(
    self,
    seed: int,
    purpose: str,
    *,
    iteration: int | None = None,
    sample_idx: int | None = None,
    persist: bool | None = None,
) -> SimulationResult:
```

## Requirements

### From Feature Request

1. Generate simulation ID and log to terminal
2. Capture ALL events from simulation
3. Extract complete cost breakdown (delay, overdraft, deadline, eod)
4. Calculate settlement rate and avg delay
5. Persist to database when `--persist-bootstrap` flag is set
6. Return `SimulationResult` with all data

### Invariants

- **INV-1**: All costs as integer cents
- **INV-2**: Determinism - same seed = same output
- **INV-3**: Replay identity - events must be complete for replay
- **INV-5**: Strict typing

## TDD Approach

### Step 1: Write Tests First

Create integration tests in `api/tests/experiments/runner/test_run_simulation.py`:

```python
"""Integration tests for _run_simulation() method."""

class TestRunSimulation:
    """Tests for the unified _run_simulation() method."""

    def test_run_simulation_returns_simulation_result(self) -> None:
        """_run_simulation() returns SimulationResult."""

    def test_run_simulation_generates_unique_id(self) -> None:
        """Each call generates a unique simulation ID."""

    def test_run_simulation_captures_all_events(self) -> None:
        """Events are captured for all ticks."""

    def test_run_simulation_extracts_cost_breakdown(self) -> None:
        """Cost breakdown includes delay, overdraft, deadline, eod."""

    def test_run_simulation_calculates_settlement_rate(self) -> None:
        """Settlement rate is calculated correctly."""

    def test_run_simulation_deterministic_with_same_seed(self) -> None:
        """Same seed produces identical results (INV-2)."""

    def test_run_simulation_logs_id_when_verbose(self) -> None:
        """Simulation ID is logged to terminal when verbose."""

    def test_run_simulation_persists_when_flag_set(self) -> None:
        """Events are persisted to database when persist_bootstrap=True."""
```

### Step 2: Implement Method

Add `_run_simulation()` to `OptimizationLoop` class in `optimization.py`:

```python
def _run_simulation(
    self,
    seed: int,
    purpose: str,
    *,
    iteration: int | None = None,
    sample_idx: int | None = None,
    persist: bool | None = None,
) -> SimulationResult:
    """Run a single simulation and capture all output.

    This is the ONE method that runs simulations. All callers use this
    and transform the result as needed.

    Args:
        seed: RNG seed for this simulation.
        purpose: Purpose tag for simulation ID (e.g., "init", "eval", "bootstrap").
        iteration: Current iteration number (for logging/persistence).
        sample_idx: Bootstrap sample index (for logging/persistence).
        persist: Override persist_bootstrap flag. If None, uses class default.

    Returns:
        SimulationResult with all simulation output.
    """
    # 1. Generate simulation ID
    sim_id = self._generate_simulation_id(purpose)

    # 2. Log to terminal if verbose
    if self._verbose_logger:
        self._verbose_logger.log_simulation_start(
            simulation_id=sim_id,
            purpose=purpose,
            iteration=iteration,
            seed=seed,
        )

    # 3. Build config and run simulation
    ffi_config = self._build_simulation_config()
    ffi_config["rng_seed"] = seed

    # Extract cost rates for LLM context (only once)
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

    # 4. Extract costs and metrics
    total_cost = 0
    per_agent_costs: dict[str, int] = {}
    delay_cost = 0
    liquidity_cost = 0
    deadline_penalty = 0

    for agent_id in self.optimized_agents:
        try:
            agent_costs = orch.get_agent_accumulated_costs(agent_id)
            cost = int(agent_costs.get("total_cost", 0))
            per_agent_costs[agent_id] = cost
            total_cost += cost
            delay_cost += int(agent_costs.get("delay_cost", 0))
            liquidity_cost += int(agent_costs.get("liquidity_cost", 0))
            deadline_penalty += int(agent_costs.get("deadline_penalty", 0))
        except Exception:
            per_agent_costs[agent_id] = 0

    # 5. Calculate settlement rate and avg delay
    try:
        metrics = orch.get_system_metrics()
        settled = metrics.get("total_settlements", 0)
        total = metrics.get("total_arrivals", 1)
        settlement_rate = settled / total if total > 0 else 1.0
        avg_delay = float(metrics.get("avg_delay_ticks", 0.0))
    except Exception:
        settlement_rate = 1.0
        avg_delay = 0.0

    # 6. Persist if flag set
    should_persist = persist if persist is not None else self._persist_bootstrap
    if self._repository and should_persist:
        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id=self._run_id,
            iteration=iteration or 0,
            event_type="simulation_run",
            event_data={
                "simulation_id": sim_id,
                "purpose": purpose,
                "seed": seed,
                "ticks": total_ticks,
                "total_cost": total_cost,
                "per_agent_costs": per_agent_costs,
                "num_events": len(all_events),
                "events": all_events,
            },
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_event(event)

    # 7. Return SimulationResult
    return SimulationResult(
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
```

## Success Criteria

- [ ] Tests written before implementation (TDD)
- [ ] All tests pass
- [ ] mypy reports no errors
- [ ] ruff reports no errors
- [ ] Method generates unique simulation IDs
- [ ] Method logs to terminal when verbose enabled
- [ ] Method persists when flag set
- [ ] Method returns complete SimulationResult
- [ ] Determinism verified (same seed = same output)

## Files to Create/Modify

| File | Action |
|------|--------|
| `api/tests/experiments/runner/test_run_simulation.py` | Create (tests first) |
| `api/payment_simulator/experiments/runner/optimization.py` | Add `_run_simulation()` method |

## Notes

- The new method consolidates ~80% identical code from two existing methods
- Callers will transform `SimulationResult` to their specific needs in Phases 3-4
- The `persist` parameter allows overriding the default persistence behavior
- The `purpose` parameter is used for simulation ID tagging (e.g., "init", "eval", "bootstrap")
