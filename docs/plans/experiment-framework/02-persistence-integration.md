# Plan: Persistence Integration

## Problem Statement

The `ExperimentRepository` exists in `experiments/persistence/repository.py` with full DuckDB support, but the `GenericExperimentRunner` and `OptimizationLoop` don't use it. Experiment results are lost when the process exits.

The persistence infrastructure includes:
- `ExperimentRepository` - DuckDB-backed storage
- `ExperimentRecord` - experiment metadata
- `IterationRecord` - per-iteration data
- `EventRecord` - individual events

The experiment YAML config has output settings:
```yaml
output:
  directory: results
  database: exp1.db
  verbose: true
```

But these are ignored.

## Goal

Wire up persistence so experiments save results to DuckDB, enabling:
1. Result analysis after completion
2. Experiment replay/audit
3. Historical comparison

## TDD Approach

### Test File: `api/tests/experiments/integration/test_persistence_integration.py`

Write tests FIRST, then implement to make them pass.

---

## Task 1: Repository created from config

### Test 1.1: Repository created when output configured

```python
def test_runner_creates_repository_when_output_configured(tmp_path):
    """GenericExperimentRunner creates ExperimentRepository when output.database set."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=Path("."),
    )

    assert runner._repository is not None
    assert isinstance(runner._repository, ExperimentRepository)
```

### Test 1.2: No repository when output not configured

```python
def test_runner_no_repository_when_output_not_configured():
    """GenericExperimentRunner has no repository when output not configured."""
    config = create_test_experiment_config(
        output_directory=None,
        output_database=None,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=Path("."),
    )

    assert runner._repository is None
```

### Test 1.3: Database file created in output directory

```python
def test_database_created_in_output_directory(tmp_path):
    """Database file is created in the configured output directory."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="experiments.db",
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=Path("."),
    )

    db_path = tmp_path / "experiments.db"
    assert db_path.exists()
```

### Implementation 1

Update `GenericExperimentRunner.__init__`:

```python
def __init__(
    self,
    config: ExperimentConfig,
    verbose_config: VerboseConfig | None = None,
    run_id: str | None = None,
    config_dir: Path | None = None,
) -> None:
    # ... existing code ...

    # Initialize repository if output configured
    self._repository: ExperimentRepository | None = None
    if config.output and config.output.database:
        output_dir = Path(config.output.directory or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        db_path = output_dir / config.output.database
        self._repository = ExperimentRepository(db_path)
```

---

## Task 2: Experiment record saved at start

### Test 2.1: Experiment record saved when run starts

```python
@pytest.mark.asyncio
async def test_experiment_record_saved_at_start(tmp_path):
    """ExperimentRecord is saved when experiment run starts."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=1,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await runner.run()

    # Verify record exists in database
    experiments = runner._repository.list_experiments()
    assert len(experiments) == 1
    assert experiments[0].experiment_name == config.name
```

### Test 2.2: Experiment record has correct metadata

```python
@pytest.mark.asyncio
async def test_experiment_record_has_metadata(tmp_path):
    """ExperimentRecord contains correct metadata."""
    config = create_test_experiment_config(
        name="test_exp",
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=1,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await runner.run()

    experiments = runner._repository.list_experiments()
    record = experiments[0]

    assert record.experiment_name == "test_exp"
    assert record.experiment_type == "generic"
    assert record.config is not None
    assert "master_seed" in str(record.config)
```

### Implementation 2

Add experiment record creation in `GenericExperimentRunner.run()`:

```python
async def run(self) -> ExperimentResult:
    import time
    from payment_simulator.experiments.persistence import ExperimentRecord

    start_time = time.time()

    # Save experiment record at start
    if self._repository:
        experiment_record = ExperimentRecord(
            experiment_id=self._run_id,
            experiment_name=self._config.name,
            experiment_type="generic",
            config=self._config.to_dict(),
            started_at=datetime.now().isoformat(),
        )
        self._repository.save_experiment(experiment_record)

    # ... rest of run method ...
```

---

## Task 3: Iteration records saved

### Test 3.1: Iteration records saved during run

```python
@pytest.mark.asyncio
async def test_iteration_records_saved(tmp_path):
    """IterationRecords are saved for each iteration."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=3,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await runner.run()

    # Query iterations from database
    iterations = runner._repository.get_iterations(runner._run_id)
    assert len(iterations) >= 1  # At least 1 iteration ran
```

### Test 3.2: Iteration records have correct cost data

```python
@pytest.mark.asyncio
async def test_iteration_records_have_costs(tmp_path):
    """IterationRecords contain cost data in integer cents."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=1,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await runner.run()

    iterations = runner._repository.get_iterations(runner._run_id)
    assert len(iterations) == 1

    iteration = iterations[0]
    assert isinstance(iteration.total_cost, int)  # INV-1: integer cents
    assert iteration.iteration_number == 1
```

### Implementation 3

Pass repository to OptimizationLoop and save iterations:

