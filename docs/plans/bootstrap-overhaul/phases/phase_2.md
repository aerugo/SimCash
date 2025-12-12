# Phase 2: Refactor Evaluation Flow

## Goal

Refactor `OptimizationLoop` to:
1. Integrate `SeedMatrix` for deterministic per-agent seed management
2. Remove pre-iteration "baseline" evaluation
3. Move bootstrap evaluation to AFTER policy generation (per-agent)
4. Change acceptance logic to use paired delta comparison

## Current Flow (INCORRECT)

```
for iteration in range(max_iterations):
    # 1. EVALUATION FIRST (incorrect)
    total_cost, per_agent_costs = await self._evaluate_policies()
        └── Runs N bootstrap samples with current policies
        └── Returns mean cost across samples
        └── Used for LLM context (best/worst seed)

    # 2. Check convergence

    # 3. Optimize each agent
    for agent_id in optimized_agents:
        new_policy = await generate_policy(...)

        # 4. PAIRED COMPARISON (correct concept, wrong seeds)
        should_accept = await _should_accept_policy(...)
            └── Re-evaluates with SAME seeds as step 1
```

## New Flow (CORRECT)

```
# INITIALIZATION
seed_matrix = SeedMatrix(master_seed, max_iterations, agents, num_samples)

for iteration in range(max_iterations):
    # 1. Run CONTEXT simulation (for LLM verbose output)
    #    Uses first agent's iteration seed
    context_seed = seed_matrix.get_iteration_seed(iteration, agents[0])
    context_events = run_simulation_for_context(context_seed)

    # 2. Optimize each agent (with bootstrap evaluation INSIDE)
    for agent_idx, agent_id in enumerate(optimized_agents):
        # Get agent-specific iteration seed
        iteration_seed = seed_matrix.get_iteration_seed(iteration, agent_id)

        # Generate new policy based on context
        new_policy = await generate_policy(agent_id, context_events)

        # 3. BOOTSTRAP EVALUATION (AFTER policy generation)
        bootstrap_seeds = seed_matrix.get_bootstrap_seeds(iteration, agent_id)

        deltas = []
        for seed in bootstrap_seeds:
            old_cost = evaluate_policy(old_policy, seed, agent_id)
            new_cost = evaluate_policy(new_policy, seed, agent_id)
            deltas.append(old_cost - new_cost)

        # 4. Accept if total improvement is positive
        delta_sum = sum(deltas)
        if delta_sum > 0:
            accept_policy(agent_id, new_policy)

        # Track progress (delta-based)
        track_delta_progress(iteration, agent_id, delta_sum)

    # 5. Check convergence (based on delta sums, not absolute costs)
```

## TDD Tests

### Test 1: SeedMatrix Integration

```python
def test_optimization_loop_uses_seed_matrix():
    """OptimizationLoop creates SeedMatrix on initialization."""
    config = create_test_config(
        master_seed=42,
        max_iterations=10,
        agents=["A", "B"],
        num_samples=5,
    )
    loop = OptimizationLoop(config)

    assert hasattr(loop, "_seed_matrix")
    assert isinstance(loop._seed_matrix, SeedMatrix)
    assert loop._seed_matrix.master_seed == 42
    assert loop._seed_matrix.max_iterations == 10
    assert loop._seed_matrix.num_bootstrap_samples == 5
```

### Test 2: No Baseline Evaluation

```python
def test_no_baseline_evaluation_before_iteration():
    """Baseline bootstrap evaluation should NOT run before first iteration."""
    config = create_test_config()
    loop = OptimizationLoop(config)

    # Track evaluation calls
    eval_calls = []
    original_run = loop._run_single_simulation
    def tracked_run(seed):
        eval_calls.append(seed)
        return original_run(seed)
    loop._run_single_simulation = tracked_run

    # Start run but stop after iteration setup (before optimize)
    # There should be NO evaluation calls before agent optimization
    # (Context simulation is separate from bootstrap evaluation)
```

### Test 3: Per-Agent Seed Isolation

```python
def test_agents_get_different_bootstrap_seeds():
    """Each agent should get different bootstrap seeds for same iteration."""
    config = create_test_config(agents=["A", "B"])
    loop = OptimizationLoop(config)

    # Simulate getting seeds for iteration 0
    seeds_a = loop._seed_matrix.get_bootstrap_seeds(0, "A")
    seeds_b = loop._seed_matrix.get_bootstrap_seeds(0, "B")

    # Seeds should be different (agent isolation)
    assert seeds_a != seeds_b
    assert set(seeds_a).isdisjoint(set(seeds_b))
```

### Test 4: Bootstrap After Policy Generation

```python
@pytest.mark.asyncio
async def test_bootstrap_runs_after_policy_generation():
    """Bootstrap evaluation must run AFTER LLM generates new policy."""
    config = create_test_config()
    loop = OptimizationLoop(config)

    # Track order of operations
    operations = []

    # Mock policy generation
    async def mock_generate(*args):
        operations.append("policy_generated")
        return {"test": "policy"}

    # Mock bootstrap evaluation
    def mock_bootstrap(*args):
        operations.append("bootstrap_eval")
        return [0, 0, 0]  # deltas

    loop._generate_policy = mock_generate
    loop._evaluate_policy_pair = mock_bootstrap

    await loop._optimize_agent("A", current_cost=100)

    # Bootstrap must come AFTER policy generation
    assert operations == ["policy_generated", "bootstrap_eval"]
```

