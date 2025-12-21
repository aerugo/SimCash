# Bootstrap Seed Fix - Development Plan

**Status**: Complete
**Created**: 2025-12-21
**Branch**: `claude/investigate-bootstrap-seeds-UhOXb`

## Summary

Fix the bootstrap evaluation mode to use iteration-specific seeds for context simulations and bootstrap sample generation, matching the original hierarchical seed design in `SeedMatrix`.

## Critical Invariants to Respect

- **INV-2**: Determinism is Sacred - All seeds derived deterministically from master_seed via SeedMatrix. Same master_seed + same config = identical outputs across runs.
- **INV-9**: Policy Evaluation Identity - Bootstrap samples must be evaluated consistently whether comparing old vs new policy.
- **INV-10**: Scenario Config Interpretation Identity - Agent configuration extraction must be consistent.

### NEW Invariant to Introduce

- **NEW INV-13**: Bootstrap Seed Hierarchy - Bootstrap mode MUST use iteration-specific seeds for both context simulations and bootstrap sample generation. The SeedMatrix hierarchy (master → iteration → bootstrap) must be respected.

---

## Desired Design (Confirmed)

### Seed Hierarchy

```
master_seed (42)
├── iteration_seed[0] = hash(42, iter=0, agent=A)
│   ├── context_simulation runs with this seed → produces transaction_history[0]
│   └── bootstrap_samples[0] = 50 samples from history[0], seeded by iteration_seed[0]
│       ├── sample[0] seed = hash(iteration_seed[0], sample=0)
│       ├── sample[1] seed = hash(iteration_seed[0], sample=1)
│       └── ... (50 total)
│
├── iteration_seed[1] = hash(42, iter=1, agent=A)
│   ├── context_simulation runs with this seed → produces transaction_history[1]
│   └── bootstrap_samples[1] = 50 samples from history[1], seeded by iteration_seed[1]
│
└── ... (50 iterations total)
```

### Per-Iteration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Iteration N                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. GET ITERATION SEED                                              │
│     iteration_seed = SeedMatrix.get_iteration_seed(N, agent_id)     │
│                                                                     │
│  2. RUN CONTEXT SIMULATION                                          │
│     Run full simulation with iteration_seed                         │
│     → Produces unique transaction_history for this iteration        │
│     → Different iterations see different stochastic arrivals        │
│                                                                     │
│  3. GENERATE BOOTSTRAP SAMPLES                                      │
│     BootstrapSampler(seed=iteration_seed)                           │
│     → Creates 50 samples from this iteration's history              │
│     → Each sample has unique seed: hash(iteration_seed, sample_idx) │
│                                                                     │
│  4. PAIRED POLICY COMPARISON (unchanged logic)                      │
│     ┌─────────────────────────────────────────────────────────┐     │
│     │  For each of 50 samples:                                │     │
│     │    • Evaluate OLD policy → old_cost[i]                  │     │
│     │    • Evaluate NEW policy → new_cost[i]  (SAME sample!)  │     │
│     │    • delta[i] = old_cost[i] - new_cost[i]               │     │
│     │                                                         │     │
│     │  Accept new policy if mean(delta) > 0                   │     │
│     └─────────────────────────────────────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Seed Counts

| Component | Count | Notes |
|-----------|-------|-------|
| Iteration seeds | 50 | One per iteration |
| Context simulations | 50 | One per iteration, each with unique seed |
| Bootstrap sample seeds | 2,500 | 50 iterations × 50 samples |
| Policy evaluations | 5,000 | Each sample evaluated twice (old + new policy) |

**Key Point**: The 5,000 evaluations use only 2,500 unique sample seeds. Each sample is evaluated twice (once per policy) to enable paired comparison.

---

## Current State Analysis

### Problem

Bootstrap mode currently:
1. Runs ONE initial simulation with `master_seed` (line 1468)
2. Creates bootstrap samples ONCE using `master_seed` (line 1511)
3. Reuses these same 50 samples for ALL 50 iterations

### What's Wrong

| Aspect | Current | Desired |
|--------|---------|---------|
| Context simulations | 1 (with master_seed) | 50 (one per iteration) |
| Bootstrap sample sets | 1 (reused all iterations) | 50 (fresh each iteration) |
| Unique sample seeds | 50 | 2,500 |
| Stochastic exploration | Minimal | Full |

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `optimization.py` | `_run_initial_simulation()` called once before loop | Move into loop, rename to `_run_context_simulation(iteration_seed)` |
| `optimization.py` | `_create_bootstrap_samples()` called once | Call per iteration with iteration-specific seed |
| `optimization.py` | `self._initial_sim_result` stored globally | Store per-iteration as `self._context_sim_result` |
| `optimization.py` | `self._bootstrap_samples` set once | Regenerate each iteration |
| `sampler.py` | No changes needed | Seed already passed at construction |
| `seed_matrix.py` | Already correct | Just needs to be used properly |

