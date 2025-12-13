# Phase 7: Experiment Runner Integration

**Status**: In Progress
**Started**: 2025-12-13
**Parent Plan**: `../development-plan.md`

## Objective

Wire the existing bootstrap infrastructure into `OptimizationLoop` to replace parametric Monte Carlo with real bootstrap evaluation.

## Current vs Target Architecture

### Current (Wrong - Parametric Monte Carlo)

```
For each iteration:
  For each bootstrap sample (i = 0..N):
    seed[i] = hash(master_seed, i)
    Run COMPLETE NEW SIMULATION with seed[i]  ← Creates new transactions!
    Collect cost[i]
  mean_cost = mean(cost[])
```

**Problem**: Each "sample" generates NEW random transactions from parametric distributions.
This is Monte Carlo, not bootstrap.

### Target (Correct - Bootstrap Resampling)

```
ONCE at start:
  Run initial simulation with master_seed
  Collect ALL historical transactions via TransactionHistoryCollector
  Capture verbose output for LLM context (Stream 1)

For each iteration:
  Create bootstrap samples via BootstrapSampler.generate_samples()
    (resamples FROM historical data with replacement)

  For each bootstrap sample:
    Build sandbox config via SandboxConfigBuilder
    Run sandbox with FIXED transactions (no stochastic arrivals)
    Collect cost

  Build 3-stream LLM context:
    Stream 1: Initial simulation output (captured once)
    Stream 2: Best bootstrap sample events
    Stream 3: Worst bootstrap sample events
```

## Key Changes to OptimizationLoop

### 1. Add Initial Simulation Step

**New method**: `_run_initial_simulation()`

```python
def _run_initial_simulation(self) -> InitialSimulationResult:
    """Run ONE initial simulation to collect historical transactions.

    This is called ONCE at the start of optimization, not every iteration.
    The historical data becomes the basis for bootstrap sampling.

    Returns:
        InitialSimulationResult with:
        - historical_transactions per agent
        - verbose output (for LLM context Stream 1)
        - initial cost
        - all events
    """
    # Build config with initial (default) policies
    ffi_config = self._build_simulation_config()
    ffi_config["rng_seed"] = self._config.master_seed

    orch = Orchestrator.new(ffi_config)

    # Run full simulation
    total_ticks = self._config.evaluation.ticks
    all_events: list[dict[str, Any]] = []

    for tick in range(total_ticks):
        orch.tick()
        tick_events = orch.get_tick_events(tick)
        all_events.extend(tick_events)

    # Collect historical transactions
    from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
        TransactionHistoryCollector,
    )

    collector = TransactionHistoryCollector()
    collector.process_events(all_events)

    # Get history per agent
    agent_histories = {
        agent_id: collector.get_agent_history(agent_id)
        for agent_id in self.optimized_agents
    }

    # Extract costs
    total_cost = 0
    per_agent_costs = {}
    for agent_id in self.optimized_agents:
        agent_costs = orch.get_agent_accumulated_costs(agent_id)
        cost = int(agent_costs.get("total_cost", 0))
        per_agent_costs[agent_id] = cost
        total_cost += cost

    return InitialSimulationResult(
        events=all_events,
        agent_histories=agent_histories,
        total_cost=total_cost,
        per_agent_costs=per_agent_costs,
    )
```

### 2. Update `run()` Method

```python
async def run(self) -> OptimizationResult:
    # ... existing setup code ...

    # NEW: Run initial simulation ONCE to collect historical data
    if self._config.evaluation.mode == "bootstrap":
        self._initial_sim = self._run_initial_simulation()

        # Create bootstrap samples from historical data
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        self._sampler = BootstrapSampler(seed=self._config.master_seed)
        self._bootstrap_samples = {}  # agent_id -> list[BootstrapSample]

        for agent_id in self.optimized_agents:
            history = self._initial_sim.agent_histories[agent_id]
            self._bootstrap_samples[agent_id] = self._sampler.generate_samples(
                agent_id=agent_id,
                n_samples=self._config.evaluation.num_samples,
                outgoing_records=history.outgoing,
                incoming_records=history.incoming,
                total_ticks=self._config.evaluation.ticks,
            )

    # ... existing optimization loop ...
```

### 3. Update `_evaluate_policies()` for Bootstrap Mode

