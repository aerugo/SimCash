# Deterministic Evaluation Modes - Development Plan

**Status**: Complete
**Created**: 2025-12-16
**Completed**: 2025-12-16
**Branch**: claude/clarify-simcash-rtgs-dHZAS

## Summary

Implement two deterministic evaluation modes (`deterministic-temporal` and `deterministic-pairwise`) and fix a seed inconsistency bug where `_evaluate_policies()` uses `master_seed` but `_evaluate_policy_pair()` uses iteration-varying seeds.

## Critical Invariants to Respect

- **INV-2**: Determinism is Sacred - Same seed + same config = identical outputs. Both evaluation modes must be reproducible.
- **INV-9**: Policy Evaluation Identity - Policy parameter extraction must produce identical results regardless of code path. The seed used for evaluation must be consistent between cost display and acceptance decision.

## Current State Analysis

### The Bug

In `optimization.py`, deterministic mode has inconsistent seed usage:

```python
# _evaluate_policies() at line 1398:
seed = self._config.master_seed  # CONSTANT

# _evaluate_policy_pair() at line 1600:
seed = self._seed_matrix.get_iteration_seed(iteration_idx, agent_id)  # VARIES
```

This causes the cost **displayed to user** (from `_evaluate_policies`) to differ from the cost **used for acceptance decision** (from `_evaluate_policy_pair`).

### Missing Feature

Currently, deterministic mode only supports "pairwise" comparison (old vs new policy on same seed within same iteration). There's no "temporal" mode that compares current iteration cost vs previous iteration cost.

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/experiments/config/experiment_config.py` | `mode: str = "bootstrap"` accepts only `bootstrap` or `deterministic` | Expand to accept `deterministic-temporal` and `deterministic-pairwise` |
| `api/payment_simulator/experiments/runner/optimization.py` | Uses inconsistent seeds; only pairwise comparison | Fix seed consistency; implement both evaluation strategies |
| `api/tests/experiments/runner/test_evaluation_modes.py` | Does not exist | Create comprehensive tests for both modes |

## Solution Design

### Evaluation Modes

```
                    ┌─────────────────────────────────────────────┐
                    │           evaluation.mode                    │
                    └─────────────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
   ┌───────────────┐         ┌──────────────────┐        ┌─────────────────┐
   │   bootstrap   │         │  deterministic-  │        │  deterministic- │
   │               │         │    pairwise      │        │    temporal     │
   └───────────────┘         └──────────────────┘        └─────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
   N samples with            Same iteration,              Compare across
   different seeds           same seed:                   iterations:
   Paired comparison         old_cost vs new_cost         cost_N vs cost_N+1
```

### Deterministic-Pairwise (Current Logic, Fixed)

```
Iteration N:
  seed = derive_iteration_seed(N, agent_id)  # Consistent!

  1. _evaluate_policies(seed) → cost_display (for logs/LLM context)
  2. LLM generates new_policy
  3. _evaluate_policy_pair(seed):
       - Run old_policy with seed → old_cost
       - Run new_policy with seed → new_cost
       - Accept if new_cost < old_cost
```

### Deterministic-Temporal (New)

```
Iteration N:
  seed = derive_iteration_seed(N, agent_id)  # Same seed derivation

  1. Run current_policy with seed → cost_N
  2. Store cost_N for next iteration
  3. If N > 0: Compare cost_N vs cost_{N-1}
     - Accept if cost_N < cost_{N-1}
     - Else: Revert to previous policy
  4. LLM generates new_policy for iteration N+1