---

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 0 | Verify Rust FFI seed propagation | Seeds affect arrivals | 2 tests |
| 1 | Per-iteration context simulation | Seed varies by iteration | 5 tests |
| 2 | Per-iteration bootstrap samples | Samples regenerated each iteration | 6 tests |
| 3 | Integration testing | Full 50×50 seed hierarchy | 4 tests |
| 4 | Documentation | INV-13, config docs | 0 tests |

---

## Phase 0: Verify Rust FFI Seed Propagation

**Goal**: Confirm that different seeds actually produce different stochastic arrivals in Rust.

### Background

Commit 058d1bc mentions: "A Rust FFI bug where seeds don't affect stochastic arrivals". Before implementing the fix, we must verify this bug is resolved or fix it first.

### TDD Approach

1. Write test: `test_different_seeds_produce_different_arrival_events`
   - Run simulation with seed=1, collect arrival events
   - Run simulation with seed=2, collect arrival events
   - Assert the events differ

2. Write test: `test_same_seed_produces_identical_arrival_events`
   - Run simulation with seed=42 twice
   - Assert events are identical

### Success Criteria
- [ ] Different seeds → different stochastic arrivals
- [ ] Same seed → identical arrivals (INV-2)

### If Bug Exists

If seeds don't affect arrivals:
1. Investigate Rust `orchestrator.rs` seed handling
2. Fix seed propagation to `ArrivalGenerator`
3. Re-run tests to confirm fix

---

## Phase 1: Per-Iteration Context Simulation

**Goal**: Move context simulation into the iteration loop with iteration-specific seeds.

### Deliverables

1. Rename `_run_initial_simulation()` → `_run_context_simulation(seed: int)`
2. Call it inside the iteration loop
3. Use `SeedMatrix.get_iteration_seed(iteration_idx, agent_id)` for seed
4. Store result as `self._context_sim_result` (overwritten each iteration)

### Code Changes

**Before** (optimization.py ~line 787-791):
```python
# For real bootstrap mode: run initial simulation ONCE
if self._config.evaluation.mode == "bootstrap":
    self._initial_sim_result = self._run_initial_simulation()
    self._create_bootstrap_samples()
```

**After**:
```python
# Bootstrap setup moved into iteration loop
# (initialization code removed from here)
```

**In iteration loop** (~line 812):
```python
while self._current_iteration < self.max_iterations:
    self._current_iteration += 1
    iteration_idx = self._current_iteration - 1  # 0-indexed

    if self._config.evaluation.mode == "bootstrap":
        # Get iteration-specific seed
        agent_id = self.optimized_agents[0]  # Use first agent for seed
        iteration_seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

        # Run context simulation with this iteration's seed
        self._context_sim_result = self._run_context_simulation(iteration_seed)

        # Create bootstrap samples from this iteration's history
        self._create_bootstrap_samples(iteration_seed)

    # ... rest of iteration
```

### TDD Approach

1. `test_context_simulation_uses_iteration_seed` - Verify seed passed matches SeedMatrix
2. `test_different_iterations_have_different_context_seeds` - Seeds differ by iteration
3. `test_context_simulation_deterministic_for_same_seed` - Same seed → same history
4. `test_context_simulation_called_each_iteration` - Not just once at start

### Success Criteria
- [ ] Context simulation runs each iteration (not just once)
- [ ] Each iteration uses `get_iteration_seed(iteration_idx, agent_id)`
- [ ] Transaction histories differ between iterations
- [ ] Same master_seed → same history for each iteration (determinism)

---

## Phase 2: Per-Iteration Bootstrap Samples

**Goal**: Regenerate bootstrap samples each iteration from that iteration's context.

### Deliverables

1. Modify `_create_bootstrap_samples()` to accept seed parameter
2. Call it each iteration after context simulation
3. Samples regenerated from current iteration's transaction history

### Code Changes

**Before** (`_create_bootstrap_samples`):
```python
def _create_bootstrap_samples(self) -> None:
    self._bootstrap_sampler = BootstrapSampler(seed=self._config.master_seed)
    # ...
```

**After**:
```python
def _create_bootstrap_samples(self, iteration_seed: int) -> None:
    self._bootstrap_sampler = BootstrapSampler(seed=iteration_seed)
    # Use self._context_sim_result instead of self._initial_sim_result
    # ...
```

### TDD Approach

1. `test_bootstrap_samples_use_iteration_seed` - Sampler created with correct seed
2. `test_bootstrap_samples_differ_between_iterations` - Samples change each iteration
3. `test_bootstrap_samples_deterministic_within_iteration` - Same iteration → same samples
4. `test_paired_comparison_uses_same_samples` - Old and new policy see identical samples
5. `test_bootstrap_sample_count_correct` - Still generates num_samples samples

### Success Criteria
- [ ] Bootstrap samples regenerated each iteration
- [ ] Samples derive from current iteration's transaction history
- [ ] Same iteration_seed → identical samples (determinism)
- [ ] Paired comparison unchanged (same samples for old vs new policy)

---

## Phase 3: Integration Testing

**Goal**: Verify end-to-end behavior with full seed hierarchy.

