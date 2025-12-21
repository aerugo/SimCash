# Bootstrap Seed Fix - Development Plan

**Status**: Pending
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

## Current State Analysis

### Problem

Bootstrap mode currently:
1. Runs ONE initial simulation with `master_seed` (line 1468)
2. Creates bootstrap samples ONCE using `master_seed` (line 1511)
3. Reuses these same samples for ALL iterations

### Expected Design

The user's intended design:
1. Generate 50 iteration_seeds at experiment start (using master_seed)
2. For EACH iteration:
   - Run context simulation with `iteration_seed[i]`
   - Generate 50 bootstrap samples using `iteration_seed[i]` as base

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `optimization.py` | Uses master_seed for initial sim | Use iteration_seed for per-iteration context sim |
| `optimization.py` | Creates samples once | Regenerate samples each iteration |
| `optimization.py` | _create_bootstrap_samples() called once | Call per iteration with iteration-specific seed |
| `sampler.py` | BootstrapSampler takes fixed seed | No change needed (seed passed at construction) |
| `seed_matrix.py` | Has get_bootstrap_seeds() | Already correct, just needs to be used |

## Solution Design

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Experiment Start                            │
│  SeedMatrix(master_seed=42, max_iterations=50, num_samples=50)  │
│  Pre-computes: 50 iteration_seeds × 50 bootstrap_seeds each     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Iteration N (1-50)                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Get iteration_seed = SeedMatrix.get_iteration_seed(N-1, A)  │
│                             │                                    │
│                             ▼                                    │
│  2. Run context simulation with iteration_seed                  │
│     └── Collects transaction history for this iteration         │
│                             │                                    │
│                             ▼                                    │
│  3. Create bootstrap samples using iteration_seed               │
│     └── BootstrapSampler(seed=iteration_seed)                   │
│     └── Generates 50 samples with unique seeds                  │
│                             │                                    │
│                             ▼                                    │
│  4. Evaluate policies on this iteration's samples               │
│     └── Paired comparison: old_policy vs new_policy             │
│                             │                                    │
│                             ▼                                    │
│  5. Accept/reject new policy based on mean delta                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Per-iteration context simulation**: Each iteration runs its own context simulation, exploring different stochastic realizations.

2. **Per-iteration bootstrap samples**: Samples are regenerated each iteration from that iteration's context simulation history.

3. **Backward compatibility**: Add a config flag `per_iteration_bootstrap: bool` to enable this behavior, defaulting to `true`. This allows reverting if needed.

4. **SeedMatrix usage**: Use existing `get_iteration_seed()` for context sims; optionally use `get_bootstrap_seeds()` for sample generation (or continue deriving from iteration_seed).

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Refactor context simulation to be per-iteration | Seed consistency, determinism | 5 tests |
| 2 | Refactor bootstrap sample generation to be per-iteration | Sample uniqueness, reproducibility | 6 tests |
| 3 | Integration testing | Full experiment with 50×50 seeds | 4 tests |
| 4 | Documentation and invariant registration | Update docs | 0 tests (docs only) |

---

## Phase 1: Per-Iteration Context Simulation

**Goal**: Move `_run_initial_simulation()` into the iteration loop, using iteration-specific seeds.

### Deliverables
1. Renamed method: `_run_context_simulation(iteration: int) -> InitialSimulationResult`
2. Uses `SeedMatrix.get_iteration_seed()` for seed
3. Stores result per-iteration (not globally)

### TDD Approach
1. Write test: `test_context_simulation_uses_iteration_seed`
2. Write test: `test_different_iterations_produce_different_contexts`
3. Implement refactored method
4. Verify determinism: same master_seed → same iteration contexts

### Success Criteria
- [ ] Context simulation seed differs by iteration
- [ ] Same master_seed produces identical context per iteration
- [ ] Transaction histories vary between iterations

---

## Phase 2: Per-Iteration Bootstrap Samples

**Goal**: Regenerate bootstrap samples each iteration from that iteration's context.

### Deliverables
1. Move `_create_bootstrap_samples()` call into iteration loop
2. Pass iteration-specific seed to `BootstrapSampler`
3. Clear/replace samples each iteration

### TDD Approach
1. Write test: `test_bootstrap_samples_regenerated_each_iteration`
2. Write test: `test_bootstrap_samples_differ_between_iterations`
3. Write test: `test_bootstrap_samples_deterministic_within_iteration`
4. Implement per-iteration sample generation
5. Verify sample seeds match SeedMatrix expectations