```python
# In OptimizationLoop.run():
while self._current_iteration < self.max_iterations:
    self._current_iteration += 1

    total_cost, per_agent_costs = await self._evaluate_policies()

    # Save iteration record
    if self._repository:
        from payment_simulator.experiments.persistence import IterationRecord

        iteration_record = IterationRecord(
            experiment_id=self._experiment_id,
            iteration_number=self._current_iteration,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            policies=self._policies.copy(),
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_iteration(iteration_record)

    # ... rest of loop ...
```

---

## Task 4: Final result saved

### Test 4.1: Experiment marked complete

```python
@pytest.mark.asyncio
async def test_experiment_marked_complete(tmp_path):
    """Experiment record is updated when run completes."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=2,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    await runner.run()

    experiments = runner._repository.list_experiments()
    record = experiments[0]

    assert record.completed_at is not None
    assert record.converged is not None
```

### Test 4.2: Final costs saved

```python
@pytest.mark.asyncio
async def test_final_costs_saved(tmp_path):
    """Final costs are saved in experiment record."""
    config = create_test_experiment_config(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=2,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )

    result = await runner.run()

    experiments = runner._repository.list_experiments()
    record = experiments[0]

    assert record.final_cost == result.final_costs
```

### Implementation 4

Update experiment record at completion:

```python
async def run(self) -> ExperimentResult:
    # ... existing code ...

    # Run optimization
    opt_result = await loop.run()

    duration = time.time() - start_time

    # Update experiment record with completion info
    if self._repository:
        self._repository.update_experiment_completion(
            experiment_id=self._run_id,
            completed_at=datetime.now().isoformat(),
            converged=opt_result.converged,
            convergence_reason=opt_result.convergence_reason,
            final_cost=opt_result.final_cost,
            total_duration_seconds=duration,
        )

    return ExperimentResult(...)
```

---

## Task 5: Events saved for audit

### Test 5.1: LLM interaction events saved

```python
@pytest.mark.asyncio
async def test_llm_events_saved(tmp_path, mock_llm_client):
    """LLM interaction events are saved for audit."""
    config = create_test_experiment_config_with_llm(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=1,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )
    # Inject mock LLM
    runner._llm_client = mock_llm_client

    await runner.run()

    events = runner._repository.get_events(runner._run_id)
    llm_events = [e for e in events if e.event_type == "llm_interaction"]
    assert len(llm_events) > 0
```

### Test 5.2: Policy acceptance events saved

```python
@pytest.mark.asyncio
async def test_policy_events_saved(tmp_path, mock_llm_client):
    """Policy acceptance/rejection events are saved."""
    config = create_test_experiment_config_with_llm(
        output_directory=str(tmp_path),
        output_database="test.db",
        max_iterations=2,
    )

    runner = GenericExperimentRunner(
        config=config,
        config_dir=get_test_config_dir(),
    )
    runner._llm_client = mock_llm_client

    await runner.run()

    events = runner._repository.get_events(runner._run_id)
    policy_events = [e for e in events if "policy" in e.event_type]
    assert len(policy_events) > 0
```

### Implementation 5

Save events in OptimizationLoop:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    # ... existing code ...

    try:
        new_policy = await self._llm_client.generate_policy(...)

        # Save LLM event
        if self._repository:
            from payment_simulator.experiments.persistence import EventRecord

            interaction = self._llm_client.get_last_interaction()
            event = EventRecord(
                experiment_id=self._experiment_id,
                iteration=self._current_iteration,
                event_type="llm_interaction",
                event_data={
                    "agent_id": agent_id,
                    "prompt_tokens": interaction.prompt_tokens,
                    "completion_tokens": interaction.completion_tokens,
                    "latency_seconds": interaction.latency_seconds,
                },
                timestamp=datetime.now().isoformat(),
            )
            self._repository.save_event(event)
```

---

## Task 6: Results command reads from database

### Test 6.1: Results command lists experiments

```python
def test_results_command_lists_experiments(tmp_path, run_experiment_fixture):
    """payment-sim experiment results lists experiments from database."""
    # Run an experiment first
    db_path = tmp_path / "test.db"
    run_experiment_fixture(db_path)

    # Use CLI to list results
    result = runner.invoke(app, ["experiment", "results", str(db_path)])

    assert result.exit_code == 0
    assert "test_exp" in result.output
```

### Implementation 6

This may already exist in the CLI. Verify and add if missing.

---

## Verification Checklist

- [ ] All tests written FIRST (TDD)
- [ ] Tests fail initially (red phase)
- [ ] Implementation makes tests pass (green phase)
- [ ] Integration test: Run experiment, verify database created
- [ ] Integration test: Results command shows saved experiments
- [ ] All costs stored as integer cents (INV-1)
- [ ] All existing tests still pass

## Files to Modify

1. `api/payment_simulator/experiments/runner/experiment_runner.py` - Add repository creation
2. `api/payment_simulator/experiments/runner/optimization.py` - Add iteration/event saving
3. `api/payment_simulator/experiments/persistence/repository.py` - May need `update_experiment_completion()`
4. `api/tests/experiments/integration/test_persistence_integration.py` - New test file

## Dependencies

- `ExperimentRepository` already exists and is tested
- `ExperimentRecord`, `IterationRecord`, `EventRecord` dataclasses exist

## Estimated Effort

- Tests: ~1.5 hours
- Implementation: ~1.5 hours
- Verification: ~30 minutes