### Deliverables

1. E2E test with small experiment (5 iterations × 5 samples)
2. Verify 25 unique bootstrap seeds generated
3. Verify determinism across runs

### Test Cases

1. `test_experiment_generates_unique_seeds_per_iteration`
   - Run experiment with 5 iterations, 5 samples
   - Collect all bootstrap sample seeds
   - Assert 25 unique seeds (5 × 5)

2. `test_experiment_deterministic_across_runs`
   - Run same experiment twice with same config
   - Compare all seeds, costs, and decisions
   - Assert identical

3. `test_experiment_context_simulations_vary`
   - Run experiment, collect context simulation event counts per iteration
   - Assert variations exist (stochastic arrivals differ)

4. `test_paired_comparison_within_iteration`
   - Verify old and new policy evaluated on same samples
   - Check sample seeds match between old/new evaluation

### Success Criteria
- [ ] iterations × samples unique seeds generated
- [ ] Full determinism with same master_seed
- [ ] Context simulations show stochastic variation
- [ ] Paired comparison logic preserved

---

## Phase 4: Documentation

**Goal**: Document the seed hierarchy and register INV-13.

### Deliverables

1. Add INV-13 to `docs/reference/patterns-and-conventions.md`:

```markdown
### INV-13: Bootstrap Seed Hierarchy

**Rule**: Bootstrap mode MUST use the full SeedMatrix hierarchy for seed generation.

**Hierarchy**:
```
master_seed
└── iteration_seed (per iteration, per agent)
    └── bootstrap_sample_seed (per sample within iteration)
```

**Requirements**:
- Context simulation runs EACH iteration with `get_iteration_seed(iteration, agent)`
- Bootstrap samples regenerated EACH iteration using iteration_seed
- Same sample used for both old and new policy (paired comparison)

**Where it applies**:
- `optimization.py._run_context_simulation()` - uses iteration_seed
- `optimization.py._create_bootstrap_samples()` - uses iteration_seed
- `BootstrapSampler` - derives sample seeds from iteration_seed
```

2. Update `docs/reference/experiments/configuration.md` with bootstrap seed behavior

3. Update `docs/reference/ai_cash_mgmt/evaluation-methodology.md` to reflect per-iteration design

### Success Criteria
- [ ] INV-13 documented in patterns-and-conventions.md
- [ ] Configuration docs explain seed hierarchy
- [ ] Evaluation methodology docs updated

---

## Testing Strategy

### Unit Tests
| Test File | Purpose |
|-----------|---------|
| `test_seed_matrix.py` | SeedMatrix generates correct hierarchical seeds |
| `test_optimization_seeds.py` | Optimization loop uses correct seeds per iteration |

### Integration Tests
| Test File | Purpose |
|-----------|---------|
| `test_bootstrap_iteration_seeds.py` | Full bootstrap with per-iteration seeds |
| `test_rust_ffi_seed_propagation.py` | Seeds affect Rust stochastic arrivals |

### Invariant Tests
| Test File | Purpose |
|-----------|---------|
| `test_inv_2_bootstrap_determinism.py` | Same master_seed → identical experiment |
| `test_inv_13_seed_hierarchy.py` | Bootstrap uses full hierarchy |

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 | Complete | Rust FFI seed propagation verified - seeds affect arrivals |
| Phase 1 | Complete | Per-iteration context simulation implemented |
| Phase 2 | Complete | Per-iteration bootstrap samples implemented |
| Phase 3 | Complete | 19 new tests added, all passing |
| Phase 4 | Complete | INV-13 added to patterns-and-conventions.md |
| Cleanup | Complete | Removed backward compatibility, made seed required, updated docs |

---

## Risk Assessment

### Risk 1: Rust FFI Seed Propagation Bug

**Description**: Commit 058d1bc mentions seeds don't affect stochastic arrivals.

**Mitigation**: Phase 0 specifically tests this. If bug exists, fix before proceeding.

### Risk 2: Performance Regression

**Description**: Running 50 context simulations instead of 1 will slow experiments.

**Impact**: ~50x slower for context simulation phase.

**Mitigation**:
- Expected and acceptable for proper stochastic exploration
- Context sims are fast (seconds each)
- Document the tradeoff

### Risk 3: LLM Context Changes

**Description**: LLM currently sees output from a single "initial" simulation. Now it will see output from each iteration's context simulation.

**Impact**: LLM context changes each iteration (intended behavior).

**Mitigation**: This is actually correct - LLM should see the current iteration's context.

---

## Implementation Notes

### Multi-Agent Seed Handling

For multi-agent experiments, each agent gets its own iteration_seed:

```python
for agent_id in self.optimized_agents:
    iteration_seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)
    # Each agent has unique seeds but derived deterministically
```

### Backward Compatibility (Optional)

If needed, add config flag:

```yaml
evaluation:
  mode: bootstrap
  num_samples: 50
  ticks: 12
  # per_iteration_context: true  # Optional: default true, set false for legacy behavior
```

However, the new behavior is correct, so this may not be necessary.