### Success Criteria
- [ ] Bootstrap samples differ between iterations
- [ ] Samples are deterministic given iteration + master_seed
- [ ] Paired comparison still works (same samples for old/new policy within iteration)

---

## Phase 3: Integration Testing

**Goal**: Verify end-to-end behavior with full seed hierarchy.

### Deliverables
1. E2E test running experiment with 5 iterations × 5 samples
2. Verification that 25 unique bootstrap seeds are generated
3. Verification of determinism across runs

### TDD Approach
1. Write test: `test_experiment_generates_iteration_times_samples_unique_seeds`
2. Write test: `test_experiment_results_deterministic_across_runs`
3. Run actual experiment and inspect database

### Success Criteria
- [ ] All 25 (5×5) seeds are unique
- [ ] Running twice with same config produces identical results
- [ ] Convergence behavior is reasonable

---

## Phase 4: Documentation

**Goal**: Document the seed hierarchy and add INV-13.

### Deliverables
1. Update `docs/reference/patterns-and-conventions.md` with INV-13
2. Update `docs/reference/experiments/configuration.md` with bootstrap seed behavior
3. Update `CLAUDE.md` if needed

### Success Criteria
- [ ] INV-13 documented in patterns-and-conventions.md
- [ ] Configuration docs explain per-iteration bootstrap behavior

---

## Testing Strategy

### Unit Tests
- `test_seed_matrix.py`: Verify SeedMatrix generates expected seeds
- `test_optimization_seeds.py`: Verify optimization loop uses correct seeds

### Integration Tests
- `test_bootstrap_iteration_seeds.py`: Full bootstrap with iteration-specific seeds
- `test_experiment_seed_determinism.py`: Reproducibility across runs

### Identity/Invariant Tests
- `test_inv_2_determinism.py`: Same seed → same results
- `test_inv_13_bootstrap_hierarchy.py`: Bootstrap uses full hierarchy

---

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add INV-13: Bootstrap Seed Hierarchy
- [ ] `docs/reference/experiments/configuration.md` - Document per-iteration bootstrap
- [ ] `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Update bootstrap description

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Per-iteration context simulation |
| Phase 2 | Pending | Per-iteration bootstrap samples |
| Phase 3 | Pending | Integration testing |
| Phase 4 | Pending | Documentation |

---

## Risk Assessment

### Risk 1: Rust FFI Seed Propagation Bug

**Description**: Commit 058d1bc mentions "A Rust FFI bug where seeds don't affect stochastic arrivals".

**Mitigation**:
1. Verify that iteration_seed properly affects stochastic arrivals in Rust
2. Add test: `test_different_seeds_produce_different_arrivals`
3. If bug exists, fix it before Phase 1

### Risk 2: Performance Regression

**Description**: Running 50 context simulations instead of 1 will slow experiments.

**Mitigation**:
1. This is expected and acceptable (exploration > speed)
2. Document the tradeoff
3. Optional: Add parallel execution of context simulations

### Risk 3: Breaking Existing Experiments

**Description**: Changing seed behavior may affect reproducibility of past experiments.

**Mitigation**:
1. Add config flag: `per_iteration_bootstrap: bool = true` (new default)
2. Old experiments can set `per_iteration_bootstrap: false` to restore old behavior
3. Document migration path

---

## Implementation Notes

### Seed Usage Patterns

Current (incorrect):
```python
# In run() before loop
self._initial_sim_result = self._run_initial_simulation()  # Uses master_seed
self._create_bootstrap_samples()  # Uses master_seed, called once
```

Fixed (correct):
```python
# In iteration loop
while self._current_iteration < self.max_iterations:
    iteration_idx = self._current_iteration  # 0-indexed

    # Get iteration-specific seed for first agent (or combine for multi-agent)
    iteration_seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

    # Run context simulation with iteration seed
    self._context_sim_result = self._run_context_simulation(iteration_seed)

    # Create bootstrap samples with iteration seed
    self._create_bootstrap_samples(iteration_seed)

    # ... rest of iteration logic
```

### Backward Compatibility Config

```yaml
evaluation:
  mode: bootstrap
  num_samples: 50
  ticks: 12
  per_iteration_bootstrap: true  # New: regenerate samples each iteration
```
