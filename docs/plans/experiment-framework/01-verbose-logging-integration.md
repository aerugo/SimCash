# Plan: Verbose Logging Integration

## Problem Statement

The `VerboseConfig` is passed to `GenericExperimentRunner` but never used. When users run experiments with `--verbose`, they see no verbose output because the `OptimizationLoop` doesn't log anything.

The verbose logging infrastructure exists in `experiments/runner/verbose.py` with:
- `VerboseConfig` - configuration flags (iterations, bootstrap, llm, policy, rejections)
- `VerboseLogger` - structured logging methods
- Helper dataclasses (`BootstrapSampleResult`, `LLMCallMetadata`, `RejectionDetail`)

## Goal

Wire up verbose logging so that `--verbose` produces meaningful output during experiment execution.

## TDD Approach

### Test File: `api/tests/experiments/integration/test_verbose_logging_integration.py`

Write tests FIRST, then implement to make them pass.

---

## Task 1: VerboseLogger receives events from OptimizationLoop

### Test 1.1: VerboseLogger is created when verbose enabled

```python
def test_optimization_loop_creates_verbose_logger_when_enabled():
    """OptimizationLoop creates VerboseLogger when VerboseConfig has any flag enabled."""
    config = create_test_experiment_config()
    verbose_config = VerboseConfig.all_enabled()

    loop = OptimizationLoop(
        config=config,
        config_dir=Path("."),
        verbose_config=verbose_config,
    )

    assert loop._verbose_logger is not None
    assert isinstance(loop._verbose_logger, VerboseLogger)
```

### Test 1.2: No VerboseLogger when verbose disabled

```python
def test_optimization_loop_no_logger_when_disabled():
    """OptimizationLoop does not create VerboseLogger when all flags disabled."""
    config = create_test_experiment_config()
    verbose_config = VerboseConfig()  # All disabled

    loop = OptimizationLoop(
        config=config,
        config_dir=Path("."),
        verbose_config=verbose_config,
    )

    assert loop._verbose_logger is None
```

### Implementation 1

Update `OptimizationLoop.__init__` to accept and store `verbose_config`:

```python
def __init__(
    self,
    config: ExperimentConfig,
    config_dir: Path | None = None,
    verbose_config: VerboseConfig | None = None,
) -> None:
    # ... existing code ...
    self._verbose_config = verbose_config or VerboseConfig()
    self._verbose_logger: VerboseLogger | None = None
    if self._verbose_config.any:
        self._verbose_logger = VerboseLogger(self._verbose_config)
```

---

## Task 2: Iteration start/end logging

### Test 2.1: Logs iteration start

```python
@pytest.mark.asyncio
async def test_logs_iteration_start(capsys):
    """OptimizationLoop logs iteration start when verbose_iterations enabled."""
    config = create_test_experiment_config(max_iterations=2)
    verbose_config = VerboseConfig(iterations=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )

    await loop.run()

    captured = capsys.readouterr()
    assert "Iteration 1" in captured.out
    assert "Iteration 2" in captured.out
```

### Test 2.2: Logs iteration costs

```python
@pytest.mark.asyncio
async def test_logs_iteration_costs(capsys):
    """OptimizationLoop logs costs after each iteration."""
    config = create_test_experiment_config(max_iterations=1)
    verbose_config = VerboseConfig(iterations=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )

    await loop.run()

    captured = capsys.readouterr()
    # Should show cost in dollars
    assert "$" in captured.out or "cost" in captured.out.lower()
```

### Implementation 2

Add logging calls in `OptimizationLoop.run()`:

```python
async def run(self) -> OptimizationResult:
    # ... existing setup ...

    while self._current_iteration < self.max_iterations:
        self._current_iteration += 1

        # Log iteration start
        if self._verbose_logger and self._verbose_config.iterations:
            self._verbose_logger.log_iteration_start(self._current_iteration)

        # Evaluate current policies
        total_cost, per_agent_costs = await self._evaluate_policies()

        # Log iteration results
        if self._verbose_logger and self._verbose_config.iterations:
            self._verbose_logger.log_iteration_end(
                iteration=self._current_iteration,
                total_cost=total_cost,
                per_agent_costs=per_agent_costs,
            )

        # ... rest of loop ...
```

---

## Task 3: Bootstrap sample logging

### Test 3.1: Logs bootstrap samples when enabled

```python
@pytest.mark.asyncio
async def test_logs_bootstrap_samples(capsys):
    """OptimizationLoop logs bootstrap sample results when verbose_bootstrap enabled."""
    config = create_test_experiment_config(
        evaluation_mode="bootstrap",
        num_samples=3,
        max_iterations=1,
    )
    verbose_config = VerboseConfig(bootstrap=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )

    await loop.run()

    captured = capsys.readouterr()
    assert "Sample" in captured.out or "sample" in captured.out
```

### Test 3.2: Does not log bootstrap in deterministic mode

```python
@pytest.mark.asyncio
async def test_no_bootstrap_logs_in_deterministic_mode(capsys):
    """No bootstrap logs in deterministic mode even if flag enabled."""
    config = create_test_experiment_config(
        evaluation_mode="deterministic",
        max_iterations=1,
    )
    verbose_config = VerboseConfig(bootstrap=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )

    await loop.run()

    captured = capsys.readouterr()
    # Should not mention samples in deterministic mode
    assert "Sample 1" not in captured.out
```

