# Plan: LiveStateProvider Integration

## Problem Statement

The `LiveStateProvider` exists in `experiments/runner/state_provider.py` with full event recording capabilities, but the `OptimizationLoop` doesn't use it. This means:

1. No events are captured during live execution
2. Verbose display functions can't show rich event data
3. Replay from database won't match live run (no events stored)

The LiveStateProvider infrastructure includes:
- `LiveStateProvider` - records iteration data and events during execution
- `DatabaseStateProvider` - reads from database for replay
- `ExperimentStateProviderProtocol` - common interface
- `display_experiment_output()` - unified display using StateProvider

The StateProvider pattern is designed for **replay identity**: run and replay should produce identical output.

## Goal

Wire up LiveStateProvider so experiments capture events during execution, enabling:
1. Rich verbose output during runs
2. Event persistence for replay
3. Identical output between run and replay

## TDD Approach

### Test File: `api/tests/experiments/integration/test_state_provider_integration.py`

Write tests FIRST, then implement to make them pass.

---

## Task 1: LiveStateProvider created for each run

### Test 1.1: OptimizationLoop creates LiveStateProvider

```python
def test_optimization_loop_creates_state_provider():
    """OptimizationLoop creates LiveStateProvider for event capture."""
    config = create_test_experiment_config()

    loop = OptimizationLoop(
        config=config,
        config_dir=Path("."),
    )

    assert loop._state_provider is not None
    assert isinstance(loop._state_provider, LiveStateProvider)
```

### Test 1.2: LiveStateProvider has correct metadata

```python
def test_state_provider_has_experiment_metadata():
    """LiveStateProvider is initialized with experiment metadata."""
    config = create_test_experiment_config(name="test_exp")

    loop = OptimizationLoop(
        config=config,
        config_dir=Path("."),
    )

    info = loop._state_provider.get_experiment_info()
    assert info["experiment_name"] == "test_exp"
    assert info["experiment_type"] == "generic"
    assert info["run_id"] is not None
```

### Implementation 1

Update `OptimizationLoop.__init__`:

```python
def __init__(
    self,
    config: ExperimentConfig,
    config_dir: Path | None = None,
    verbose_config: VerboseConfig | None = None,
    run_id: str | None = None,
) -> None:
    # ... existing code ...

    # Initialize state provider for event capture
    from payment_simulator.experiments.runner.state_provider import LiveStateProvider

    self._state_provider = LiveStateProvider(
        experiment_name=config.name,
        experiment_type="generic",
        config=config.to_dict(),
        run_id=self._run_id,
    )
```

---

## Task 2: Iteration events recorded

### Test 2.1: Iteration start events recorded

```python
@pytest.mark.asyncio
async def test_iteration_start_events_recorded():
    """OptimizationLoop records iteration_start events."""
    config = create_test_experiment_config(max_iterations=2)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    # Check events were recorded
    events = list(loop._state_provider.get_all_events())
    iteration_starts = [e for e in events if e["event_type"] == "iteration_start"]

    assert len(iteration_starts) >= 1
    assert "iteration" in iteration_starts[0]
    assert "total_cost" in iteration_starts[0]
```

### Test 2.2: Iteration costs recorded

```python
@pytest.mark.asyncio
async def test_iteration_costs_recorded():
    """OptimizationLoop records per-agent costs for each iteration."""
    config = create_test_experiment_config(max_iterations=2)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    costs = loop._state_provider.get_iteration_costs(0)
    assert len(costs) > 0  # At least one agent
    assert all(isinstance(v, int) for v in costs.values())  # INV-1: integer cents
```

### Implementation 2

Add event recording in `OptimizationLoop.run()`:

