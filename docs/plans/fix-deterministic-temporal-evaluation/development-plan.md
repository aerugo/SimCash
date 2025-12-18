# Fix Deterministic-Temporal Evaluation Mode - Development Plan

**Status**: In Progress
**Created**: 2025-12-18
**Branch**: claude/simcash-paper-proposal-LNRkl

## Summary

Fix the experiment runner to correctly handle `deterministic-temporal` and `deterministic-pairwise` evaluation modes. Currently, the code only checks for the literal string `"deterministic"` instead of using the `is_deterministic` property, causing deterministic modes to incorrectly fall into the bootstrap evaluation path when `num_samples > 1`.

## Critical Invariants to Respect

- **INV-9**: Policy Evaluation Identity - Policies must be evaluated consistently regardless of code path

## Current State Analysis

### The Bug

In `optimization.py`, there are 5 places that check `== "deterministic"` instead of using `self._config.evaluation.is_deterministic`:

| Line | Current Code | Should Be |
|------|--------------|-----------|
| 1369 | `eval_mode == "deterministic"` | `self._config.evaluation.is_deterministic` |
| 1493 | `eval_mode == "deterministic"` | `self._config.evaluation.is_deterministic` |
| 1661 | `eval_mode == "deterministic"` | `self._config.evaluation.is_deterministic` |
| 1704 | `self._config.evaluation.mode == "deterministic"` | `self._config.evaluation.is_deterministic` |
| 2131 | `self._config.evaluation.mode == "deterministic"` | `self._config.evaluation.is_deterministic` |

### Impact

When using `deterministic-temporal` mode with `num_samples > 1` (e.g., `num_samples: 50` for statistical rigor):

1. **Wrong**: Runs 50 bootstrap simulations before each iteration
2. **Wrong**: Uses accept/reject based on cost comparison
3. **Correct**: `_optimize_agent_temporal()` is called (routing works)

### Expected Behavior for deterministic-temporal

```
Iteration 1:
  1. Run single simulation with default policy
  2. LLM observes results
  3. LLM suggests new policy for iteration 2

Iteration 2:
  1. Run single simulation with new policy
  2. LLM observes results
  3. LLM suggests next policy (or declares stable)

... repeat until LLM declares policy stable or max_iterations reached
```

**Key points:**
- **NO bootstrap sampling** - scenario is deterministic, one run is enough
- **NO accept/reject** - LLM always tries suggested policy
- Trust LLM to keep policy stable once it finds a good one

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/experiments/runner/optimization.py` | 5 broken string comparisons | Use `is_deterministic` property |

## Solution Design

### Simple Fix

Replace string comparisons with the existing `is_deterministic` property from `EvaluationConfig`:

```python
# experiment_config.py already has:
@property
def is_deterministic(self) -> bool:
    """Check if using any deterministic mode."""
    return self.mode in ("deterministic", "deterministic-pairwise", "deterministic-temporal")
```

### Key Design Decisions

1. **Use existing property**: The `is_deterministic` property already exists and correctly handles all three deterministic variants
2. **Minimal change**: Only fix the 5 broken comparisons, no structural changes needed

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Fix string comparisons | Test that temporal mode runs single simulations | 3 tests |
| 2 | Verify end-to-end | Run exp1 with deterministic-temporal | Manual verification |

## Phase 1: Fix String Comparisons

**Goal**: Replace all `== "deterministic"` checks with `is_deterministic` property

### Deliverables
1. Fix all 5 locations in `optimization.py`

### Changes

```python
# Line 1369 - change from:
purpose = "eval" if eval_mode == "deterministic" else "bootstrap"
# To:
purpose = "eval" if self._config.evaluation.is_deterministic else "bootstrap"

# Line 1493 - change from:
if eval_mode == "deterministic" or num_samples <= 1:
# To:
if self._config.evaluation.is_deterministic or num_samples <= 1:

# Line 1661 - change from:
if eval_mode == "deterministic" or num_samples == 1:
# To:
if self._config.evaluation.is_deterministic or num_samples == 1:

# Line 1704 - change from:
if self._config.evaluation.mode == "deterministic" or num_samples <= 1:
# To:
if self._config.evaluation.is_deterministic or num_samples <= 1:

# Line 2131 - change from:
is_deterministic = self._config.evaluation.mode == "deterministic"
# To:
is_deterministic = self._config.evaluation.is_deterministic
```

### Success Criteria
- [ ] All 5 string comparisons replaced
- [ ] Existing tests pass
- [ ] `deterministic-temporal` mode runs single simulations (not 50 bootstrap samples)

## Phase 2: End-to-End Verification

**Goal**: Verify exp1 runs correctly with deterministic-temporal mode

### Test Plan
1. Run exp1 experiment
2. Verify output shows single simulation per iteration (not bootstrap tables)
3. Verify LLM iteratively improves policy
4. Verify experiment completes without bootstrap overhead

### Success Criteria
- [ ] Exp1 runs with single simulation per iteration
- [ ] No "Bootstrap Evaluation (50 samples)" messages
- [ ] Experiment completes in reasonable time

## Testing Strategy

### Unit Tests
- Existing `test_evaluation_modes_integration.py` should continue to pass
- Tests use `num_samples=1` so they pass even with the bug

### Integration Tests
- Manual verification with exp1 config (`num_samples: 50`)

## Documentation Updates

None needed - this is a bug fix, not a new feature.

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Complete | Fixed 5 string comparisons, added TDD test |
| Phase 2 | Pending | End-to-end verification |

## Phase 1 Results

Commit: `4a95dea`

**TDD Process:**
1. **RED**: Wrote test `test_temporal_mode_runs_single_simulation_not_bootstrap` that failed with "50 != 1"
2. **GREEN**: Fixed 5 string comparisons to use `is_deterministic` property
3. **REFACTOR**: Removed unused `eval_mode` variables, all 14 evaluation mode tests pass