### Implementation 3

Add logging in `_evaluate_policies()` for bootstrap mode:

```python
async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
    # ... existing code ...

    if eval_mode == "bootstrap" and num_samples > 1:
        for sample_idx in range(num_samples):
            seed = self._derive_sample_seed(sample_idx)
            cost, agent_costs = self._run_single_simulation(seed)

            # Log sample result
            if self._verbose_logger and self._verbose_config.bootstrap:
                self._verbose_logger.log_bootstrap_sample(
                    BootstrapSampleResult(
                        sample_idx=sample_idx,
                        seed=seed,
                        total_cost=cost,
                        per_agent_costs=agent_costs,
                    )
                )

            total_costs.append(cost)
            # ... rest of loop ...
```

---

## Task 4: LLM call logging

### Test 4.1: Logs LLM calls when enabled

```python
@pytest.mark.asyncio
async def test_logs_llm_calls(capsys, mock_llm_client):
    """OptimizationLoop logs LLM interactions when verbose_llm enabled."""
    config = create_test_experiment_config_with_llm(max_iterations=1)
    verbose_config = VerboseConfig(llm=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )
    loop._llm_client = mock_llm_client  # Inject mock

    await loop.run()

    captured = capsys.readouterr()
    assert "LLM" in captured.out or "policy" in captured.out.lower()
```

### Implementation 4

Add logging in `_optimize_agent()`:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    # ... existing code ...

    try:
        new_policy = await self._llm_client.generate_policy(...)

        # Log LLM interaction
        if self._verbose_logger and self._verbose_config.llm:
            interaction = self._llm_client.get_last_interaction()
            if interaction:
                self._verbose_logger.log_llm_call(
                    LLMCallMetadata(
                        agent_id=agent_id,
                        iteration=self._current_iteration,
                        prompt_tokens=interaction.prompt_tokens,
                        completion_tokens=interaction.completion_tokens,
                        latency_seconds=interaction.latency_seconds,
                    )
                )
```

---

## Task 5: Policy acceptance/rejection logging

### Test 5.1: Logs policy rejections

```python
@pytest.mark.asyncio
async def test_logs_policy_rejections(capsys, mock_llm_client_returns_invalid):
    """OptimizationLoop logs when policy is rejected."""
    config = create_test_experiment_config_with_constraints(max_iterations=1)
    verbose_config = VerboseConfig(rejections=True)

    loop = OptimizationLoop(
        config=config,
        config_dir=get_test_config_dir(),
        verbose_config=verbose_config,
    )
    loop._llm_client = mock_llm_client_returns_invalid

    await loop.run()

    captured = capsys.readouterr()
    assert "reject" in captured.out.lower() or "invalid" in captured.out.lower()
```

### Implementation 5

Add rejection logging in `_optimize_agent()`:

```python
# After constraint validation
if not result.is_valid:
    if self._verbose_logger and self._verbose_config.rejections:
        self._verbose_logger.log_rejection(
            RejectionDetail(
                agent_id=agent_id,
                iteration=self._current_iteration,
                reason="constraint_violation",
                details=str(result.violations),
            )
        )
    return

# After paired comparison rejection
if not should_accept:
    if self._verbose_logger and self._verbose_config.rejections:
        self._verbose_logger.log_rejection(
            RejectionDetail(
                agent_id=agent_id,
                iteration=self._current_iteration,
                reason="paired_comparison",
                details=f"mean_delta={mean_delta:.2f} <= 0",
            )
        )
```

---

## Task 6: Pass verbose_config through GenericExperimentRunner

### Test 6.1: GenericExperimentRunner passes verbose_config to OptimizationLoop

```python
def test_runner_passes_verbose_config():
    """GenericExperimentRunner passes verbose_config to OptimizationLoop."""
    config = create_test_experiment_config()
    verbose_config = VerboseConfig.all_enabled()

    runner = GenericExperimentRunner(
        config=config,
        verbose_config=verbose_config,
        config_dir=Path("."),
    )

    # The runner should store verbose_config and pass it to the loop
    assert runner._verbose_config == verbose_config
```

### Implementation 6

Update `GenericExperimentRunner.run()`:

```python
async def run(self) -> ExperimentResult:
    # ... existing code ...

    loop = OptimizationLoop(
        config=self._config,
        config_dir=self._config_dir,
        verbose_config=self._verbose_config,  # Pass through
    )
```

---

## Verification Checklist

- [ ] All tests written FIRST (TDD)
- [ ] Tests fail initially (red phase)
- [ ] Implementation makes tests pass (green phase)
- [ ] Code is refactored if needed (refactor phase)
- [ ] Integration test: `payment-sim experiment run exp1.yaml --verbose` shows output
- [ ] All existing tests still pass
- [ ] No regression in experiment functionality

## Files to Modify

1. `api/payment_simulator/experiments/runner/optimization.py` - Add verbose logging
2. `api/payment_simulator/experiments/runner/experiment_runner.py` - Pass verbose_config
3. `api/tests/experiments/integration/test_verbose_logging_integration.py` - New test file

## Estimated Effort

- Tests: ~1 hour
- Implementation: ~1 hour
- Verification: ~30 minutes