```python
async def run(self) -> OptimizationResult:
    # Record experiment start
    self._state_provider.record_event(
        iteration=0,
        event_type="experiment_start",
        event_data={
            "experiment_name": self._config.name,
            "max_iterations": self.max_iterations,
            "num_samples": self._config.evaluation.num_samples,
            "model": self._config.llm.model,
        },
    )

    while self._current_iteration < self.max_iterations:
        self._current_iteration += 1

        total_cost, per_agent_costs = await self._evaluate_policies()

        # Record iteration start event
        self._state_provider.record_event(
            iteration=self._current_iteration,
            event_type="iteration_start",
            event_data={
                "iteration": self._current_iteration,
                "total_cost": total_cost,
            },
        )

        # Record iteration data
        self._state_provider.record_iteration(
            iteration=self._current_iteration - 1,  # 0-indexed
            costs_per_agent=per_agent_costs,
            accepted_changes={},  # Updated after optimization
            policies=self._policies.copy(),
        )

        # ... rest of loop ...
```

---

## Task 3: Bootstrap evaluation events

### Test 3.1: Bootstrap events recorded in bootstrap mode

```python
@pytest.mark.asyncio
async def test_bootstrap_events_recorded():
    """OptimizationLoop records bootstrap_evaluation events in bootstrap mode."""
    config = create_test_experiment_config(
        evaluation_mode="bootstrap",
        num_samples=3,
        max_iterations=1,
    )

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    events = list(loop._state_provider.get_all_events())
    bootstrap_events = [e for e in events if e["event_type"] == "bootstrap_evaluation"]

    assert len(bootstrap_events) >= 1
    assert "seed_results" in bootstrap_events[0]
    assert "mean_cost" in bootstrap_events[0]
```

### Test 3.2: Bootstrap event has correct structure

```python
@pytest.mark.asyncio
async def test_bootstrap_event_structure():
    """Bootstrap events contain all required fields for display."""
    config = create_test_experiment_config(
        evaluation_mode="bootstrap",
        num_samples=3,
        max_iterations=1,
    )

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    events = list(loop._state_provider.get_all_events())
    bootstrap_events = [e for e in events if e["event_type"] == "bootstrap_evaluation"]

    event = bootstrap_events[0]
    assert "seed_results" in event
    assert len(event["seed_results"]) == 3  # num_samples
    assert "seed" in event["seed_results"][0]
    assert "cost" in event["seed_results"][0]
```

### Implementation 3

Add bootstrap event recording in `_evaluate_policies()`:

```python
async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
    eval_mode = self._config.evaluation.mode
    num_samples = self._config.evaluation.num_samples or 1

    if eval_mode == "deterministic" or num_samples <= 1:
        seed = self._config.master_seed + self._current_iteration
        return self._run_single_simulation(seed)

    # Bootstrap mode: run multiple simulations
    seed_results: list[dict[str, Any]] = []
    total_costs: list[int] = []

    for sample_idx in range(num_samples):
        seed = self._derive_sample_seed(sample_idx)
        cost, agent_costs = self._run_single_simulation(seed)
        total_costs.append(cost)

        seed_results.append({
            "seed": seed,
            "cost": cost,
            "settled": self._last_settled_count,  # Track in simulation
            "total": self._last_total_count,
            "settlement_rate": self._last_settlement_rate,
        })

    mean_cost = int(sum(total_costs) / len(total_costs))
    std_cost = int((sum((c - mean_cost) ** 2 for c in total_costs) / len(total_costs)) ** 0.5)

    # Record bootstrap evaluation event
    self._state_provider.record_event(
        iteration=self._current_iteration,
        event_type="bootstrap_evaluation",
        event_data={
            "seed_results": seed_results,
            "mean_cost": mean_cost,
            "std_cost": std_cost,
        },
    )

    return mean_cost, self._aggregate_agent_costs()
```

---

## Task 4: Policy change events

### Test 4.1: Policy change events recorded

```python
@pytest.mark.asyncio
async def test_policy_change_events_recorded(mock_llm_client):
    """OptimizationLoop records policy_change events when policies are updated."""
    config = create_test_experiment_config_with_llm(max_iterations=2)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )
    loop._llm_client = mock_llm_client

    await loop.run()

    events = list(loop._state_provider.get_all_events())
    policy_events = [e for e in events if e["event_type"] == "policy_change"]

    # Should have at least one policy event if LLM was called
    assert len(policy_events) > 0
    assert "agent_id" in policy_events[0]
    assert "old_cost" in policy_events[0]
    assert "new_cost" in policy_events[0]
    assert "accepted" in policy_events[0]
```

