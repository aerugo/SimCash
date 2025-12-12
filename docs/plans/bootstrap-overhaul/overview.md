# Bootstrap Evaluation Overhaul - Overview

## Problem Statement

The current bootstrap evaluation implementation is incorrect. Based on output analysis:

```
Bootstrap Baseline (10 samples):  ← Runs BEFORE any iteration
[...]
Iteration 1
Total cost: $79.36
LLM Call for BANK_A:  ← Policy generation
[...]
Bootstrap Evaluation (10 samples):  ← Runs AFTER iteration
```

### Current (Incorrect) Behavior

1. Bootstrap Baseline runs **before** any iteration
2. Seeds are derived on-the-fly using `SHA256(f"{master_seed}:sample:{sample_idx}")`
3. All agents share the same sample seeds
4. Evaluation happens before policy generation
5. Progress tracked via absolute costs, not deltas

### Expected (Correct) Behavior

1. **Pre-generate iteration seeds** in N×A matrix (N=iterations, A=agents)
2. **No baseline evaluation** - bootstrap happens per-agent, per-iteration
3. **Per-agent seed streams** derived from iteration seeds
4. **Dual evaluation** - each sample runs twice (old policy, new policy)
5. **Delta-based acceptance** - track improvement deltas, not absolute costs
6. **Bootstrap AFTER policy generation** - compare old vs new policy

## Correct Algorithm

### Initialization

```python
# Before starting simulation:
# Generate N*A iteration seeds from master_seed
# Store in matrix iteration_seeds[N][A]

iteration_seeds: list[list[int]] = []  # [iteration][agent_idx]
for i in range(max_iterations):
    agent_seeds = []
    for a in range(num_agents):
        seed = derive_seed(master_seed, iteration=i, agent_idx=a)
        agent_seeds.append(seed)
    iteration_seeds.append(agent_seeds)
```

### Iteration Loop

```python
for iteration in range(max_iterations):
    # 1. Run simulation with iteration seed for context
    #    This provides verbose output for LLM consumption
    context_seed = iteration_seeds[iteration][0]  # Use first agent's seed for context
    run_simulation_for_context(context_seed)

    # 2. Generate new policies per agent
    for agent_idx, agent_id in enumerate(optimized_agents):
        # Get iteration seed for this agent
        iteration_seed = iteration_seeds[iteration][agent_idx]

        # Generate S bootstrap seeds from iteration seed
        bootstrap_seeds = [
            derive_bootstrap_seed(iteration_seed, sample_idx)
            for sample_idx in range(num_samples)
        ]

        # Get LLM to generate new policy based on context
        new_policy = await generate_policy(agent_id, context)

        # 3. Run bootstrap evaluation (AFTER policy generation)
        old_costs = []
        new_costs = []

        for seed in bootstrap_seeds:
            # Run each sample TWICE
            old_cost = evaluate_policy(old_policy, seed, agent_id)
            new_cost = evaluate_policy(new_policy, seed, agent_id)

            old_costs.append(old_cost)
            new_costs.append(new_cost)

        # 4. Calculate deltas (old - new: positive = new is cheaper)
        deltas = [old - new for old, new in zip(old_costs, new_costs)]
        delta_sum = sum(deltas)

        # 5. Accept if delta_sum > 0 (new policy is cheaper overall)
        if delta_sum > 0:
            accept_policy(agent_id, new_policy)

        # 6. Track delta_sum as progress metric
        track_progress(iteration, agent_id, delta_sum)
```

## Key Changes Required

### 1. Seed Management

**Current**: SHA256-based derivation on-the-fly
```python
def _derive_sample_seed(self, sample_idx: int) -> int:
    key = f"{self._config.master_seed}:sample:{sample_idx}"
    return hash_to_seed(key)
```

**New**: Pre-generated matrix with iteration×agent structure
```python
class SeedMatrix:
    """Pre-generated iteration seeds for reproducibility."""

    def __init__(self, master_seed: int, max_iterations: int, agents: list[str]):
        self._seeds: list[dict[str, int]] = []  # [iteration][agent_id]
        for i in range(max_iterations):
            agent_seeds = {}
            for agent_id in agents:
                seed = self._derive(master_seed, i, agent_id)
                agent_seeds[agent_id] = seed
            self._seeds.append(agent_seeds)

    def get_iteration_seed(self, iteration: int, agent_id: str) -> int:
        return self._seeds[iteration][agent_id]

    def get_bootstrap_seed(self, iteration: int, agent_id: str, sample_idx: int) -> int:
        base = self.get_iteration_seed(iteration, agent_id)
        return self._derive(base, sample_idx, f"{agent_id}:bootstrap")
```