### Test 5: Delta Sum Acceptance

```python
def test_accept_policy_when_delta_sum_positive():
    """Policy accepted when sum of deltas is positive."""
    deltas = [10, -5, 15, -3, 8]  # Sum = 25 > 0
    delta_sum = sum(deltas)

    # Positive sum means new policy is cheaper overall
    assert delta_sum > 0
    # Should accept

def test_reject_policy_when_delta_sum_negative():
    """Policy rejected when sum of deltas is negative."""
    deltas = [-10, 5, -15, 3, -8]  # Sum = -25 < 0
    delta_sum = sum(deltas)

    # Negative sum means new policy is more expensive overall
    assert delta_sum < 0
    # Should reject
```

## Implementation Changes

### 1. Add SeedMatrix to `__init__`

```python
# In OptimizationLoop.__init__:
from payment_simulator.experiments.runner.seed_matrix import SeedMatrix

# Create seed matrix
self._seed_matrix = SeedMatrix(
    master_seed=config.master_seed,
    max_iterations=config.convergence.max_iterations,
    agents=list(config.optimized_agents),
    num_bootstrap_samples=config.evaluation.num_samples or 1,
)
```

### 2. Remove/Simplify `_evaluate_policies`

The current `_evaluate_policies` method runs bootstrap BEFORE agent optimization.
We need to:
- Keep the "context simulation" for LLM verbose output
- Move bootstrap evaluation into `_optimize_agent`

```python
async def _run_context_simulation(self, iteration: int) -> EnrichedEvaluationResult:
    """Run single simulation for LLM context building.

    Uses first agent's iteration seed for determinism.
    Does NOT run bootstrap - that happens in _optimize_agent.
    """
    first_agent = self.optimized_agents[0]
    seed = self._seed_matrix.get_iteration_seed(iteration, first_agent)
    return self._run_simulation_with_events(seed, sample_idx=0)
```

### 3. Add `_evaluate_policy_pair`

```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    iteration: int,
) -> tuple[list[int], int]:
    """Evaluate old vs new policy with paired bootstrap samples.

    Returns:
        Tuple of (deltas, delta_sum) where:
        - deltas: list of (old_cost - new_cost) per sample
        - delta_sum: sum of deltas (positive = new is cheaper)
    """
    bootstrap_seeds = self._seed_matrix.get_bootstrap_seeds(
        iteration - 1,  # 0-indexed
        agent_id,
    )

    deltas: list[int] = []

    for seed in bootstrap_seeds:
        # Temporarily set old policy
        self._policies[agent_id] = old_policy
        old_cost = self._run_single_simulation(seed)[1].get(agent_id, 0)

        # Temporarily set new policy
        self._policies[agent_id] = new_policy
        new_cost = self._run_single_simulation(seed)[1].get(agent_id, 0)

        deltas.append(old_cost - new_cost)

    return deltas, sum(deltas)
```

### 4. Update `_optimize_agent`

Move bootstrap into the optimization flow:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    # ... existing policy generation code ...

    new_policy = await self._generate_policy(...)

    if new_policy is None:
        return  # Validation failed

    # BOOTSTRAP EVALUATION (after policy generation)
    old_policy = self._policies.get(agent_id, self._create_default_policy(agent_id))
    deltas, delta_sum = self._evaluate_policy_pair(
        agent_id=agent_id,
        old_policy=old_policy,
        new_policy=new_policy,
        iteration=self._current_iteration,
    )

    # Accept if delta_sum > 0 (new policy is cheaper)
    if delta_sum > 0:
        self._policies[agent_id] = new_policy
        self._accepted_changes[agent_id] = True
        # Log acceptance
    else:
        # Log rejection with delta details
```

### 5. Update Progress Tracking

Track delta sums instead of absolute costs:

```python
@dataclass
class IterationDelta:
    """Per-agent delta from iteration."""
    iteration: int
    agent_id: str
    deltas: list[int]  # Per-sample deltas
    delta_sum: int      # Sum (positive = improvement)
    accepted: bool

# In OptimizationLoop:
self._delta_history: list[IterationDelta] = []

# After evaluation:
self._delta_history.append(IterationDelta(
    iteration=self._current_iteration,
    agent_id=agent_id,
    deltas=deltas,
    delta_sum=delta_sum,
    accepted=delta_sum > 0,
))
```

## Files to Modify

| File | Changes |
|------|---------|
| `optimization.py` | Major refactor: add SeedMatrix, change evaluation flow |
| `verbose.py` | Update output to show deltas |
| `test_optimization_flow.py` | New integration tests |

## Acceptance Criteria

- [ ] SeedMatrix integrated into OptimizationLoop
- [ ] No "Bootstrap Baseline" before first iteration
- [ ] Each agent gets isolated seed stream
- [ ] Bootstrap runs AFTER policy generation
- [ ] Acceptance based on delta_sum > 0
- [ ] Delta history tracked for progress
- [ ] All existing tests pass
- [ ] New tests cover the correct flow

## Risk Assessment

**High Risk Changes:**
1. `_evaluate_policies` is heavily used - refactoring may break things
2. Verbose output format will change - may affect existing tools

**Mitigation:**
1. Keep old method signatures but change internals
2. Update verbose output incrementally
3. Run full test suite after each change