### Test 4.2: Policy rejection events recorded

```python
@pytest.mark.asyncio
async def test_policy_rejected_events_recorded(mock_llm_returns_invalid):
    """OptimizationLoop records policy_rejected events for invalid policies."""
    config = create_test_experiment_config_with_constraints(max_iterations=1)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )
    loop._llm_client = mock_llm_returns_invalid

    await loop.run()

    events = list(loop._state_provider.get_all_events())
    rejected_events = [e for e in events if e["event_type"] == "policy_rejected"]

    assert len(rejected_events) > 0
    assert "agent_id" in rejected_events[0]
    assert "rejection_reason" in rejected_events[0]
```

### Implementation 4

Add policy event recording in `_optimize_agent()`:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    old_policy = self._policies.get(agent_id, {})

    try:
        new_policy = await self._llm_client.generate_policy(...)

        # Validate policy
        validation_result = self._validate_policy(new_policy)
        if not validation_result.is_valid:
            # Record rejection event
            self._state_provider.record_event(
                iteration=self._current_iteration,
                event_type="policy_rejected",
                event_data={
                    "agent_id": agent_id,
                    "rejection_reason": "constraint_violation",
                    "validation_errors": validation_result.errors,
                },
            )
            return

        # Evaluate new policy
        accepted = await self._should_accept_policy(agent_id, old_policy, new_policy)
        new_cost = self._last_evaluated_cost  # Track during evaluation

        # Record policy change event
        self._state_provider.record_event(
            iteration=self._current_iteration,
            event_type="policy_change",
            event_data={
                "agent_id": agent_id,
                "old_policy": old_policy,
                "new_policy": new_policy,
                "old_cost": current_cost,
                "new_cost": new_cost,
                "accepted": accepted,
            },
        )

        if accepted:
            self._policies[agent_id] = new_policy

    except Exception as e:
        self._state_provider.record_event(
            iteration=self._current_iteration,
            event_type="policy_rejected",
            event_data={
                "agent_id": agent_id,
                "rejection_reason": "llm_error",
                "validation_errors": [str(e)],
            },
        )
```

---

## Task 5: Final result recorded

### Test 5.1: Experiment end event recorded

```python
@pytest.mark.asyncio
async def test_experiment_end_event_recorded():
    """OptimizationLoop records experiment_end event on completion."""
    config = create_test_experiment_config(max_iterations=2)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    events = list(loop._state_provider.get_all_events())
    end_events = [e for e in events if e["event_type"] == "experiment_end"]

    assert len(end_events) == 1
    assert "final_cost" in end_events[0]
    assert "converged" in end_events[0]
```

### Test 5.2: Final result accessible from provider

```python
@pytest.mark.asyncio
async def test_final_result_accessible():
    """LiveStateProvider.get_final_result() returns correct data."""
    config = create_test_experiment_config(max_iterations=2)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await loop.run()

    result = loop._state_provider.get_final_result()
    assert result is not None
    assert "final_cost" in result
    assert "best_cost" in result
    assert "converged" in result
    assert isinstance(result["final_cost"], int)  # INV-1
```

### Implementation 5

Add experiment end recording:

```python
async def run(self) -> OptimizationResult:
    # ... run loop ...

    # Record experiment end
    self._state_provider.record_event(
        iteration=self._current_iteration,
        event_type="experiment_end",
        event_data={
            "final_cost": total_cost,
            "best_cost": self._best_cost,
            "converged": converged,
            "convergence_reason": convergence_reason,
            "num_iterations": self._current_iteration,
        },
    )

    # Set final result in provider
    self._state_provider.set_final_result(
        final_cost=total_cost,
        best_cost=self._best_cost,
        converged=converged,
        convergence_reason=convergence_reason,
    )

    return OptimizationResult(...)
```

---

## Task 6: StateProvider exposed for display

### Test 6.1: GenericExperimentRunner exposes provider

```python
def test_runner_exposes_state_provider():
    """GenericExperimentRunner exposes state_provider property."""
    config = create_test_experiment_config()

    runner = GenericExperimentRunner(
        config=config,
        config_dir=Path("."),
    )

    assert hasattr(runner, "state_provider")
    # Provider should exist after run