```

### Key Design Decisions

1. **Always use iteration-varying seed**: Even in deterministic mode, use `_seed_matrix.get_iteration_seed()` for consistency between `_evaluate_policies` and `_evaluate_policy_pair`.

2. **Backward compatibility**: `deterministic` (without suffix) will be treated as `deterministic-pairwise` for backward compatibility.

3. **Temporal stores previous cost**: Temporal mode needs to track `_previous_iteration_cost: dict[str, int]` to compare across iterations.

4. **Temporal skips pair evaluation**: In temporal mode, `_evaluate_policy_pair()` is not called since we compare iteration-to-iteration, not old-vs-new within iteration.

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Fix seed inconsistency | Seed consistency between display and acceptance | 4 tests |
| 2 | Add evaluation mode parsing | Config validation for new modes | 5 tests |
| 3 | Implement deterministic-temporal | Temporal comparison logic | 6 tests |
| 4 | Integration tests | End-to-end verification | 4 tests |

## Phase 1: Fix Seed Inconsistency

**Goal**: Ensure `_evaluate_policies()` and `_evaluate_policy_pair()` use the same seed in deterministic mode.

### Deliverables
1. Modified `_evaluate_policies()` to use iteration seed
2. Tests verifying seed consistency

### TDD Approach
1. Write failing test that asserts seed used in `_evaluate_policies` equals seed used in `_evaluate_policy_pair`
2. Modify `_evaluate_policies()` to use `_seed_matrix.get_iteration_seed()`
3. Verify tests pass

### Success Criteria
- [ ] `_evaluate_policies()` uses iteration seed in deterministic mode
- [ ] Displayed cost matches cost used for acceptance decision
- [ ] All existing tests pass

## Phase 2: Add Evaluation Mode Parsing

**Goal**: Extend `EvaluationConfig` to accept `deterministic-temporal` and `deterministic-pairwise`.

### Deliverables
1. Updated `EvaluationConfig` validation
2. Helper methods to check mode type
3. Tests for config parsing

### TDD Approach
1. Write failing tests for new mode values
2. Update `EvaluationConfig.__post_init__()` validation
3. Add helper properties: `is_bootstrap`, `is_deterministic_pairwise`, `is_deterministic_temporal`

### Success Criteria
- [ ] `mode: deterministic-pairwise` is accepted
- [ ] `mode: deterministic-temporal` is accepted
- [ ] `mode: deterministic` is treated as `deterministic-pairwise` (backward compat)
- [ ] Invalid modes raise `ValueError`

## Phase 3: Implement Deterministic-Temporal

**Goal**: Implement temporal comparison that compares cost across iterations.

### Deliverables
1. `_previous_iteration_costs: dict[str, int]` tracking
2. Temporal acceptance logic in `_evaluate_policy_pair()` or new method
3. Policy revert logic when cost increases

### TDD Approach
1. Write failing tests for temporal comparison behavior
2. Implement `_evaluate_temporal()` method
3. Add policy revert logic
4. Integrate into optimization loop

### Success Criteria
- [ ] First iteration always accepts (no previous to compare)
- [ ] Subsequent iterations compare vs previous
- [ ] Policy reverted if cost increases
- [ ] Previous cost stored for next iteration

## Phase 4: Integration Tests

**Goal**: Verify end-to-end behavior with real experiment configs.

### Deliverables
1. Integration test with `deterministic-pairwise` config
2. Integration test with `deterministic-temporal` config
3. Test verifying both modes produce valid optimization trajectories

### TDD Approach
1. Create minimal experiment YAML configs for each mode
2. Run experiments and verify behavior
3. Assert convergence behavior matches expectations

### Success Criteria
- [ ] Pairwise mode produces expected acceptance pattern
- [ ] Temporal mode produces expected acceptance pattern
- [ ] Both modes are deterministic (same seed = same results)

## Testing Strategy

### Unit Tests
- `test_seed_consistency.py`: Verify seed usage is consistent
- `test_evaluation_config.py`: Verify mode parsing

### Integration Tests
- `test_evaluation_modes.py`: End-to-end mode behavior
- `test_determinism.py`: Same seed produces identical results

### Identity/Invariant Tests
- INV-2 (Determinism): Run same experiment twice, verify identical trajectories
- INV-9 (Policy Evaluation Identity): Verify displayed cost matches acceptance cost

## Documentation Updates

- [x] `docs/reference/patterns-and-conventions.md` - No new invariants needed (existing INV-2 and INV-9 cover this)
- [x] `docs/reference/experiments/configuration.md` - Documented new evaluation modes
- [x] `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Added deterministic modes section

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ Complete | Fixed seed inconsistency (7 tests) |
| Phase 2 | ✅ Complete | Added mode parsing (18 tests) |
| Phase 3 | ✅ Complete | Implemented temporal logic (8 tests) |
| Phase 4 | ✅ Complete | Integration tests (9 tests) |
| Phase 5 | ✅ Complete | Wired temporal into optimization loop (7 tests) |
| Phase 6 | ✅ Complete | End-to-end proof of correctness (19 tests) |

**Total: 68 new tests, all passing**
