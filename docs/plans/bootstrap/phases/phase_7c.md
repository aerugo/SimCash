# Phase 7c: Remove Monte Carlo Fallback (Cleanup)

**Status**: In Progress
**Started**: 2025-12-13
**Parent Plan**: `../development-plan.md`
**Continues**: `phase_7b.md`

## Objective

Remove the parametric Monte Carlo fallback code from `_evaluate_policy_pair()`. Per the design decision in Phase 7b, we use ONLY real bootstrap for evaluation.

## Background

The current `_evaluate_policy_pair()` has two code paths:
1. **Real bootstrap** (when `_bootstrap_samples` exist): Uses `BootstrapPolicyEvaluator`
2. **Fallback Monte Carlo** (when no samples): Runs new simulations

We want to remove path #2 to simplify the code.

## Changes Required

### 1. Update `_evaluate_policy_pair()` in `optimization.py`

**Before** (current):
```python
# Real bootstrap mode: use pre-computed bootstrap samples if available
if self._bootstrap_samples and agent_id in self._bootstrap_samples:
    samples = self._bootstrap_samples[agent_id]
    if samples:
        # ... use BootstrapPolicyEvaluator ...
        return deltas, sum(deltas)

# Fallback: Parametric Monte Carlo mode (runs new simulations)
bootstrap_seeds = self._seed_matrix.get_bootstrap_seeds(...)
fallback_deltas: list[int] = []
for seed in bootstrap_seeds:
    # ... run simulations ...
```

**After** (simplified):
```python
# Real bootstrap mode: use pre-computed bootstrap samples
if self._bootstrap_samples and agent_id in self._bootstrap_samples:
    samples = self._bootstrap_samples[agent_id]
    if samples:
        # ... use BootstrapPolicyEvaluator ...
        return deltas, sum(deltas)

# No samples available - this is an error in bootstrap mode
raise RuntimeError(f"No bootstrap samples available for agent {agent_id}")
```

### 2. Ensure bootstrap samples are always created

Update `run()` to ALWAYS run initial simulation and create samples for bootstrap mode:
- Currently guarded by `if self._config.evaluation.mode == "bootstrap"`
- This is correct - the error should only occur if bootstrap mode is configured but samples weren't created

### 3. Update test that checks fallback behavior

The test `test_evaluate_policy_pair_falls_back_to_monte_carlo_without_samples` should be updated to verify the error is raised instead of fallback behavior.

## TDD Approach

### Step 1: Update Test (RED → GREEN transition)

Update the fallback test to expect an error:
```python
def test_evaluate_policy_pair_raises_without_samples(self) -> None:
    """Without bootstrap samples, should raise RuntimeError."""
    # ... setup ...
    loop._bootstrap_samples = {}

    with pytest.raises(RuntimeError, match="No bootstrap samples"):
        loop._evaluate_policy_pair(...)
```

### Step 2: Remove Fallback Code (GREEN)

Remove the Monte Carlo fallback code from `_evaluate_policy_pair()`.

### Step 3: Verify (REFACTOR)

- Run all tests
- mypy check
- ruff check

## Acceptance Criteria

- [ ] Monte Carlo fallback code removed from `_evaluate_policy_pair()`
- [ ] RuntimeError raised when bootstrap samples unavailable
- [ ] Test updated to verify error behavior
- [ ] All other tests still pass
- [ ] mypy passes
- [ ] ruff passes

## Files to Modify

1. `api/payment_simulator/experiments/runner/optimization.py` - Remove fallback code
2. `api/tests/integration/test_real_bootstrap_evaluation.py` - Update test

---

*Created: 2025-12-13*