```python
async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
    """Evaluate current policies using bootstrap samples (NOT new simulations)."""

    if self._config.evaluation.mode != "bootstrap" or not hasattr(self, '_bootstrap_samples'):
        # Fall back to current behavior for deterministic mode
        return await self._evaluate_policies_deterministic()

    # Bootstrap mode: evaluate on pre-computed samples
    from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator

    total_costs: list[int] = []
    per_agent_costs: dict[str, int] = {}
    enriched_results: list[EnrichedEvaluationResult] = []

    for agent_id in self.optimized_agents:
        samples = self._bootstrap_samples[agent_id]
        policy = self._policies.get(agent_id, self._create_default_policy(agent_id))

        # Use BootstrapPolicyEvaluator
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=self._get_agent_opening_balance(agent_id),
            credit_limit=self._get_agent_credit_limit(agent_id),
            cost_rates=self._cost_rates,
        )

        results = evaluator.evaluate_samples(samples, policy)

        # Convert to EnrichedEvaluationResult for LLM context
        for result in results:
            enriched_results.append(self._convert_to_enriched(result, samples[result.sample_idx]))

        # Compute mean cost for this agent
        agent_mean_cost = int(sum(r.total_cost for r in results) / len(results))
        per_agent_costs[agent_id] = agent_mean_cost
        total_costs.append(agent_mean_cost)

    mean_total = sum(total_costs)

    # Store enriched results for LLM context
    self._current_enriched_results = enriched_results
    self._current_agent_contexts = self._build_agent_contexts_with_initial_sim(enriched_results)

    return mean_total, per_agent_costs
```

### 4. Update `_should_accept_policy()` for Paired Bootstrap Comparison

```python
async def _should_accept_policy(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    current_cost: int,
) -> tuple[bool, int, int, list[int], int]:
    """Use BootstrapPolicyEvaluator.compute_paired_deltas()."""

    if self._config.evaluation.mode != "bootstrap" or not hasattr(self, '_bootstrap_samples'):
        # Fall back to current behavior
        return await self._should_accept_policy_deterministic(...)

    from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator

    samples = self._bootstrap_samples[agent_id]

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=self._get_agent_opening_balance(agent_id),
        credit_limit=self._get_agent_credit_limit(agent_id),
        cost_rates=self._cost_rates,
    )

    # Use paired comparison (same samples, different policies)
    deltas = evaluator.compute_paired_deltas(
        samples=samples,
        policy_a=old_policy,
        policy_b=new_policy,
    )

    # Extract costs and compute acceptance
    old_costs = [d.cost_a for d in deltas]
    new_costs = [d.cost_b for d in deltas]
    delta_values = [d.delta for d in deltas]
    delta_sum = sum(delta_values)

    old_cost = int(sum(old_costs) / len(old_costs))
    new_cost = int(sum(new_costs) / len(new_costs))

    # Accept if delta_sum > 0 (new policy is cheaper)
    should_accept = delta_sum > 0

    return (should_accept, old_cost, new_cost, delta_values, delta_sum)
```

### 5. Add Initial Simulation to LLM Context (Stream 1)

**Update `AgentSimulationContext` or create new context type**:

```python
@dataclass
class BootstrapLLMContext:
    """Complete LLM context with 3 event streams."""

    # Stream 1: Initial simulation (captured ONCE at start)
    initial_simulation_output: str
    initial_simulation_cost: int

    # Stream 2: Best bootstrap sample
    best_seed: int
    best_seed_cost: int
    best_seed_output: str | None

    # Stream 3: Worst bootstrap sample
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str | None

    # Statistics
    mean_cost: int
    cost_std: int
    num_samples: int


def _build_agent_contexts_with_initial_sim(
    self,
    enriched_results: list[EnrichedEvaluationResult],
) -> dict[str, BootstrapLLMContext]:
    """Build LLM context including initial simulation output."""

    contexts: dict[str, BootstrapLLMContext] = {}

    for agent_id in self.optimized_agents:
        # Get initial simulation output for Stream 1
        initial_output = self._format_initial_simulation_events(agent_id)
        initial_cost = self._initial_sim.per_agent_costs.get(agent_id, 0)

        # Use EnrichedBootstrapContextBuilder for Streams 2 & 3
        builder = EnrichedBootstrapContextBuilder(
            results=enriched_results,
            agent_id=agent_id,
        )
        agent_context = builder.build_agent_context()

        contexts[agent_id] = BootstrapLLMContext(
            # Stream 1: Initial simulation
            initial_simulation_output=initial_output,
            initial_simulation_cost=initial_cost,

            # Stream 2: Best sample
            best_seed=agent_context.best_seed,
            best_seed_cost=agent_context.best_seed_cost,
            best_seed_output=agent_context.best_seed_output,

            # Stream 3: Worst sample
            worst_seed=agent_context.worst_seed,
            worst_seed_cost=agent_context.worst_seed_cost,
            worst_seed_output=agent_context.worst_seed_output,

            # Statistics
            mean_cost=agent_context.mean_cost,
            cost_std=agent_context.cost_std,
            num_samples=len(enriched_results),
        )

    return contexts
```