```

### Test 6.2: Display function works with live provider

```python
@pytest.mark.asyncio
async def test_display_with_live_provider(capsys):
    """display_experiment_output() works with LiveStateProvider."""
    config = create_test_experiment_config(max_iterations=1)
    verbose_config = VerboseConfig.all_enabled()

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )

    await loop.run()

    # Display using provider
    from payment_simulator.experiments.runner.display import display_experiment_output
    from rich.console import Console

    console = Console(file=StringIO())
    display_experiment_output(loop._state_provider, console, verbose_config)

    output = console.file.getvalue()
    assert config.name in output
    assert "Iteration" in output
```

### Implementation 6

Add property to GenericExperimentRunner:

```python
@property
def state_provider(self) -> ExperimentStateProviderProtocol | None:
    """Get the state provider from the optimization loop."""
    if hasattr(self, "_loop") and self._loop is not None:
        return self._loop._state_provider
    return None
```

---

## Task 7: Replay identity verification

### Test 7.1: Run and replay produce identical output

```python
@pytest.mark.asyncio
async def test_run_replay_identity(tmp_path):
    """Run output matches replay output when using StateProvider pattern."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=2,
    )
    verbose_config = VerboseConfig.all_enabled()

    # Run experiment
    runner = GenericExperimentRunner(
        config=config,
        verbose_config=verbose_config,
        config_dir=get_test_config_dir(),
    )
    await runner.run()

    # Capture run output
    run_console = Console(file=StringIO())
    display_experiment_output(runner.state_provider, run_console, verbose_config)
    run_output = run_console.file.getvalue()

    # Replay from database
    db_path = tmp_path / "test.db"
    repo = ExperimentRepository(db_path)
    db_provider = repo.as_state_provider(runner._run_id)

    replay_console = Console(file=StringIO())
    display_experiment_output(db_provider, replay_console, verbose_config)
    replay_output = replay_console.file.getvalue()

    # Compare (excluding timing info)
    run_lines = [l for l in run_output.split('\n') if 'Duration' not in l]
    replay_lines = [l for l in replay_output.split('\n') if 'Duration' not in l]

    assert run_lines == replay_lines
```

### Implementation 7

This test validates the integration. It should pass once Tasks 1-6 and persistence integration are complete.

---

## Verification Checklist

- [ ] All tests written FIRST (TDD)
- [ ] Tests fail initially (red phase)
- [ ] Implementation makes tests pass (green phase)
- [ ] LiveStateProvider captures all event types
- [ ] Events have all required fields for display
- [ ] Run output matches replay output (replay identity)
- [ ] All existing tests still pass
- [ ] All costs stored as integer cents (INV-1)

## Files to Modify

1. `api/payment_simulator/experiments/runner/optimization.py` - Add event recording
2. `api/payment_simulator/experiments/runner/experiment_runner.py` - Expose state_provider
3. `api/tests/experiments/integration/test_state_provider_integration.py` - New test file

## Dependencies

- `LiveStateProvider` already exists and is tested
- `display_experiment_output()` exists in `experiments/runner/display.py`
- Persistence integration (Plan 02) for replay identity test

## Event Types Reference

For display functions to work, these event types must be recorded:

| Event Type | Required Fields | Display Function |
|------------|-----------------|------------------|
| experiment_start | experiment_name, max_iterations, model | display_experiment_start() |
| iteration_start | iteration, total_cost | display_iteration_start() |
| bootstrap_evaluation | seed_results, mean_cost, std_cost | display_bootstrap_evaluation() |
| llm_call | agent_id, model, prompt_tokens, completion_tokens, latency_seconds | display_llm_call() |
| policy_change | agent_id, old_policy, new_policy, old_cost, new_cost, accepted | display_policy_change() |
| policy_rejected | agent_id, rejection_reason, validation_errors | display_policy_rejected() |
| experiment_end | final_cost, converged, convergence_reason | display_experiment_end() |