### 2. Evaluation Flow

**Current**: Bootstrap before each iteration
```python
async def _evaluate_policies(self):
    # Runs at start of each iteration
    # Returns mean cost across samples
```

**New**: Bootstrap after policy generation, per-agent
```python
async def _evaluate_policy_pair(self, agent_id, old_policy, new_policy, iteration):
    """Evaluate old vs new policy with paired bootstrap samples."""
    seeds = self._seed_matrix.get_bootstrap_seeds(iteration, agent_id, self._num_samples)

    deltas = []
    for seed in seeds:
        old_cost = self._run_single_simulation(old_policy, seed)[agent_id]
        new_cost = self._run_single_simulation(new_policy, seed)[agent_id]
        deltas.append(old_cost - new_cost)

    return deltas  # Positive = new is cheaper
```

### 3. Acceptance Logic

**Current**: Accept if mean(new_costs) < mean(old_costs)
```python
mean_delta = sum(deltas) / len(deltas)
return mean_delta > 0  # Accept if positive
```

**New**: Accept if sum(deltas) > 0 (paired comparison)
```python
delta_sum = sum(deltas)
return delta_sum > 0  # Accept if total improvement is positive
```

### 4. Progress Tracking

**Current**: Absolute costs
```python
self._iteration_history.append(total_cost)
```

**New**: Delta sums per iteration
```python
@dataclass
class IterationDeltas:
    iteration: int
    agent_deltas: dict[str, int]  # agent_id -> delta_sum
    total_delta: int

self._delta_history.append(IterationDeltas(...))
```

## Phase Breakdown

### Phase 1: Seed Matrix Implementation
- Create `SeedMatrix` class with deterministic seed derivation
- Unit tests for seed reproducibility
- Integration tests for matrix generation

### Phase 2: Refactor Evaluation Flow
- Remove pre-iteration baseline evaluation
- Implement per-agent paired evaluation
- Ensure agent-isolated seed streams

### Phase 3: Delta-Based Acceptance
- Change acceptance logic to delta-sum based
- Update progress tracking to use deltas
- Modify verbose output to show deltas

### Phase 4: Integration & Testing
- End-to-end tests with known outcomes
- Replay identity verification
- Performance benchmarks

## Invariants to Maintain

1. **INV-1 (Integer Cents)**: All costs remain i64 integer cents
2. **INV-2 (Determinism)**: Same master_seed produces identical results
3. **INV-3 (Replay Identity)**: Run and replay produce identical output
4. **INV-4 (Per-Agent Isolation)**: Each agent's evaluation is independent

## Files to Modify

### Core Changes
- `api/payment_simulator/experiments/runner/optimization.py` - Main loop changes
- `api/payment_simulator/ai_cash_mgmt/bootstrap/sampler.py` - Seed matrix
- `api/payment_simulator/experiments/runner/verbose.py` - Output format changes

### Test Files
- `api/tests/unit/test_seed_matrix.py` - New unit tests
- `api/tests/integration/test_bootstrap_evaluation.py` - Integration tests
- `api/tests/integration/test_replay_identity.py` - Ensure no regression

## Success Criteria

1. Bootstrap evaluation runs AFTER policy generation (not before)
2. Each agent has independent seed stream per iteration
3. Delta sums are tracked and displayed correctly
4. Determinism preserved (same seed = same results)
5. All existing tests pass
6. New tests cover the correct algorithm

## Timeline

- Phase 1: Seed Matrix - 1 session
- Phase 2: Evaluation Flow - 1-2 sessions
- Phase 3: Delta Acceptance - 1 session
- Phase 4: Integration - 1 session

Total: ~4-5 sessions with TDD approach

## References

- Current implementation: `api/payment_simulator/experiments/runner/optimization.py:810-935`
- Experiment config: `api/payment_simulator/experiments/config/experiment_config.py`
- Verbose output: `api/payment_simulator/experiments/runner/verbose.py`