## TDD Test Plan

### Test File: `api/tests/integration/test_bootstrap_integration.py`

#### Test 1: Initial Simulation Runs Once

```python
class TestBootstrapIntegration:
    """Integration tests for bootstrap evaluation in OptimizationLoop."""

    def test_initial_simulation_runs_once(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """Initial simulation should run exactly once, not per iteration."""
        loop = OptimizationLoop(config=bootstrap_experiment_config)

        # Track simulation runs
        original_run = loop._run_single_simulation
        run_count = 0

        def counting_run(*args, **kwargs):
            nonlocal run_count
            run_count += 1
            return original_run(*args, **kwargs)

        loop._run_single_simulation = counting_run

        # Run optimization
        await loop.run()

        # Should have exactly 1 initial simulation + N bootstrap evaluations
        # (not N new simulations per iteration like Monte Carlo)
        expected_initial = 1
        expected_bootstrap = num_samples * num_iterations * 2  # old + new per agent

        # Initial simulation is separate from sandbox evaluations
        assert run_count == expected_initial + expected_bootstrap
```

#### Test 2: Bootstrap Samples Come From Historical Data

```python
    def test_bootstrap_samples_from_historical_data(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """Bootstrap samples should resample from initial simulation, not generate new."""
        loop = OptimizationLoop(config=bootstrap_experiment_config)

        # Run initial simulation
        initial_result = loop._run_initial_simulation()

        # Get historical transactions
        agent_id = list(loop.optimized_agents)[0]
        history = initial_result.agent_histories[agent_id]
        original_tx_ids = {tx.tx_id for tx in history.outgoing}

        # Create bootstrap samples
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler
        sampler = BootstrapSampler(seed=loop.master_seed)
        samples = sampler.generate_samples(
            agent_id=agent_id,
            n_samples=10,
            outgoing_records=history.outgoing,
            incoming_records=history.incoming,
            total_ticks=100,
        )

        # Verify bootstrap samples only contain transactions from history
        for sample in samples:
            for tx in sample.outgoing_txns:
                # tx_id format is "original_tx_id:out:idx"
                original_id = tx.tx_id.split(":")[0]
                assert original_id in original_tx_ids, \
                    f"Bootstrap transaction {tx.tx_id} not from historical data"
```

#### Test 3: LLM Receives 3 Event Streams

```python
    def test_llm_receives_three_streams(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """LLM context should include initial sim + best + worst samples."""
        loop = OptimizationLoop(config=bootstrap_experiment_config)

        # Run one iteration to get context
        await loop.run()

        for agent_id in loop.optimized_agents:
            context = loop._current_agent_contexts.get(agent_id)
            assert context is not None

            # Stream 1: Initial simulation
            assert hasattr(context, 'initial_simulation_output')
            assert context.initial_simulation_output is not None
            assert context.initial_simulation_cost > 0

            # Stream 2: Best sample
            assert context.best_seed_output is not None
            assert context.best_seed_cost >= 0

            # Stream 3: Worst sample
            assert context.worst_seed_output is not None
            assert context.worst_seed_cost >= context.best_seed_cost
```

#### Test 4: Paired Comparison Uses Same Samples

```python
    def test_paired_comparison_uses_same_samples(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """Old and new policies must be evaluated on identical samples."""
        loop = OptimizationLoop(config=bootstrap_experiment_config)

        # Setup
        await loop._initialize_for_bootstrap()
        agent_id = list(loop.optimized_agents)[0]

        old_policy = {"type": "Fifo"}
        new_policy = {"type": "LiquidityAware", "target_buffer": 50000}

        # Track which samples are used for each evaluation
        evaluated_samples_old: list[int] = []
        evaluated_samples_new: list[int] = []

        # Mock evaluator to track samples
        # ... (mock setup)

        # Run paired comparison
        should_accept, _, _, deltas, _ = await loop._should_accept_policy(
            agent_id=agent_id,
            old_policy=old_policy,
            new_policy=new_policy,
            current_cost=10000,
        )

        # Verify same samples used
        assert evaluated_samples_old == evaluated_samples_new
```

