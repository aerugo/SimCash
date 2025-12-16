# Phase 5: Wire Temporal Mode into Optimization Loop

**Status**: ✅ Complete
**Depends on**: Phases 1-4 (Complete)

---

## Objective

Integrate `_evaluate_temporal_acceptance()` into the main optimization loop so that when `evaluation.mode == "deterministic-temporal"`, the optimization uses temporal (cross-iteration) comparison instead of pairwise (within-iteration) comparison.

---

## Current State Analysis

The optimization loop in `_optimize_agent()` currently:
1. Calls `_evaluate_policies()` to get current cost
2. Generates new policy via LLM
3. Calls `_should_accept_policy()` which runs **paired evaluation** (old vs new on same seed)
4. Accepts/rejects based on `delta_sum > 0`

For temporal mode, we need:
1. Calls `_evaluate_policies()` to get current cost with current policy
2. First iteration: Always accept, store cost as baseline
3. Subsequent iterations: Compare current cost to previous iteration's cost
4. If `current_cost > previous_cost`: Reject and revert policy
5. No paired evaluation needed (saves simulation time)

---

## Key Insight: Temporal Mode Flow

```
Pairwise Mode (current):
  Iteration N:
    1. Run sim with current policy → cost (for context)
    2. LLM generates new_policy
    3. Run sim with OLD policy → old_cost
    4. Run sim with NEW policy → new_cost  (same seed as step 3)
    5. Accept if new_cost < old_cost
    6. If accepted: policy = new_policy

  Total simulations per iteration: 3

Temporal Mode (new):
  Iteration N:
    1. Run sim with current policy → cost_N
    2. Compare cost_N vs cost_{N-1}
    3. If cost_N <= cost_{N-1} OR first iteration:
         - Accept
         - Store cost_N as baseline
         - LLM generates new_policy
         - policy = new_policy for iteration N+1
    4. Else:
         - Reject
         - Revert to policy_{N-1}
         - Keep cost_{N-1} as baseline

  Total simulations per iteration: 1
```

---

## TDD Steps

### Step 5.1: Write Failing Tests (RED)

**Test File**: `api/tests/experiments/runner/test_temporal_integration.py`

**Test Cases**:
1. `test_temporal_mode_skips_paired_evaluation` - `_should_accept_policy` NOT called in temporal mode
2. `test_temporal_mode_uses_evaluate_temporal_acceptance` - `_evaluate_temporal_acceptance` IS called
3. `test_temporal_mode_first_iteration_accepts` - First iteration always accepts without comparison
4. `test_temporal_mode_cost_decrease_accepts` - Cost improvement leads to acceptance
5. `test_temporal_mode_cost_increase_reverts_policy` - Cost regression reverts to previous policy
6. `test_temporal_mode_stores_previous_policy_for_revert` - `_previous_policies` is populated
7. `test_temporal_mode_fewer_simulations_than_pairwise` - Temporal runs 1 sim, pairwise runs 3

### Step 5.2: Implement Integration (GREEN)

Modify `_optimize_agent()` in `optimization.py`:

```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    """Optimize policy for a single agent."""
    try:
        current_policy = self._policies.get(agent_id) or self._create_default_policy(agent_id)

        # Check if using temporal mode
        if self._config.evaluation.is_deterministic_temporal:
            await self._optimize_agent_temporal(agent_id, current_policy, current_cost)
        else:
            await self._optimize_agent_pairwise(agent_id, current_policy, current_cost)

    except Exception as e:
        # ... existing error handling ...
```

New method `_optimize_agent_temporal()`:
```python
async def _optimize_agent_temporal(
    self,
    agent_id: str,
    current_policy: dict[str, Any],
    current_cost: int,
) -> None:
    """Optimize agent using temporal (cross-iteration) comparison.

    Temporal mode compares cost_N vs cost_{N-1} instead of old_policy vs new_policy.
    This is simpler and matches game-like learning where agents only see historical outcomes.
    """
    # Step 1: Evaluate acceptance based on temporal comparison
    should_accept = self._evaluate_temporal_acceptance(agent_id, current_cost)

    if not should_accept:
        # Revert to previous policy
        previous_policy = self._previous_policies.get(agent_id)
        if previous_policy:
            self._policies[agent_id] = previous_policy
        # Log rejection
        # ...
        return

    # Step 2: Store current policy before generating new one (for potential revert)
    self._previous_policies[agent_id] = current_policy.copy()

    # Step 3: Generate new policy via LLM
    new_policy = await self._generate_new_policy(agent_id, current_policy, current_cost)

    # Step 4: Accept the new policy for next iteration
    self._policies[agent_id] = new_policy
    self._accepted_changes[agent_id] = True

    # Step 5: Record history and persist
    # ...
```

### Step 5.3: Refactor

- Extract common code between `_optimize_agent_temporal` and the existing pairwise path
- Ensure persistence captures temporal-specific fields
- Add verbose logging for temporal decisions

---

## Files to Modify

| File | Changes |
|------|---------|
| `optimization.py` | Add temporal path in `_optimize_agent()`, new `_optimize_agent_temporal()` method |
| `test_temporal_integration.py` | New integration tests |

---

## Verification

```bash
# Run new integration tests
uv run python -m pytest tests/experiments/runner/test_temporal_integration.py -v

# Run all optimization tests
uv run python -m pytest tests/experiments/runner/ -v

# Type check
uv run python -m mypy payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [x] Temporal mode calls `_evaluate_temporal_acceptance`, not `_should_accept_policy`
- [x] First iteration always accepts
- [x] Cost increase reverts to previous policy
- [x] `_previous_policies` populated correctly
- [x] All existing tests still pass (49 tests)
- [x] Type check passes
