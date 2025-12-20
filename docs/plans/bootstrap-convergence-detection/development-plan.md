# Bootstrap Convergence Detection - Development Plan

**Status**: In Progress
**Created**: 2025-12-20
**Branch**: `claude/improve-bootstrap-convergence-Jeqpo`

## Summary

Replace the simple relative-change convergence detector with a statistically robust `BootstrapConvergenceDetector` that uses coefficient of variation (CV), Mann-Kendall trend test, and regret bound criteria to prevent premature convergence and divergence failures.

## Critical Invariants to Respect

- **INV-2**: Determinism is Sacred - Same cost sequence → same convergence decision (no randomness in detection)
- **Backward Compatibility**: Existing `ConvergenceDetector` unchanged; deterministic modes continue using it

## Current State Analysis

The current `ConvergenceDetector` class in `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py`:
- Uses simple relative-change check: `|current - prev| / |prev| <= threshold`
- Triggers convergence after `stability_window` consecutive stable changes
- Problems identified in Exp2:
  - Pass 1/3: Converged at 4-5% drops (still meaningful improvement)
  - Pass 2: Converged at point 74% worse than best observed

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py` | Has `ConvergenceDetector` class | Add `BootstrapConvergenceDetector` class |
| `api/payment_simulator/ai_cash_mgmt/optimization/__init__.py` | Exports `ConvergenceDetector` | Also export `BootstrapConvergenceDetector` |
| `api/payment_simulator/ai_cash_mgmt/__init__.py` | Exports `ConvergenceDetector` | Also export `BootstrapConvergenceDetector` |
| `api/payment_simulator/experiments/runner/optimization.py` | Uses `ConvergenceDetector` | Use `BootstrapConvergenceDetector` for bootstrap mode |
| `api/payment_simulator/experiments/config/experiment_config.py` | Has `ConvergenceConfig` | Add `cv_threshold`, `regret_threshold` fields |
| `api/payment_simulator/experiments/README.md` | May not exist | Create with convergence mechanics docs |

## Solution Design

```
┌─────────────────────────────────────────────────────────────┐
│              BootstrapConvergenceDetector                   │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │ CV Criterion │  │ Trend Test   │  │ Regret Bound    │    │
│  │ cv < 0.03   │  │ p > 0.05     │  │ regret < 0.10   │    │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘    │
│         │                │                    │             │
│         └────────────────┴────────────────────┘             │
│                          │                                  │
│                          ▼                                  │
│                  ALL must pass                              │
│                  for is_converged                           │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Three criteria, ALL must pass**: More conservative than any single criterion
2. **Mann-Kendall trend test**: Non-parametric, robust for small samples
3. **CV over window**: Standard statistical measure for relative variability
4. **Regret bound**: Prevents converging at worse-than-best points

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Core detector implementation | CV, Trend, Regret criteria | ~15 tests |
| 2 | Integration with optimization runner | Mode selection, config | ~5 tests |
| 3 | Documentation | Experiment README | N/A |

## Phase 1: Core Implementation

**Goal**: Implement `BootstrapConvergenceDetector` with all three criteria

### Deliverables
1. `BootstrapConvergenceDetector` class in `convergence_detector.py`
2. Comprehensive unit tests in `tests/unit/test_bootstrap_convergence.py`

### TDD Approach
1. Write failing tests for each criterion independently
2. Implement each criterion with edge case handling
3. Combine into final `is_converged` property

### Success Criteria
- [ ] CV criterion correctly computed (std/mean over window)
- [ ] Mann-Kendall trend test correct for ascending, descending, flat sequences
- [ ] Regret bound correctly handles positive/negative/zero costs
- [ ] Edge cases: empty history, single value, window larger than history
- [ ] All three criteria must pass for convergence

## Phase 2: Integration

**Goal**: Use new detector for bootstrap evaluation mode

### Deliverables
1. Updated `ConvergenceConfig` with new parameters
2. Updated `optimization.py` to select detector based on mode

### Success Criteria
- [ ] Bootstrap mode uses `BootstrapConvergenceDetector`
- [ ] Deterministic modes still use `ConvergenceDetector`
- [ ] Config parameters flow correctly

## Phase 3: Documentation

**Goal**: Document convergence mechanics

### Deliverables
1. `api/payment_simulator/experiments/README.md` with convergence section

### Success Criteria
- [ ] All criteria explained with formulas
- [ ] Thresholds documented with rationale
- [ ] Examples of when each criterion triggers

## Testing Strategy

### Unit Tests
- CV computation with various data patterns
- Mann-Kendall S statistic computation
- Mann-Kendall variance and p-value calculation
- Regret bound with edge cases
- Combined criteria logic

### Integration Tests
- Pass 1 scenario doesn't converge prematurely
- Pass 2 scenario doesn't converge at diverged point
- Exp2 data replay shows improved behavior

## Documentation Updates

- [ ] `api/payment_simulator/experiments/README.md` - Create/update with convergence mechanics

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Core implementation |
| Phase 2 | Pending | Integration |
| Phase 3 | Pending | Documentation |