#### Test 5: Determinism Preserved

```python
    def test_same_seed_produces_identical_results(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """Same master_seed should produce identical bootstrap evaluation."""
        config = bootstrap_experiment_config

        # Run 1
        loop1 = OptimizationLoop(config=config)
        result1 = await loop1.run()

        # Run 2 (same config)
        loop2 = OptimizationLoop(config=config)
        result2 = await loop2.run()

        # Should be identical
        assert result1.iteration_history == result2.iteration_history
        assert result1.final_cost == result2.final_cost
        assert result1.final_policies == result2.final_policies
```

#### Test 6: Money is Integer Cents Throughout

```python
    def test_costs_are_integer_cents(
        self, bootstrap_experiment_config: ExperimentConfig
    ) -> None:
        """All cost values must be integers (INV-1)."""
        loop = OptimizationLoop(config=bootstrap_experiment_config)

        # Run initial simulation
        initial_result = loop._run_initial_simulation()

        # Check initial simulation costs
        assert isinstance(initial_result.total_cost, int)
        for agent_id, cost in initial_result.per_agent_costs.items():
            assert isinstance(cost, int)

        # Run evaluation
        total_cost, per_agent_costs = await loop._evaluate_policies()

        assert isinstance(total_cost, int)
        for cost in per_agent_costs.values():
            assert isinstance(cost, int)
```

## Implementation Steps

### Step 1: Write Tests First (RED)

1. Create `api/tests/integration/test_bootstrap_integration.py`
2. Write all tests from TDD plan above
3. Run tests - they should FAIL

```bash
cd api
.venv/bin/python -m pytest tests/integration/test_bootstrap_integration.py -v
```

### Step 2: Add Helper Data Structures

Create `api/payment_simulator/experiments/runner/bootstrap_support.py`:

```python
@dataclass(frozen=True)
class InitialSimulationResult:
    """Result from the initial simulation used for bootstrap."""
    events: list[dict[str, Any]]
    agent_histories: dict[str, AgentTransactionHistory]
    total_cost: int
    per_agent_costs: dict[str, int]
```

### Step 3: Update OptimizationLoop

1. Add `_run_initial_simulation()` method
2. Update `run()` to call initial simulation once
3. Update `_evaluate_policies()` for bootstrap mode
4. Update `_should_accept_policy()` for paired comparison
5. Update LLM context building for 3 streams

### Step 4: Run Tests (GREEN)

```bash
cd api
.venv/bin/python -m pytest tests/integration/test_bootstrap_integration.py -v
```

### Step 5: Type Check and Lint (REFACTOR)

```bash
cd api
.venv/bin/python -m mypy payment_simulator/experiments/runner/optimization.py
.venv/bin/python -m ruff check payment_simulator/experiments/runner/
.venv/bin/python -m ruff format payment_simulator/experiments/runner/
```

## Acceptance Criteria

- [ ] Initial simulation runs exactly ONCE at start
- [ ] Bootstrap samples are created from historical data
- [ ] Evaluation uses `BootstrapPolicyEvaluator` not new simulations
- [ ] Paired comparison uses `compute_paired_deltas()` on same samples
- [ ] LLM context includes all 3 streams (initial, best, worst)
- [ ] All costs are integers (INV-1)
- [ ] Same seed produces identical results (INV-2)
- [ ] All tests pass
- [ ] mypy passes with no errors
- [ ] ruff passes with no errors

## Backwards Compatibility

**Critical**: Deterministic mode (num_samples=1) should continue to work as before.

The changes should be gated by `evaluation.mode == "bootstrap"`:
- Deterministic mode: Current behavior (single simulation)
- Bootstrap mode: New behavior (initial sim + bootstrap sampling)

## Definition of Done

Phase 7 is complete when:
1. All acceptance criteria are met
2. Integration tests pass
3. Deterministic mode still works
4. Code is committed to feature branch
5. Work notes updated with completion status

---

*Created: 2025-12-13*
*Last updated: 2025-12-13*
